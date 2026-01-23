# Repo Style

Keep the code compact, readable, and consistent with the surrounding file. Prefer clarity over strict formatting rules. Do not follow PEP-8.

## Layout
- Aim to avoid >140 chars on a line.  
- Keep one logical idea per line.  
- Never use `;` to combine multiple statements on a line
- Avoid inefficient multi-line expressions/signatures: if the combined stripped length would fit in fewer ~120-char lines, keep it tighter.
- Single-line bodies are preferred for short `with`, `open`, `try`, `except`, `catch`, `for`, and `if` statements, plus small one-line functions.  
  - Good: `if not data: return None`  
  - Bad: `if not data:\n    return None`  
- Single-line bodies are preferred for small one-line functions that don't need a docstring (i.e because they're private or a dunder function).  
  - Good: `def _is_ready(self): return self._ready.is_set()`  
  - Bad: `def _is_ready(self):\n    return self._ready.is_set()`  
- Be frugal with vertical whitespace.
- Avoid nearly all comments, unless really required to explain an otherwise-obscure issue.  
- Indent with 4 spaces; avoid trailing whitespace.  
- Avoid auto-formatters that rewrite layout.  
- Group imports; multiple modules on one line is preferred.  
  - Good: `import json, os, time`  
  - Bad: `import json\nimport os\nimport time`  
  - Good: `from mymod import (\n    a,\n    b\n)`
  - Bad: `from mymod import a,b`

## Naming
- Use standard Python casing.  
- Prefer short, conventional names for frequently used values; follow existing abbreviations.  
  - Good: `msg_id`, `iopub`, `ctx`, `i`
  - Bad: `message_identifier`, `io_pub_channel`, `context_object`, `loop_index`

## Structure
- Favor small helpers over repetitive blocks.  
  - Good: `def _send_stream(self, name, text): ...; self._send_stream("stdout", out)`  
  - Bad: `self._send(sock, "stream", {"name": "stdout", "text": out}, parent)`  
- Use comprehensions or inline expressions when they improve clarity.  
  - Good: `ids = [m["header"]["msg_id"] for m in msgs]`  
  - Bad: `ids = []\nfor m in msgs: ids.append(m["header"]["msg_id"])`  

## Typing
- Never add type annotations to LHS assignments (e.g. `x: int = 1`), except dataclass fields.  
- Keep annotations simple; avoid nested generics beyond one level unless you have a strong reason.  

## Documentation
- Use brief single-line docstrings for multi-line functions.  
  - Good: `def run(self):\n    "Run the thread."\n    ...`  
  - Bad: `def run(self):\n    \"\"\"\n    Run the thread.\n    \"\"\"\n    ...`  
- Add comments only when they explain why. That means add VERY few comments!
  - Good: `self._stop_event.set()  # ensures poll loop exits before socket close`  
  - Bad: `self._stop_event.set()  # stop the event`  

## Testing
- All tests must pass before changes are considered complete.  
