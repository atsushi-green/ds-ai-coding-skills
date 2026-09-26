---
name: python-project-ops
description: Use this when managing Python dependencies with uv, running tests with pytest, linting with ruff, formatting code, type checking with mypy, or executing notebooks.
---

# Skill: Python Project Operations

Use this skill when changing dependencies, running tests, linting, formatting, type checking, or executing notebooks.

## Package Manager: uv Only

- Use `uv` for all dependency installation, synchronization, addition, removal, and updates.
- **Never** use pip, pip3, `python -m pip`, poetry, conda, pipenv, or easy_install.
- **Never** manually create or edit `requirements.txt`.
- Use `uv add <package>` when adding dependencies.
- Use `uv add --group dev <package>` for dev-only dependencies.
- Review diffs in `pyproject.toml` and `uv.lock` after dependency changes.

## Python Version

- Python 3.11.

## Common Commands

```bash
uv sync                    # Install/synchronize dependencies
uv run pytest              # Run tests
uv run ruff check .        # Lint
uv run ruff format .       # Format
uv run mypy src            # Type check
uv run papermill notebooks/input.ipynb notebooks/output.ipynb  # Execute notebook
bash scripts/run_quality_checks.sh  # Run all quality checks
```

## Workflow

1. After modifying `pyproject.toml`, run `uv sync`.
2. After adding code, run `uv run ruff check .` and `uv run ruff format .`.
3. Before committing, run `uv run pytest` and `uv run mypy src`.
4. For notebook execution in CI or automation, prefer `papermill`.

## Tests and Tool Configuration

- Place tests under `tests/`; keep them fast by minimizing external dependencies.
- `ruff` settings live in the `[tool.ruff]` section of `pyproject.toml`.
- `mypy` settings live in the `[tool.mypy]` section of `pyproject.toml`.
- Verify notebooks re-run from a clean kernel — see [notebook-workflow skill](.claude/skills/notebook-workflow/SKILL.md).

## Validation Scripts

These run in GitHub Actions CI, and can be run locally before committing.

```bash
uv run python scripts/check_no_raw_data_commit.py    # rawデータのコミットを検知
uv run python scripts/check_no_sensitive_patterns.py # 秘密情報のパターンを検知
uv run python scripts/validate_agent_docs.py         # エージェント文書の必須ファイル確認
uv run python scripts/sync_agent_docs.py --check     # CLAUDE.md / AGENTS.md のドリフト検出
bash scripts/run_quality_checks.sh                   # 上記を含む一括実行
```
