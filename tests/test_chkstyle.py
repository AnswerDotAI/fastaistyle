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
