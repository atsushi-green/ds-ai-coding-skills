# GLM（ロジスティック・ポアソン・負の二項）の必須セット

短縮名: `glm`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_glm/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: ロジスティック回帰（二値）、ポアソン・負の二項（カウント）、GLM 全般（`family=`）
- 扱わない: 連続目的変数の線形回帰 → `references/ols.md` / 混合効果 GLMM → `references/mixed-effects.md` / 生存時間 → `references/survival.md`

## ライブラリ

- statsmodels（`sm.Logit`、`sm.GLM(family=sm.families.Poisson())`、`NegativeBinomial`、`variance_inflation_factor`）
- scikit-learn（`calibration_curve`、`roc_auc_score`、`average_precision_score`、`brier_score_loss`、`confusion_matrix`）
- statsmodels 未導入なら `uv add statsmodels`（`LogisticRegression` は既定で L2 正則化が入るので `penalty=None` を明示）

## 必ず出す図（二値分類は 1 枚 4 パネル）

- ROC 曲線 — AUC と **陽性率を必ず併記**。陽性率が 10% 未満なら主指標は PR 曲線に切り替える
- PR 曲線 — ベースライン（= 陽性率）を水平破線で。曲線がベースラインから明確に離れていれば合格
- キャリブレーションプロット（10 分位） — 対角線に沿えば合格。S 字は過信、逆 S 字は過小
- deviance 残差 vs 予測値（線形予測子） — 無構造なら合格。曲線は関数形の誤り
- カウント系: 観測度数 vs 期待度数（ゼロを含む rootogram または棒の重ね描き） — ゼロの棒が一致すれば合格

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| 係数の絶対値と SE | \|係数\| < 10 かつ SE < 1e3 | 完全分離。Firth 補正・正則化・変数のカテゴリ統合 |
| AUC（+ 陽性率） | 文脈依存。陽性率と並べて報告 | 陽性率 < 10% なら PR-AUC を主指標に |
| Brier score | 小さいほど良い。ベースライン（陽性率で常に予測）より小さい | Platt / Isotonic 較正（学習に使っていないデータで） |
| VIF (max) | < 10 | 変数削除 |
| カウント系: Pearson χ² / df | ≈ 1（> 1.5 で過分散の疑い） | 負の二項、準ポアソン（`scale="X2"`） |
| カウント系: 観測ゼロ数 vs 期待ゼロ数 | 乖離なし | ZIP / ZINB |
| 混同行列の閾値 | 明記されている（0.5 が目的に合うか問う） | コスト・目標再現率から閾値を決める |

取得例（動作確認済み）:

```python
import numpy as np, statsmodels.api as sm
from sklearn.calibration import calibration_curve
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss

res = sm.Logit(y, sm.add_constant(X)).fit(disp=0)
p = res.predict(sm.add_constant(X))
print(f"陽性率={y.mean():.3f} AUC={roc_auc_score(y, p):.3f} "
      f"PR-AUC={average_precision_score(y, p):.3f} Brier={brier_score_loss(y, p):.3f}")
odds = np.exp(res.params).to_frame("OR").join(np.exp(res.conf_int()))  # OR と 95% CI をセットで
frac_pos, mean_pred = calibration_curve(y, p, n_bins=10)  # キャリブレーション図用
```

## 落とし穴

- AUC だけ報告しない。キャリブレーションが崩れていれば予測確率は意思決定に使えない
- Hosmer-Lemeshow 検定は n > 1000 でほぼ必ず棄却される。キャリブレーション図を主にする
- 混同行列は閾値を明記して出す。0.5 が目的（コスト・再現率要件）に合うかを必ず問う
- オッズ比は `np.exp(params)` と `np.exp(conf_int())` をセットで。対数オッズのまま「◯倍」と書かない
  ```python
  # NG: 対数オッズをそのまま倍率として報告する
  print(f"x1 の効果は {res.params['x1']:.2f} 倍")
  ```
- カウントデータで曝露量（期間・人数）が異なるなら `offset=np.log(exposure)` を入れる
