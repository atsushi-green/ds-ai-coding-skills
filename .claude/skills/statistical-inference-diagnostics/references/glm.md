# GLM（ロジスティック・ポアソン・負の二項）の必須セット

短縮名: `glm`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_glm/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: ロジスティック回帰（二値）、ポアソン・負の二項（カウント）、GLM 全般（`family=`）
- 扱わない: 連続目的変数の線形回帰 → `references/ols.md` / 混合効果 GLMM → `references/mixed-effects.md` / 生存時間 → `references/survival.md`

## ライブラリ

- statsmodels — **二値も含めて `sm.GLM` に統一する**。`sm.Logit` は結果オブジェクトの属性名が違い（`resid_dev` / `resid_deviance`）、`pearson_chi2` も持たないため、診断を機械的に取りに行くと落ちる
  - 二値: `sm.GLM(y, X, family=sm.families.Binomial())`
  - カウント: `sm.GLM(y, X, family=sm.families.Poisson())` / `sm.NegativeBinomial(y, X)`
  - `statsmodels.stats.outliers_influence.variance_inflation_factor`
- scikit-learn（`calibration_curve`、`roc_auc_score`、`average_precision_score`、`brier_score_loss`、`confusion_matrix`、`StratifiedKFold`）
- statsmodels 未導入なら `uv add statsmodels`
- sklearn の `LogisticRegression` を使う場合は既定で L2 正則化が入るので `penalty=None` を明示（推論目的なら statsmodels を使うこと）

**入力の前提**: `X` は DataFrame、`y` は Series。numpy 配列を渡すと `res.params` が ndarray になり、以下のコードの `.rename()` / `params["x1"]` が全て落ちる。

## 評価はホールドアウトまたは CV の予測で行う

学習に使ったデータで AUC・Brier・キャリブレーションを計算しない。特に Brier とキャリブレーションは in-sample だと構造的に楽観側へ寄る。

```python
import numpy as np, pandas as pd, statsmodels.api as sm
from sklearn.model_selection import StratifiedKFold

def cv_predict(y, Xc, k=5, seed=0):
    """out-of-fold の予測確率を返す。全ての性能指標はこれに対して計算する。"""
    p = np.empty(len(y))
    for tr, te in StratifiedKFold(k, shuffle=True, random_state=seed).split(Xc, y):
        m = sm.GLM(y.iloc[tr], Xc.iloc[tr], family=sm.families.Binomial()).fit()
        p[te] = m.predict(Xc.iloc[te])
    return p
```

係数・オッズ比の報告は全データで再フィットしたモデルから出す。性能指標だけ out-of-fold を使う。

## 必ず出す図（二値分類は 1 枚 4 パネル）

- ROC 曲線 — AUC、**陽性率、n、陽性件数を必ず併記**。陽性率が 10% 未満なら主指標は PR 曲線に切り替える
- PR 曲線 — ベースライン（= 陽性率）を水平破線で。曲線がベースラインから明確に離れていれば合格
- キャリブレーションプロット（**十分位 = `strategy="quantile"`**） — 対角線に沿えば合格。S 字は過信、逆 S 字は過小
- **binned residual plot** — 予測確率で分位ビンに切り、ビン内平均残差を ±2SE バンドと重ねる。バンド外が 5% 程度までなら合格、系統的な曲線は関数形の誤り
  - 二値の deviance 残差 vs 予測値は y が 0/1 のため 2 本のバンドに分かれ、「無構造かどうか」を目視判定できない。二値では必ずこちらを使う
- カウント系: 観測度数 vs 期待度数（ゼロを含む rootogram または棒の重ね描き） — ゼロの棒が一致すれば合格
- カウント系: deviance 残差 vs 線形予測子

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| 係数の SE | SE < 1e2（分離の一次判定はこちら） | 完全分離。カテゴリ統合・変数削減が先。Firth は statsmodels 未実装なので `firthlogist`。**正則化で通した係数に通常の CI は出ない**ので OR + CI を報告する用途では選ばない |
| 係数の絶対値 | \|係数\| < 10（**変数のスケールに依存**するので二値・標準化済み変数での目安） | 上に同じ |
| EPV（少数クラスの件数 / 説明変数の数） | ≥ 10 | 変数削減・正則化。図を描く前にここで止める |
| AUC（+ 陽性率・n・陽性件数） | 文脈依存。必ず並べて報告 | 陽性率 < 10% なら PR-AUC を主指標に |
| Brier score | ベースライン `p(1-p)`（p = 陽性率）より小さい | Platt / Isotonic 較正（学習に使っていないデータで） |
| VIF (max) | < 10 | 変数削除。**定数項を含む design matrix に対して計算する**（外すと値が壊れる） |
| カウント系: Pearson χ² / df | ≈ 1（> 1.5 で過分散の疑い） | 負の二項、準ポアソン（`.fit(scale="X2")`） |
| カウント系: 観測ゼロ数 vs 期待ゼロ数 | 乖離なし | `ZeroInflatedPoisson` / `ZeroInflatedNegativeBinomialP` |
| 混同行列の閾値 | 明記されている（0.5 が目的に合うか問う） | コスト・目標再現率から閾値を決める |
| 反復測定・パネル構造 | ない、または cluster robust SE を使っている | `.fit(cov_type="cluster", cov_kwds={"groups": g})` |

