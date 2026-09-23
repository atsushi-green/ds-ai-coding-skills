# GLM（ロジスティック・ポアソン・負の二項）の必須セット

短縮名: `glm`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_glm/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 係数・オッズ比・率比を解釈する GLM。ロジスティック回帰（二値）、ポアソン・負の二項（カウント）、ガンマ等の `family=` 全般
- 扱わない: 連続目的変数の線形回帰 → `references/ols.md` / 混合効果 GLMM → `references/mixed-effects.md` / 生存時間 → `references/survival.md` / 係数を解釈せず予測性能を報告する分類モデル → `predictive-modeling-diagnostics`（`references/ml-evaluation.md`） / 傾向スコアのモデル → `causal-inference-diagnostics`（`references/causal-observational.md`）
- 下の性能指標を出すための `StratifiedKFold` は推定の部品なので、これだけで `ml-evaluation.md` は適用しない

## ライブラリ

- statsmodels — **二値も含めて `sm.GLM` に統一する**。`sm.Logit` は結果オブジェクトの属性名が違い（`resid_dev` / `resid_deviance`）、`pearson_chi2` も持たないため、診断を機械的に取りに行くと落ちる
  - 二値: `sm.GLM(y, X, family=sm.families.Binomial())`
  - カウント: `sm.GLM(y, X, family=sm.families.Poisson())`、過分散なら `sm.NegativeBinomial(y, X)`（alpha を推定する）。`sm.families.NegativeBinomial()` は alpha を推定せず、既定 `alpha=1.0` のまま `ValueWarning` を出して通ってしまう
- scikit-learn（`calibration_curve`、`roc_auc_score`、`average_precision_score`、`brier_score_loss`、`StratifiedKFold`）。sklearn の `LogisticRegression` は既定で L2 正則化が入るので、推論目的なら statsmodels を使う
- statsmodels には変数名付きの pandas で渡す（`df.to_pandas()`）。numpy 配列だと `res.params` が ndarray になり、変数名で係数を引けない。未導入なら `uv add statsmodels`

## 必ず出す図

性能の図（ROC・PR・キャリブレーション）は、学習に使っていないデータの予測（out-of-fold かホールドアウト）で描く。in-sample だと Brier とキャリブレーションは構造的に楽観側へ寄る。係数・オッズ比は全データで再フィットしたモデルから出す。

**目的変数の型の行だけ**を出す:

| 目的変数 | 出す図 | 合格の読み方 |
|---|---|---|
| 二値（1 枚 4 パネル） | ROC 曲線（AUC・陽性率・n・陽性件数を併記）/ PR 曲線（陽性率を水平破線）/ キャリブレーションプロット（十分位 = `strategy="quantile"`）/ binned residual plot（予測確率の分位ビンごとの平均残差と ±2SE バンド） | 陽性率 < 10% なら PR を主に読む / 曲線が陽性率の線から明確に離れる / 対角線に沿う（S 字は過信、逆 S 字は過小）/ バンド外が 5% 程度まで。系統的な曲線は関数形の誤り |
| カウント | 観測度数 vs 期待度数（ゼロを含む rootogram か棒の重ね描き）/ deviance 残差 vs 線形予測子 | ゼロの棒が一致する / 無構造 |
| 連続（ガンマ・逆ガウス） | deviance 残差 vs 線形予測子 + 残差 Q-Q / ビン別の平均 vs 分散（両対数） | 無構造・直線上 / 分散関数の仮定どおり（ガンマは分散 ∝ 平均² なので傾き 2 付近） |

二値の deviance 残差 vs 予測値は y が 0/1 のため 2 本の帯に分かれ、無構造かどうかを目視判定できない。二値では binned residual plot を使う。

## 必ず出す値

| 区分 | 項目 | 合格基準 | 違反時の対処 |
|---|---|---|---|
| 共通 | 係数の SE | SE < 1e2（二値では完全分離の一次判定） | 二値なら完全分離。カテゴリ統合・変数削減が先。Firth は statsmodels 未実装なので `firthlogist`。正則化で通した係数に通常の CI は出ないので、OR + CI を報告する用途では選ばない |
| 共通 | VIF (max) | < 10 | 変数削除。**定数項を含む design matrix に対して計算する**（外すと値が壊れる） |
| 共通 | 反復測定・パネル構造 | ない、または cluster robust SE を使っている | `.fit(cov_type="cluster", cov_kwds={"groups": g})` |
| 二値 | 係数の絶対値 | \|係数\| < 10（変数のスケールに依存するので、二値・標準化済み変数での目安） | 上の SE の行と同じ |
| 二値 | EPV（少数クラスの件数 / 説明変数の数） | ≥ 10 | 変数削減・正則化。図を描く前にここで止める |
| 二値 | AUC・PR-AUC（+ 陽性率・n・陽性件数） | 文脈依存。必ず並べて報告 | 陽性率 < 10% なら PR-AUC を主指標に |
| 二値 | Brier score | ベースライン `p(1-p)`（p = 陽性率）より小さい | Platt / Isotonic 較正（学習に使っていないデータで） |
| 二値（混同行列を出すとき） | 閾値 | 明記されている（0.5 が目的に合うか問う） | コスト・目標再現率から閾値を決める |
| カウント | Pearson χ² / df | ≈ 1（> 1.5 で過分散の疑い） | 負の二項、準ポアソン（`.fit(scale="X2")`） |
| カウント | 観測ゼロ数 vs 期待ゼロ数 | 乖離なし | `ZeroInflatedPoisson` / `ZeroInflatedNegativeBinomialP` |
| カウント | 曝露量の扱い | 行ごとに曝露量が違うなら `offset=np.log(曝露量)` が入っている | 入れ忘れると係数の意味（率比）が変わる |

