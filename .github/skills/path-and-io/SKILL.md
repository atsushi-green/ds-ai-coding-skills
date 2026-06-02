---
name: path-and-io
description: Use this when reading from or writing to local files — including constructing file paths with pathlib, creating directories, choosing output locations, and using path utilities from src/analysis_project/paths.py.
---

# Skill: Path and I/O

Use this skill when reading from or writing to local files.

## Rules

- Use `pathlib.Path` for all file path operations.
- **Do not** hard-code absolute local paths.
- Prefer paths relative to repository root or configured directories.
- Use the path utilities in `src/analysis_project/paths.py`.
- **Do not** write outputs into raw data directories (`data/raw/`, `data/external/`).
- Create parent directories explicitly when writing outputs: `path.parent.mkdir(parents=True, exist_ok=True)`.
- Use descriptive file names.
- Include dates or run identifiers when outputs are time-dependent.
- Avoid overwriting existing outputs unless explicitly requested.

## Available Utilities

`src/analysis_project/paths.py` provides:

- `get_repo_root()` — リポジトリルートの `Path`
- `data_dir()` — `data/` ディレクトリの `Path`
- `outputs_dir()` — `outputs/` ディレクトリの `Path`
- `ensure_parent_dir(path)` — 親ディレクトリを作成してパスを返す

## Examples

```python
from analysis_project.paths import data_dir, outputs_dir, ensure_parent_dir

# 入力データの読み込み
input_path = data_dir() / "raw" / "titanic" / "train.csv"

# 出力パスを構成して書き込み
output_path = outputs_dir() / "tables" / "summary_2024q1.csv"
ensure_parent_dir(output_path)
df.write_csv(output_path)
```
