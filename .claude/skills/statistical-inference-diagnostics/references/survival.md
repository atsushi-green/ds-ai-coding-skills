# 生存時間分析（KM・Cox）の必須セット

短縮名: `surv`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_surv/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: Kaplan-Meier、ログランク検定、Cox 比例ハザード、AFT、RMST、競合リスクの判定
- 扱わない: 時間を使わない二値アウトカム → `references/glm.md` / 生存予測モデルの CV・リーク → `predictive-modeling-diagnostics`（`references/ml-evaluation.md`） / 一般の検定作法 → `references/hypothesis-test.md`

## ライブラリ

- lifelines（`KaplanMeierFitter`、`CoxPHFitter`、`add_at_risk_counts`、`proportional_hazard_test`、`logrank_test`、`restricted_mean_survival_time`）
- 未導入なら `uv add lifelines`。scikit-survival は予測用途（`concordance_index_censored`）で併用可

## 必ず出す図

- KM 曲線（**95% CI + 打ち切りマーク + at-risk テーブル**、群別） — at-risk テーブルなしの曲線は出さない。右端で at-risk が数人の区間は薄く描く
- Schoenfeld 残差プロット（`cph.check_assumptions(show_plots=True)` の図を共変量ごとに**個別に保存**） — LOWESS が水平なら比例ハザード性を支持。傾きがあれば時間依存
- log(-log(S(t))) vs log(t) プロット（群別） — 曲線が平行なら比例ハザード性を支持。交差すれば単一 HR で要約しない
- Cox: HR と 95% CI のフォレストプロット（HR = 1 に縦破線） — CI が 1 をまたぐ共変量を「効果あり」と書かない

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| 打ち切りの割合と種類（右 / 左 / 区間）、追跡期間の中央値 | 報告に含む | 打ち切りが情報を持つ（脱落理由がアウトカムに依存）なら明記 |
| ログランク p（群比較時） | — | 曲線が交差するなら RMST 差（時点を明記）へ |
| **Schoenfeld 検定 p（共変量ごと + 全体）** | > 0.05 | 調整共変量なら層別化（`strata=`）、主要曝露なら時間依存係数、全体なら AFT / RMST |
| C-index | > 0.7 目安（学習データ外で） | 予測用途なら時間依存 AUC も |
| HR + 95% CI | `exp(coef)` で報告。基準カテゴリ・単位を明記 | — |
| イベント数 / 共変量数 | ≥ 10 イベント / 共変量（目安） | 共変量を減らす、正則化（`penalizer`） |

取得例（動作確認済み。`df` は polars。列 `T`（時間）, `E`（イベント=1）, `group`, 共変量）:

```python
from lifelines import KaplanMeierFitter, CoxPHFitter
from lifelines.plotting import add_at_risk_counts
from lifelines.statistics import proportional_hazard_test

kmf = {g: KaplanMeierFitter().fit(d["T"].to_numpy(), d["E"].to_numpy(), label=str(g))
       for (g,), d in df.group_by("group", maintain_order=True)}
fig, ax = plt.subplots(figsize=(8, 6)); [k.plot_survival_function(ax=ax, ci_show=True, show_censors=True) for k in kmf.values()]
add_at_risk_counts(*kmf.values(), ax=ax)  # at-risk テーブルなしの KM 曲線は出さない
df_pd = df.to_pandas()  # lifelines の Cox は列名付きの pandas DataFrame を前提とする
cph = CoxPHFitter().fit(df_pd, "T", "E")
ph = proportional_hazard_test(cph, df_pd, time_transform="rank").summary  # Schoenfeld 検定 p（共変量ごと）
hr_table = cph.summary[["exp(coef)", "exp(coef) lower 95%", "exp(coef) upper 95%"]]; c_index = cph.concordance_index_
```

## 落とし穴

- 比例ハザード性の検証なしに HR を報告しない
  ```python
  # NG: PH 仮定を確認せずに HR を報告する
  CoxPHFitter().fit(df, "T", "E").print_summary()
  ```
- 曲線が交差しているのに単一 HR で要約しない（RMST 差か時間依存係数）
- 追跡中に値が変わる変数を時点 0 の値で扱うと不死時間バイアスが生じる（時間依存共変量・ランドマーク解析）
- 競合リスクがあると KM は累積発生率を過大評価する（Fine-Gray / CIF へ）
- KM 曲線の右端（at-risk が数人）を過剰解釈しない。中央生存時間が定義できない場合はそう書く
