---
name: visualization
description: Use this when creating, modifying, reviewing, or saving charts, figures, plots, or visual summaries — including matplotlib/seaborn code, EDA figures, report figures, dashboards, or any task involving Japanese chart labels, color palettes, or figure styling.
---

# Skill: Visualization

Use this skill whenever the user asks to:

- Plot, visualize, chart, or graph data.
- Create figures for EDA, reports, dashboards, or presentations.
- Modify or improve existing matplotlib / seaborn code.
- Save figures to disk for reports or notebooks.

## Library

- Use **matplotlib** for charts.
- Use **seaborn** alongside matplotlib for theming, palettes, and statistical plots.

## Global Setup (do this first)

At the start of any notebook or script that produces figures, set the theme once. `font_scale` enlarges all text elements proportionally, so individual `fontsize=` arguments are usually unnecessary.

```python
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(
    style="whitegrid",
    palette="muted",
    font_scale=1.2,
)
```

### Japanese text

If any text (titles, labels, legends, annotations) contains Japanese, configure a CJK-capable font, **otherwise characters render as tofu (□□□)**.

Preferred approach (cross-platform):

```python
import japanize_matplotlib  # uv add japanize-matplotlib
```

Alternative (set an installed CJK font explicitly):

```python
plt.rcParams["font.family"] = "Noto Sans CJK JP"  # or "IPAexGothic", "Hiragino Sans", "Yu Gothic"
```

## Figure Creation

- **Do not** use the stateful `plt.figure(...)` / `plt.plot(...)` style.
- **Always** create figures and axes explicitly, and prefer `constrained_layout=True` over `tight_layout()`:

```python
fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
```

- Use the **object-oriented** API: `ax.set_title()`, `ax.set_xlabel()`, `ax.plot()`, etc.
- `figsize=(10, 6)` is a reasonable default. Adjust to content: wide time series → `(12, 4)`, square scatter → `(6, 6)`, multi-panel → scale up accordingly.

## Color Map / Color Palette

Choose by data type:

- **Categorical**: `"muted"`, `"Set2"`, `"colorblind"` (seaborn palettes).
- **Sequential (continuous)**: `"viridis"`, `"cividis"`, `"mako"` — perceptually uniform.
- **Diverging**: `"coolwarm"`, `"RdBu"`, `"vlag"`.
- **Forbidden**: `"jet"`, `"rainbow"` — not perceptually uniform, poor for colorblind viewers.

## Font Size

`sns.set_theme(font_scale=1.2)` covers most cases. Override per-element **only when needed** (e.g. a long title needs to be smaller, or one label needs emphasis):

```python
ax.set_title("...", fontsize=18)
```

Do **not** repeat `fontsize=` on every call — it is redundant when `font_scale` is set.

## Axis Scale Guidelines

- **Bar charts**: start y-axis at 0 (`ax.set_ylim(bottom=0)`). Truncated bars are misleading.
- **Line / scatter**: do **not** force y-axis to 0 — it can hide meaningful variation. Let matplotlib autoscale, or set limits based on the data range.
- **Log scale**: use `ax.set_yscale("log")` when data spans multiple orders of magnitude.

## Legend

- Use `ax.legend()` only when ≥2 series are plotted.
- If the auto-placement overlaps data, set explicitly: `ax.legend(loc="upper left")` or place outside: `ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5))`.

## Saving

- Save final figures under `outputs/figures/`.
- Use the path utilities from `src/analysis_project/paths.py`.

```python
from analysis_project.paths import outputs_dir, ensure_parent_dir

# 出力パスを構成して保存
output_path = outputs_dir() / "figures" / "survival_by_class.png"
ensure_parent_dir(output_path)
fig.savefig(output_path, dpi=150)
```

- Use descriptive snake_case filenames: `monthly_sales_2024h1.png`, not `fig1.png`.
- DPI guidance:
  - Notebook / README / slides: `dpi=150`
  - Publication / print: `dpi=300`
- Always call `plt.close(fig)` after saving to free memory.

```python
fig.savefig("outputs/figures/monthly_sales.png", dpi=150, bbox_inches="tight")
plt.close(fig)
```

## Chart Quality Checklist

Before finalizing a chart, verify:

- [ ] **Title** clearly describes what the chart shows.
- [ ] **Axis labels** include units where applicable (e.g. "売上 (万円)", "Latency (ms)").
- [ ] **Font sizes** are readable (rely on `font_scale=1.2` as baseline).
- [ ] **Color palette** is perceptually uniform / colorblind-friendly (no jet/rainbow).
- [ ] **Date range** noted in title, subtitle, or annotation when relevant.
- [ ] **Sample / filter note** when data is subsetted (e.g. "n=1,234, 2024年1月〜6月").
- [ ] **Bar charts** start y-axis at 0; other chart types use sensible limits.
- [ ] **Legend** present when multiple series; placement does not overlap data.
- [ ] **Japanese text** renders correctly (japanize-matplotlib or CJK font configured).
- [ ] **Saved** to `outputs/figures/` with descriptive filename, followed by `plt.close(fig)`.

## Example

```python
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
import japanize_matplotlib  # noqa: F401  # 日本語フォント有効化

sns.set_theme(style="whitegrid", palette="muted", font_scale=1.2)

Path("outputs/figures").mkdir(parents=True, exist_ok=True)

fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)

ax.bar(categories, values)
ax.set_title("月別売上推移 (2024年1月〜6月)")
ax.set_xlabel("月")
ax.set_ylabel("売上 (万円)")
ax.set_ylim(bottom=0)  # 棒グラフは0起点

fig.savefig("outputs/figures/monthly_sales_2024h1.png", dpi=150, bbox_inches="tight")
plt.close(fig)
```
