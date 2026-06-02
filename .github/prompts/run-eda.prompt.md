---
agent: 'agent'
description: 'Implement and run EDA for a dataset using this repository’s data science conventions'
---

Implement EDA for the dataset below.

Dataset:
${input:dataset_path:Path to the input dataset}

Topic:
${input:topic:Short description of the analysis topic}

Follow `AGENTS.md`, repository custom instructions, relevant skills, and `docs/agent/*`.

Expected work:

1. Read the raw dataset as immutable input.
2. Create reusable EDA code under `src/analysis_project/`.
3. Create a script under `scripts/` to run the EDA.
4. Save summary tables under `outputs/tables/`.
5. Save figures under `outputs/figures/`.
6. Use repository conventions for data handling, paths, Python style, DataFrame operations, and visualization.
7. Run the EDA script and quality checks if possible.

At the end, summarize in Japanese:

- files created or changed
- commands run
- outputs generated
- main findings
- any remaining issues