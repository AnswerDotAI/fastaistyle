#!/usr/bin/env python
__version__ = "0.0.5"

import ast, io, math, os, re, sys, tokenize

SKIP_DIRS = {".git", ".hg", ".svn", "__pycache__", ".mypy_cache", ".pytest_cache", ".venv", "venv", "dist", "build"}
WRAP_WIDTH = 120
COMPOUND_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.FunctionDef,
    ast.AsyncFunctionDef, ast.ClassDef)

def iter_py_files(root: str):
    "Iter py files."
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if not name.endswith(".py"): continue
            path = os.path.join(dirpath, name)
            if os.path.islink(path): continue
            yield path

def is_identifier_str(node) -> bool:
    "Identifier str."
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.isidentifier()

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

def is_inefficient_multiline(seg_lines: list[str], indent: int) -> bool:
    "Inefficient multiline."
    if len(seg_lines) <= 1: return False
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

def check_single_line_docstring(source: str, lines: list[str], stmt, path: str, violations: list[tuple], suppressed: set[int]):
    "Check single-line docstring."
    doc = stmt.value.value
    if "\n" in doc: return
    seg = ast.get_source_segment(source, stmt) or ""
    if re.match(r'^[ \t]*[rRuUbBfF]*\"\"\"', seg):
        add_violation(violations, path, stmt.lineno, "single-line docstring uses triple quotes",
            node_lines(source, lines, stmt), suppressed)

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
    total_len = suite_len(lines, header_lineno, stmt.lineno)
    if total_len is not None and total_len > 130: return
    header_line = lines[header_lineno - 1].rstrip("\n")
    body_line = lines[stmt.lineno - 1].rstrip("\n")
    add_violation(violations, path, header_lineno, f"{parent_kind} single-statement body not one-liner",
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
    if isinstance(node, ast.ClassDef) and any(line.lstrip().startswith("@") for line in seg_lines[1:]): return
    indent = first_line_indent(lines, start)
    if not is_inefficient_multiline(seg_lines, indent): return
    add_violation(violations, path, start, "inefficient multiline signature/header", seg_lines, suppressed)

def check_multiline_expr(node, source: str, lines: list[str], path: str, violations: list[tuple], suppressed: set[int]):
    "Check multiline expression layout."
    if not node: return
    if getattr(node, "end_lineno", node.lineno) <= node.lineno: return
    if isinstance(node, ast.Constant) and isinstance(node.value, str): return
    if isinstance(node, ast.JoinedStr): return
    seg_lines = segment_lines(source, node)
    if not seg_lines or len(seg_lines) <= 1: return
    indent = first_line_indent(lines, node.lineno)
    if not is_inefficient_multiline(seg_lines, indent): return
    add_violation(violations, path, node.lineno, "inefficient multiline expression", seg_lines, suppressed)

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

def dataclass_annassigns(tree) -> set:
    "Dataclass annassigns."
    annassigns = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef): continue
        if not any(is_dataclass_decorator(dec) for dec in node.decorator_list): continue
        for stmt in node.body:
            if isinstance(stmt, ast.AnnAssign): annassigns.add(stmt)
    return annassigns

def check_annotation(node, source: str, lines: list[str], path: str, violations: list[tuple], suppressed: set[int]):
    "Check annotation depth and layout."
    if node is None: return
    if getattr(node, "end_lineno", node.lineno) > node.lineno:
        seg_lines = segment_lines(source, node)
        indent = first_line_indent(lines, node.lineno)
        if is_inefficient_multiline(seg_lines, indent):
            add_violation(violations, path, node.lineno, "inefficient multiline annotation", seg_lines, suppressed)
    depth = max_subscript_depth(node)
    if depth >= 2:
        add_violation(violations, path, getattr(node, "lineno", 1), f"nested generics depth {depth}",
            node_lines(source, lines, node), suppressed)

def should_skip_file(lines: list[str]) -> bool:
    "Skip file."
    head = lines[:5]
    return any("chkstyle: skip" in line for line in head)

def suppressed_lines(lines: list[str]) -> set[int]:
    "Suppressed lines."
    suppressed = set()
    off = False
    ignore_next = False
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if "chkstyle: on" in line:
            off = False
            ignore_next = False
            continue
        if "chkstyle: off" in line:
            off = True
            ignore_next = False
            suppressed.add(lineno)
            continue
        if off: suppressed.add(lineno)
        if "chkstyle: ignore" in line:
            if stripped.startswith("#"): ignore_next = True
            else: suppressed.add(lineno)
        elif ignore_next and stripped and not stripped.startswith("#"):
            suppressed.add(lineno)
            ignore_next = False
    return suppressed

