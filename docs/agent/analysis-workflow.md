# 分析ワークフロー

## 1. 分析開始前

- [ ] 分析目的と意思決定への影響を確認する
- [ ] 必要なデータの有無と品質を確認する
- [ ] 分析計画を作成する（`.github/prompts/plan-analysis.prompt.md` を利用）
- [ ] 指標定義を `docs/agent/metrics-and-definitions.md` で確認する

## 2. データ探索

- [ ] データの基本統計量を確認する
- [ ] 欠損値・異常値を確認する
- [ ] 粒度とキーの一意性を確認する
- [ ] 探索結果をNotebookに記録する

## 3. 分析・検証

- [ ] 分析ロジックを実装する
- [ ] 結果の妥当性を確認する（既知の事実との整合性）
- [ ] エッジケースを検討する

## 4. 成果物作成

- [ ] 図表を `outputs/` に保存する
- [ ] 分析結果をまとめる（`.github/prompts/summarize-analysis.prompt.md` を利用）
- [ ] 再現手順を記録する

## 5. レビュー

- [ ] コードの品質チェックを実行する（`bash scripts/run_quality_checks.sh`）
- [ ] PR概要を作成する（`.github/prompts/prepare-pr.prompt.md` を利用）
- [ ] レビュアーに依頼する
