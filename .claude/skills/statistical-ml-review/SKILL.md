---
name: statistical-ml-review
description: Use this when performing statistical analysis, hypothesis testing, A/B testing, model training, model evaluation, feature engineering, or any machine learning task — including documenting assumptions, leakage risks, and validation strategies.
---

# Skill: Statistical and ML Review

Use this skill when doing statistical analysis, experiments, model evaluation, or ML work.

## Required Context for Any Analysis

Before starting analysis, clearly state:

- **Target variable**: What are we predicting or measuring?
- **Unit of analysis**: What does one row represent?
- **Time period**: What date range does the data cover?
- **Sample definition**: What population is included?
- **Exclusions**: What was filtered out, and why?
- **Assumptions**: What statistical or business assumptions apply?
- **Leakage risks**: Could future information leak into training data?
- **Evaluation metric**: How will success be measured?
- **Baseline**: What is the simplest comparison point?

## Experiments and Causal Inference

- Distinguish **correlation** from **causation** explicitly.
- Mention **confidence intervals** or uncertainty when reporting results.
- Avoid **overclaiming** — state what the data supports, not what you hope it shows.
- Document the **experimental design** (A/B test, pre-post, observational, etc.).

## Machine Learning

- **Separate** train, validation, and test sets clearly.
- **Avoid leakage** — no future data in training, no target leakage in features.
- **Document preprocessing** — encoding, scaling, imputation, feature engineering.
- **Compare against a simple baseline** before reporting model performance.
- **Consider cross-validation** — especially for small datasets where a single split may be unreliable.
- **Report limitations** — data quality, sample bias, generalizability.
- **Version** datasets and model artifacts when practical.

## Review Checklist

- [ ] Is the target variable well-defined?
- [ ] Is the unit of analysis clear?
- [ ] Are train/test splits time-aware if data is temporal?
- [ ] Is there a baseline comparison?
- [ ] Are evaluation metrics appropriate for the problem?
- [ ] Are limitations documented?
- [ ] Is the analysis reproducible?
