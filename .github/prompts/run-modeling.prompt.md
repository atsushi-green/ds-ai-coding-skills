---
agent: 'agent'
description: 'Implement and evaluate a simple predictive model using this repository’s ML conventions'
---

Implement a predictive modeling workflow for the dataset below.

Dataset:
${input:dataset_path:Path to the input dataset}

Target:
${input:target:Target variable}

Task:
${input:task:Prediction task description}

Follow `AGENTS.md`, repository custom instructions, relevant skills, and `docs/agent/*`.

Expected work:

1. Create feature engineering code under `src/analysis_project/`.
2. Create modeling code under `src/analysis_project/`.
3. Create a script under `scripts/` to run training and evaluation.
4. Compare at least one baseline model with one simple ML model.
5. Use a train/validation split.
6. Check for target leakage.
7. Save metrics under `outputs/tables/`.
8. Save relevant figures under `outputs/figures/`.
9. Add or update tests for feature engineering.
10. Run tests and quality checks if possible.

At the end, summarize in Japanese:

- files created or changed
- features used
- baseline result
- model results
- best model
- limitations
- commands run
- remaining issues