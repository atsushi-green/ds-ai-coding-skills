# 生存時間分析（KM・Cox・AFT）の必須セット

短縮名: `surv`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_surv/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: Kaplan-Meier、ログランク検定、Cox 比例ハザード、AFT、RMST、競合リスクの判定
- 扱わない: 時間を使わない二値アウトカム → `references/glm.md` / 生存予測モデルの CV・リーク → `predictive-modeling-diagnostics`（`references/ml-evaluation.md`） / 一般の検定作法 → `references/hypothesis-test.md`

## ライブラリ

- lifelines（`KaplanMeierFitter`、`CoxPHFitter`、`WeibullAFTFitter` / `LogNormalAFTFitter` / `LogLogisticAFTFitter`、`AalenJohansenFitter`、`add_at_risk_counts`、`proportional_hazard_test`、`logrank_test`、`restricted_mean_survival_time`、`k_fold_cross_validation`、`plotting.qq_plot`）
- 未導入なら `uv add lifelines`。scikit-survival は予測用途（`concordance_index_censored`）で併用可。Fine-Gray 回帰は lifelines に無いので「R 推奨（cmprsk / tidycmprsk）」と 1 行書く

## 必ず出す図

共通（どの手法でも出す）:

- KM 曲線（**95% CI + 打ち切りマーク + at-risk テーブル**、群があれば群別） — at-risk テーブルなしの曲線は出さない。右端で at-risk が数人の区間は薄く描く。RMST を使うなら時点 τ に縦破線

**使った手法の行だけ**を追加する:

| 使った手法 | 出す図 | 合格の読み方 |
|---|---|---|
| ログランク検定（群比較） | log(-log(S(t))) vs log(t) の群別プロット | 曲線が平行なら比例ハザード性を支持。交差すれば単一 HR・ログランクで要約せず RMST 差へ |
| Cox | Schoenfeld 残差プロット（`cph.check_assumptions(show_plots=True)` の図を共変量ごとに**個別に保存**）/ HR と 95% CI のフォレストプロット（HR = 1 に縦破線）。カテゴリ共変量があるなら、その変数の群別 log(-log(S(t))) プロットも | LOWESS が水平なら比例ハザード性を支持。傾きがあれば時間依存 / CI が 1 をまたぐ共変量を「効果あり」と書かない |
| AFT | 候補分布（Weibull / 対数正規 / 対数ロジスティック）ごとの Q-Q プロット（共変量なしの単変量当てはめ、`qq_plot`） | 点が対角線上に乗る分布が、仮定として妥当 |
| 競合リスクがある場合 | 原因別の累積発生率（CIF、`AalenJohansenFitter`）と 1 − KM（競合イベントを打ち切り扱い）の重ね描き | 1 − KM が CIF を上回る分が KM の過大評価。差が大きいなら KM で累積発生を語らない |

## 必ず出す値

| 区分 | 項目 | 合格基準 | 違反時の対処 |
|---|---|---|---|
| 共通 | 打ち切りの割合と種類（右 / 左 / 区間）、追跡期間の中央値、イベント数 | 報告に含む | 打ち切りが情報を持つ（脱落理由がアウトカムに依存）なら明記 |
| ログランク検定 | ログランク p | — | 曲線が交差するなら RMST 差（時点を明記）へ |
| Cox | **Schoenfeld 検定 p（共変量ごと + 全体）** | > 0.05 | 調整共変量なら層別化（`strata=`）、主要曝露なら時間依存係数、全体なら AFT / RMST |
| Cox | C-index（**学習データ外**。k-fold の平均 ± SD） | > 0.7 目安 | 予測用途なら時間依存 AUC も。in-sample の `cph.concordance_index_` は楽観側に寄るので報告しない |
| Cox | HR + 95% CI | `exp(coef)` で報告。基準カテゴリ・単位を明記 | — |
| Cox・AFT | イベント数 / 共変量数 | ≥ 10 イベント / 共変量（目安） | 共変量を減らす、正則化（`penalizer`） |
| AFT | 候補分布の AIC と採用した分布 | AIC 最小と Q-Q が整合 | 食い違うなら Q-Q を優先し理由を書く |
| AFT | 時間比 `exp(coef)` + 95% CI | 「生存時間が何倍に延びるか」として報告。基準・単位を明記 | — |
| RMST | 時点 τ と群間差 + 95% CI（ブートストラップ） | τ は事前に決め、全群で at-risk が十分残る時点にする | — |
| 競合リスク | 競合イベントの件数と割合 | 報告に含む | 原因別 Cox（競合イベントを打ち切り扱い）と CIF を併記 |

取得例（`df` は polars。列 `T`（時間）, `E`（イベント=1）, `group`, 共変量）。KM・Cox:

