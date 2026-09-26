---
name: analysis-reporting
description: Use this when summarizing analysis results, writing reports, documenting experiment outcomes, or presenting model evaluation — including structuring findings in Japanese with conclusions, facts, assumptions, interpretations, and caveats.
---

# Skill: Analysis Reporting

Use this skill when summarizing analysis results, experiment outcomes, or model evaluation.

## Language

- Reports should be written in **Japanese** unless otherwise requested.

## Structure

1. **結論** — Start with the conclusion or key finding.
2. **事実** — Present objective facts from the data.
3. **仮定** — State assumptions made during analysis.
4. **解釈** — Provide interpretations and implications.
5. **制約・注意点** — Mention limitations, caveats, and possible bias.

A fill-in-the-blank report skeleton with all of the above, plus the reproducibility
section, is in [references/report-template.md](.claude/skills/analysis-reporting/references/report-template.md).

## Diagnostics Summary（診断サマリー）

When any statistical / ML / causal / simulation / optimization method was applied, add a **診断サマリー**
section between 事実 and 解釈, containing the table defined by the matching `*-diagnostics` skill:

| 診断項目 | 実測値 | 合格基準 | 判定 | 次アクション |
|---|---|---|---|---|

- 判定 is one of `OK` / `要対処` / `確認`（人間の判断待ち）. Every `要対処` needs a 次アクション.
- The analysis code only saves the figures and prints (or saves) the diagnostic values as a table of metric names and numbers. Copy 実測値 from that output, then write 合格基準, 判定 and 次アクション in the report by reading the values and figures against the skill's criteria. Do not build verdict strings, criteria text or next actions with if-branches or f-strings in the analysis code (an `assert` that stops an invalid analysis, such as an SRM check, is fine).
- Include the table even when every item is OK.
- Link the figure directory (`outputs/diagnostics/<YYYYMMDD-HHMM>_<skill>/`) instead of embedding figures.

## Required Context

Include the following when relevant:

- **データ期間**: Date range of the analysis.
- **フィルタ条件**: Filters applied to the data.
- **サンプルサイズ**: Number of records or observations.
- **指標定義**: How key metrics are calculated.

## Reproducibility Notes

Every report should include or reference:

- **入力データパス**: Path to input data used.
- **クエリ/スクリプトパス**: Path to the query, notebook, or script that produced the results.
- **出力パス**: Path to output artifacts (figures, tables, reports).
- **実行コマンド**: Command used to generate results.

## Tone

- Use **business-friendly language** for summaries intended for stakeholders.
- Keep **technical details** available for reviewers (in appendix or linked notebook).
- Avoid jargon when simpler terms suffice.
- Be precise about what the data shows vs. what is inferred.
