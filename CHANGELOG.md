# Release notes

<!-- do not remove -->

## 0.0.20

### Bugs Squashed

- Fix generated-file detection and skipped-cell import tracking ([#29](https://github.com/AnswerDotAI/fastaistyle/pull/29)), thanks to [@jph00](https://github.com/jph00)
- Fix single-statement-body autofix to strip trailing whitespace from the header line before joining the body ([#28](https://github.com/AnswerDotAI/fastaistyle/issues/28))


## 0.0.19

### New Features

- Read a user-level chkstyle config, and read source segments in linear time ([#27](https://github.com/AnswerDotAI/fastaistyle/pull/27)), thanks to [@jph00](https://github.com/jph00)


## 0.0.18

### New Features

- split over-long condensed dict/expression fixes across multiple lines instead of skipping them ([#24](https://github.com/AnswerDotAI/fastaistyle/issues/24))
- Use fastcore `mk_cell` directives for notebook export/mix-exempt detection, supporting nbdev directives in cell metadata ([#23](https://github.com/AnswerDotAI/fastaistyle/issues/23))
- Add `chkstyle: ignore-node` pragma to suppress violations across an entire AST node ([#21](https://github.com/AnswerDotAI/fastaistyle/issues/21))
- Add --show-rule flag, document rule IDs, and skip `nbdev_export`() cells via cell skip flag ([#20](https://github.com/AnswerDotAI/fastaistyle/issues/20))
- Add f-string tokens to line-length exemption set ([#19](https://github.com/AnswerDotAI/fastaistyle/issues/19))
- Add `cell mixes imports and other code` rule for notebooks ([#18](https://github.com/AnswerDotAI/fastaistyle/issues/18))

### Bugs Squashed

- Fix `--fix` corruption from comment-joined closers, non-ASCII spans, string re-indents and class field annotations, and skip nbdev-generated modules ([#26](https://github.com/AnswerDotAI/fastaistyle/pull/26)), thanks to [@jph00](https://github.com/jph00)
- Count logical lines in the notebook cell-length rules ([#25](https://github.com/AnswerDotAI/fastaistyle/pull/25)), thanks to [@jph00](https://github.com/jph00)
- Handle backslash continuations after IPython magics; make skip pragma work per notebook cell even on unparseable source ([#22](https://github.com/AnswerDotAI/fastaistyle/issues/22))


## 0.0.17

### New Features

- Refactor rule handling: store rule id on Issue/violation tuples and add `COMBINE_WIDTH` for fixes ([#17](https://github.com/AnswerDotAI/fastaistyle/issues/17))
- Exempt long comments from line-length check ([#16](https://github.com/AnswerDotAI/fastaistyle/issues/16))


## 0.0.16

### New Features

- Allow semicolon-separated field annotations in dataclasses ([#15](https://github.com/AnswerDotAI/fastaistyle/issues/15))
- Add --fix mode with per-rule auto-fixers and --ignore support ([#14](https://github.com/AnswerDotAI/fastaistyle/issues/14))
- suppress __all__ lines from style checks and resolve config root from nearest pyproject.toml ([#13](https://github.com/AnswerDotAI/fastaistyle/issues/13))
- Rename --skip-folder-re to --skip-path-re with support for matching normalized relative paths ([#12](https://github.com/AnswerDotAI/fastaistyle/issues/12))
- Add `disabled` option ([#11](https://github.com/AnswerDotAI/fastaistyle/issues/11))
- Add inefficient multi-line from-import check and corresponding test ([#10](https://github.com/AnswerDotAI/fastaistyle/issues/10))


## 0.0.15

### New Features

- Add unused import detection for Python files and notebooks with nbdev export-cell awareness ([#9](https://github.com/AnswerDotAI/fastaistyle/issues/9))


## 0.0.14

### New Features

- Add checks for consecutive short imports, standalone closers, and continuation line indents ([#8](https://github.com/AnswerDotAI/fastaistyle/issues/8))


## 0.0.13

### New Features

- Add skip-path support, fix hints, exempt string-heavy long lines ([#7](https://github.com/AnswerDotAI/fastaistyle/issues/7))


## 0.0.12

### New Features

- Reduce fussiness of line length ([#5](https://github.com/AnswerDotAI/fastaistyle/issues/5))


## 0.0.11

### Bugs Squashed

- Fix pragma detection in string literals ([#4](https://github.com/AnswerDotAI/fastaistyle/pull/4)), thanks to [@jph00](https://github.com/jph00)


## 0.0.10

### New Features

- Add Jupyter notebook (.ipynb) support ([#3](https://github.com/AnswerDotAI/fastaistyle/pull/3)), thanks to [@jph00](https://github.com/jph00)


## 0.0.9

### New Features

- allow docmented function signatures and restructure as package ([#2](https://github.com/AnswerDotAI/fastaistyle/pull/2)), thanks to [@jph00](https://github.com/jph00)
