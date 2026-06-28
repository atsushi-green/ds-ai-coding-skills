# CLAUDE.md

This is a **Python 3.11 data science / analysis project**.

Detailed task-specific procedures are in `.claude/skills/*/SKILL.md`.
Project-specific context is in `docs/agent/*`.

## Hard Rules (Always Apply)

- Never commit raw data, credentials, API keys, tokens, or customer-level records.
- Never modify, overwrite, delete, or regenerate raw data directly.
- Prefer small, reviewable changes.
- Explain assumptions before non-trivial analytical decisions.
- Ask for clarification when data semantics are unclear.
- Use `uv` exclusively for Python dependency management. Never use pip, conda, poetry, or pipenv.

## Package Management

- Use **uv** exclusively for all dependency management.
- Never use pip, pip3, `python -m pip`, poetry, conda, pipenv, or easy_install.

## Data Safety

- Never commit raw data, credentials, API keys, tokens, or customer-level records.
- Never modify or delete raw data directly.
- Treat `data/raw` and `data/external` as immutable.

## Common Commands

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format .          # ローカル整形
uv run ruff format --check .  # CI用（差分チェックのみ）
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

## File-Specific Guidelines

### Python files (`**/*.py`)

- Follow `python-style` skill: type hints, Google-style docstrings, Japanese comments.
- Follow `dataframe-polars` skill: prefer polars over pandas.
- Follow `path-and-io` skill: use pathlib.Path, no absolute paths.

### Data files (`data/**`)

- Do not create, modify, or commit real data files under `data/raw/` or `data/external/` — these are immutable.
- Writing derived data to `data/interim/` or `data/processed/` is allowed in code, but do not commit large data files.
- Only `.gitkeep` files and documentation (README, markdown) are acceptable to commit.
- See `safe-data-handling` skill.

### SQL files (`**/*.sql`)

- Use explicit column names; avoid `SELECT *`.
- Use CTEs for readability.
- Add date filters for large tables.
- Validate join cardinality and row counts.
- Never run `DROP`, `TRUNCATE`, `DELETE`, or `UPDATE` unless explicitly requested.
- See `sql-analysis` skill.

### Notebooks (`**/*.ipynb`, `notebooks/**/*.md`)

- Keep restartable from a clean kernel; no secrets in outputs.
- See `notebook-workflow` and `safe-data-handling` skills.

### Documentation (`README.md`, `docs/**/*.md`)

- Write documentation in clear Japanese.
- Keep code snippets, commands, file paths, and config values in English as-is.
- Do not translate technical terms unnecessarily.

## Skill Routing

| Task | Skill |
|------|-------|
| Dependencies, tests, lint, type check, notebook execution | [python-project-ops](.claude/skills/python-project-ops/SKILL.md) |
| Reading / writing / moving data files | [safe-data-handling](.claude/skills/safe-data-handling/SKILL.md) + [path-and-io](.claude/skills/path-and-io/SKILL.md) |
| Writing or reviewing SQL | [sql-analysis](.claude/skills/sql-analysis/SKILL.md) |
| Writing or reviewing Python code | [python-style](.claude/skills/python-style/SKILL.md) |
| DataFrame operations | [dataframe-polars](.claude/skills/dataframe-polars/SKILL.md) |
| Charts and visualization | [visualization](.claude/skills/visualization/SKILL.md) |
| Notebook creation and editing | [notebook-workflow](.claude/skills/notebook-workflow/SKILL.md) |
| Statistics or ML | [statistical-ml-review](.claude/skills/statistical-ml-review/SKILL.md) |
| Analysis summaries and reports | [analysis-reporting](.claude/skills/analysis-reporting/SKILL.md) |
| File paths and I/O | [path-and-io](.claude/skills/path-and-io/SKILL.md) |

## Project Context (docs/agent)

| Document | Purpose |
|----------|---------|
| [project-overview.md](docs/agent/project-overview.md) | プロジェクトの目的とスコープ |
| [repository-structure.md](docs/agent/repository-structure.md) | ディレクトリ構成 |
| [data-catalog.md](docs/agent/data-catalog.md) | データセット一覧と定義 |
| [metrics-and-definitions.md](docs/agent/metrics-and-definitions.md) | 指標定義 |
| [analysis-workflow.md](docs/agent/analysis-workflow.md) | 分析ワークフロー |
| [statistical-and-ml-guidelines.md](docs/agent/statistical-and-ml-guidelines.md) | 統計・MLガイドライン |
| [validation-and-testing.md](docs/agent/validation-and-testing.md) | テスト・検証方針 |
| [reporting-guidelines.md](docs/agent/reporting-guidelines.md) | 報告テンプレート |
| [security-and-privacy.md](docs/agent/security-and-privacy.md) | セキュリティ・プライバシー |
| [agent-behavior.md](docs/agent/agent-behavior.md) | エージェント行動指針 |

## Skills

@.claude/skills/python-project-ops/SKILL.md
@.claude/skills/python-style/SKILL.md
@.claude/skills/dataframe-polars/SKILL.md
@.claude/skills/path-and-io/SKILL.md
@.claude/skills/safe-data-handling/SKILL.md
@.claude/skills/sql-analysis/SKILL.md
@.claude/skills/notebook-workflow/SKILL.md
@.claude/skills/statistical-ml-review/SKILL.md
@.claude/skills/visualization/SKILL.md
@.claude/skills/analysis-reporting/SKILL.md
