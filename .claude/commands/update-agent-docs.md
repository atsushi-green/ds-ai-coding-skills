---
description: "リポジトリの規約が変更されたときにCLAUDE.md・スキル・docs/agentを更新する"
---
When repository conventions change, update the relevant agent documentation.

$ARGUMENTS

If the above is empty, first ask the user what convention or rule has changed.

Steps:

1. Check if `CLAUDE.md` routing table or rules need updating.
2. Check if any `.claude/skills/*/SKILL.md` needs updating.
3. Check if any `docs/agent/*.md` needs updating.

Rules:

- Keep `CLAUDE.md` thin — it is a router, not a detailed guide.
- Do not duplicate detailed rules across multiple files.
- Prefer linking to skill files instead of copying content.
- Run `uv run python scripts/validate_agent_docs.py` after changes.
