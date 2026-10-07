# chkstyle: skip
import ast, json, textwrap

import chkstyle
import pytest


def _source(src): return textwrap.dedent(src).lstrip()
def _rules(issues): return {v[2] for v in issues}
def _check(src): return chkstyle.check_source(_source(src), "t.py")

def _write(root, name, src):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_source(src), encoding="utf-8")
    return path

def _notebook(root, cells, name="t.ipynb"):
    cells = [{"cell_type": "code", "id": f"cell{i}", "metadata": {},
              **(dict(source=_source(c)) if isinstance(c, str) else c)} for i, c in enumerate(cells)]
    return _write(root, name, json.dumps(dict(cells=cells, metadata={}, nbformat=4, nbformat_minor=5)))

def _check_nb(root, cells, name="t.ipynb"): return chkstyle.check_notebook(str(_notebook(root, cells, name)))

def _fix(src, rules=("all",)):
    fixed, _ = chkstyle.fix_source(_source(src), "t.py", set(rules))
    ast.parse(fixed)
    assert chkstyle.fix_source(fixed, "t.py", set(rules))[0] == fixed
    return fixed

def _run(src):
    ns = {}
    exec(src, ns)
    return ns

def test_source_rewrite_preserves_results_and_reaches_a_stable_clean_source():
    src = _source('''
        import math
        import json
        import os
        from math import (
            ceil,
        )

        def summarize(xs: list[list[int]]):
            """Calculate the summary."""
            bonus: int = 1
            cfg = {"scale": 2, "offset": bonus, "label": "→ next"}
            singleton = (
                sum(xs),
            )
            weights = [
                    2,
            ]
            a = math.floor(singleton[0]); b = ceil(weights[0])
            if xs:
                a += cfg["offset"]
            return json.loads(json.dumps(dict(
                value=a * b * cfg["scale"],
                label=cfg["label"])))
        ''')
    expected = {"consecutive-short-imports", "unused-import", "multi-line-from-import", "single-line-docstring",
        "lhs-assignment-annotation", "dict-literal", "closing-bracket", "continuation-indent", "semicolon",
        "single-statement-body", "nested-generics", "inefficient-multiline-expression"}
    assert expected <= _rules(_check(src))
    fixed = _fix(src)
    assert _check(fixed) == []
    before, after = _run(src), _run(fixed)
    for xs in ([], [1, 2, 3]): assert before["summarize"](xs) == after["summarize"](xs)
    assert "def summarize(xs: list[list]):" in fixed and "→ next" in fixed


def test_source_rewrite_protects_field_contracts_comments_and_literal_contents():
    src = _source('''
        from dataclasses import dataclass

        @dataclass
        class Item:
            value: int; kind: str = "constant"

        unbound: int
        col = "id"
        def keep(text): return text
        text = keep(f"""
            SELECT {col}
                    FROM t""")
        def choose(
            value: int,  # The value to preserve
        ):
            return value
        if col:  # Keep this explanation with the branch
            answer = choose(1)
        costs = dict(
            cpu=1,  # per minute
        )
        invalid_kwargs = {"class": 1, "b": 2, "c": 3}
        duplicate_keys = {"a": 1, "a": 2, "b": 3}
        ''')
    assert _rules(_check(src)) == {"lhs-assignment-annotation", "closing-bracket"}
    fixed = _fix(src)
    assert fixed == src
    ns = _run(fixed)
    assert ns["Item"](3).kind == "constant" and ns["answer"] == 1
    assert ns["text"] == "\n    SELECT id\n            FROM t"


