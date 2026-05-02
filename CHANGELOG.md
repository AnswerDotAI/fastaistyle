# Release notes

<!-- do not remove -->

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

