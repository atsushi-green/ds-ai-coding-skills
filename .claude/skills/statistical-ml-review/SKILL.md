---
name: statistical-ml-review
description: Use this when reviewing statistical analysis, experiments, model evaluation, or ML work done by someone else (a notebook, PR, or report) — checking that the required context is stated and that every method applied comes with the figures and values required by the matching *-diagnostics skill. When running an analysis yourself, apply the matching *-diagnostics skill directly.
---

# Skill: Statistical and ML Review

Use this skill when **reviewing** statistical analysis, experiments, model evaluation, or ML work.
When you run an analysis yourself, the matching `*-diagnostics` skill applies directly; this skill
only checks that its required outputs (図・値・判定表) are present and that the context below is stated.

## Required Context for Any Analysis

The analysis must clearly state:

- **Target variable**: What are we predicting or measuring?
- **Unit of analysis**: What does one row represent?
- **Time period**: What date range does the data cover?
- **Sample definition**: What population is included?
- **Exclusions**: What was filtered out, and why?
- **Assumptions**: What statistical or business assumptions apply?
- **Leakage risks**: Could future information leak into training data?
- **Evaluation metric**: How will success be measured?
- **Baseline**: What is the simplest comparison point?

## Method → Diagnostics Skill

The `*-diagnostics` skills are two-tier: a family router (`SKILL.md`) plus one `references/<method>.md` per method.
For each method used in the code, open the router, then the reference named below, and check its 「必ず出す図」「必ず出す値」
against the outputs. Trigger vocabulary (library / class / function names) is listed in each router's description and routing table.

| Method used | Router skill | Reference to check |
|---|---|---|
| Linear regression, Lasso / Ridge, quantile regression | [statistical-inference-diagnostics](.claude/skills/statistical-inference-diagnostics/SKILL.md) | `references/ols.md` |
| Logistic / Poisson / negative binomial, GLM | same | `references/glm.md` |
| Mixed effects, panel fixed effects | same | `references/mixed-effects.md` |
| Hypothesis tests (t / χ² / ANOVA / nonparametric) | same | `references/hypothesis-test.md` |
| Kaplan-Meier, Cox, AFT, competing risks | same | `references/survival.md` |
| MCMC (cmdstanpy) | same | `references/bayesian-mcmc.md` |
| Supervised ML evaluation (splits, CV, tuning, leakage) | [predictive-modeling-diagnostics](.claude/skills/predictive-modeling-diagnostics/SKILL.md) | `references/ml-evaluation.md` |
| Decision tree, random forest, GBDT | same | `references/tree-model.md` |
| SHAP, permutation importance, PDP / ICE | same | `references/model-interpretation.md` |
| ARIMA / state space / Prophet / VAR, change points, forecasting | same | `references/time-series.md` |
| A/B test | [causal-inference-diagnostics](.claude/skills/causal-inference-diagnostics/SKILL.md) | `references/ab-test.md` |
| Propensity score, IPW, DML | same | `references/causal-observational.md` |
| DiD, IV, RDD, synthetic control | same | `references/causal-quasi-experimental.md` |
| Missing data, outliers, EDA preprocessing | [unsupervised-eda-diagnostics](.claude/skills/unsupervised-eda-diagnostics/SKILL.md) | `references/missing-data.md` |
| k-means, hierarchical, GMM, DBSCAN | same | `references/clustering.md` |
| PCA, factor analysis, UMAP / t-SNE | same | `references/dimensionality-reduction.md` |
| Anomaly detection | same | `references/anomaly-detection.md` |
| Monte Carlo, discrete-event simulation | [simulation-optimization-diagnostics](.claude/skills/simulation-optimization-diagnostics/SKILL.md) | `references/simulation.md` |
| LP / MIP, metaheuristics | same | `references/optimization.md` |

## Review Procedure

1. List every method applied as an analysis in its own right (search the code for the library calls named in each router's description and routing table). Do not count helper usages that the routers exclude — e.g. a PCA projection inside a clustering figure, a propensity-score `LogisticRegression`, `smf.ols` used to estimate an event study, random numbers for permutation or bootstrap baselines. Within one reference, check only the rows for the method actually used; a missing figure for a method that was not used is not a gap.
2. For each method, compare the outputs with the reference's 「必ず出す図」「必ず出す値」 and 「落とし穴」, and the router's 「出力と報告」 format.
3. Check that the report contains the 診断サマリー table (`| 診断項目 | 実測値 | 合格基準 | 判定 | 次アクション |`) and that every `要対処` has a next action.
4. Report gaps as a table, in Japanese:

   | 手法 | 欠けている図・値 | 結論への影響 | 推奨アクション |
   |---|---|---|---|

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
- [ ] For every method applied, are the figures and values required by its `*-diagnostics` skill present, with the 判定表?