def test_width_decisions_distinguish_code_from_literal_and_comment_tokens():
    for width in (80, 81):
        src = f"if {'x' * width}:\n    return_value = {'y' * 40}\n"
        assert ("single-statement-body" in _rules(_check(src))) == (width == 80)
        fixed = _fix(src, ["single-statement-body"])
        assert fixed == (src.replace(":\n    ", ": ") if width == 80 else src)
    src = f"a = '{'x' * 180}'\nb = f'prefix {{x}} {'y' * 180}'\nc = 1 # {'z' * 220}\n{'v' * 161} = 'x' # comment\n"
    assert [(v[2], v[1]) for v in _check(src)] == [("line-too-long", 4)]
    wide = _source('''
        result = send({
            'client_id': client['client_id'], 'redirect_uri': redirect_uri, 'response_type': 'code',
            'scope': ' '.join(scopes), 'access_type': 'offline', 'prompt': 'consent',
            'include_granted_scopes': 'true', 'code_challenge': challenge,
            'code_challenge_method': 'S256', 'state': state})
        ''')
    fixed = _fix(wide)
    assert "dict(client_id=client['client_id']" in fixed and _check(fixed) == []
    assert all(len(line) <= 140 for line in fixed.splitlines())
    unsplittable = f"cfg = {{'alpha': 'a' * 200, 'beta': '{'x' * 130}', 'gamma': 3}}\n"
    assert _fix(unsplittable, ["dict-literal"]) == unsplittable


def test_pragmas_and_generated_headers_protect_sources_from_checking_and_fixing(tmp_path):
    src = _source('''
        x: int = 1  # chkstyle: ignore
        # chkstyle: ignore
        y: int = 2
        # chkstyle: off
        z: int = 3
        # chkstyle: on
        registry = {  # chkstyle: ignore-node
            'a/b': lambda x: x,
            'c/d': lambda x: x * 2,
        }
        text = "chkstyle: off"
        answer: int = 4
        ''')
    assert [(v[2], v[1]) for v in _check(src)] == [("lhs-assignment-annotation", 12)]
    fixed = _fix(src)
    assert fixed == src.replace("answer: int", "answer")
    assert _check(fixed) == []
    generated = '"""' + "Module documentation. " * 15 + '"""\n# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/core.ipynb.\nimport os\n'
    for name, content in (("generated.py", generated), ("skipped.py", "# chkstyle: skip\nnot valid Python!\n")):
        path = _write(tmp_path, name, content)
        assert chkstyle.check_file(str(path)) == []
        assert not chkstyle.fix_file(str(path), {"all"})
        assert path.read_text() == content


def test_import_analysis_resolves_closures_annotations_exports_and_comprehension_shadowing():
    src = _source('''
        import os, sys, math, pathlib
        from collections import Counter
        __all__ = ["Counter"]
        def outer():
            def inner(): return os.getcwd()
            return inner()
        f = lambda: sys.version_info
        xs = [math for math in range(3)]
        def typed(value: pathlib.Path) -> pathlib.Path: return value
        ''')
    assert [v[3].split(" (hint:")[0] for v in _check(src) if v[2] == "unused-import"] == ["unused import: math"]
    fixed = _fix(src, ["unused-import"])
    assert "import os, sys, pathlib\n" in fixed and "unused-import" not in _rules(_check(fixed))
    assert _run(src)["xs"] == _run(fixed)["xs"] == [0, 1, 2]
    assert chkstyle.check_source("from .mod import foo\n", "pkg/__init__.py") == []


def test_source_segment_matches_the_stdlib_for_multiline_and_utf8_nodes():
    src = 'x = {"a": 1,\n     "é": [2, 3]}\ny = "ü"; z = f(1,\n  2)\n'
    for node in ast.walk(ast.parse(src)):
        if hasattr(node, "lineno"): assert chkstyle.get_source_segment(src, node) == ast.get_source_segment(src, node)


def test_notebook_fix_preserves_ipython_commands_literal_text_and_diagnostic_locations(tmp_path):
    sources = ["v = %apl ⍳3\nx: int = 2", "files = !ls\ny: int = 3", "len??\nz: int = 4",
        "if ready:\n    v = %apl ⍳3\nx: int = 5", 'text = """literal\n%apl ⍳3\n"""\nx: int = 6',
        "!codex exec --json \\\n    -c key=val \\\n    'p' > out.jsonl\nz: int = 7", "%%bash\nls | wc -l", "# chkstyle: skip\nnot valid Python!\n",
        "a = 1; b = 2"]
    path = _notebook(tmp_path, [dict(source=s.splitlines(True)) if i == 1 else s for i, s in enumerate(sources)])
    issues = chkstyle.check_notebook(str(path))
    assert "syntax-error" not in _rules(issues)
    assert [(v[0].split(":cell")[1], v[1]) for v in issues if v[2] == "lhs-assignment-annotation"] == [
        ("[cell0]", 2), ("[cell1]", 2), ("[cell2]", 2), ("[cell3]", 3), ("[cell4]", 4), ("[cell5]", 4)]
    assert chkstyle.fix_notebook(str(path), {"lhs-assignment-annotation", "single-statement-body", "semicolon"})
    cells = json.loads(path.read_text())["cells"]
    assert ["".join(c["source"]) for c in cells] == [s.replace(": int", "") for s in sources[:-1]] + ["a = 1\nb = 2"]
    assert isinstance(cells[1]["source"], list)
    assert chkstyle.check_notebook(str(path)) == []
    before = path.read_text()
    assert not chkstyle.fix_notebook(str(path), {"all"}) and path.read_text() == before


