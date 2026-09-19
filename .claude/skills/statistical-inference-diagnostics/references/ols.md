# 線形回帰の必須セット

短縮名: `ols`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_ols/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 線形回帰・重回帰・OLS / WLS、Lasso / Ridge / ElasticNet、分位点回帰
- 扱わない: ロジスティック・ポアソン・負の二項 → `references/glm.md` / 混合効果・パネル → `references/mixed-effects.md` / 自己回帰・時系列 → `predictive-modeling-diagnostics`（`references/time-series.md`）

## ライブラリ

- statsmodels（推論: `sm.OLS` / `smf.ols`、`het_breuschpagan`、`variance_inflation_factor`、`OLSInfluence`、`QuantReg`）
- scikit-learn（正則化: `LassoCV` / `RidgeCV` / `ElasticNetCV`。必ず `make_pipeline(StandardScaler(), ...)` で使う）
- scipy.stats（`shapiro`、`probplot`）。statsmodels 未導入なら `uv add statsmodels`（sklearn だけでは検定値が出ない）

## 必ず出す図

- 残差 4 点セット（1 枚 4 パネル）
  - 残差 vs 予測値（LOWESS 線付き） — LOWESS が水平で点が無構造なら合格。扇形は不等分散、曲線は非線形
  - Q-Q プロット — 点が対角線上なら合格。両裾の乖離は裾の重さ
  - Scale-Location（√|標準化残差| vs 予測値） — 水平なら合格。右上がりは不等分散
  - レバレッジ vs 標準化残差（点サイズ = Cook's D、4/n に破線） — 右上・右下に孤立点がなければ合格
- 正則化時: CV 誤差 vs α（対数軸。最小 α と 1-SE ルールの α に縦破線）+ 係数パス — 最小 α が探索範囲の端でなければ合格
- 分位点回帰時: 分位点 0.1〜0.9 ごとの係数と 95% CI（OLS 係数を水平破線） — 係数が分位点で変わるかが見える

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| Breusch-Pagan p | > 0.05 | `fit(cov_type="HC3")` で再推定（係数は不変、SE のみ修正）。両方の SE を並べる |
| VIF (max) | < 10（厳格 < 5） | 変数削除、中心化（交互作用項）、Ridge |
| Cook's D > 4/n の件数 | 0 件目安 | 該当行の実データを表示（判定 = 確認。除外は人間判断） |
| Durbin-Watson | 1.5〜2.5 | 観測に順序があるなら `cov_type="HAC"` か `predictive-modeling-diagnostics`（`references/time-series.md`） へ |
| Shapiro-Wilk p（n < 5000） | > 0.05 | n 大なら中心極限定理で緩和可と明記。小標本ならブートストラップ CI |
| 正則化時: 採用 α・非ゼロ係数数 | 1-SE ルール α との差を併記 | 最小 α が端なら探索範囲を広げる |

取得例（動作確認済み）:

```python
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson

Xc = sm.add_constant(X.to_pandas())  # statsmodels には変数名付きの pandas で渡す。回帰も VIF も定数項込みで
res = sm.OLS(y, Xc).fit()
bp_p = het_breuschpagan(res.resid, res.model.exog)[1]
vif_max = max(variance_inflation_factor(Xc.to_numpy(), i) for i in range(1, Xc.shape[1]))
cooks_n = int((res.get_influence().cooks_distance[0] > 4 / res.nobs).sum())
dw = durbin_watson(res.resid)
```

## 落とし穴

- VIF は定数項込みのデザイン行列で計算する。素の X を渡すと過大評価になる
  ```python
  # NG: 定数項なしの X で VIF → 値が過大になる
  vif = [variance_inflation_factor(X.to_numpy(), i) for i in range(X.shape[1])]
  ```
- R² が高くても不等分散なら SE は信頼できない。R² は診断の代わりにならない
- Cook's D が大きい点を機械的に除外しない。実データを見て理由（入力ミス・別母集団）を特定する
- Lasso で選ばれた係数に通常の p 値・CI を付けない（post-selection inference）。必要ならブートストラップで選択頻度を出す
- 正則化の前に標準化する。ただし Pipeline の外で全データに `fit_transform` するとリーク
