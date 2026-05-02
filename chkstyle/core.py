import ast, io, json, keyword, math, os, re, symtable, sys, tokenize
try: import tomllib
except ImportError: import tomli as tomllib

SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache", ".venv", "venv", "dist", "build"}
WRAP_WIDTH = 120
MAX_LINE_LEN = 160
NB_EXPORT_RE = re.compile(r"^\s*#\|\s*exports?\b", re.M)
ALL_RULES = "all"
SUPPORTED_FIX_RULES = set("consecutive-short-imports continuation-indent closing-bracket dict-literal inefficient-multiline-expression "
    "lhs-assignment-annotation multi-line-from-import nested-generics semicolon single-line-docstring "
    "single-statement-body unused-import".split())
RULE_PREFIXES = [
    ("exported-cell import only used in non-exported cells", "exported-import-nonexport"), ("single-line docstring uses triple quotes", "single-line-docstring"),
    ("dict literal with 3+ identifier keys", "dict-literal"), ("consecutive short imports", "consecutive-short-imports"),
    ("closing bracket on its own line", "closing-bracket"), ("continuation line indent", "continuation-indent"),
    ("multi-line from-import", "multi-line-from-import"), ("inefficient multi-line from-import", "inefficient-multiline-from-import"),
    ("inefficient multiline signature/header", "inefficient-multiline-signature"), ("inefficient multiline annotation", "inefficient-multiline-annotation"),
    ("inefficient multiline expression", "inefficient-multiline-expression"), ("lhs assignment annotation", "lhs-assignment-annotation"),
    ("semicolon statement separator", "semicolon"), ("unused import", "unused-import"), ("line >", "line-too-long"),
    ("nested generics depth", "nested-generics"), ("syntax error", "syntax-error")]
COMPOUND_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.FunctionDef,
    ast.AsyncFunctionDef, ast.ClassDef)

def load_config(root="."):
    "Load config from pyproject.toml."
    path = os.path.join(root, "pyproject.toml")
    if not os.path.exists(path): return {}
    with open(path, "rb") as f: data = tomllib.load(f)
    return data.get("tool", {}).get("chkstyle", {})

def _norm_relpath(path: str) -> str:
    "Normalize a relative path for config matching."
    norm = os.path.normpath(path).replace(os.sep, "/")
    if norm == ".": return ""
    return norm.removeprefix("./").strip("/")

def _parse_skip_paths(skip_paths) -> tuple[set, set]:
    "Split skip paths into folder names and relative paths."
    if not skip_paths: return set(), set()
    if isinstance(skip_paths, str): skip_paths = [part.strip() for part in skip_paths.split(",")]
    names, rel_paths = set(), set()
    for item in skip_paths:
        if not item: continue
        path = _norm_relpath(str(item).strip())
        if not path: continue
        if "/" in path: rel_paths.add(path)
        else: names.add(path)
    return names, rel_paths

def _skip(d, rel_path: str, skip_path_re, skip_names: set[str], skip_rel_paths: set[str]) -> bool:
    "Check whether path entry should be skipped."
    if d in SKIP_DIRS or d.startswith("."): return True
    if skip_path_re and (skip_path_re.match(d) or skip_path_re.match(rel_path)): return True
    if d in skip_names: return True
    return any(rel_path == path or rel_path.startswith(f"{path}/") for path in skip_rel_paths)

def iter_py_files(root: str, skip_path_re=None, skip_paths=None):
    "Iter py and ipynb files."
    skip_names, skip_rel_paths = _parse_skip_paths(skip_paths)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = _norm_relpath(os.path.relpath(dirpath, root))
        dirnames[:] = [d for d in dirnames if not _skip(d, _norm_relpath(f"{rel_dir}/{d}"), skip_path_re, skip_names, skip_rel_paths)]
        for name in filenames:
            if not (name.endswith(".py") or name.endswith(".ipynb")): continue
            rel_path = _norm_relpath(f"{rel_dir}/{name}")
            if _skip(name, rel_path, skip_path_re, skip_names, skip_rel_paths): continue
            path = os.path.join(dirpath, name)
            if os.path.islink(path): continue
            yield path

def dict_keyword_keys(node) -> list[str] | None:
    "Dict keys that can be represented as kwargs."
    keys = []
    for key in node.keys:
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str): return None
        if not key.value.isidentifier() or keyword.iskeyword(key.value): return None
        keys.append(key.value)
    return keys if len(keys) == len(set(keys)) else None

def is_docstring_stmt(stmt) -> bool:
    "Docstring stmt."
    return isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)

def node_lines(source: str, lines: list[str], node) -> list[str]:
    "Node lines."
    seg = ast.get_source_segment(source, node)
    if seg: return [line.rstrip() for line in seg.splitlines()]
    lineno = getattr(node, "lineno", None)
    if lineno and 1 <= lineno <= len(lines): return [lines[lineno - 1].rstrip("\n")]
    return []

def segment_lines(source: str, node) -> list[str]:
    "Segment lines."
    seg = ast.get_source_segment(source, node)
    if not seg: return []
    return [line.rstrip() for line in seg.splitlines()]

def first_line_indent(lines: list[str], lineno: int | None) -> int:
    "First line indent."
    if not lineno or lineno < 1 or lineno > len(lines): return 0
    line = lines[lineno - 1]
    return len(line) - len(line.lstrip())

def combined_len(seg_lines: list[str], indent: int) -> int:
    "Combined length."
    return sum(len(line.strip()) for line in seg_lines) + indent

def _has_trailing_comment(line: str) -> bool:
    "Check if line has a trailing comment (# not at start of stripped content)."
    stripped = line.strip()
    if not stripped or stripped.startswith('#'): return False
    return '#' in stripped

def _has_comment(line: str) -> bool:
    "Check if line has a comment."
    stripped = line.strip()
    return stripped.startswith("#") or _has_trailing_comment(line)

def line_indent(line: str) -> int:
    "Line indent."
    return len(line) - len(line.lstrip())

def is_inefficient_multiline(seg_lines: list[str], indent: int) -> bool:
    "Inefficient multiline."
    if len(seg_lines) <= 1: return False
    if any(_has_comment(line) for line in seg_lines): return False
    total = combined_len(seg_lines, indent)
    needed = math.ceil(total / WRAP_WIDTH)
    return needed < len(seg_lines)

def suite_len(lines: list[str], header_lineno: int | None, stmt_lineno: int | None) -> int | None:
    "Suite length."
    if not header_lineno or not stmt_lineno: return None
    if header_lineno < 1 or stmt_lineno < 1: return None
    if header_lineno > len(lines) or stmt_lineno > len(lines): return None
    first = lines[header_lineno - 1]
    second = lines[stmt_lineno - 1]
    indent = len(first) - len(first.lstrip())
    return len(first.strip()) + len(second.strip()) + indent

def find_suite_header(lines: list[str], start: int, stop: int, keyword: str) -> int:
    "Find suite header."
    if start < 1 or stop < 1 or start > len(lines): return stop
    stop = max(1, min(stop, len(lines)))
    for idx in range(start - 1, stop - 2, -1):
        if lines[idx].lstrip().startswith(f"{keyword}:"): return idx + 1
    return stop

def add_violation(violations: list[tuple], path: str, lineno: int, msg: str, lines: list[str], suppressed: set[int]):
    "Add violation."
    if lineno in suppressed: return
    violations.append((path, lineno, msg, lines))

