# chkstyle: skip
import json, textwrap

import chkstyle

def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return path

def _write_nb(tmp_path, name, cells):
    nb = {
        "cells": [{"cell_type": "code", "id": f"cell{i}", "source": src} for i, src in enumerate(cells)],
        "metadata": {}, "nbformat": 4, "nbformat_minor": 5,
    }
    path = tmp_path / name
    path.write_text(json.dumps(nb), encoding="utf-8")
    return path

def _check_py(tmp_path, content): return chkstyle.check_file(str(_write(tmp_path, "t.py", content)))
def _check_nb(tmp_path, cells): return chkstyle.check_notebook(str(_write_nb(tmp_path, "t.ipynb", cells)))
def _msgs(violations): return {msg for _p, _l, msg, _lines in violations}
def _has_msg(msgs, prefix): return any(msg.startswith(prefix) for msg in msgs)

def test_chkstyle_reports_expected_violations(tmp_path):
    msgs = _msgs(_check_py(tmp_path, '''
        def f():
            """doc"""
            return 1

        x: int = 1
        data = {"a": 1, "b": 2, "c": 3}
        a = 1; b = 2
        from os import (
            path,
            environ,
        )
        if True:
            y = 1
        z = dict(
            a=1,
            b=2,
        )
        long_variable_name_to_trigger_line_length_limit_because_line_is_super_long_and_should_fail_even_without_long_string_literal_or_repeated_dots_in_tests = long_variable_name_to_trigger_line_length_limit_because_line_is_super_long_and_should_fail_even_without_long_string_literal_or_repeated_dots_in_tests
        def g(x: list[list[int]]): return x
        '''))
    expected = {"single-line docstring uses triple quotes", "lhs assignment annotation",
        "dict literal with 3+ identifier keys", "semicolon statement separator", "multi-line from-import",
        "if single-statement body not one-liner", "inefficient multiline expression", "line >160 chars",
        "nested generics depth 2"}
    assert all(_has_msg(msgs, msg) for msg in expected), msgs

def test_chkstyle_ignore_and_off_on(tmp_path):
    assert _check_py(tmp_path, """
        x: int = 1  # chkstyle: ignore
        # chkstyle: ignore
        y: int = 2
        # chkstyle: off
        z: int = 3
        # chkstyle: on
        """) == []

def test_chkstyle_skip_file(tmp_path):
    assert _check_py(tmp_path, """
        # chkstyle: skip
        x: int = 1
        data = {"a": 1, "b": 2, "c": 3}
        """) == []

def test_chkstyle_allows_multiline_strings(tmp_path):
    assert _check_py(tmp_path, '''
        value = """
        line one
        line two
        """
        ''') == []

def test_chkstyle_long_line_with_short_string_still_fails(tmp_path):
    msgs = _msgs(_check_py(tmp_path, """
        some_really_long_variable_name_that_keeps_going_and_going_and_going = some_really_long_func_name_that_keeps_going_and_going_and_going(another_really_long_variable_name_that_keeps_going_and_going_and_going, "x")
        """))
    assert _has_msg(msgs, "line >160 chars"), msgs

def test_chkstyle_long_line_mostly_string_is_exempt(tmp_path):
    assert _check_py(tmp_path, f'msg = "{"x" * 180}"\n') == []

def test_chkstyle_allows_decorated_inner_defs(tmp_path):
    assert _check_py(tmp_path, """
        def dec(f): return f

        def outer():
            @dec
            def inner(): return 1
        """) == []

def test_chkstyle_allows_multiline_string_calls(tmp_path):
    assert _check_py(tmp_path, '''
        def f():
            return _lines("""
            one
            two
            """)
        ''') == []

def test_chkstyle_allows_trailing_comments(tmp_path):
    assert _check_py(tmp_path, """
        def ship_new(
            name: str,              # Project name
            package: str = None,    # Package name
            force: bool = False,    # Overwrite existing
        ):
            return name

        __all__ = [
            "one",   # first
            "two"]   # second
        """) == []

