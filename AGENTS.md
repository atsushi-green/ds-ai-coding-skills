# AGENTS.md

This file is an **agent router**. It provides high-level rules and directs agents to the appropriate skill files for detailed instructions.

Detailed task-specific procedures are in `.github/skills/*/SKILL.md`.
Project-specific context is in `docs/agent/*`.

## Hard Rules (Always Apply)

- Never commit raw data, credentials, API keys, tokens, or customer-level records.
- Never modify, overwrite, delete, or regenerate raw data directly.
- Prefer small, reviewable changes.
- Explain assumptions before non-trivial analytical decisions.
- Ask for clarification when data semantics are unclear.
- Use `uv` exclusively for Python dependency management. Never use pip, conda, poetry, or pipenv.

## Routing Table

| Task | Skill |
|------|-------|
| Dependencies, tests, lint, type check, notebook execution | [python-project-ops](.github/skills/python-project-ops/SKILL.md) |
| Reading / writing / moving data files | [safe-data-handling](.github/skills/safe-data-handling/SKILL.md) + [path-and-io](.github/skills/path-and-io/SKILL.md) |
| Writing or reviewing SQL | [sql-analysis](.github/skills/sql-analysis/SKILL.md) |
| Writing or reviewing Python code | [python-style](.github/skills/python-style/SKILL.md) |
| DataFrame operations | [dataframe-polars](.github/skills/dataframe-polars/SKILL.md) |
| Charts and visualization | [visualization](.github/skills/visualization/SKILL.md) |
| Notebook creation and editing | [notebook-workflow](.github/skills/notebook-workflow/SKILL.md) |
| Statistics or ML | [statistical-ml-review](.github/skills/statistical-ml-review/SKILL.md) |
| Analysis summaries and reports | [analysis-reporting](.github/skills/analysis-reporting/SKILL.md) |
| File paths and I/O | [path-and-io](.github/skills/path-and-io/SKILL.md) |

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