def with_hint(msg: str, hint: str | None = None) -> str:
    "Attach optional fix hint to violation message."
    if not hint: return msg
    return f"{msg} (hint: {hint})"

def violation_rule(msg: str) -> str:
    "Rule id for a violation message."
    base = msg.split(" (hint:", 1)[0]
    for prefix,rule in RULE_PREFIXES:
        if base.startswith(prefix): return rule
    return base.lower().replace(" ", "-")

def filter_violations(violations: list[tuple], ignored: set[str] | None = None) -> list[tuple]:
    "Remove ignored violations."
    if not ignored or ALL_RULES in ignored: return [] if ignored and ALL_RULES in ignored else violations
    return [v for v in violations if violation_rule(v[2]) not in ignored]

def check_single_line_docstring(source: str, lines: list[str], stmt, path: str, violations: list[tuple], suppressed: set[int]):
    "Check single-line docstring."
    doc = stmt.value.value
    if "\n" in doc: return
    seg = ast.get_source_segment(source, stmt) or ""
    if re.match(r'^[ \t]*[rRuUbBfF]*\"\"\"', seg):
        msg = with_hint("single-line docstring uses triple quotes", "use single quotes or double quotes for one-line docstrings")
        add_violation(violations, path, stmt.lineno, msg, node_lines(source, lines, stmt), suppressed)

def check_suite(parent_kind: str, node, suite, path: str, source: str, lines: list[str], violations: list[tuple],
    suppressed: set[int]):
    "Check single-statement suites."
    if not suite: return
    if len(suite) != 1: return
    stmt = suite[0]
    if is_docstring_stmt(stmt): return
    if parent_kind == "else" and isinstance(node, ast.If) and isinstance(stmt, ast.If): return
    if isinstance(stmt, COMPOUND_NODES): return
    if getattr(stmt, "end_lineno", stmt.lineno) > stmt.lineno: return
    header_lineno = getattr(node, "lineno", stmt.lineno)
    if parent_kind in ("else", "finally"): header_lineno = find_suite_header(lines, stmt.lineno, header_lineno, parent_kind)
    if stmt.lineno <= header_lineno: return
    if any(_has_comment(lines[i-1]) for i in range(header_lineno, stmt.lineno + 1)): return
    total_len = suite_len(lines, header_lineno, stmt.lineno)
    if total_len is not None and total_len > MAX_LINE_LEN: return
    header_line = lines[header_lineno - 1].rstrip("\n")
    body_line = lines[stmt.lineno - 1].rstrip("\n")
    add_violation(violations, path, header_lineno, with_hint(f"{parent_kind} single-statement body not one-liner",
        "put the simple body statement on the header line if it still reads clearly"),
        [header_line] if header_lineno == stmt.lineno else [header_line, body_line], suppressed)

def check_multiline_sig(node, lines: list[str], path: str, violations: list[tuple], suppressed: set[int]):
    "Check multiline signature/header."
    if not node.body: return
    start = node.lineno
    body_start = node.body[0].lineno
    if not start or not body_start or body_start <= start + 0: return
    end = body_start - 1
    if end <= start: return
    seg_lines = [lines[i - 1].rstrip("\n") for i in range(start, end + 1)]
    if any(line.lstrip().startswith("@") for line in seg_lines[1:]): return
    indent = first_line_indent(lines, start)
    if not is_inefficient_multiline(seg_lines, indent): return
    add_violation(violations, path, start, with_hint("inefficient multiline signature/header",
        "condense to fewer lines; avoid leaving `(`, `dict(`, or `{` on their own line"), seg_lines, suppressed)

def _contains_multiline_str(node) -> bool:
    "Check if node or any descendant is a multiline string."
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and "\n" in n.value: return True
        if isinstance(n, ast.JoinedStr) and any(isinstance(v, ast.Constant) and "\n" in str(v.value) for v in n.values): return True
    return False

def check_multiline_expr(node, source: str, lines: list[str], path: str, violations: list[tuple], suppressed: set[int]):
    "Check multiline expression layout."
    if not node: return
    if getattr(node, "end_lineno", node.lineno) <= node.lineno: return
    if _contains_multiline_str(node): return
    seg_lines = segment_lines(source, node)
    if not seg_lines or len(seg_lines) <= 1: return
    indent = first_line_indent(lines, node.lineno)
    if not is_inefficient_multiline(seg_lines, indent): return
    add_violation(violations, path, node.lineno, with_hint("inefficient multiline expression",
        "condense to fewer lines; avoid leaving `(`, `dict(`, or `{` on their own line"), seg_lines, suppressed)

def max_subscript_depth(node, depth: int = 0) -> int:
    "Max subscript depth."
    if node is None: return depth
    if isinstance(node, ast.Subscript):
        depth += 1
        return max(depth, max_subscript_depth(node.value, depth), max_subscript_depth(node.slice, depth))
    depths = [max_subscript_depth(child, depth) for child in ast.iter_child_nodes(node)]
    return max(depths) if depths else depth

def is_dataclass_decorator(dec) -> bool:
    "Dataclass decorator."
    if isinstance(dec, ast.Name): return dec.id == "dataclass"
    if isinstance(dec, ast.Attribute): return dec.attr == "dataclass"
    if isinstance(dec, ast.Call): return is_dataclass_decorator(dec.func)
    return False

def _is_basemodel_subclass(node) -> bool:
    "Check if class inherits from BaseModel."
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "BaseModel": return True
        if isinstance(base, ast.Attribute) and base.attr == "BaseModel": return True
    return False

def dataclass_annassigns(tree) -> set:
    "Dataclass and BaseModel annassigns."
    annassigns = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef): continue
        is_dataclass = any(is_dataclass_decorator(dec) for dec in node.decorator_list)
        if not is_dataclass and not _is_basemodel_subclass(node): continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign): annassigns.add(stmt)
    return annassigns

def check_annotation(node, source: str, lines: list[str], path: str, violations: list[tuple], suppressed: set[int],
    check_nested: bool=False):
    "Check annotation depth and layout."
    if node is None: return
    if getattr(node, "end_lineno", node.lineno) > node.lineno:
        seg_lines = segment_lines(source, node)
        indent = first_line_indent(lines, node.lineno)
        if is_inefficient_multiline(seg_lines, indent):
            add_violation(violations, path, node.lineno, with_hint("inefficient multiline annotation",
                "condense to fewer lines or extract part of the type into a named alias"), seg_lines, suppressed)
    if not check_nested: return
    depth = max_subscript_depth(node)
    if depth >= 2:
        msg = with_hint(f"nested generics depth {depth}", "simplify or alias nested parts; less precise is fine if still correct")
        add_violation(violations, path, getattr(node, "lineno", 1), msg, node_lines(source, lines, node), suppressed)

def _has_pragma(line, pragma):
    "Check if line has pragma in a comment (after #)."
    idx = line.find(pragma)
    if idx == -1: return False
    comment_idx = line.find('#')
    return comment_idx != -1 and comment_idx < idx

def string_token_spans(source: str, lines: list[str]) -> dict:
    "Return line->column spans covered by string tokens."
    spans = {}
    try: tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    except tokenize.TokenError: return spans
    for tok in tokens:
        if tok.type != tokenize.STRING: continue
        srow, scol = tok.start
        erow, ecol = tok.end
        if not (1 <= srow <= len(lines) and 1 <= erow <= len(lines)): continue
        if srow == erow:
            spans.setdefault(srow, []).append((scol, ecol))
            continue
        spans.setdefault(srow, []).append((scol, len(lines[srow - 1])))
        for row in range(srow + 1, erow): spans.setdefault(row, []).append((0, len(lines[row - 1])))
        spans.setdefault(erow, []).append((0, ecol))
    return spans

