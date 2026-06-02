---
name: python-style
description: Use this when creating, editing, or reviewing Python code — including type hints, docstrings, naming conventions, imports, error handling, and code structure.
---

# Skill: Python Style

Use this skill when creating, editing, or reviewing Python code.

## Type Hints

- Add type hints to all public function signatures.
- Use `from __future__ import annotations` when convenient.

## Docstrings

- Use **Google-style** docstrings for all public modules, classes, functions, and methods.
- Docstrings should describe:
  - Purpose
  - Args
  - Returns
  - Raises (if applicable)
  - Examples (when helpful)
  - Important assumptions

## Comments

- **Inline comments and explanatory comments must be written in Japanese.**
- Comments should explain non-obvious intent, assumptions, or business logic.
- Do not comment obvious syntax.

## Code Style

- Prefer small, pure functions where practical.
- Prefer explicit error handling over bare `except`.
- Use `pathlib.Path` for file paths — see [path-and-io skill](../path-and-io/SKILL.md).
- Follow `ruff` linting and formatting rules configured in `pyproject.toml`.

## Example

```python
import json
from pathlib import Path


def load_config(config_path: Path) -> dict:
    """設定ファイルを読み込んで辞書として返す。

    Args:
        config_path: 設定ファイルのパス。

    Returns:
        設定内容を格納した辞書。

    Raises:
        FileNotFoundError: 指定されたパスにファイルが存在しない場合。
    """
    # JSONファイルを読み込む
    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)
```