def test_chkstyle_if_else_single_statement(tmp_path):
    assert _has_msg(_msgs(_check_py(tmp_path, """
        if branch == expected:
            print(f"ok")
        else:
            print(f"not ok")
        """)), "if single-statement body not one-liner")

def test_chkstyle_main_accepts_file_path(tmp_path):
    assert chkstyle.main(["chkstyle", str(_write(tmp_path, "t.py", "x: int = 1\n"))]) == 1

def test_chkstyle_main_shows_style_guidance_on_violations(tmp_path, capsys):
    chkstyle.main(["chkstyle", str(_write(tmp_path, "t.py", "x: int = 1\n"))])
    out = capsys.readouterr().out
    assert "Style guidance: fix violations in the spirit of the fast.ai style guide." in out
    assert "Never apply a change that satisfies chkstyle but makes the code less clear." in out

def test_chkstyle_main_accepts_multiple_paths(tmp_path, capsys):
    p1 = _write(tmp_path, "a.py", "x: int = 1\n")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    p2 = pkg / "b.py"
    p2.write_text("y: int = 2\n", encoding="utf-8")
    assert chkstyle.main(["chkstyle", str(p1), str(pkg)]) == 1
    out = capsys.readouterr().out
    assert str(p1) in out and str(p2) in out