def token_line_infos(source: str) -> dict:
    "Return line start bracket stack and code tokens."
    infos, stack = {}, []
    try: tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    except tokenize.TokenError: return infos
    skip = {tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT, tokenize.ENDMARKER}
    for tok in tokens:
        row = tok.start[0]
        info = infos.setdefault(row, {"stack": tuple(stack), "tokens": []})
        if tok.type in skip: continue
        info["tokens"].append(tok)
        if tok.type == tokenize.OP and tok.string in "([{": stack.append(row)
        elif tok.type == tokenize.OP and tok.string in ")]}" and stack: stack.pop()
    return infos

def _sym_scope_kind(tab) -> str:
    "Normalize symtable scope kinds."
    kind = tab.get_type()
    return "lambda" if kind == "function" and tab.get_name() == "lambda" else kind

def _scope_key(kind: str, name: str, lineno: int) -> tuple[str, str, int]:
    "Stable scope key for AST/symtable matching."
    return kind, name, lineno

def _scope_bindings(tab) -> set[str]:
    "Names bound in a scope."
    return {sym.get_name() for sym in tab.get_symbols() if sym.is_local() or sym.is_imported() or sym.is_parameter() or sym.is_assigned()
        or sym.is_namespace()}

def _scope_globals(tab) -> set[str]:
    "Explicit global declarations in a scope."
    return {sym.get_name() for sym in tab.get_symbols() if hasattr(sym, "is_declared_global") and sym.is_declared_global()}

def _scope_nonlocals(tab) -> set[str]:
    "Explicit nonlocal declarations in a scope."
    return {sym.get_name() for sym in tab.get_symbols() if sym.is_nonlocal()}

def _build_scope_tree(tab, parent=None):
    "Build scope metadata tree from symtable."
    info = dict(kind=_sym_scope_kind(tab), name=tab.get_name(), lineno=tab.get_lineno(), parent=parent, bindings=_scope_bindings(tab),
        globals=_scope_globals(tab), nonlocals=_scope_nonlocals(tab), imports=[], used=set(), free=set(), children={}, kids=[])
    for child in tab.get_children():
        child_info = _build_scope_tree(child, info)
        info["kids"].append(child_info)
        info["children"].setdefault(_scope_key(child_info["kind"], child_info["name"], child_info["lineno"]), []).append(child_info)
    return info

def _root_scope(scope):
    "Root/module scope."
    while scope["parent"] is not None: scope = scope["parent"]
    return scope

def _next_closure_scope(scope):
    "Next enclosing closure scope, skipping class scopes."
    scope = scope["parent"]
    while scope is not None and scope["kind"] == "class": scope = scope["parent"]
    return scope

def _resolve_nonlocal(scope, name: str):
    "Resolve a nonlocal binding."
    scope = _next_closure_scope(scope)
    while scope is not None and scope["kind"] != "module":
        if name in scope["bindings"]: return scope
        scope = _next_closure_scope(scope)
    return None

def _resolve_name(scope, name: str):
    "Resolve a load name to the scope that binds it."
    start,cur = scope,scope
    while cur is not None:
        if cur["kind"] in {"function", "lambda", "comp"}:
            if name in cur["globals"]: return _root_scope(cur)
            if name in cur["nonlocals"]: return _resolve_nonlocal(cur, name)
            if name in cur["bindings"]: return cur
            cur = _next_closure_scope(cur)
            continue
        if cur["kind"] == "class":
            if cur is start and name in cur["bindings"]: return cur
            cur = cur["parent"]
            continue
        return cur if name in cur["bindings"] else None
    return None

def _bind_names(node, names: set[str]):
    "Collect bound names from a target."
    if isinstance(node, ast.Name): names.add(node.id)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for o in node.elts: _bind_names(o, names)
    elif isinstance(node, ast.Starred): _bind_names(node.value, names)

def _literal_strs(node):
    "Extract literal string names from __all__-like expressions."
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        if not all(isinstance(o, ast.Constant) and isinstance(o.value, str) for o in node.elts): return None
        return [o.value for o in node.elts]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left,right = _literal_strs(node.left),_literal_strs(node.right)
        return None if left is None or right is None else left + right
    return None

def exported_names(tree) -> set[str]:
    "Names exported through a simple static __all__."
    res = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            if vals := _literal_strs(node.value): res.update(vals)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__" and isinstance(node.op, ast.Add):
            if vals := _literal_strs(node.value): res.update(vals)
    return res

def _import_name(alias, from_import: bool=False) -> str:
    "Bound name for an import alias."
    if alias.asname: return alias.asname
    return alias.name if from_import else alias.name.split(".", 1)[0]

def _base_path(path: str) -> str:
    "Notebook cell paths include a cell suffix."
    return path.split(":cell[", 1)[0]

class _UnusedImportVisitor(ast.NodeVisitor):
    "Track imported names that are referenced."
    def __init__(self, scope): self.scope = scope

    def _child_scope(self, kind: str, name: str, lineno: int):
        kids = self.scope["children"].get(_scope_key(kind, name, lineno), [])
        if kids: return kids.pop(0)
        return dict(kind=kind, name=name, lineno=lineno, parent=self.scope, bindings=set(), globals=set(), nonlocals=set(),
            imports=[], used=set(), free=set(), children={}, kids=[])

    def _visit_args(self, args):
        for o in args.defaults:
            if o is not None: self.visit(o)
        for o in args.kw_defaults:
            if o is not None: self.visit(o)
        for arg in args.posonlyargs + args.args + args.kwonlyargs:
            if arg.annotation is not None: self.visit(arg.annotation)
        if args.vararg and args.vararg.annotation is not None: self.visit(args.vararg.annotation)
        if args.kwarg and args.kwarg.annotation is not None: self.visit(args.kwarg.annotation)

    def _push(self, scope):
        old,self.scope = self.scope,scope
        return old

    def _pop(self, old): self.scope = old

    def _visit_function(self, node, kind: str):
        for o in node.decorator_list: self.visit(o)
        self._visit_args(node.args)
        if getattr(node, "returns", None) is not None: self.visit(node.returns)
        old = self._push(self._child_scope(kind, node.name, node.lineno))
        for stmt in node.body: self.visit(stmt)
        self._pop(old)

    def _visit_comp(self, node, *parts):
        if not node.generators:
            for o in parts: self.visit(o)
            return
        first = node.generators[0]
        self.visit(first.iter)
        comp = dict(kind="comp", name="comp", lineno=node.lineno, parent=self.scope, bindings=set(), globals=set(), nonlocals=set(),
            imports=[], used=set(), free=set(), children={}, kids=[])
        old = self._push(comp)
        _bind_names(first.target, comp["bindings"])
        for o in first.ifs: self.visit(o)
        for gen in node.generators[1:]:
            self.visit(gen.iter)
            _bind_names(gen.target, comp["bindings"])
            for o in gen.ifs: self.visit(o)
        for o in parts: self.visit(o)
        self._pop(old)

    def visit_Import(self, node): self.scope["imports"].append((node, [_import_name(o) for o in node.names]))

    def visit_ImportFrom(self, node):
        if node.module == "__future__": return
        names = [_import_name(o, from_import=True) for o in node.names if o.name != "*"]
        if names: self.scope["imports"].append((node, names))

    def visit_Name(self, node):
        if not isinstance(node.ctx, ast.Load): return
        scope = _resolve_name(self.scope, node.id)
        if scope and node.id in scope["bindings"]:
            if any(name == node.id for _node,names in scope["imports"] for name in names): scope["used"].add(node.id)
            return
        self.scope["free"].add(node.id)

    def visit_FunctionDef(self, node): self._visit_function(node, "function")
    def visit_AsyncFunctionDef(self, node): self._visit_function(node, "function")

    def visit_ClassDef(self, node):
        for o in node.decorator_list: self.visit(o)
        for o in node.bases: self.visit(o)
        for o in node.keywords: self.visit(o)
        old = self._push(self._child_scope("class", node.name, node.lineno))
        for stmt in node.body: self.visit(stmt)
        self._pop(old)

    def visit_Lambda(self, node):
        self._visit_args(node.args)
        old = self._push(self._child_scope("lambda", "lambda", node.lineno))
        self.visit(node.body)
        self._pop(old)

    def visit_ListComp(self, node): self._visit_comp(node, node.elt)
    def visit_SetComp(self, node): self._visit_comp(node, node.elt)
    def visit_GeneratorExp(self, node): self._visit_comp(node, node.elt)
    def visit_DictComp(self, node): self._visit_comp(node, node.key, node.value)