def test_notebook_imports_are_analyzed_as_an_exported_module_not_as_isolated_cells(tmp_path):
    path = _notebook(tmp_path, ["#| export\nimport os, sys, math\n", "import json\n", "print(sys.version_info)\n",
        dict(source="print(os.getcwd())\n", metadata={"nbdev": {"export": "true"}}),
        "import pathlib\nprint(pathlib.Path('.'))\n", "#| exec_doc\nimport typing\nprint(typing.Any)\n",
        "#| export\n# chkstyle: skip\nprint(math.pi)\n",
        "import nbdev; nbdev.nbdev_export()\n"])
    issues = chkstyle.check_notebook(str(path))
    assert [(v[2], v[0].split(":cell")[1], v[1]) for v in issues] == [
        ("exported-import-nonexport", "[cell0]", 2), ("mixed-imports", "[cell4]", 1)]
    assert "sys" in issues[0][3] and "cell1" in issues[0][3]
    nb = json.loads(path.read_text())
    nb["cells"][2]["metadata"] = {"nbdev": {"export": "true"}}
    nb["cells"][4]["source"] = "import pathlib  # chkstyle: ignore\nprint(pathlib.Path('.'))\n"
    path.write_text(json.dumps(nb))
    assert chkstyle.check_notebook(str(path)) == []
    nb["cells"][0]["source"] += "import collections\n"
    path.write_text(json.dumps(nb))
    assert _rules(chkstyle.check_notebook(str(path))) == {"unused-import"}


@pytest.mark.xfail(raises=AssertionError, strict=True, reason="A skipped unparsable cell poisons valid-cell import analysis.")
def test_skipped_invalid_cell_preserves_import_usage_in_valid_notebook_cells(tmp_path):
    cells = ["#| export\nimport sys\n", "print(sys.version_info)\n"]
    expected = _check_nb(tmp_path, cells)
    assert _rules(expected) == {"exported-import-nonexport"}
    assert _check_nb(tmp_path, [*cells, "# chkstyle: skip\nnot valid Python!\n"]) == expected


def test_notebook_narrative_tracks_lessons_in_document_order_not_cell_layout(tmp_path):
    intro = ["#| default_exp core\n", dict(cell_type="markdown", source="Introduction")]
    exported = "#| export\n" + "".join(f"x{i} = {i}\n" for i in range(24))
    extra = "#| export\ny = 1\n"
    lesson = [dict(cell_type="markdown", source="Use the helper."), "helper()\n"]
    rule = "long-implementation-run"
    cells = [*intro, exported, dict(cell_type="markdown", source="Prose alone"), extra,
        exported, *lesson, exported, extra]
    issues = _check_nb(tmp_path, cells)
    runs = [v for v in issues if v[2] == rule]
    assert [(v[0].split(":cell")[1], v[1]) for v in runs] == [("[cell4]", 2), ("[cell9]", 2)]
    for gap in (["helper()\n"], [lesson[0], "import math\n"], [lesson[0], extra, lesson[1]]):
        assert rule in _rules(_check_nb(tmp_path, [*intro, exported, *gap, extra]))
    setup = ["#| export\nimport math\n", "#| export\n", "#| hide\nhelper()\n", "# chkstyle: skip\nhelper()\n"]
    assert rule not in _rules(_check_nb(tmp_path, [*intro, exported, lesson[0], *setup, lesson[1], exported]))


