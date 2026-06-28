---
description: "データセットのEDAを実装・実行する。引数: <dataset_path> <topic>"
---
Implement EDA for a dataset following this repository's conventions.

Dataset and topic specified by the user:
$ARGUMENTS

If the above is empty or unclear, ask the user for:
- **Dataset path** (e.g., `data/raw/titanic/train.csv`)
- **Analysis topic** (brief description in Japanese or English)

Then follow `CLAUDE.md`, relevant skills in `.claude/skills/`, and `docs/agent/*` to complete the following:

1. Read the raw dataset as immutable input.
2. Create reusable EDA code under `src/analysis_project/`.
3. Create a script under `scripts/` to run the EDA.
4. Save summary tables under `outputs/tables/`.
5. Save figures under `outputs/figures/`.
6. Use repository conventions for data handling, paths, Python style, DataFrame operations, and visualization.
7. Run the EDA script and quality checks if possible.

At the end, summarize in Japanese:

- 作成・変更したファイル
- 実行したコマンド
- 生成した出力物
- 主な発見事項
- 残課題
