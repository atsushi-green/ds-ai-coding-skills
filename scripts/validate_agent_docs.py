"""エージェント文書の必須ファイルが存在するか検証するスクリプト。"""

from __future__ import annotations

import sys
from pathlib import Path

# 手法別診断スキル(2段構成: ルーター SKILL.md + references/<method>.md)。
# skill の正本は .claude/skills/ だけで、Claude Code・Copilot・Codex のいずれもここを読む。
# Codex 向けの .agents/skills/ は正本へのシンボリックリンクなので、
# リンクの健全性だけを別に検証する。
DIAGNOSTICS_ROUTERS: dict[str, list[str]] = {
    "statistical-inference-diagnostics": [
        "ols",
        "glm",
        "mixed-effects",
        "hypothesis-test",
        "survival",
        "bayesian-mcmc",
    ],
    "predictive-modeling-diagnostics": [
        "ml-evaluation",
        "tree-model",
        "model-interpretation",
        "time-series",
    ],
    "causal-inference-diagnostics": [
        "ab-test",
        "causal-observational",
        "causal-quasi-experimental",
    ],
    "unsupervised-eda-diagnostics": [
        "missing-data",
        "clustering",
        "dimensionality-reduction",
        "anomaly-detection",
    ],
    "simulation-optimization-diagnostics": [
        "simulation",
        "optimization",
    ],
}
DIAGNOSTICS_FILES = [
    f"{router}/{rel}"
    for router, refs in DIAGNOSTICS_ROUTERS.items()
    for rel in ["SKILL.md", *[f"references/{ref}.md" for ref in refs]]
]

REQUIRED_FILES = [
    # --- GitHub Copilot / Codex ---
    "AGENTS.md",
    # Copilot Instructions (パス別。applyTo で自動適用される Copilot 固有の入口)
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
    ".github/prompts/sync-agent-docs.prompt.md",
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
    ".claude/skills/analysis-reporting/references/report-template.md",
    # Claude Code Task Skills (旧 commands)
    ".claude/skills/plan-analysis/SKILL.md",
    ".claude/skills/prepare-pr/SKILL.md",
    ".claude/skills/review-sql/SKILL.md",
    ".claude/skills/run-eda/SKILL.md",
    ".claude/skills/run-modeling/SKILL.md",
    ".claude/skills/summarize-analysis/SKILL.md",
    ".claude/skills/update-agent-docs/SKILL.md",
    ".claude/skills/sync-agent-docs/SKILL.md",
    # --- 共通ドキュメント ---
    # プロジェクト固有の知識のみを置く。作業手順・規約は skill 側が正本。
    "docs/agent/project-overview.md",
    "docs/agent/data-catalog.md",
    "docs/agent/metrics-and-definitions.md",
    # --- 手法別診断スキル(正本のみ検証。ルーターと references の両方) ---
    "docs/agent/diagnostics-reference-template.md",
    *[f".claude/skills/{rel}" for rel in DIAGNOSTICS_FILES],
]

# 他ツールの入口。正本へのリンクが外れていないかだけを見る(中身は正本側で検証済み)。
REQUIRED_SYMLINKS: dict[str, str] = {
    ".agents/skills": "../.claude/skills",
}


def main() -> None:
    """メイン処理。"""
    repo_root = Path(".")
    missing: list[str] = []

    for filepath in REQUIRED_FILES:
        if not (repo_root / filepath).exists():
            missing.append(filepath)

    broken_links: list[str] = []
    for link, target in REQUIRED_SYMLINKS.items():
        path = repo_root / link
        # リンクの実体と向き先だけを確認する(解決先のファイルは正本として検証済み)
        if not path.is_symlink() or path.readlink() != Path(target):
            broken_links.append(f"{link} -> {target}")

    if missing:
        print("ERROR: The following required agent documentation files are missing:")
        for m in missing:
            print(f"  - {m}")
    if broken_links:
        print("ERROR: The following symlinks to the canonical .claude/skills/ are broken:")
        for b in broken_links:
            print(f"  - {b}")
    if missing or broken_links:
        sys.exit(1)

    print(
        f"OK: All {len(REQUIRED_FILES)} required agent documentation files exist "
        f"({len(REQUIRED_SYMLINKS)} symlink(s) verified)."
    )


if __name__ == "__main__":
    main()
