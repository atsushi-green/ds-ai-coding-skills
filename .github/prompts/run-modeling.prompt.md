---
agent: "agent"
description: "予測モデリングのワークフローを実装・評価する。引数: <dataset_path> <target> <task>"
---

# Skill: Run Modeling

このリポジトリの規約に従って、予測モデリングのワークフローを実装する。

Dataset:
${input:dataset_path:Path to the input dataset}

Target:
${input:target:Target variable}

Task:
${input:task:Prediction task description}

`AGENTS.md`、`.claude/skills/` 配下の関連スキル、`docs/agent/`（プロジェクト概要・データカタログ・指標定義）に従って以下を実施する。

1. 特徴量エンジニアリングのコードを `src/analysis_project/` 配下に作成する。
2. モデリングのコードを `src/analysis_project/` 配下に作成する。
3. 学習・評価を実行するスクリプトを `scripts/` 配下に作成する。
4. ベースラインモデルとシンプルなMLモデルを最低1つずつ比較する。
5. train/validation分割を使用する。
6. ターゲットリーケージを確認する。
7. 使った手法に対応する `*-diagnostics` skill（例: `predictive-modeling-diagnostics` の `references/ml-evaluation.md`・`references/tree-model.md`）の「必ず出す図・値」を出し、診断サマリー表を作成する。
8. 評価指標を `outputs/tables/` に保存する。
9. 関連する図を `outputs/figures/` に保存する（診断図は `outputs/diagnostics/<run>/`）。
10. 特徴量エンジニアリングのテストを追加・更新する。
11. 可能であればテストと品質チェックを実行する。

最後に日本語で以下をまとめる。

- 作成・変更したファイル
- 使用した特徴量
- ベースラインの結果
- モデルの結果
- 診断サマリー表（`| 診断項目 | 実測値 | 合格基準 | 判定 | 次アクション |`）
- 最良モデル
- 制限事項・注意点
- 実行したコマンド
- 残課題
