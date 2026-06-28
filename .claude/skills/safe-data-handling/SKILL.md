---
name: safe-data-handling
description: Use this when reading, writing, moving, copying, modifying, deleting, or generating data files — including any operation that touches data/raw, data/external, data/interim, data/processed, or outputs directories.
---

# Skill: Safe Data Handling

Use this skill before reading, writing, moving, modifying, deleting, or generating data files.

## Hard Rules

- **Never** commit raw data, credentials, API keys, tokens, or customer-level records.
- **Never** directly modify, overwrite, delete, or regenerate raw data.
- Treat `data/raw/` and `data/external/` as **immutable**.
- Write derived data to `data/interim/`, `data/processed/`, or `outputs/`.
- Before writing output, confirm the target path is **not** under `data/raw/` or `data/external/`.

## Recommended Workflow

1. **Identify** whether input data is raw, external, interim, processed, or output.
2. **Read** raw/external data as immutable input — never modify the source.
3. **Write** generated artifacts to a separate output path (`data/interim/`, `data/processed/`, or `outputs/`).
4. **Summarize** files read and written at the end of the operation.

## Directory Roles

| Directory | Role | Mutable? |
|-----------|------|----------|
| `data/raw/` | Original source data | No |
| `data/external/` | Third-party reference data | No |
| `data/interim/` | Intermediate transforms | Yes |
| `data/processed/` | Final cleaned/derived data | Yes |
| `outputs/` | Figures, tables, reports | Yes |

## PII and Customer-Level Records

- Do not include personally identifiable information (PII) or customer-level records in committed files.
- If analysis requires customer-level data, keep it in `data/raw/` (gitignored) and never commit.
- Aggregated or anonymized outputs are acceptable for `data/processed/` or `outputs/`.
- When in doubt, ask before writing customer-level data to any path.