def _analyze_usage(source: str, tree, path: str):
    "Build scope tree populated with import and free-name usage."
    root = _build_scope_tree(symtable.symtable(source, _base_path(path), "exec"))
    _UnusedImportVisitor(root).visit(tree)
    return root

def _collect_scope_names(scope, key: str) -> set[str]:
    "Collect a set-valued field from a scope tree."
    names = set(scope[key])
    for child in scope["kids"]: names.update(_collect_scope_names(child, key))
    return names

def _unused_import_items(scope, exports: set[str], items: list[tuple]):
    "Collect unused imports from a scope tree."
    keep = exports if scope["kind"] == "module" else set()
    for node,names in scope["imports"]:
        unused = [name for name in names if name not in scope["used"] and name not in keep]
        if unused: items.append((node, unused, scope["kind"]))
    for child in scope["kids"]: _unused_import_items(child, exports, items)

def unused_import_items(source: str, tree, path: str) -> list[tuple]:
    "Return unused import items, excluding package __init__.py re-export patterns."
    if os.path.basename(_base_path(path)) == "__init__.py": return []
    items = []
    _unused_import_items(_analyze_usage(source, tree, path), exported_names(tree), items)
    return items

def free_load_names(source: str, tree, path: str) -> set[str]:
    "Return unresolved loaded names."
    return _collect_scope_names(_analyze_usage(source, tree, path), "free")

def check_unused_imports(source: str, tree, lines: list[str], path: str, violations: list[tuple], suppressed: set[int]):
    "Check for unused imports, excluding package __init__.py re-export patterns."
    hint = "remove unused imports; re-exports belong in `__all__` or package `__init__.py`"
    for node,unused,_kind in unused_import_items(source, tree, path):
        msg = with_hint(f"unused import: {', '.join(unused)}", hint)
        add_violation(violations, path, node.lineno, msg, node_lines(source, lines, node), suppressed)

def _is_short_single_import(node, lines: list[str]) -> bool:
    "Check if node is a short single-module import."
    if not isinstance(node, ast.Import): return False
    if getattr(node, "end_lineno", node.lineno) != node.lineno or len(node.names) != 1: return False
    line = lines[node.lineno - 1].rstrip("\n")
    if not line.strip().startswith("import "): return False
    return len(line) < 50 and not _has_trailing_comment(line)

def _combined_import_len(nodes: list, lines: list[str]) -> int:
    "Combined length for a run of import statements."
    indent = first_line_indent(lines, nodes[0].lineno)
    names = ", ".join(lines[node.lineno - 1].strip().removeprefix("import ").strip() for node in nodes)
    return indent + len("import ") + len(names)

def check_short_import_runs(tree, lines: list[str], path: str, violations: list[tuple], suppressed: set[int]):
    "Check consecutive short imports."
    imports = sorted((node for node in ast.walk(tree) if isinstance(node, ast.Import)),
        key=lambda node: (node.lineno, getattr(node, "end_lineno", node.lineno)))
    run = []
    def flush():
        if len(run) < 2: return
        import_lines = [lines[node.lineno - 1].rstrip("\n") for node in run]
        add_violation(violations, path, run[0].lineno, with_hint("consecutive short imports",
            "combine consecutive short imports onto one line: `import a, b`"), import_lines, suppressed)
    for node in imports:
        if not _is_short_single_import(node, lines):
            flush()
            run = []
            continue
        if not run:
            run = [node]
            continue
        prev = run[-1]
        same_indent = first_line_indent(lines, node.lineno) == first_line_indent(lines, prev.lineno)
        if node.lineno != getattr(prev, "end_lineno", prev.lineno) + 1 or not same_indent:
            flush()
            run = [node]
            continue
        cand = run + [node]
        if _combined_import_len(cand, lines) > MAX_LINE_LEN:
            flush()
            run = [node]
            continue
        run = cand
    flush()

def check_standalone_closers(line_infos: dict, lines: list[str], path: str, violations: list[tuple], suppressed: set[int]):
    "Check closers on their own line."
    for lineno, info in sorted(line_infos.items()):
        toks = info["tokens"]
        if len(toks) != 1: continue
        tok = toks[0]
        if _has_comment(lines[lineno - 1]): continue
        if lines[lineno - 1].strip() != tok.string: continue
        if tok.type != tokenize.OP or tok.string not in ")]}" or not info["stack"]: continue
        add_violation(violations, path, lineno, with_hint("closing bracket on its own line",
            "move `)`, `]`, or `}` to the end of the previous content line"), [lines[lineno - 1]], suppressed)

def check_continuation_indents(line_infos: dict, lines: list[str], path: str, violations: list[tuple], suppressed: set[int]):
    "Check continuation indentation."
    for lineno, info in sorted(line_infos.items()):
        if not info["stack"] or not info["tokens"]: continue
        first = info["tokens"][0]
        if first.type == tokenize.OP and first.string in ")]}": continue
        expected = first_line_indent(lines, info["stack"][-1]) + 4
        actual = line_indent(lines[lineno - 1])
        if actual == expected: continue
        hint = "indent continuation lines exactly 4 spaces beyond the line that opened the block"
        add_violation(violations, path, lineno, with_hint("continuation line indent", hint), [lines[lineno - 1]], suppressed)

def line_len_without_spans(line: str, spans: list[tuple]) -> int:
    "Length after removing span ranges from a line."
    if not spans: return len(line)
    merged = []
    for start, end in sorted(spans):
        start, end = max(0, min(start, len(line))), max(0, min(end, len(line)))
        if start > end: start, end = end, start
        if not merged or start > merged[-1][1]: merged.append([start, end])
        else: merged[-1][1] = max(merged[-1][1], end)
    removed = sum(end - start for start, end in merged)
    return len(line) - removed

def should_skip_file(lines: list[str]) -> bool:
    "Skip file."
    head = lines[:5]
    return any(_has_pragma(line, "chkstyle: skip") for line in head)

