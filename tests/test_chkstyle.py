# chkstyle: skip
import textwrap

import chkstyle

def _write(tmp_path, name: str, content: str):
    path = tmp_path / name
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return path

def _messages(violations):
    return {msg for _path, _lineno, msg, _lines in violations}

def test_chkstyle_reports_expected_violations(tmp_path):
    path = _write(
        tmp_path,
        "cases.py",
        '''
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
        long = "......................................................................................................................................................."
        def g(x: list[list[int]]): return x
        ''',
    )
    msgs = _messages(chkstyle.check_file(str(path)))
    expected = {
        "single-line docstring uses triple quotes",
        "lhs assignment annotation",
        "dict literal with 3+ identifier keys",
        "semicolon statement separator",
        "multi-line from-import",
        "if single-statement body not one-liner",
        "inefficient multiline expression",
        "line >150 chars",
        "nested generics depth 2",
    }
    assert expected.issubset(msgs)

def test_chkstyle_ignore_and_off_on(tmp_path):
    path = _write(
        tmp_path,
        "ignore.py",
        """
        x: int = 1  # chkstyle: ignore
        # chkstyle: ignore
        y: int = 2
        # chkstyle: off
        z: int = 3
        # chkstyle: on
        """,
    )
    assert chkstyle.check_file(str(path)) == []

def test_chkstyle_skip_file(tmp_path):
    path = _write(
        tmp_path,
        "skip.py",
        """
        # chkstyle: skip
        x: int = 1
        data = {"a": 1, "b": 2, "c": 3}
        """,
    )
    assert chkstyle.check_file(str(path)) == []

def test_chkstyle_allows_multiline_strings(tmp_path):
    path = _write(
        tmp_path,
        "strings.py",
        '''
        value = """
        line one
        line two
        """
        ''',
    )
    assert chkstyle.check_file(str(path)) == []

def test_chkstyle_allows_decorated_inner_defs(tmp_path):
    path = _write(
        tmp_path,
        "decorators.py",
        """
        def dec(f): return f

        def outer():
            @dec
            def inner(): return 1
        """,
    )
    assert chkstyle.check_file(str(path)) == []

def test_chkstyle_allows_multiline_string_calls(tmp_path):
    path = _write(
        tmp_path,
        "multiline_call.py",
        '''
        def f():
            return _lines("""
            one
            two
            """)
        ''',
    )
    assert chkstyle.check_file(str(path)) == []

def test_chkstyle_allows_trailing_comments(tmp_path):
    path = _write(
        tmp_path,
        "docments.py",
        """
        def ship_new(
            name: str,              # Project name
            package: str = None,    # Package name
            force: bool = False,    # Overwrite existing
        ):
            return name

        __all__ = [
            "one",   # first
            "two",   # second
        ]
        """,
    )
    assert chkstyle.check_file(str(path)) == []

def test_chkstyle_if_else_single_statement(tmp_path):
    path = _write(
        tmp_path,
        "if_else.py",
        """
        if branch == expected:
            print(f"ok")
        else:
            print(f"not ok")
        """,
    )
    msgs = _messages(chkstyle.check_file(str(path)))
    assert "if single-statement body not one-liner" in msgs

def test_chkstyle_main_accepts_file_path(tmp_path):
    path = _write(tmp_path, "single.py", "x: int = 1\n")
    ret = chkstyle.main(["chkstyle", str(path)])
    assert ret == 1  # should find violation

def test_chkstyle_allows_multiline_def_with_docments(tmp_path):
    path = _write(
        tmp_path,
        "docment_def.py",
        """
        def ws_clone_cli(
            repos_file: str = "repos.txt",  # File containing repo list
            workers: int = 16,  # Number of parallel workers
        ): ws_clone(repos_file, workers)
        """,
    )
    assert chkstyle.check_file(str(path)) == []
