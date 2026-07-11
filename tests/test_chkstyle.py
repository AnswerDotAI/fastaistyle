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
def _msgs(violations): return {v[3] for v in violations}
def _has_msg(msgs, prefix): return any(msg.startswith(prefix) for msg in msgs)

def test_chkstyle_reports_expected_violations(tmp_path):
    msgs = _msgs(_check_py(tmp_path, '''
        def f():
            """doc"""
            return 1

        import pathlib
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
        "if single-statement body not one-liner", "inefficient multiline expression", "line >160 chars", "unused import: pathlib",
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

def test_chkstyle_dict_literal_skips_invalid_kwargs(tmp_path):
    assert not _has_msg(_msgs(_check_py(tmp_path, """
        a = {"class": 1, "b": 2, "c": 3}
        b = {"a": 1, "a": 2, "b": 3}
        """)), "dict literal with 3+ identifier keys")

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

def test_chkstyle_long_fstring_line_is_exempt(tmp_path):
    assert _check_py(tmp_path, f'msg = f"prefix {{x}} {"y" * 180}"\n') == []

def test_chkstyle_long_comments_are_exempt(tmp_path):
    long_comment = "# " + "x" * 220
    trailing_comment = "x = 1  # " + "y" * 220
    assert not _has_msg(_msgs(_check_py(tmp_path, f"{long_comment}\n{trailing_comment}\n")), "line >160 chars")

def test_chkstyle_long_code_before_comment_still_fails(tmp_path):
    code = "some_really_long_variable_name_that_keeps_going_and_going_and_going = some_really_long_func_name_that_keeps_going_and_going_and_going(another_really_long_variable_name_that_keeps_going_and_going_and_going)"
    msgs = _msgs(_check_py(tmp_path, f"{code}  # comment\n"))
    assert _has_msg(msgs, "line >160 chars"), msgs

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

def test_chkstyle_allows_standalone_comments_in_multiline_expr(tmp_path):
    assert not _has_msg(_msgs(_check_py(tmp_path, """
        result = call(
            # explain
            a,
            b)
        """)), "inefficient multiline expression")

def test_chkstyle_if_else_single_statement(tmp_path):
    assert _has_msg(_msgs(_check_py(tmp_path, """
        if branch == expected:
            print(f"ok")
        else:
            print(f"not ok")
        """)), "if single-statement body not one-liner")

def test_chkstyle_single_statement_body_allows_comments(tmp_path):
    assert not _has_msg(_msgs(_check_py(tmp_path, """
        if ready:  # explain
            return True

        if waiting:
            # explain
            return False

        if done:
            return None  # explain
        """)), "single-statement body not one-liner")

def test_chkstyle_single_statement_body_allows_long_combined_line(tmp_path):
    assert not _has_msg(_msgs(_check_py(tmp_path, """
        if ready:
            return some_really_long_function_name_that_would_make_the_combined_line_too_long(alpha, beta, gamma, delta, epsilon, zeta, eta, theta, iota, kappa, lambda_arg, mu)
        """)), "if single-statement body not one-liner")

def test_chkstyle_single_statement_body_combined_over_140_not_flagged(tmp_path):
    assert not _has_msg(_msgs(_check_py(tmp_path, f"""
        if {"x" * 93}:
            return_value = {"y" * 40}
        """)), "if single-statement body not one-liner")

def test_chkstyle_single_statement_body_combined_at_most_140_flagged(tmp_path):
    assert _has_msg(_msgs(_check_py(tmp_path, f"""
        if {"x" * 80}:
            return_value = {"y" * 40}
        """)), "if single-statement body not one-liner")

def test_chkstyle_fix_single_statement_body_never_exceeds_140(tmp_path):
    p = _write(tmp_path, "t.py", f"""
        if {"x" * 93}:
            return_value = {"y" * 40}
        """)
    chkstyle.main(["chkstyle", "--fix", "--fix-rule", "single-statement-body", str(p)])
    assert all(len(line) <= 140 for line in p.read_text(encoding="utf-8").splitlines())

def test_chkstyle_violations_include_rule_id(tmp_path):
    violations = _check_py(tmp_path, "x: int = 1\n")
    assert violations[0][2] == "lhs-assignment-annotation"

def test_chkstyle_ignore_single_statement_body_by_rule_id(tmp_path):
    p = _write(tmp_path, "t.py", "if True:\n    y = 1\n")
    assert chkstyle.main(["chkstyle", "--ignore", "single-statement-body", str(p)]) == 0

def test_chkstyle_main_accepts_file_path(tmp_path):
    assert chkstyle.main(["chkstyle", str(_write(tmp_path, "t.py", "x: int = 1\n"))]) == 1

def test_chkstyle_main_shows_style_guidance_on_violations(tmp_path, capsys):
    chkstyle.main(["chkstyle", str(_write(tmp_path, "t.py", "x: int = 1\n"))])
    out = capsys.readouterr().out
    assert "Style guidance: fix violations in the spirit of the fast.ai style guide." in out
    assert "Never apply a change that satisfies chkstyle but makes the code less clear." in out

def test_chkstyle_main_show_rule_flag(tmp_path, capsys):
    p = _write(tmp_path, "t.py", "x: int = 1\n")
    chkstyle.main(["chkstyle", str(p)])
    assert "[lhs-assignment-annotation]" not in capsys.readouterr().out
    chkstyle.main(["chkstyle", "--show-rule", str(p)])
    assert "[lhs-assignment-annotation]" in capsys.readouterr().out

def test_chkstyle_ignore_config_and_cli(tmp_path, capsys):
    p = _write(tmp_path, "t.py", "x: int = 1\n")
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""
        [tool.chkstyle]
        ignore = ["lhs-assignment-annotation"]
        """), encoding="utf-8")
    assert chkstyle.main(["chkstyle", str(p)]) == 0
    assert "found 0 potential violation(s)" in capsys.readouterr().out
    assert chkstyle.main(["chkstyle", "--ignore", "lhs-assignment-annotation", str(p)]) == 0

def test_chkstyle_main_accepts_multiple_paths(tmp_path, capsys):
    p1 = _write(tmp_path, "a.py", "x: int = 1\n")
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    p2 = pkg / "b.py"
    p2.write_text("y: int = 2\n", encoding="utf-8")
    assert chkstyle.main(["chkstyle", str(p1), str(pkg)]) == 1
    out = capsys.readouterr().out
    assert str(p1) in out and str(p2) in out

def test_chkstyle_config_skip_path_re(tmp_path, capsys):
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
        skip-path-re = "skip|src/gen"
        """), encoding="utf-8")
    assert chkstyle.main(["chkstyle", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert str(keep_file) in out and str(skip_file) not in out and str(gen_file) not in out

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

def test_chkstyle_cli_skip_path_re(tmp_path, capsys):
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
    assert chkstyle.main(["chkstyle", "--skip-path-re", "skip|src/gen", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert str(keep_file) in out and str(skip_file) not in out and str(gen_file) not in out

def test_chkstyle_cli_skip_path(tmp_path, capsys):
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
    assert chkstyle.main(["chkstyle", "--skip-path", "skipme", "--skip-path", "src/generated", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert str(keep_file) in out and str(skip_file) not in out and str(gen_file) not in out

def test_chkstyle_config_skip_file_with_path_re(tmp_path, capsys):
    keep_file = _write(tmp_path, "keep.py", "x: int = 1\n")
    skip_file = _write(tmp_path, "_modidx.py", "y: int = 2\n")
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""
        [tool.chkstyle]
        skip-path-re = "_modidx.py"
        """), encoding="utf-8")
    assert chkstyle.main(["chkstyle", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert str(keep_file) in out and str(skip_file) not in out

def test_chkstyle_config_skip_file_with_skip_paths(tmp_path, capsys):
    keep_file = _write(tmp_path, "keep.py", "x: int = 1\n")
    skip_file = _write(tmp_path, "_modidx.py", "y: int = 2\n")
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""
        [tool.chkstyle]
        skip_paths = ["_modidx.py"]
        """), encoding="utf-8")
    assert chkstyle.main(["chkstyle", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert str(keep_file) in out and str(skip_file) not in out

def test_chkstyle_subdir_target_uses_parent_pyproject(monkeypatch, tmp_path, capsys):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    keep_file = pkg / "keep.py"
    skip_file = pkg / "_modidx.py"
    keep_file.write_text("x: int = 1\n", encoding="utf-8")
    skip_file.write_text("y: int = 2\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""
        [tool.chkstyle]
        skip-path-re = "_modidx.py"
        """), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert chkstyle.main(["chkstyle", "pkg/"]) == 1
    out = capsys.readouterr().out
    assert str(keep_file.relative_to(tmp_path)) in out and str(skip_file.relative_to(tmp_path)) not in out

def test_chkstyle_fix_uses_config_allowlist(tmp_path):
    p = _write(tmp_path, "t.py", """
        data = {"a": 1, "b": 2, "c": 3}
        x: int = 1
        """)
    (tmp_path / "pyproject.toml").write_text(textwrap.dedent("""
        [tool.chkstyle]
        fix = ["dict-literal"]
        """), encoding="utf-8")
    assert chkstyle.main(["chkstyle", "--fix", str(p)]) == 1
    fixed = p.read_text(encoding="utf-8")
    assert "data = dict(a=1, b=2, c=3)" in fixed
    assert "x: int = 1" in fixed

def test_chkstyle_fix_lhs_annotation_preserves_dataclass_and_bare_annotations(tmp_path):
    p = _write(tmp_path, "t.py", """
        from dataclasses import dataclass

        @dataclass
        class A:
            x: int = 1

        y: int
        z: int = 2
        """)
    assert chkstyle.main(["chkstyle", "--fix", "--fix-rule", "lhs-assignment-annotation", str(p)]) == 1
    fixed = p.read_text(encoding="utf-8")
    assert "x: int = 1" in fixed
    assert "y: int" in fixed
    assert "z = 2" in fixed
    assert "z: int = 2" not in fixed

def test_chkstyle_fix_common_rules(tmp_path):
    p = _write(tmp_path, "t.py", '''
        import os
        import sys

        def f(x: list[list[int]]):
            """doc"""
            return dict(
                a=1,
                b=2)

        if ready:
            print(True)
        ''')
    chkstyle.main(["chkstyle", "--fix", "--fix-rule", "consecutive-short-imports", "--fix-rule", "nested-generics",
        "--fix-rule", "single-line-docstring", "--fix-rule", "single-statement-body", "--fix-rule", "inefficient-multiline-expression", str(p)])
    fixed = p.read_text(encoding="utf-8")
    assert "import os, sys" in fixed
    assert "def f(x: list[list]):" in fixed
    assert "'doc'" in fixed
    assert "return dict(a=1, b=2)" in fixed
    assert "if ready: print(True)" in fixed

def test_chkstyle_fix_imports_brackets_indent_and_semicolon(tmp_path):
    p = _write(tmp_path, "t.py", """
        import os
        import sys
        from os import (
            path,
            environ,
        )
        data = {"a": 1, "b": 2, "c": 3}
        result = call(
                alpha,
                beta,
        )
        a = 1; b = 2
        print(path, environ, sys.version)
        """)
    chkstyle.main(["chkstyle", "--fix", "--fix-rule", "unused-import", "--fix-rule", "multi-line-from-import",
        "--fix-rule", "closing-bracket", "--fix-rule", "continuation-indent", "--fix-rule", "semicolon", "--fix-rule", "dict-literal", str(p)])
    fixed = p.read_text(encoding="utf-8")
    assert "import os" not in fixed
    assert "import sys" in fixed
    assert "from os import path, environ" in fixed
    assert "data = dict(a=1, b=2, c=3)" in fixed
    assert "    alpha,\n    beta,)" in fixed
    assert "a = 1\nb = 2" in fixed

def test_chkstyle_allows_standalone_closer_with_comment(tmp_path):
    assert not _has_msg(_msgs(_check_py(tmp_path, """
        result = call(
            alpha,
        )  # explain
        """)), "closing bracket on its own line")

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

def test_chkstyle_flags_inefficient_multiline_from_import(tmp_path):
    msgs = _msgs(_check_py(tmp_path, """
        from .session import (
            DEFAULT_MAX_BUFFER_BYTES,
            DEFAULT_MAX_OUTPUT_BYTES,
            BgtermError,
            PollResult,
            Session,
            close_session,
            kill_session,
            list_sessions,
            poll_session,
            read_output,
            start_session,
            terminate_session,
            wait_for_result,
            write_stdin)
        """))
    assert _has_msg(msgs, "inefficient multi-line from-import"), msgs

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

def test_chkstyle_flags_unused_import(tmp_path):
    msgs = _msgs(_check_py(tmp_path, """
        import os
        """))
    assert _has_msg(msgs, "unused import: os"), msgs

def test_chkstyle_allows_dataclass_field_semicolons(tmp_path):
    msgs = _msgs(_check_py(tmp_path, """
        from dataclasses import dataclass

        @dataclass
        class Item:
            rule: str; path: str; lineno: int; msg: str; lines: list[str]
        """))
    assert not _has_msg(msgs, "semicolon statement separator"), msgs
    assert not _has_msg(msgs, "lhs assignment annotation"), msgs

def test_chkstyle_trailing_semicolons(tmp_path):
    "Trailing `;` separates nothing (it's Jupyter's output-suppression idiom) - only real separators count; and splitting a cell's last line (which has no line ending) must still insert newlines."
    assert not _has_msg(_msgs(_check_nb(tmp_path, ["s.run_cell('a=1');"])), "semicolon statement separator")
    assert not _has_msg(_msgs(_check_py(tmp_path, "x = print();\n")), "semicolon statement separator")
    assert _has_msg(_msgs(_check_py(tmp_path, "a = 1; b = 2;\n")), "semicolon statement separator")
    p = _write_nb(tmp_path, "t.ipynb", ["#| hide\nimport nbdev; nbdev.nbdev_export()"])
    chkstyle.main(["chkstyle", "--fix", "--fix-rule", "semicolon", str(p)])
    nb = json.loads(p.read_text(encoding="utf-8"))
    src = nb["cells"][0]["source"]
    if not isinstance(src, str): src = "".join(src)
    assert src == "#| hide\nimport nbdev\nnbdev.nbdev_export()", repr(src)

def test_chkstyle_skips_ipython_magics(tmp_path):
    "IPython `!`/`%` lines and `%%` cell magics aren't Python: no syntax errors, but the cell's real code is still checked."
    msgs = _msgs(_check_nb(tmp_path, ["!exec_nb --help", "%%bash\nls | wc -l", "%time x = 1\ny: int = 2"]))
    assert not _has_msg(msgs, "syntax error"), msgs
    assert _has_msg(msgs, "lhs assignment annotation"), msgs

def test_chkstyle_flags_bare_lhs_annotation(tmp_path):
    assert _has_msg(_msgs(_check_py(tmp_path, """
        x: int
        """)), "lhs assignment annotation")

def test_chkstyle_allows_import_used_in_nested_function(tmp_path):
    assert _check_py(tmp_path, """
        import os

        def outer():
            def inner(): return os.getcwd()
            return inner()
        """) == []

def test_chkstyle_allows_import_used_in_lambda_and_listcomp(tmp_path):
    assert _check_py(tmp_path, """
        import os
        f = lambda: os.getcwd()
        xs = [p for p in os.listdir('.')]
        """) == []

def test_chkstyle_flags_import_shadowed_in_listcomp(tmp_path):
    msgs = _msgs(_check_py(tmp_path, """
        import os
        xs = [os for os in range(3)]
        """))
    assert _has_msg(msgs, "unused import: os"), msgs

def test_chkstyle_allows_import_used_in___all__(tmp_path):
    assert _check_py(tmp_path, """
        from .mod import foo, bar

        __all__ = ["foo"]
        __all__ += ["bar"]
        """) == []

def test_chkstyle_never_flags___all__(tmp_path):
    long_all = ', '.join(f'"item_{i}"' for i in range(30))
    assert _check_py(tmp_path, f"""
        __all__ = [{long_all}]
        """) == []
    assert _check_py(tmp_path, """
        __all__ = [
            "one",
            "two",
            "three",
        ]
        """) == []

def test_chkstyle_allows_type_only_import_with_future_annotations(tmp_path):
    assert _check_py(tmp_path, """
        from __future__ import annotations
        from pathlib import Path

        def f(x: Path) -> Path: return x
        """) == []

def test_chkstyle_skips_unused_import_rule_in___init__(tmp_path):
    path = _write(tmp_path, "__init__.py", "from .mod import foo\n")
    assert chkstyle.check_file(str(path)) == []

def test_chkstyle_notebook_unused_import_checks_only_export_cells(tmp_path):
    assert _check_nb(tmp_path, ["import os\n"]) == []

def test_chkstyle_notebook_flags_exported_import_used_only_in_non_export_cells(tmp_path):
    violations = _check_nb(tmp_path, ["#| export\nimport os\n", "import sys\n", "print(os.getcwd())\n"])
    msgs = _msgs(violations)
    assert _has_msg(msgs, "exported-cell import only used in non-exported cells: os"), msgs
    assert any("cell1" in msg for msg in msgs), msgs
    assert not _has_msg(msgs, "unused import: os"), msgs
    assert len(violations) == 1 and violations[0][1] == 2

def test_chkstyle_notebook_exported_import_message_falls_back_without_import_cell(tmp_path):
    msgs = _msgs(_check_nb(tmp_path, ["#| export\nimport os\n", "print(os.getcwd())\n"]))
    assert _has_msg(msgs, "exported-cell import only used in non-exported cells: os"), msgs
    assert not any("move imports used only in non-exported cells to cell" in msg for msg in msgs), msgs

def test_chkstyle_notebook_allows_exported_import_used_in_later_export_cell(tmp_path):
    assert _check_nb(tmp_path, ["#| export\nimport os\n", "#| export\nprint(os.getcwd())\n"]) == []

def test_chkstyle_notebook_flags_truly_unused_exported_import(tmp_path):
    msgs = _msgs(_check_nb(tmp_path, ["#| export\nimport os\n"]))
    assert _has_msg(msgs, "unused import: os"), msgs

def test_chkstyle_notebook_reports_violations(tmp_path):
    msgs = _msgs(_check_nb(tmp_path, ["x: int = 1\ndata = {'a': 1, 'b': 2, 'c': 3}\n"]))
    assert _has_msg(msgs, "lhs assignment annotation")
    assert _has_msg(msgs, "dict literal with 3+ identifier keys")

def test_chkstyle_notebook_shows_cell_id_in_path(tmp_path):
    violations = _check_nb(tmp_path, ["x: int = 1\n"])
    assert len(violations) == 1
    vpath, lineno, rule, msg, lines = violations[0]
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

def test_chkstyle_notebook_flags_mixed_imports_and_code(tmp_path):
    violations = _check_nb(tmp_path, ["import os\nprint(os.getcwd())\n"])
    assert len(violations) == 1
    vpath, lineno, rule, msg, lines = violations[0]
    assert rule == "mixed-imports" and lineno == 1 and "cell0" in vpath
    assert _has_msg({msg}, "cell mixes imports and other code")
    violations = _check_nb(tmp_path, ["# setup\nx = 1\nfrom pathlib import PurePath\n"])
    assert [v[2] for v in violations] == ["mixed-imports"] and violations[0][1] == 3

def test_chkstyle_notebook_skips_nbdev_export_cell(tmp_path):
    assert _check_nb(tmp_path, ["import nbdev; nbdev.nbdev_export()\n"]) == []

def test_chkstyle_notebook_mixed_imports_allowed_cases(tmp_path):
    for cells in (["import os, sys\n"],  # imports only
            ["import os\n", "print(os.getcwd())\n"],  # separate cells
            ["#| export\nimport os\nprint(os.getcwd())\n"],  # exported cells exempt
            ["#| exec_doc\nimport os\nprint(os.getcwd())\n"],  # exec_doc exempt
            ["#| eval: false\nimport os\nprint(os.getcwd())\n"],  # eval false exempt
            ["import nbdev\nnbdev_export()\n"],  # nbdev_export cell exempt
            ["try: import foo\nexcept ImportError: foo=None\nprint(1)\n"],  # try-import allowed
            ["def f():\n    import os\n    return os.getcwd()\nprint(f())\n"],  # import in def allowed
            ["import os\ndef f(): return os.getcwd()\n"]):  # import + def, no top-level code
        assert "mixed-imports" not in {v[2] for v in _check_nb(tmp_path, cells)}, cells

def test_chkstyle_notebook_mixed_imports_ignore_pragma(tmp_path):
    cells = ["import os  # chkstyle: ignore\nprint(os.getcwd())\n"]
    assert "mixed-imports" not in {v[2] for v in _check_nb(tmp_path, cells)}

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
        def f(x: list[list[int]]): return x
        y: list[int] = [
            1,
            2,
        ]
        """))
    assert any(msg.startswith("nested generics depth 2") and "hint:" in msg for msg in msgs), msgs
    assert any(msg.startswith("inefficient multiline expression") and "hint:" in msg for msg in msgs), msgs

def test_chkstyle_nested_generics_only_parameter_annotations(tmp_path):
    msgs = _msgs(_check_py(tmp_path, """
        x: list[list[int]] = []
        def f() -> list[list[int]]: return []
        """))
    assert not _has_msg(msgs, "nested generics depth 2"), msgs
    assert _has_msg(msgs, "lhs assignment annotation"), msgs

def test_chkstyle_core_py_no_violations():
    "core.py should have no style violations."
    import pathlib
    core_path = pathlib.Path(__file__).parent.parent / "chkstyle" / "core.py"
    violations = chkstyle.check_file(str(core_path))
    assert violations == [], f"Unexpected violations in core.py: {[v[:4] for v in violations]}"