def suppressed_lines(lines: list[str]) -> set[int]:
    "Suppressed lines."
    suppressed = set()
    off = False
    ignore_next = False
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if _has_pragma(line, "chkstyle: on"):
            off = False
            ignore_next = False
            continue
        if _has_pragma(line, "chkstyle: off"):
            off = True
            ignore_next = False
            suppressed.add(lineno)
            continue
        if off: suppressed.add(lineno)
        if _has_pragma(line, "chkstyle: ignore"):
            if stripped.startswith("#"): ignore_next = True
            else: suppressed.add(lineno)
        elif ignore_next and stripped and not stripped.startswith("#"):
            suppressed.add(lineno)
            ignore_next = False
    return suppressed

def _line_offsets(source: str) -> list[int]:
    "Starting offset for each 1-based source line."
    offsets, pos = [], 0
    for line in source.splitlines(True):
        offsets.append(pos)
        pos += len(line)
    if not offsets: offsets.append(0)
    return offsets

def _node_span(node, offsets: list[int]) -> tuple[int, int]:
    "Absolute source span for an AST node."
    return offsets[node.lineno - 1] + node.col_offset, offsets[node.end_lineno - 1] + node.end_col_offset

def _line_span(source_lines: list[str], offsets: list[int], start: int, end: int | None = None) -> tuple[int, int]:
    "Absolute source span for inclusive 1-based line range."
    end = start if end is None else end
    return offsets[start - 1], offsets[end - 1] + len(source_lines[end - 1])

def _line_ending(line: str) -> str:
    "Line ending."
    if line.endswith("\r\n"): return "\r\n"
    if line.endswith("\n"): return "\n"
    return ""

def _line_body(line: str) -> str:
    "Line without ending."
    return line.removesuffix("\n").removesuffix("\r")

def _has_comments(lines: list[str]) -> bool:
    "Check if any line has a comment."
    return any(_has_comment(line) for line in lines)

def _apply_edits(source: str, edits: list) -> str:
    "Apply non-overlapping source edits from bottom to top."
    last_start = len(source) + 1
    for start,end,repl in sorted(edits, key=lambda edit: (edit[0], edit[1]), reverse=True):
        if end > last_start: continue
        source = source[:start] + repl + source[end:]
        last_start = start
    return source

def _rule_enabled(rule: str, selected: set[str]) -> bool:
    "Check whether a rule is selected."
    return ALL_RULES in selected or rule in selected

