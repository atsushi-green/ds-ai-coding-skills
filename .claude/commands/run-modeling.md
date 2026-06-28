---
description: "予測モデリングのワークフローを実装・評価する。引数: <dataset_path> <target> <task>"
---
Implement a predictive modeling workflow following this repository's conventions.

Dataset, target variable, and task specified by the user:
$ARGUMENTS

If the above is empty or unclear, ask the user for:
- **Dataset path** (e.g., `data/raw/titanic/train.csv`)
- **Target variable** (e.g., `Survived`)
- **Prediction task** (brief description, e.g., "乗客の生存を予測する二値分類")

Then follow `CLAUDE.md`, relevant skills in `.claude/skills/`, and `docs/agent/*` to complete the following:

1. Create feature engineering code under `src/analysis_project/`.
2. Create modeling code under `src/analysis_project/`.
3. Create a script under `scripts/` to run training and evaluation.
4. Compare at least one baseline model with one simple ML model.
5. Use a train/validation split.
6. Check for target leakage.
7. Save metrics under `outputs/tables/`.
8. Save relevant figures under `outputs/figures/`.
9. Add or update tests for feature engineering.
10. Run tests and quality checks if possible.

At the end, summarize in Japanese:

- 作成・変更したファイル
- 使用した特徴量
- ベースラインの結果
- モデルの結果
- 最良モデル
- 制限事項・注意点
- 実行したコマンド
- 残課題
