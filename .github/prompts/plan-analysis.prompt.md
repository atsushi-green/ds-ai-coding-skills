---
agent: "agent"
description: "分析を始める前に構造化された分析計画を作成する"
---

# Skill: Plan Analysis

コードを書く前に、構造化された分析計画を作成する。

## 確認・整理する項目

1. **Objective**: どんな問いに答えようとしているか。
2. **Data sources**: 使用するデータ（テーブル、ファイル、API）。
3. **Unit of analysis**: 1行が何を表すか。
4. **Key metrics**: どの指標を計算するか、その定義。
5. **Risks**: 何が問題になりうるか（データ品質、リーケージ、バイアス、欠損値など）。
6. **Validation**: 結果をどう検証するか。
7. **Outputs**: 期待される成果物（テーブル、チャート、レポート、モデルなど）。

計画は日本語でまとめる。プロジェクト固有の文脈については `docs/agent/metrics-and-definitions.md` と `docs/agent/data-catalog.md` を参照する。

## 分析ワークフロー全体

この skill は下記の1に相当する。計画時には後続フェーズまで見通しておく。

1. **分析開始前** — 分析目的と意思決定への影響を確認する / 必要なデータの有無と品質を確認する / 分析計画を作成する（この skill）/ 指標定義を `docs/agent/metrics-and-definitions.md` で確認する
2. **データ探索** — 基本統計量・欠損値・異常値を確認する / 粒度とキーの一意性を確認する / 結果をNotebookに記録する（`run-eda` skill）
3. **分析・検証** — 分析ロジックを実装する / 既知の事実との整合性で妥当性を確認する / エッジケースを検討する（`run-modeling` skill、手法に応じた `*-diagnostics` skill）
4. **成果物作成** — 図表を `outputs/` に保存する / 分析結果をまとめる（`summarize-analysis` skill）/ 再現手順を記録する
5. **レビュー** — 品質チェックを実行する（`bash scripts/run_quality_checks.sh`）/ PR概要を作成する（`prepare-pr` skill）/ レビュアーに依頼する