def check_file(path: str) -> list[tuple]:
    "Check file."
    with open(path, encoding="utf-8") as f: source = f.read()
    lines = source.splitlines()
    if should_skip_file(lines): return []
    try: tree = ast.parse(source, filename=path)
    except SyntaxError as e: return [(path, e.lineno or 1, f"syntax error: {e.msg}", [])]
    violations = []
    suppressed = suppressed_lines(lines)
    for lineno, line in enumerate(lines, start=1):
        if len(line) > 150: add_violation(violations, path, lineno, "line >150 chars", [line], suppressed)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.OP and tok.string == ";":
                lineno = tok.start[0]
                add_violation(violations, path, lineno, "semicolon statement separator", [lines[lineno - 1]], suppressed)
    except tokenize.TokenError: pass
    if tree.body and is_docstring_stmt(tree.body[0]):
        check_single_line_docstring(source, lines, tree.body[0], path, violations, suppressed)
    dataclass_fields = dataclass_annassigns(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict) and len(node.keys) >= 3 and all(is_identifier_str(k) for k in node.keys):
            add_violation(violations, path, node.lineno, "dict literal with 3+ identifier keys",
                node_lines(source, lines, node), suppressed)
        if isinstance(node, ast.AnnAssign):
            if node not in dataclass_fields:
                add_violation(violations, path, node.lineno, "lhs assignment annotation", node_lines(source, lines, node), suppressed)
            check_multiline_expr(node.value, source, lines, path, violations, suppressed)
            check_annotation(node.annotation, source, lines, path, violations, suppressed)
        if isinstance(node, ast.ImportFrom):
            seg = ast.get_source_segment(source, node) or ""
            if "\n" in seg:
                import_lines = node_lines(source, lines, node)
                total_len = sum(len(line.strip()) for line in import_lines)
                if total_len <= 150:
                    add_violation(violations, path, node.lineno, "multi-line from-import", import_lines, suppressed)
        has_doc = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body
        if has_doc and is_docstring_stmt(node.body[0]):
            check_single_line_docstring(source, lines, node.body[0], path, violations, suppressed)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_multiline_sig(node, lines, path, violations, suppressed)
            if node.returns: check_annotation(node.returns, source, lines, path, violations, suppressed)
            for arg in node.args.args + node.args.kwonlyargs:
                if arg.annotation: check_annotation(arg.annotation, source, lines, path, violations, suppressed)
            if node.args.vararg and node.args.vararg.annotation:
                check_annotation(node.args.vararg.annotation, source, lines, path, violations, suppressed)
            if node.args.kwarg and node.args.kwarg.annotation:
                check_annotation(node.args.kwarg.annotation, source, lines, path, violations, suppressed)
            if node.args.posonlyargs:
                for arg in node.args.posonlyargs:
                    if arg.annotation: check_annotation(arg.annotation, source, lines, path, violations, suppressed)
        if isinstance(node, ast.ClassDef): check_multiline_sig(node, lines, path, violations, suppressed)
        if isinstance(node, ast.Assign): check_multiline_expr(node.value, source, lines, path, violations, suppressed)
        if isinstance(node, ast.AugAssign): check_multiline_expr(node.value, source, lines, path, violations, suppressed)
        if isinstance(node, ast.Return): check_multiline_expr(node.value, source, lines, path, violations, suppressed)
        if isinstance(node, ast.Expr) and not is_docstring_stmt(node):
            check_multiline_expr(node.value, source, lines, path, violations, suppressed)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_suite("def", node, node.body, path, source, lines, violations, suppressed)
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

def main(argv: list[str]) -> int:
    "Main."
    root = argv[1] if len(argv) > 1 else "."
    all_violations = []
    for path in iter_py_files(root): all_violations.extend(check_file(path))
    for path, lineno, msg, lines in sorted(all_violations,
        key=lambda item: (item[0], item[1], item[2])):
        print(f"# {path}:{lineno}: {msg}")
        for line in lines: print(line)
    print(f"found {len(all_violations)} potential violation(s)")
    return 1 if all_violations else 0

def cli(): raise SystemExit(main(sys.argv))

if __name__ == "__main__": cli()
