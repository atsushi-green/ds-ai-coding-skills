"""エージェント文書の必須ファイルが存在するか検証するスクリプト。"""

from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_FILES = [
    # --- GitHub Copilot ---
    "AGENTS.md",
    ".github/copilot-instructions.md",
    # Copilot Skills
    ".github/skills/python-project-ops/SKILL.md",
    ".github/skills/safe-data-handling/SKILL.md",
    ".github/skills/sql-analysis/SKILL.md",
    ".github/skills/python-style/SKILL.md",
    ".github/skills/dataframe-polars/SKILL.md",
    ".github/skills/visualization/SKILL.md",
    ".github/skills/path-and-io/SKILL.md",
    ".github/skills/notebook-workflow/SKILL.md",
    ".github/skills/statistical-ml-review/SKILL.md",
    ".github/skills/analysis-reporting/SKILL.md",
    # Copilot Instructions
    ".github/instructions/data.instructions.md",
    ".github/instructions/docs.instructions.md",
    ".github/instructions/notebooks.instructions.md",
    ".github/instructions/python.instructions.md",
    ".github/instructions/sql.instructions.md",
    # Copilot Prompts
    ".github/prompts/plan-analysis.prompt.md",
    ".github/prompts/prepare-pr.prompt.md",
    ".github/prompts/review-sql.prompt.md",
    ".github/prompts/run-eda.prompt.md",
    ".github/prompts/run-modeling.prompt.md",
    ".github/prompts/summarize-analysis.prompt.md",
    ".github/prompts/update-agent-docs.prompt.md",
    # --- Claude Code ---
    "CLAUDE.md",
    # Claude Code Skills
    ".claude/skills/python-project-ops/SKILL.md",
    ".claude/skills/safe-data-handling/SKILL.md",
    ".claude/skills/sql-analysis/SKILL.md",
    ".claude/skills/python-style/SKILL.md",
    ".claude/skills/dataframe-polars/SKILL.md",
    ".claude/skills/visualization/SKILL.md",
    ".claude/skills/path-and-io/SKILL.md",
    ".claude/skills/notebook-workflow/SKILL.md",
    ".claude/skills/statistical-ml-review/SKILL.md",
    ".claude/skills/analysis-reporting/SKILL.md",
    # Claude Code Commands
    ".claude/commands/plan-analysis.md",
    ".claude/commands/prepare-pr.md",
    ".claude/commands/review-sql.md",
    ".claude/commands/run-eda.md",
    ".claude/commands/run-modeling.md",
    ".claude/commands/summarize-analysis.md",
    ".claude/commands/update-agent-docs.md",
    # --- 共通ドキュメント ---
    "docs/agent/project-overview.md",
    "docs/agent/repository-structure.md",
    "docs/agent/data-catalog.md",
    "docs/agent/metrics-and-definitions.md",
    "docs/agent/analysis-workflow.md",
    "docs/agent/statistical-and-ml-guidelines.md",
    "docs/agent/validation-and-testing.md",
    "docs/agent/reporting-guidelines.md",
    "docs/agent/security-and-privacy.md",
    "docs/agent/agent-behavior.md",
]


def main() -> None:
    """メイン処理。"""
    repo_root = Path(".")
    missing: list[str] = []

    for filepath in REQUIRED_FILES:
        if not (repo_root / filepath).exists():
            missing.append(filepath)

    if missing:
        print("ERROR: The following required agent documentation files are missing:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)
    else:
        print(f"OK: All {len(REQUIRED_FILES)} required agent documentation files exist.")


if __name__ == "__main__":
    main()
