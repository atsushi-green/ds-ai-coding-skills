"""エージェント文書の必須ファイルが存在するか検証するスクリプト。"""

from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_FILES = [
    "AGENTS.md",
    ".github/copilot-instructions.md",
    # Skills
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
    # Instructions
    ".github/instructions/data.instructions.md",
    ".github/instructions/docs.instructions.md",
    ".github/instructions/notebooks.instructions.md",
    ".github/instructions/python.instructions.md",
    ".github/instructions/sql.instructions.md",
    # Prompts
    ".github/prompts/plan-analysis.prompt.md",
    ".github/prompts/prepare-pr.prompt.md",
    ".github/prompts/review-sql.prompt.md",
    ".github/prompts/run-eda.prompt.md",
    ".github/prompts/run-modeling.prompt.md",
    ".github/prompts/summarize-analysis.prompt.md",
    ".github/prompts/update-agent-docs.prompt.md",
    # Docs
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
