---
description: "SQLクエリの正確性と安全性をレビューする"
---
Review the provided SQL query using the checklist from `.claude/skills/sql-analysis/SKILL.md`.

$ARGUMENTS

If no query is provided above, ask the user to paste the SQL query to review.

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
