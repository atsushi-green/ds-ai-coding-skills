---
name: notebook-workflow
description: Use this when creating, editing, executing, or reviewing Jupyter notebooks — including cell structure, kernel management, extracting reusable logic to src/, and ensuring notebooks are restartable.
---

# Skill: Notebook Workflow

Use this skill when creating, editing, executing, or reviewing Jupyter notebooks.

## Purpose of Notebooks

- Notebooks are for **exploration and communication**.
- Reusable logic should be extracted to `src/analysis_project/`.

## Rules

- Keep notebooks **restartable from a clean kernel** (Kernel → Restart & Run All must work).
- Avoid hidden state — do not rely on cells being run in a non-linear order.
- Do not include secrets or customer-level records in notebook outputs.
- Prefer saving final charts and tables to `outputs/`.

## Naming Convention

```
NNN_short_description.ipynb
```

Example: `001_data_exploration.ipynb`, `002_feature_analysis.ipynb`

## Automation

- Use **papermill** for parameterized notebook execution when automation is needed.

```bash
uv run papermill notebooks/input.ipynb notebooks/output.ipynb -p param_name value
```

## Structure

1. **Header cell** (Markdown): Title, author, date, objective.

   ```markdown
   # タイトル
   - **作成者**: 名前
   - **作成日**: YYYY-MM-DD
   - **目的**: この分析で明らかにしたいこと
   ```

2. **Imports**: All imports in the first code cell.
3. **Configuration**: Parameters, paths, constants.
4. **Analysis**: Exploratory or analytical cells.
5. **Summary**: Key findings and next steps.

## Cleanup Before Commit

- Clear large outputs that are not essential for review.
- Ensure no credentials or PII in cell outputs.
- Verify the notebook runs end-to-end with a fresh kernel.
