---
applyTo: "**/*.sql"
---
Follow `.github/skills/sql-analysis/SKILL.md` for all SQL files:
- Use explicit column names; avoid SELECT *.
- Use CTEs for readability.
- Add date filters for large tables.
- Validate join cardinality and row counts.
- Never run DROP, TRUNCATE, DELETE, or UPDATE unless explicitly requested.