```python
import matplotlib.pyplot as plt
import numpy as np
from lifelines import CoxPHFitter, KaplanMeierFitter
from lifelines.plotting import add_at_risk_counts
from lifelines.statistics import proportional_hazard_test
from lifelines.utils import k_fold_cross_validation

kmf = {g: KaplanMeierFitter().fit(d["T"].to_numpy(), d["E"].to_numpy(), label=str(g))
       for (g,), d in df.group_by("group", maintain_order=True)}
fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)
for k in kmf.values():
    k.plot_survival_function(ax=ax, ci_show=True, show_censors=True)
add_at_risk_counts(*kmf.values(), ax=ax)  # at-risk テーブルなしの KM 曲線は出さない
df_pd = df.to_pandas()  # lifelines の Cox は列名付きの pandas DataFrame を前提とする
cph = CoxPHFitter().fit(df_pd, "T", "E")
ph = proportional_hazard_test(cph, df_pd, time_transform="rank").summary  # Schoenfeld 検定 p（共変量ごと）
hr_table = cph.summary[["exp(coef)", "exp(coef) lower 95%", "exp(coef) upper 95%"]]
c_cv = k_fold_cross_validation(CoxPHFitter(), df_pd, "T", "E", k=5, scoring_method="concordance_index", seed=0)
c_index_mean, c_index_sd = np.mean(c_cv), np.std(c_cv)  # 学習データ外の C-index
```

AFT（候補分布を比べる）:

```python
from lifelines import LogLogisticAFTFitter, LogNormalAFTFitter, WeibullAFTFitter
from lifelines import LogLogisticFitter, LogNormalFitter, WeibullFitter
from lifelines.plotting import qq_plot

aic = {f.__name__: f().fit(df_pd, "T", "E").AIC_ for f in (WeibullAFTFitter, LogNormalAFTFitter, LogLogisticAFTFitter)}
fig, axes = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
for ax, f in zip(axes, (WeibullFitter, LogNormalFitter, LogLogisticFitter), strict=True):
    qq_plot(f().fit(df_pd["T"], df_pd["E"]), ax=ax)  # 共変量なしの当てはめで分布の形を見る
```

RMST（2 群。τ は事前に決めた時点）:

```python
import polars as pl
from lifelines.utils import restricted_mean_survival_time

tau = 10.0  # 事前に決めた時点（全群で at-risk が十分残る時点）


def rmst(d: pl.DataFrame) -> float:
    """KM の階段関数の τ までの面積（survival_function_ を渡すと厳密に積分される）。"""
    km = KaplanMeierFitter().fit(d["T"].to_numpy(), d["E"].to_numpy())
    return restricted_mean_survival_time(km.survival_function_, t=tau)


g0, g1 = [d for _, d in df.group_by("group", maintain_order=True)]
rmst_diff = rmst(g1) - rmst(g0)
rng = np.random.default_rng(0)  # 差の CI は群ごとの復元抽出で
boot = [rmst(g1.sample(fraction=1, with_replacement=True, seed=int(rng.integers(2**31))))
        - rmst(g0.sample(fraction=1, with_replacement=True, seed=int(rng.integers(2**31)))) for _ in range(500)]
rmst_ci = np.percentile(boot, [2.5, 97.5])
```

競合リスク（`event` は 0 = 打ち切り、1 = 関心イベント、2 以上 = 競合イベント）:

```python
from lifelines import AalenJohansenFitter

t_, ev = df["T"].to_numpy(), df["event"].to_numpy()
cif = AalenJohansenFitter(seed=0).fit(t_, ev, event_of_interest=1).cumulative_density_  # 原因別 CIF
km_naive = KaplanMeierFitter().fit(t_, ev == 1)  # 競合を打ち切り扱いした 1 − KM（過大評価側）
```

## 落とし穴

- 比例ハザード性の検証なしに HR を報告しない
  ```python
  # NG: PH 仮定を確認せずに HR を報告する
  CoxPHFitter().fit(df, "T", "E").print_summary()
  ```
- 曲線が交差しているのに単一 HR で要約しない（RMST 差か時間依存係数）
- 追跡中に値が変わる変数を時点 0 の値で扱うと不死時間バイアスが生じる（時間依存共変量・ランドマーク解析）
- 競合リスクがあると KM は累積発生率を過大評価する（CIF へ）
- KM 曲線の右端（at-risk が数人）を過剰解釈しない。中央生存時間が定義できない場合はそう書く
- `restricted_mean_survival_time(..., return_variance=True)` の分散は min(T, τ) そのものの分散で、RMST 推定量の分散ではない（n に比例して桁違いに大きい）。これで CI を作らず、ブートストラップを使う