def test_chkstyle_config_skip_paths(tmp_path, capsys):
    keep_dir, skip_dir, gen_dir = tmp_path / "keep", tmp_path / "skipme", tmp_path / "src" / "generated"
    keep_dir.mkdir()
    skip_dir.mkdir()
    gen_dir.mkdir(parents=True)
    keep_file = keep_dir / "keep.py"
    skip_file = skip_dir / "skip.py"
    gen_file = gen_dir / "gen.py"
    keep_file.write_text("x: int = 1\n", encoding="utf-8")
    skip_file.write_text("y: int = 2\n", encoding="utf-8")
    gen_file.write_text("z: int = 3\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""
        [tool.chkstyle]
        skip_paths = ["skipme", "src/generated"]
        """), encoding="utf-8")
    assert chkstyle.main(["chkstyle", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert str(keep_file) in out and str(skip_file) not in out and str(gen_file) not in out

def test_chkstyle_allows_multiline_def_with_docments(tmp_path):
    assert _check_py(tmp_path, """
        def ws_clone_cli(
            repos_file: str = "repos.txt",  # File containing repo list
            workers: int = 16,  # Number of parallel workers
        ): ws_clone(repos_file, workers)
        """) == []

def test_chkstyle_flags_consecutive_short_imports(tmp_path):
    msgs = _msgs(_check_py(tmp_path, """
        import os
        import sys
        import pathlib
        """))
    assert _has_msg(msgs, "consecutive short imports"), msgs

def test_chkstyle_flags_closing_bracket_on_own_line(tmp_path):
    msgs = _msgs(_check_py(tmp_path, """
        result = some_really_long_function_name_for_testing_closer_layout(
            alpha_parameter_name=first_value_identifier,
            beta_parameter_name=second_value_identifier,
        )
        """))
    assert _has_msg(msgs, "closing bracket on its own line"), msgs

def test_chkstyle_flags_continuation_indent(tmp_path):
    msgs = _msgs(_check_py(tmp_path, """
        result = some_really_long_function_name_for_testing_indent_layout(
                alpha_parameter_name=first_value_identifier,
                beta_parameter_name=second_value_identifier)
        """))
    assert _has_msg(msgs, "continuation line indent"), msgs

def test_chkstyle_notebook_reports_violations(tmp_path):
    msgs = _msgs(_check_nb(tmp_path, ["x: int = 1\ndata = {'a': 1, 'b': 2, 'c': 3}\n"]))
    assert _has_msg(msgs, "lhs assignment annotation")
    assert _has_msg(msgs, "dict literal with 3+ identifier keys")

def test_chkstyle_notebook_shows_cell_id_in_path(tmp_path):
    violations = _check_nb(tmp_path, ["x: int = 1\n"])
    assert len(violations) == 1
    vpath, lineno, msg, lines = violations[0]
    assert ":cell[cell0]" in vpath and lineno == 1

def test_chkstyle_notebook_shows_line_within_cell(tmp_path):
    violations = _check_nb(tmp_path, ["# ok\n# still ok\nx: int = 1\n"])
    assert len(violations) == 1 and violations[0][1] == 3

def test_chkstyle_notebook_multiple_cells(tmp_path):
    violations = _check_nb(tmp_path, ["x = 1\n", "y: int = 2\n", "z: str = 'hi'\n"])
    assert len(violations) == 2
    paths = {v[0] for v in violations}
    assert any("cell1" in p for p in paths) and any("cell2" in p for p in paths)

def test_chkstyle_notebook_skip_pragma(tmp_path):
    assert _check_nb(tmp_path, ["# chkstyle: skip\nx: int = 1\n"]) == []

def test_chkstyle_notebook_ignore_pragma(tmp_path):
    assert _check_nb(tmp_path, ["x: int = 1  # chkstyle: ignore\n"]) == []

def test_chkstyle_check_path_dispatches_correctly(tmp_path):
    py_path, nb_path = _write(tmp_path, "t.py", "x: int = 1\n"), _write_nb(tmp_path, "t.ipynb", ["y: int = 2\n"])
    py_v, nb_v = chkstyle.check_path(str(py_path)), chkstyle.check_path(str(nb_path))
    assert len(py_v) == len(nb_v) == 1 and "cell" not in py_v[0][0] and "cell" in nb_v[0][0]

def test_chkstyle_main_accepts_notebook_path(tmp_path):
    assert chkstyle.main(["chkstyle", str(_write_nb(tmp_path, "t.ipynb", ["x: int = 1\n"]))]) == 1

def test_chkstyle_iter_py_files_includes_notebooks(tmp_path):
    _write(tmp_path, "t.py", "x = 1\n")
    _write_nb(tmp_path, "t.ipynb", ["y = 2\n"])
    files = list(chkstyle.iter_py_files(str(tmp_path)))
    assert any(f.endswith(".py") for f in files) and any(f.endswith(".ipynb") for f in files)

def test_chkstyle_if_with_multiline_else_still_flags_single_if_body(tmp_path):
    "If body should be flagged even when else body is multi-line."
    assert _has_msg(_msgs(_check_py(tmp_path, """
        import os
        def main():
            root = '.'
            if os.path.isfile(root):
                print(root)
            else:
                a = 1
                b = 2
        """)), "if single-statement body not one-liner")

def test_chkstyle_pragma_in_string_not_suppressed(tmp_path):
    "Pragma strings in code (not comments) should not trigger suppression."
    violations = _check_py(tmp_path, """
        def check_pragma(line):
            if "chkstyle: off" in line:
                return True
            return False
        x: int = 1
        """)
    assert _has_msg(_msgs(violations), "lhs assignment annotation"), f"Got: {_msgs(violations)}"

def test_chkstyle_messages_include_hints(tmp_path):
    msgs = _msgs(_check_py(tmp_path, """
        x: list[list[int]] = [
            1,
            2,
        ]
        """))
    assert any(msg.startswith("nested generics depth 2") and "hint:" in msg for msg in msgs), msgs
    assert any(msg.startswith("inefficient multiline expression") and "hint:" in msg for msg in msgs), msgs

def test_chkstyle_core_py_no_violations():
    "core.py should have no style violations."
    import pathlib
    core_path = pathlib.Path(__file__).parent.parent / "chkstyle" / "core.py"
    violations = chkstyle.check_file(str(core_path))
    assert violations == [], f"Unexpected violations in core.py: {[(l, m) for _, l, m, _ in violations]}"