def _all_assign_lines(tree):
    "Line ranges of __all__ assignments (auto-generated by nbdev)."
    lines = set()
    for node in ast.iter_child_nodes(tree):
        is_all = (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
            or isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__")
        if is_all: lines.update(range(node.lineno, node.end_lineno + 1))
    return lines

def _alias_src(alias) -> str:
    "Import alias source."
    return alias.name if alias.asname is None else f"{alias.name} as {alias.asname}"

def _from_import_src(node, names: list | None = None) -> str:
    "Single-line from import source."
    mod = "." * node.level + (node.module or "")
    return f"from {mod} import {', '.join(_alias_src(alias) for alias in (names or node.names))}"

def _dict_fix_src(node, source: str, offsets: list[int], indent: int) -> str | None:
    "Replacement source for an eligible dict literal."
    keys = dict_keyword_keys(node)
    if not keys or any(value is None for value in node.values): return None
    parts = []
    for key,value in zip(keys, node.values):
        val_src = ast.get_source_segment(source, value)
        if val_src is None: return None
        parts.append(f"{key}={val_src.strip()}")
    res = f"dict({', '.join(parts)})"
    return res if indent + len(res) <= MAX_LINE_LEN else None

def _simplify_annotation(node, depth: int = 0):
    "Remove nested generic levels beyond depth 1."
    if isinstance(node, ast.Subscript):
        if depth >= 1: return _simplify_annotation(node.value, depth)
        return ast.copy_location(ast.Subscript(value=_simplify_annotation(node.value, depth),
            slice=_simplify_annotation(node.slice, depth + 1), ctx=ast.Load()), node)
    if isinstance(node, ast.Tuple):
        elts = [_simplify_annotation(elt, depth) for elt in node.elts]
        return ast.copy_location(ast.Tuple(elts=elts, ctx=ast.Load()), node)
    return node

def _suite_fix_edit(source_lines: list[str], offsets: list[int], parent_kind: str, node, suite) -> tuple[int, int, str] | None:
    "Edit for a single-statement suite."
    if not suite or len(suite) != 1: return None
    stmt = suite[0]
    if is_docstring_stmt(stmt) or isinstance(stmt, COMPOUND_NODES): return None
    if parent_kind == "else" and isinstance(node, ast.If) and isinstance(stmt, ast.If): return None
    if getattr(stmt, "end_lineno", stmt.lineno) > stmt.lineno: return None
    header_lineno = getattr(node, "lineno", stmt.lineno)
    lines = [_line_body(line) for line in source_lines]
    if parent_kind in ("else", "finally"): header_lineno = find_suite_header(lines, stmt.lineno, header_lineno, parent_kind)
    if stmt.lineno != header_lineno + 1: return None
    if any(_has_comment(lines[i - 1]) for i in range(header_lineno, stmt.lineno + 1)): return None
    total_len = suite_len(lines, header_lineno, stmt.lineno)
    if total_len is None or total_len > MAX_LINE_LEN: return None
    start,end = _line_span(source_lines, offsets, header_lineno, stmt.lineno)
    return start, end, f"{lines[header_lineno - 1]} {lines[stmt.lineno - 1].strip()}{_line_ending(source_lines[stmt.lineno - 1])}"

def _fix_source_once(source: str, path: str, selected: set[str]) -> str:
    "Apply one conservative fix pass."
    source_lines, lines = source.splitlines(True), source.splitlines()
    if not source_lines or should_skip_file(lines): return source
    try: tree = ast.parse(source, filename=path)
    except SyntaxError: return source
    offsets = _line_offsets(source)
    suppressed = suppressed_lines(lines) | _all_assign_lines(tree)
    edits = []
    dataclass_fields = dataclass_annassigns(tree)
    line_infos = token_line_infos(source)
    for node in ast.walk(tree):
        seg_lines = segment_lines(source, node)
        if isinstance(node, ast.Expr) and is_docstring_stmt(node) and _rule_enabled("single-line-docstring", selected):
            if "\n" not in node.value.value and not _has_comments(seg_lines):
                seg = ast.get_source_segment(source, node) or ""
                if re.match(r'^[ \t]*[rRuUbBfF]*\"\"\"', seg): edits.append((*_node_span(node, offsets), repr(node.value.value)))
        if isinstance(node, ast.Dict) and len(node.keys) >= 3 and _rule_enabled("dict-literal", selected):
            if node.lineno not in suppressed and not _has_comments(seg_lines):
                if repl := _dict_fix_src(node, source, offsets, first_line_indent(lines, node.lineno)): edits.append((*_node_span(node, offsets), repl))
        if isinstance(node, ast.AnnAssign) and _rule_enabled("lhs-assignment-annotation", selected):
            if node.value is not None and node not in dataclass_fields and node.lineno not in suppressed and not _has_comments(seg_lines):
                target, value = ast.get_source_segment(source, node.target), ast.get_source_segment(source, node.value)
                if target and value: edits.append((*_node_span(node, offsets), f"{target.strip()} = {value.strip()}"))
        if isinstance(node, ast.ImportFrom) and "\n" in (ast.get_source_segment(source, node) or "") and _rule_enabled("multi-line-from-import", selected):
            if node.lineno not in suppressed and not _has_comments(seg_lines):
                repl = _from_import_src(node)
                if first_line_indent(lines, node.lineno) + len(repl) <= MAX_LINE_LEN: edits.append((*_node_span(node, offsets), repl))
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.Return, ast.Expr)) and _rule_enabled("inefficient-multiline-expression", selected):
            expr = node.value if not isinstance(node, ast.Expr) else node.value
            if expr is None: continue
            expr_lines = segment_lines(source, expr)
            if expr and len(expr_lines) > 1 and not _contains_multiline_str(expr) and not _has_comments(expr_lines):
                repl = ast.unparse(expr)
                if first_line_indent(lines, expr.lineno) + len(repl) <= MAX_LINE_LEN: edits.append((*_node_span(expr, offsets), repl))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _rule_enabled("nested-generics", selected):
            args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
            args += [arg for arg in (node.args.vararg, node.args.kwarg) if arg is not None]
            for arg in args:
                ann = arg.annotation
                if ann is not None and max_subscript_depth(ann) >= 2 and ann.lineno not in suppressed:
                    edits.append((*_node_span(ann, offsets), ast.unparse(_simplify_annotation(ann))))
    if _rule_enabled("unused-import", selected):
        for node,unused,_kind in unused_import_items(source, tree, path):
            if node.lineno in suppressed or getattr(node, "end_lineno", node.lineno) != node.lineno: continue
            if _has_comment(lines[node.lineno - 1]): continue
            aliases = [alias for alias in node.names if _import_name(alias, isinstance(node, ast.ImportFrom)) not in unused]
            start,end = _line_span(source_lines, offsets, node.lineno)
            if aliases:
                repl = ("import " + ", ".join(_alias_src(alias) for alias in aliases)) if isinstance(node, ast.Import) else _from_import_src(node, aliases)
                repl = " " * first_line_indent(lines, node.lineno) + repl + _line_ending(source_lines[node.lineno - 1])
            else: repl = ""
            edits.append((start, end, repl))
    if _rule_enabled("consecutive-short-imports", selected):
        imports = sorted((node for node in ast.walk(tree) if isinstance(node, ast.Import)), key=lambda node: node.lineno)
        run = []
        def flush_run():
            if len(run) < 2: return
            start,end = _line_span(source_lines, offsets, run[0].lineno, run[-1].lineno)
            names = ", ".join(lines[node.lineno - 1].strip().removeprefix("import ").strip() for node in run)
            edits.append((start, end, " " * first_line_indent(lines, run[0].lineno) + f"import {names}{_line_ending(source_lines[run[-1].lineno - 1])}"))
        for node in imports:
            if not _is_short_single_import(node, lines) or node.lineno in suppressed:
                flush_run()
                run = []
                continue
            if run and (node.lineno != run[-1].lineno + 1 or first_line_indent(lines, node.lineno) != first_line_indent(lines, run[-1].lineno)):
                flush_run()
                run = []
            run.append(node)
        flush_run()
    if _rule_enabled("single-statement-body", selected):
        for node in ast.walk(tree):
            items = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): items.append(("def", node, node.body))
            elif isinstance(node, ast.If): items += [("if", node, node.body), ("else", node, node.orelse)]
            elif isinstance(node, (ast.For, ast.AsyncFor)): items += [("for", node, node.body), ("else", node, node.orelse)]
            elif isinstance(node, ast.While): items += [("while", node, node.body), ("else", node, node.orelse)]
            elif isinstance(node, (ast.With, ast.AsyncWith)): items.append(("with", node, node.body))
            elif isinstance(node, ast.Try):
                items += [("try", node, node.body), ("else", node, node.orelse), ("finally", node, node.finalbody)]
                items += [("except", handler, handler.body) for handler in node.handlers]
            for kind,owner,suite in items:
                if edit := _suite_fix_edit(source_lines, offsets, kind, owner, suite): edits.append(edit)
    if _rule_enabled("closing-bracket", selected):
        for lineno, info in sorted(line_infos.items()):
            toks = info["tokens"]
            if len(toks) != 1 or not info["stack"]: continue
            tok = toks[0]
            if tok.type != tokenize.OP or tok.string not in ")]}": continue
            if _has_comment(lines[lineno - 1]) or lines[lineno - 1].strip() != tok.string: continue
            prev = lineno - 1
            if prev < 1: continue
            start,end = _line_span(source_lines, offsets, prev, lineno)
            edits.append((start, end, f"{_line_body(source_lines[prev - 1]).rstrip()}{tok.string}{_line_ending(source_lines[lineno - 1])}"))
    if _rule_enabled("continuation-indent", selected):
        for lineno, info in sorted(line_infos.items()):
            if not info["stack"] or not info["tokens"]: continue
            first = info["tokens"][0]
            if first.type == tokenize.OP and first.string in ")]}": continue
            expected = first_line_indent(lines, info["stack"][-1]) + 4
            if line_indent(lines[lineno - 1]) == expected: continue
            start,end = _line_span(source_lines, offsets, lineno)
            edits.append((start, end, " " * expected + lines[lineno - 1].lstrip() + _line_ending(source_lines[lineno - 1])))
    if _rule_enabled("semicolon", selected):
        try: tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
        except tokenize.TokenError: tokens = []
        semis = {}
        for tok in tokens:
            if tok.type == tokenize.OP and tok.string == ";": semis.setdefault(tok.start[0], []).append(tok.start[1])
        for lineno, cols in semis.items():
            line = lines[lineno - 1]
            if _has_comment(line) or line.lstrip().startswith("class ") or ":" in line[:min(cols)]: continue
            parts = [part.strip() for part in line.split(";")]
            if all(parts):
                start,end = _line_span(source_lines, offsets, lineno)
                indent = " " * first_line_indent(lines, lineno)
                newline = _line_ending(source_lines[lineno - 1])
                repl = parts[0] + newline + "".join(f"{indent}{part}{newline}" for part in parts[1:])
                edits.append((start, end, repl))
    return _apply_edits(source, edits)

def fix_source(source: str, path: str, selected: set[str]) -> tuple[str, int]:
    "Fix source, returning new source and number of passes that changed it."
    changes = 0
    for _i in range(8):
        fixed = _fix_source_once(source, path, selected)
        if fixed == source: break
        source, changes = fixed, changes + 1
    return source, changes

