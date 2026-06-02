---
agent: "agent"
description: "Update AGENTS.md, skills, and docs/agent when repo conventions change"
---
When repository conventions change, update the relevant agent documentation:

1. Check if `AGENTS.md` routing table needs updating.
2. Check if any `.github/skills/*/SKILL.md` needs updating.
3. Check if any `docs/agent/*.md` needs updating.

Rules:
- Keep `AGENTS.md` thin — it is a router, not a detailed guide.
- Do not duplicate detailed rules across multiple files.
- Prefer linking to skill files instead of copying content.
- Run `uv run python scripts/validate_agent_docs.py` after changes.
