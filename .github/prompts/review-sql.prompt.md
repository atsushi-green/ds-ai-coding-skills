---
agent: "agent"
description: "Review SQL for correctness and safety"
---
Review the provided SQL query using the checklist from `.github/skills/sql-analysis/SKILL.md`.

Check for:
- `SELECT *` usage (should use explicit columns)
- Missing date filters on large tables
- Join cardinality issues (1:1, 1:N, M:N)
- Row count validation before and after joins
- Destructive statements (DROP, TRUNCATE, DELETE, UPDATE)
- Unclear metric definitions
- NULL handling
- Duplicate risk
- Implicit cross joins

Provide feedback in Japanese with specific line references and suggested fixes.