def check_source(source: str, path: str, check_unused: bool=True) -> list[tuple]:
    "Check source code string for style violations."
    lines = source.splitlines()
    if should_skip_file(lines): return []
    try: tree = ast.parse(source, filename=path)
    except SyntaxError as e: return [(path, e.lineno or 1, f"syntax error: {e.msg}", [])]
    violations = []
    suppressed = suppressed_lines(lines) | _all_assign_lines(tree)
    str_spans = string_token_spans(source, lines)
    line_infos = token_line_infos(source)
    if check_unused: check_unused_imports(source, tree, lines, path, violations, suppressed)
    check_short_import_runs(tree, lines, path, violations, suppressed)
    check_standalone_closers(line_infos, lines, path, violations, suppressed)
    check_continuation_indents(line_infos, lines, path, violations, suppressed)
    for lineno, line in enumerate(lines, start=1):
        if len(line) <= MAX_LINE_LEN: continue
        if line_len_without_spans(line, str_spans.get(lineno, [])) <= MAX_LINE_LEN: continue
        hint = "wrap at a natural boundary (args/operators); if reformatted literals got taller, avoid lonely `dict(`/`{` lines"
        add_violation(violations, path, lineno, with_hint(f"line >{MAX_LINE_LEN} chars", hint), [line], suppressed)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.OP and tok.string == ";":
                lineno = tok.start[0]
                if lines[lineno - 1].lstrip().startswith("class "): continue
                add_violation(violations, path, lineno, with_hint("semicolon statement separator",
                    "split into separate statements on separate lines"), [lines[lineno - 1]], suppressed)
    except tokenize.TokenError: pass
    if tree.body and is_docstring_stmt(tree.body[0]): check_single_line_docstring(source, lines, tree.body[0], path, violations, suppressed)
    dataclass_fields = dataclass_annassigns(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and len(node.keys) >= 3 and dict_keyword_keys(node):
            msg = with_hint("dict literal with 3+ identifier keys", "prefer dict(a=a, b=b, c=c) when keys are identifiers")
            add_violation(violations, path, node.lineno, msg, node_lines(source, lines, node), suppressed)
        if isinstance(node, ast.AnnAssign):
            if node not in dataclass_fields:
                msg = with_hint("lhs assignment annotation", "move the type hint to function signatures; keep plain assignments in normal code")
                add_violation(violations, path, node.lineno, msg, node_lines(source, lines, node), suppressed)
            check_multiline_expr(node.value, source, lines, path, violations, suppressed)
            check_annotation(node.annotation, source, lines, path, violations, suppressed)
        if isinstance(node, ast.ImportFrom):
            seg = ast.get_source_segment(source, node) or ""
            if "\n" in seg:
                import_lines = node_lines(source, lines, node)
                total_len = sum(len(line.strip()) for line in import_lines)
                if total_len <= MAX_LINE_LEN:
                    add_violation(violations, path, node.lineno, with_hint("multi-line from-import",
                        "use a single-line import when it fits"), import_lines, suppressed)
                elif is_inefficient_multiline(import_lines, first_line_indent(lines, node.lineno)):
                    add_violation(violations, path, node.lineno, with_hint("inefficient multi-line from-import",
                        "condense to fewer lines"), import_lines, suppressed)
        has_doc = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body
        if has_doc and is_docstring_stmt(node.body[0]): check_single_line_docstring(source, lines, node.body[0], path, violations, suppressed)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_multiline_sig(node, lines, path, violations, suppressed)
            if node.returns: check_annotation(node.returns, source, lines, path, violations, suppressed)
            for arg in node.args.args + node.args.kwonlyargs:
                if arg.annotation: check_annotation(arg.annotation, source, lines, path, violations, suppressed, check_nested=True)
            if node.args.vararg and node.args.vararg.annotation:
                check_annotation(node.args.vararg.annotation, source, lines, path, violations, suppressed, check_nested=True)
            if node.args.kwarg and node.args.kwarg.annotation:
                check_annotation(node.args.kwarg.annotation, source, lines, path, violations, suppressed, check_nested=True)
            if node.args.posonlyargs:
                for arg in node.args.posonlyargs:
                    if arg.annotation: check_annotation(arg.annotation, source, lines, path, violations, suppressed, check_nested=True)
        if isinstance(node, ast.ClassDef): check_multiline_sig(node, lines, path, violations, suppressed)
        if isinstance(node, ast.Assign): check_multiline_expr(node.value, source, lines, path, violations, suppressed)
        if isinstance(node, ast.AugAssign): check_multiline_expr(node.value, source, lines, path, violations, suppressed)
        if isinstance(node, ast.Return): check_multiline_expr(node.value, source, lines, path, violations, suppressed)
        if isinstance(node, ast.Expr) and not is_docstring_stmt(node): check_multiline_expr(node.value, source, lines, path, violations, suppressed)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): check_suite("def", node, node.body, path, source, lines, violations, suppressed)
        elif isinstance(node, ast.If):
            check_suite("if", node, node.body, path, source, lines, violations, suppressed)
            check_suite("else", node, node.orelse, path, source, lines, violations, suppressed)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            check_suite("for", node, node.body, path, source, lines, violations, suppressed)
            check_suite("else", node, node.orelse, path, source, lines, violations, suppressed)
        elif isinstance(node, ast.While):
            check_suite("while", node, node.body, path, source, lines, violations, suppressed)
            check_suite("else", node, node.orelse, path, source, lines, violations, suppressed)
        elif isinstance(node, (ast.With, ast.AsyncWith)): check_suite("with", node, node.body, path, source, lines, violations, suppressed)
        elif isinstance(node, ast.Try):
            check_suite("try", node, node.body, path, source, lines, violations, suppressed)
            for handler in node.handlers: check_suite("except", handler, handler.body, path, source, lines, violations, suppressed)
            check_suite("else", node, node.orelse, path, source, lines, violations, suppressed)
            check_suite("finally", node, node.finalbody, path, source, lines, violations, suppressed)
    return violations

def check_file(path: str) -> list[tuple]:
    "Check Python file for style violations."
    with open(path, encoding="utf-8") as f: source = f.read()
    return check_source(source, path)

def fix_file(path: str, selected: set[str]) -> bool:
    "Fix Python file in place."
    with open(path, encoding="utf-8") as f: source = f.read()
    fixed, changes = fix_source(source, path, selected)
    if not changes: return False
    with open(path, "w", encoding="utf-8") as f: f.write(fixed)
    return True

def _cell_source(cell) -> str:
    "Notebook cell source."
    source = cell.get("source", [])
    return source if isinstance(source, str) else "".join(source)

def _is_export_cell(source: str) -> bool:
    "Check for nbdev export markers."
    return bool(NB_EXPORT_RE.search(source))

def _notebook_cells(nb, path: str) -> list[dict]:
    "Notebook code cell metadata."
    cells = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code": continue
        source = _cell_source(cell)
        if not source.strip(): continue
        cell_id = cell.get("id", "unknown")
        lines = source.splitlines()
        cells.append(dict(id=cell_id, path=f"{path}:cell[{cell_id}]", source=source, lines=lines, export=_is_export_cell(source),
            skip=should_skip_file(lines)))
    return cells

def _combine_notebook_cells(cells: list[dict]) -> tuple[str, dict]:
    "Combine notebook cell sources and map line numbers back to cells."
    combined, line_map = [], {}
    for i, cell in enumerate(cells):
        for lineno, line in enumerate(cell["lines"], start=1):
            line_map[len(combined) + 1] = (cell, lineno)
            combined.append(line)
        if i != len(cells) - 1: combined.append("")
    return "\n".join(combined), line_map

def _notebook_node_location(node, line_map: dict) -> tuple[str, int, list]:
    "Map a combined-source node back to its notebook cell."
    cell, lineno = line_map[node.lineno]
    end = lineno + getattr(node, "end_lineno", node.lineno) - node.lineno
    return cell["path"], lineno, cell["lines"][lineno - 1:end]

def _first_non_export_import_cell_id(cells: list[dict]) -> str | None:
    "First non-exported cell with top-level import/from statements."
    for cell in cells:
        try: tree = ast.parse(cell["source"], filename=cell["path"])
        except SyntaxError: continue
        if any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in tree.body): return cell["id"]
    return None