`Pearson χ² / df` は**グループ化されたカウントに対する統計量**で、個票の二値データでは意味を持たない。二値モデルでこの値を過分散の根拠にしない。

## 取得例

```python
import numpy as np, pandas as pd, statsmodels.api as sm
from sklearn.calibration import calibration_curve
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from statsmodels.stats.outliers_influence import variance_inflation_factor

Xc = sm.add_constant(X)                       # X は DataFrame、y は Series
res = sm.GLM(y, Xc, family=sm.families.Binomial()).fit()

# オッズ比は必ず 95% CI とセットで
odds = (np.exp(res.params).rename("OR").to_frame()
        .join(np.exp(res.conf_int()).set_axis(["lo95", "hi95"], axis=1)))

# VIF は定数項込みの行列で計算し、報告時に const を落とす
vif = pd.Series([variance_inflation_factor(Xc.values, i) for i in range(Xc.shape[1])],
                index=Xc.columns).drop("const")

# 性能指標は out-of-fold の予測に対して
p = cv_predict(y, Xc)
base = y.mean()
print(f"n={len(y)} pos={int(y.sum())} rate={base:.3f} EPV={min(y.sum(), (1-y).sum())/ X.shape[1]:.1f}\n"
      f"AUC={roc_auc_score(y, p):.3f} PR-AUC={average_precision_score(y, p):.3f} "
      f"Brier={brier_score_loss(y, p):.4f} (baseline {base*(1-base):.4f}) VIFmax={vif.max():.1f}")

# キャリブレーション図用（等幅ビンが既定なので quantile を明示）
frac_pos, mean_pred = calibration_curve(y, p, n_bins=10, strategy="quantile")
```

### binned residual plot

```python
def binned_residuals(y, p, n_bins=20):
    """二値専用。予測確率の分位ビンごとの平均残差と ±2SE バンドを返す（SE は p(1-p) 由来）。"""
    df = pd.DataFrame({"p": np.asarray(p), "r": np.asarray(y) - np.asarray(p)})
    df["bin"] = pd.qcut(df.p.rank(method="first"), n_bins, labels=False)
    g = df.groupby("bin").agg(p=("p", "mean"), resid=("r", "mean"), n=("r", "size"))
    g["se2"] = 2 * np.sqrt(df.groupby("bin").p.apply(lambda s: (s * (1 - s)).mean()) / g.n)
    return g   # resid を p に対して散布し、±se2 を折れ線で重ねる
```

### カウント系

```python
# 曝露量が行ごとに違うなら offset（入れ忘れると係数の意味が変わる。expo は全て正・y と同じ行順）
pois = sm.GLM(cnt, Xc, family=sm.families.Poisson(), offset=np.log(expo)).fit()
print("Pearson/df =", round(pois.pearson_chi2 / pois.df_resid, 2))

# 過分散だったとき
quasi = sm.GLM(cnt, Xc, family=sm.families.Poisson(), offset=np.log(expo)).fit(scale="X2")
nb    = sm.NegativeBinomial(cnt, Xc, offset=np.log(expo)).fit(disp=0)   # alpha を推定する
print("NB alpha =", round(nb.params.iloc[-1], 3))

# ゼロ過剰
obs0, exp0 = int((cnt == 0).sum()), float(np.exp(-pois.fittedvalues).sum())
from statsmodels.discrete.count_model import ZeroInflatedPoisson, ZeroInflatedNegativeBinomialP
```

`sm.families.NegativeBinomial()` は **alpha を推定しない**。既定 `alpha=1.0` のまま `ValueWarning` を出して通ってしまうので、alpha を推定したいときは `sm.NegativeBinomial` か `NegativeBinomialP` を使う。

## 落とし穴

- **AUC だけ報告しない。** キャリブレーションが崩れていれば予測確率は意思決定に使えない
- **学習データで性能を測らない。** out-of-fold かホールドアウトで評価する
- **Hosmer-Lemeshow 検定は n > 1000 でほぼ必ず棄却される。** キャリブレーション図を主にする
- **混同行列は閾値を明記して出す。** 0.5 が目的（コスト・再現率要件）に合うかを必ず問う
- **オッズ比は `np.exp(params)` と `np.exp(conf_int())` をセットで。** 対数オッズのまま「◯倍」と書かない。連続変数は「1 単位増えたときのオッズ倍率」、ダミーは基準カテゴリとの比だと報告に書く
  ```python
  # NG: 対数オッズをそのまま倍率として報告する
  print(f"x1 の効果は {res.params['x1']:.2f} 倍")
  ```
- **`offset` と `exposure` を混同しない。** `offset=` は対数を取った値、`exposure=` は生の曝露量。両方指定したり log を二重に取ったりする事故が多い
- **完全分離は例外を投げない。** statsmodels は係数 666、SE 21627 のような値を `ConvergenceWarning` 付きで返してくるだけなので、判定は例外ではなく SE の大きさで行う
- **反復測定を素の SE で報告しない。** 同一個体が複数行に出るデータは cluster robust SE を使う。上の判定表のどの項目にも引っかからずに通過してしまう抜け穴
