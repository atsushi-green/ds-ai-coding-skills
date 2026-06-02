---
name: sql-analysis
description: Use this when writing, reviewing, or modifying SQL queries — including SELECT, CTEs, joins, aggregations, window functions, and validating query correctness or performance.
---

# Skill: SQL Analysis

Use this skill when writing, reviewing, or modifying SQL queries.

## Rules

- Use **explicit column names** — avoid `SELECT *` except for quick exploration.
- Use **CTEs** (Common Table Expressions) for readability and modularity.
- Add **date filters** for large fact tables to limit scan scope.
- Check **join keys** and **join cardinality** before writing joins.
- **Validate row counts** before and after joins to detect fanout or data loss.
- Avoid **implicit cross joins**.
- **Never** run `DROP`, `TRUNCATE`, `DELETE`, or `UPDATE` unless explicitly requested by the user.
- If destructive SQL is requested, propose a dry-run, backup, or transaction strategy first.

## Query Structure

```sql
WITH base AS (
    SELECT
        column_a,
        column_b,
        event_date
    FROM schema.table_name
    WHERE event_date BETWEEN '2024-01-01' AND '2024-01-31'
),
aggregated AS (
    SELECT
        column_a,
        COUNT(*) AS row_count,
        SUM(column_b) AS total_b
    FROM base
    GROUP BY column_a
)
SELECT
    column_a,
    row_count,
    total_b
FROM aggregated
ORDER BY row_count DESC;
```

## Review Checklist

Before finalizing a query, verify:

- [ ] Are **grains** (unit of analysis per row) clear?
- [ ] Are **date ranges** explicit and appropriate?
- [ ] Are **NULLs** handled (filtered, coalesced, or documented)?
- [ ] Are **duplicates** considered (distinct, dedup logic)?
- [ ] Is **join cardinality** validated (1:1, 1:N, M:N)?
- [ ] Are **business definitions** documented in comments or CTEs?
- [ ] Are **row counts** checked before and after key transformations?
- [ ] Is there any risk of **implicit cross join**?
- [ ] Are **destructive operations** absent or explicitly approved?