def _check_notebook_unused_imports(cells: list[dict], path: str, violations: list[tuple]):
    "Check unused imports across exported notebook cells."
    export_cells = [cell for cell in cells if cell["export"] and not cell["skip"]]
    if not export_cells: return
    export_source, line_map = _combine_notebook_cells(export_cells)
    export_lines = export_source.splitlines()
    try: export_tree = ast.parse(export_source, filename=path)
    except SyntaxError: return
    suppressed = suppressed_lines(export_lines)
    non_export_cells = [cell for cell in cells if not cell["export"] and not cell["skip"]]
    non_export_used = set()
    target_cell_id = _first_non_export_import_cell_id(non_export_cells)
    if non_export_cells:
        non_export_source, _ = _combine_notebook_cells(non_export_cells)
        try: non_export_tree = ast.parse(non_export_source, filename=path)
        except SyntaxError: non_export_tree = None
        if non_export_tree is not None: non_export_used = free_load_names(non_export_source, non_export_tree, path)
    hint = "remove unused imports; re-exports belong in `__all__` or package `__init__.py`"
    move_hint = "move imports used only in non-exported cells into a non-exported imports cell"
    if target_cell_id: move_hint = f"move imports used only in non-exported cells to cell {target_cell_id}"
    for node,unused,kind in unused_import_items(export_source, export_tree, path):
        if node.lineno in suppressed: continue
        cell_path, lineno, node_src = _notebook_node_location(node, line_map)
        moved = [name for name in unused if kind == "module" and name in non_export_used]
        dead = [name for name in unused if name not in moved]
        if moved:
            msg = with_hint(f"exported-cell import only used in non-exported cells: {', '.join(moved)}", move_hint)
            violations.append((cell_path, lineno, msg, node_src))
        if dead:
            msg = with_hint(f"unused import: {', '.join(dead)}", hint)
            violations.append((cell_path, lineno, msg, node_src))

def check_notebook(path: str) -> list[tuple]:
    "Check Jupyter notebook for style violations."
    with open(path, encoding="utf-8") as f: nb = json.load(f)
    violations = []
    cells = _notebook_cells(nb, path)
    for cell in cells:
        cell_violations = check_source(cell["source"], cell["path"], check_unused=False)
        violations.extend(cell_violations)
    _check_notebook_unused_imports(cells, path, violations)
    return violations

def fix_notebook(path: str, selected: set[str]) -> bool:
    "Fix notebook code cells in place."
    with open(path, encoding="utf-8") as f: nb = json.load(f)
    changed = False
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code": continue
        source = _cell_source(cell)
        fixed, changes = fix_source(source, f"{path}:cell[{cell.get('id', 'unknown')}]", selected - {"unused-import"})
        if not changes: continue
        cell["source"] = fixed if isinstance(cell.get("source", []), str) else fixed.splitlines(True)
        changed = True
    if not changed: return False
    with open(path, "w", encoding="utf-8") as f: json.dump(nb, f, ensure_ascii=False, indent=1)
    with open(path, "a", encoding="utf-8") as f: f.write("\n")
    return True

def check_path(path: str) -> list[tuple]:
    "Check a single file (py or ipynb) for style violations."
    if path.endswith(".ipynb"): return check_notebook(path)
    return check_file(path)

def fix_path(path: str, selected: set[str]) -> bool:
    "Fix a single file."
    if path.endswith(".ipynb"): return fix_notebook(path, selected)
    return fix_file(path, selected)

def _find_cfg_root(path: str) -> str | None:
    "Find nearest ancestor with pyproject.toml."
    cur = os.path.abspath(path)
    if os.path.isfile(cur): cur = os.path.dirname(cur)
    while True:
        if os.path.exists(os.path.join(cur, "pyproject.toml")): return cur
        parent = os.path.dirname(cur)
        if parent == cur: return None
        cur = parent

def _cfg_root(paths: list[str]) -> str:
    "Choose config root."
    if len(paths) != 1: return "."
    return _find_cfg_root(paths[0]) or (paths[0] if os.path.isdir(paths[0]) else ".")

def _cfg_skip_paths(cfg: dict) -> list[str]:
    "Load skip paths from config."
    return cfg.get("skip_paths") or cfg.get("skip-paths") or []

def _cfg_skip_path_re(cfg: dict) -> str | None:
    "Load skip path regex from config."
    return cfg.get("skip-path-re")

def _as_list(value) -> list[str]:
    "Normalize config/CLI list values."
    if value is None or value is False: return []
    if value is True: return [ALL_RULES]
    if isinstance(value, str): return [part.strip() for part in value.split(",") if part.strip()]
    res = []
    for item in value:
        if item is None: continue
        res += _as_list(item)
    return res

def _rule_set(*values) -> set[str]:
    "Normalize rule list values."
    return {item for value in values for item in _as_list(value)}

def _fix_rule_set(enabled: bool, cli_rules, cfg: dict) -> set[str]:
    "Rules selected for fixing."
    if not enabled: return set()
    rules = _rule_set(cli_rules)
    if not rules: rules = _rule_set(cfg.get("fix"))
    if not rules: rules = {ALL_RULES}
    return SUPPORTED_FIX_RULES if ALL_RULES in rules else rules & SUPPORTED_FIX_RULES

def main(argv: list[str]) -> int:
    "Main."
    import argparse
    parser = argparse.ArgumentParser(description="Check Python files for style violations")
    parser.add_argument("paths", nargs="*", default=["."], help="Files and/or directories to check")
    parser.add_argument("--skip-path", action="append", default=None, help="Path to skip (repeatable)")
    parser.add_argument("--skip-path-re", help="Regex to skip normalized paths (uses Python re.match)")
    parser.add_argument("--ignore", action="append", default=None, help="Rule id to ignore (repeatable or comma-separated)")
    parser.add_argument("--fix", action="store_true", help="Fix files in place before checking")
    parser.add_argument("--fix-rule", action="append", default=None, help="Rule id to fix (repeatable or comma-separated)")
    args = parser.parse_args(argv[1:])
    cfg = load_config(_cfg_root(args.paths))
    if cfg.get("disabled"): return 0
    skip_pattern = args.skip_path_re or _cfg_skip_path_re(cfg)
    skip_path_re = re.compile(skip_pattern) if skip_pattern else None
    skip_paths = args.skip_path if args.skip_path is not None else _cfg_skip_paths(cfg)
    ignored = _rule_set(cfg.get("ignore"), args.ignore)
    fix_rules = _fix_rule_set(args.fix, args.fix_rule, cfg)
    all_violations = []
    seen = set()
    for root in args.paths:
        if os.path.isfile(root):
            if root in seen: continue
            if fix_rules: fix_path(root, fix_rules)
            all_violations.extend(check_path(root))
            seen.add(root)
            continue
        for path in iter_py_files(root, skip_path_re, skip_paths):
            if path in seen: continue
            if fix_rules: fix_path(path, fix_rules)
            all_violations.extend(check_path(path))
            seen.add(path)
    all_violations = filter_violations(all_violations, ignored)
    for path, lineno, msg, lines in sorted(all_violations, key=lambda item: (item[0], item[1], item[2])):
        print(f"# {path}:{lineno}: {msg}")
        for line in lines: print(line)
    print(f"found {len(all_violations)} potential violation(s)")
    if all_violations:
        print("Style guidance: fix violations in the spirit of the fast.ai style guide.")
        print("Aim for code that is elegant, readable, and concise, not merely checker-compliant.")
        print("Never apply a change that satisfies chkstyle but makes the code less clear.")
    return 1 if all_violations else 0

def cli(): raise SystemExit(main(sys.argv))

if __name__ == "__main__": cli()
