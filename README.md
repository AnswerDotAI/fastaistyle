# chkstyle

```bash
pip install chkstyle
```

A style checker that enforces the [fast.ai coding style](https://docs.fast.ai/dev/style.html)—a compact, readable approach to Python that keeps more code visible on screen and reduces cognitive load.

## Why This Style?

Most style guides optimize for the wrong thing. They add vertical space, mandate verbose names, and scatter related code across many lines. The result? You see less code at once, which means more scrolling, more context-switching, and more mental effort to understand what's happening.

The fast.ai style takes a different approach, rooted in decades of experience with APL, J, K, and scientific programming. The core insight comes from Kenneth Iverson: **"brevity facilitates reasoning."**

### Your Brain Can Only Hold So Much

When you're reading code, your working memory is limited. If a function spans 50 lines, you can't see the whole thing at once. You scroll down, forget what was at the top, scroll back up. Each scroll is a context switch. Each context switch costs mental energy.

But if that same function fits in 15 lines? You see the whole picture. Your eyes can jump between related parts instantly. Patterns become obvious. Bugs stand out.

This isn't about cramming code together—it's about *removing unnecessary vertical space* so your brain can do what it's good at: recognizing patterns across visible information.

### One Line, One Idea

The goal is density without confusion. Each line should express one complete thought:

```python
# Good: you see the whole pattern at once
if not data: return None
for item in items: process(item)
def _is_ready(self): return self._ready.is_set()

# Bad: same logic, but now it's 6 lines instead of 3
if not data:
    return None
for item in items:
    process(item)
def _is_ready(self):
    return self._ready.is_set()
```

When the body is simple, keep it on the same line. Save vertical space for code that actually needs it.

### Names Should Be Short (When Used Often)

This follows "Huffman coding" for variable names—frequently used things get short names:

```python
# Good: conventional, recognizable
img, i, msg, ctx

# Bad: verbose for no benefit
image_data, loop_index, message_object, context_instance
```

Domain experts recognize `nll` (negative log likelihood) instantly. Spelling it out doesn't help them, and the extra characters push code off the right edge of the screen.

## Installation

```bash
pip install chkstyle
```

Or install from source:

```bash
git clone https://github.com/AnswerDotAI/chkstyle
cd chkstyle
pip install -e .
```

## Usage

Check the current directory:
```bash
chkstyle
```

Check a specific path:
```bash
chkstyle path/to/code/
```

The checker prints violations with file paths, line numbers, and the offending code.

## What It Checks

### `dict literal with 3+ identifier keys`
Use `dict()` for keyword-like keys—it's easier to scan and produces cleaner diffs.

```python
# Bad
payload = {"host": host, "port": port, "timeout": timeout}

# Good
payload = dict(host=host, port=port, timeout=timeout)
```

### `single-statement body not one-liner`
If the body is one simple statement, keep it on the header line.

```python
# Bad
if ready:
    return True

# Good
if ready: return True
```

### `single-line docstring uses triple quotes`
Triple quotes are for multi-line strings. Single-line docstrings should use regular quotes.

```python
# Bad
def foo():
    """Return the value."""
    return x

# Good
def foo():
    "Return the value."
    return x
```

### `multi-line from-import`
If it fits on one line, keep it on one line.

```python
# Bad
from os import (
    path,
    environ,
)

# Good
from os import path, environ
```

### `line >150 chars`
Wrap at a natural boundary: argument lists, binary operators, or strings. But 150 is generous—aim for ~120 when practical.

### `semicolon statement separator`
Don't use `;` to combine statements. Use separate lines.

### `inefficient multiline expression`
If the content would fit in fewer lines, condense it.

```python
# Bad
result = call(
    a,
    b,
    c,
)

# Good
result = call(a, b, c)
```

### `lhs assignment annotation`
Avoid `x: int = 1` in normal code. Put type hints on function parameters and return values instead. The exception is dataclass fields, where annotations are required.

```python
# Bad
x: int = 1
name: str = "hello"

# Good (in a function signature)
def process(x: int, name: str) -> Result: ...
```

### `nested generics depth >= 2`
Keep type annotations simple. Deep nesting makes them hard to read.

```python
# Bad
items: list[dict[str, list[int]]]

# Good
Payload = dict[str, list[int]]
items: list[Payload]
```

## Opting Out

Sometimes you have a good reason to format code a specific way. The checker supports pragmas:

```python
# Ignore a single line
x: int = 1  # chkstyle: ignore

# Ignore the next line
# chkstyle: ignore
y: int = 2

# Disable for a block
# chkstyle: off
carefully_formatted = {
    "alignment": "matters",
    "here":      "for readability",
}
# chkstyle: on

# Skip an entire file (must be in first 5 lines)
# chkstyle: skip
```

## Running Tests

```bash
pytest
```

## Philosophy

This tool exists to catch mechanical issues, not to enforce taste. The violations it reports are almost always things you'd want to fix—extra vertical space that doesn't help, type annotations that clutter rather than clarify, formatting that makes diffs noisier than necessary.

The goal is code that's pleasant to read and easy to maintain. Dense, but not cramped. Clear, but not verbose. When in doubt, look at the surrounding code and match its style.

For the full style guide, see:
- [fast.ai Style Guide](https://docs.fast.ai/dev/style.html)
- [style.md](style.md) in this repo

## License

Apache 2.0