def test_notebook_narrative_scores_structure_and_exempts_docs_and_non_narrative_notebooks(tmp_path):
    intro, rule = ["#| default_exp core\n"], "long-implementation-run"
    for helper in ("def f(): return 1\n", "async def f(): return await g()\n", "def f():\n    'Docs.'\n    import math\n    return math.pi\n"):
        for cells in (["#| export\n" + helper * 24], [dict(source=helper, metadata={"nbdev": {"export": "true"}})] * 24):
            assert rule not in _rules(_check_nb(tmp_path, intro + cells))
            assert rule in _rules(_check_nb(tmp_path, intro + cells + ["#| export\nx = 1"]))
    setup = "#| export\n" + "x = 1\n" * 23
    for body in ("if x: return 1", "if x:\n        return 1", "def g(): return 1"):
        assert rule in _rules(_check_nb(tmp_path, [*intro, setup, "#| export\ndef f():\n    " + body]))
    cells = [*intro, "#| export\ndef a(): pass\ndef b(): pass\ndef c(): pass\ndef d(): pass\n",
        "#| export\n" + "x = 1\n" * 51, dict(cell_type="markdown", source="Examples"),
        "y = 1\n" * 11, "y # explain\n", "y\n", "y + 1\n"]
    assert _rules(_check_nb(tmp_path, cells)) == {
        "too-many-defs", "long-exported-cell", "long-implementation-run", "long-example-cell", "comment-in-example", "example-run"}
    logical = [*intro, '#| export\ndef f():\n    """' + "Documentation.\n" * 60 + '"""\n    return 1\n',
        dict(cell_type="markdown", source="A literal is one unit"), 'ask("""' + "line\n" * 15 + '""")\n']
    assert _check_nb(tmp_path, logical) == []
    assert _check_nb(tmp_path, ["y # explain\n"]) == []
    assert _rules(_check_nb(tmp_path, ["y # explain\n"], "index.ipynb")) == {"comment-in-example"}


def test_cli_combines_user_project_config_traverses_sources_and_overrides_fix_selection(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    _write(tmp_path, "xdg/chkstyle/config.toml", 'skip_paths = ["_proc"]\nignore = ["lhs-assignment-annotation"]\n')
    root = tmp_path / "proj"
    _write(root, "pyproject.toml", '''
        [tool.chkstyle]
        skip_paths = ["gen"]
        skip-path-re = "_modidx.py"
        ignore = ["semicolon"]
        fix = ["dict-literal"]
        ''')
    src = 'x: int = 1\ndata = {"a": 1, "b": 2, "c": 3}\na = 1; b = 2\n'
    files = {name: _write(root, name, src) for name in ("_proc/t.py", "gen/t.py", "pkg/_modidx.py", "pkg/a.py")}
    nb_path = _notebook(root, [src], "pkg/t.ipynb")
    monkeypatch.chdir(tmp_path)
    assert chkstyle.main(["chkstyle", "--fix", "proj/pkg"]) == 0
    assert chkstyle.main(["chkstyle", "--fix", "proj"]) == 0
    assert files["pkg/a.py"].read_text() == src.replace('{"a": 1, "b": 2, "c": 3}', "dict(a=1, b=2, c=3)")
    assert "data = dict(" in json.loads(nb_path.read_text())["cells"][0]["source"]
    for name in ("_proc/t.py", "gen/t.py", "pkg/_modidx.py"): assert files[name].read_text() == src
    capsys.readouterr()
    assert chkstyle.main(["chkstyle", "--fix", "--fix-rule", "lhs-assignment-annotation", "--skip-path", "_proc",
        "--skip-path-re", "^never$", "proj"]) == 1
    for name in ("gen/t.py", "pkg/_modidx.py"): assert files[name].read_text() == src.replace("x: int", "x")
    assert files["_proc/t.py"].read_text() == src
    out = capsys.readouterr().out
    assert "gen/t.py" in out and "pkg/_modidx.py" in out and "_proc/t.py" not in out
    assert "lhs-assignment-annotation" not in _rules(chkstyle.check_notebook(str(nb_path)))
