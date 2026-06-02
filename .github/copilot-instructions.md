# Repository-Wide Custom Instructions

This is a **Python 3.11 data science / analysis project**.

## Package Management

- Use **uv** exclusively for all dependency management.
- Never use pip, pip3, `python -m pip`, poetry, conda, pipenv, or easy_install.

## Data Safety

- Never commit raw data, credentials, API keys, tokens, or customer-level records.
- Never modify or delete raw data directly.
- Treat `data/raw` and `data/external` as immutable.

## Where to Find Detailed Rules

- **Task-specific skills**: `.github/skills/*/SKILL.md` — see `AGENTS.md` for routing.
- **Project context**: `docs/agent/*` — data catalog, metrics, workflow, etc.
- **Path-specific hints**: `.github/instructions/*.instructions.md`

## Common Commands

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format .          # ローカル整形
uv run ruff format --check .   # CI用（差分チェックのみ）
uv run mypy src
uv run python scripts/check_no_raw_data_commit.py
uv run python scripts/check_no_sensitive_patterns.py
```

## Key Conventions

- DataFrame operations: prefer **polars** over pandas.
- Visualization: use `fig, ax = plt.subplots(...)`, not `plt.figure(...)`.
- File paths: use `pathlib.Path`, no absolute local paths.
- Docstrings: Google-style.
- Inline comments: Japanese.
- Reports and documentation: Japanese.