Pearson χ² / df はカウントの過分散の目安で、個票のカウントにもそのまま使える。個票の二値データでは意味を持たないので、二値モデルの過分散の根拠にしない。

取得例（`df` は polars。二値の目的変数 `y`、説明変数の列名リスト `cols`）。二値:

```python
import numpy as np
import polars as pl
import statsmodels.api as sm
from sklearn.calibration import calibration_curve
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from statsmodels.stats.outliers_influence import variance_inflation_factor

pdf = df.to_pandas()  # statsmodels には変数名付きの pandas で渡す
y, Xc = pdf["y"], sm.add_constant(pdf[cols])
res = sm.GLM(y, Xc, family=sm.families.Binomial()).fit()  # 係数・OR は全データで
ci = np.exp(res.conf_int())
odds = pl.DataFrame({"変数": list(res.params.index), "OR": np.exp(res.params.to_numpy()),
                     "lo95": ci[0].to_numpy(), "hi95": ci[1].to_numpy()})  # OR は必ず 95% CI とセット
vif = [variance_inflation_factor(Xc.to_numpy(), i) for i in range(1, Xc.shape[1])]  # 定数項込みで計算し const は除く
p = np.empty(len(y))  # 性能指標は out-of-fold の予測確率で
for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(Xc, y):
    p[te] = sm.GLM(y.iloc[tr], Xc.iloc[tr], family=sm.families.Binomial()).fit().predict(Xc.iloc[te])
rate = y.mean()
vals = {"n": len(y), "陽性件数": int(y.sum()), "陽性率": rate, "EPV": min(y.sum(), len(y) - y.sum()) / len(cols),
        "SE_max": res.bse.max(), "AUC": roc_auc_score(y, p), "PR_AUC": average_precision_score(y, p),
        "Brier": brier_score_loss(y, p), "Brier_baseline": rate * (1 - rate), "VIF_max": max(vif)}
print(pl.DataFrame({"項目": list(vals), "値": list(vals.values())}, strict=False))  # int・float・文字列が混ざっても落ちない
frac_pos, mean_pred = calibration_curve(y, p, n_bins=10, strategy="quantile")  # 等幅ビンが既定なので quantile を明示
# binned residual plot 用: 予測確率の分位ビンごとの平均残差と ±2SE（SE は p(1-p) 由来）
binned = (pl.DataFrame({"p": p, "r": y.to_numpy() - p})
          .with_columns(bin=(pl.col("p").rank("ordinal") - 1) * 20 // pl.len())
          .group_by("bin").agg(p=pl.col("p").mean(), resid=pl.col("r").mean(),
                               se2=2 * ((pl.col("p") * (1 - pl.col("p"))).mean() / pl.len()).sqrt())
          .sort("bin"))  # resid を p に対して散布し、±se2 を折れ線で重ねる
```

カウント（`cnt` は件数の Series、曝露量 `expo` は全て正で `cnt` と同じ行順）:

```python
pois = sm.GLM(cnt, Xc, family=sm.families.Poisson(), offset=np.log(expo)).fit()
disp = pois.pearson_chi2 / pois.df_resid  # ≈ 1。> 1.5 で過分散の疑い
obs0, exp0 = int((cnt == 0).sum()), float(np.exp(-pois.fittedvalues).sum())  # 観測ゼロ数 vs 期待ゼロ数
quasi = sm.GLM(cnt, Xc, family=sm.families.Poisson(), offset=np.log(expo)).fit(scale="X2")  # 準ポアソン
nb = sm.NegativeBinomial(cnt, Xc, offset=np.log(expo)).fit(disp=0)  # alpha を推定する（最後のパラメータ）
nb_alpha = nb.params.iloc[-1]
```

## 落とし穴

- **AUC だけ報告しない。** キャリブレーションが崩れていれば予測確率は意思決定に使えない
- **学習データで性能を測らない。** out-of-fold かホールドアウトで評価する
- **Hosmer-Lemeshow 検定は n > 1000 でほぼ必ず棄却される。** キャリブレーション図を主にする
- **オッズ比は `np.exp(params)` と `np.exp(conf_int())` をセットで。** 対数オッズのまま「◯倍」と書かない。連続変数は「1 単位増えたときのオッズ倍率」、ダミーは基準カテゴリとの比だと報告に書く
  ```python
  # NG: 対数オッズをそのまま倍率として報告する
  print(f"x1 の効果は {res.params['x1']:.2f} 倍")
  ```
- **`offset` と `exposure` を混同しない。** `offset=` は対数を取った値、`exposure=` は生の曝露量。両方指定したり log を二重に取ったりする事故が多い
- **完全分離は例外を投げない。** statsmodels は係数 666、SE 21627 のような値を `ConvergenceWarning` 付きで返してくるだけなので、判定は例外ではなく SE の大きさで行う
- **反復測定を素の SE で報告しない。** 同一個体が複数行に出るデータは cluster robust SE を使う。上の判定表のどの項目にも引っかからずに通過してしまう抜け穴
