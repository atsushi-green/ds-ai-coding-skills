---
name: run-eda
description: "データセットのEDAを実装・実行する。引数: <dataset_path> <topic>"
disable-model-invocation: true
---

# Skill: Run EDA

このリポジトリの規約に従って、データセットのEDA（探索的データ分析）を実装する。

呼び出し時の引数として、データセットパスと分析トピックを受け取る。引数が空または不明な場合は、ユーザーに以下を確認する。

- **データセットパス**（例: `data/raw/titanic/train.csv`）
- **分析トピック**（日本語または英語での簡単な説明）

`CLAUDE.md`、`.claude/skills/` 配下の関連スキル、`docs/agent/`（プロジェクト概要・データカタログ・指標定義）に従って以下を実施する。

1. 元データを不変の入力として読み込む。
2. 再利用可能なEDAコードを `src/analysis_project/` 配下に作成する。
3. EDAを実行するスクリプトを `scripts/` 配下に作成する。
4. 集計テーブルを `outputs/tables/` に保存する。
5. 図を `outputs/figures/` に保存する。
6. データ取り扱い、パス、Pythonスタイル、DataFrame操作、可視化についてリポジトリの規約に従う。
7. 欠測・外れ値を扱う場合は `unsupervised-eda-diagnostics` skill（`references/missing-data.md`）の「必ず出す図・値」を出し、診断サマリー表を作成する。
8. 可能であればEDAスクリプトと品質チェックを実行する。

最後に日本語で以下をまとめる。

- 作成・変更したファイル
- 実行したコマンド
- 生成した出力物
- 主な発見事項
- 残課題
