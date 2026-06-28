---
description: "分析結果を日本語でまとめる"
---
Summarize the analysis findings following `.claude/skills/analysis-reporting/SKILL.md`.

$ARGUMENTS

If no specific analysis or findings are provided above, ask the user which analysis to summarize (e.g., notebook path, script output, or paste the findings directly).

Use the structure, required context, and reproducibility notes defined in the skill file:

1. **結論** — Start with the conclusion or key finding.
2. **事実** — Present objective facts from the data.
3. **仮定** — State assumptions made during analysis.
4. **解釈** — Provide interpretations and implications.
5. **制約・注意点** — Mention limitations, caveats, and possible bias.

Include where relevant: データ期間、フィルタ条件、サンプルサイズ、指標定義、入力データパス、クエリ/スクリプトパス、出力パス、実行コマンド。

Write the summary in Japanese.
