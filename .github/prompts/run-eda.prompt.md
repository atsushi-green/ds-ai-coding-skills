---
agent: "agent"
description: "データセットのEDAを実装・実行する。引数: <dataset_path> <topic>"
---

# Skill: Run EDA

このリポジトリの規約に従って、データセットのEDA（探索的データ分析）を実装する。

Dataset:
${input:dataset_path:Path to the input dataset}

Topic:
${input:topic:Short description of the analysis topic}

`AGENTS.md`、`.github/skills/` 配下の関連スキル、`docs/agent/*` に従って以下を実施する。

1. 元データを不変の入力として読み込む。
2. 再利用可能なEDAコードを `src/analysis_project/` 配下に作成する。
3. EDAを実行するスクリプトを `scripts/` 配下に作成する。
4. 集計テーブルを `outputs/tables/` に保存する。
5. 図を `outputs/figures/` に保存する。
6. データ取り扱い、パス、Pythonスタイル、DataFrame操作、可視化についてリポジトリの規約に従う。
7. 可能であればEDAスクリプトと品質チェックを実行する。

最後に日本語で以下をまとめる。

- 作成・変更したファイル
- 実行したコマンド
- 生成した出力物
- 主な発見事項
- 残課題
