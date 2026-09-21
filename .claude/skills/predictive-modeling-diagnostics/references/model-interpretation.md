# モデル解釈（SHAP・permutation・PDP/ICE）の必須セット

短縮名: `interp`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_interp/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: permutation importance、SHAP（Tree / Kernel / Linear）、PDP / ICE、ALE、代理モデル
- 扱わない: 因果効果の推定 → `causal-inference-diagnostics`（references/causal-observational.md・causal-quasi-experimental.md） / 木の構造診断 → `references/tree-model.md` / 線形モデルの係数推論 → `statistical-inference-diagnostics`（references/ols.md・glm.md）

## ライブラリ

- shap（`TreeExplainer`、`KernelExplainer` + `shap.kmeans`、`plots.beeswarm` / `plots.bar`）
- scikit-learn（`permutation_importance`、`PartialDependenceDisplay.from_estimator(kind="both")`）
- ALE: PyALE または alibi（任意）。未導入なら `uv add shap`。ALE が無ければ「相関が強い特徴の PDP は参考値」と明記

## 必ず出す図

- permutation importance（validation / test 側、`n_repeats ≥ 10`）の棒 + エラーバー — エラーバーが重ならない上位が読めれば合格
- SHAP summary（beeswarm）+ bar — 上位特徴の符号と分布が読めれば合格。木系は `TreeExplainer`、それ以外は背景データを k-means で 50〜100 点に要約した `KernelExplainer`
- 上位 3〜5 特徴の PDP に ICE を重ね、x 軸に rug（データ密度）を描く — ICE が PDP と平行なら交互作用小。密度の薄い領域の PDP は読まない
- 特徴量間相関ヒートマップ — \|r\| > 0.8 のペアを列挙し、その特徴の重要度は「分散して見える」と注記

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| 「解釈 ≠ 因果」の 1 文 | 報告冒頭にある | 因果を主張するなら `causal-inference-diagnostics` へ |
| SHAP 加法性の検算（数件） | `base_value + Σshap ≒ 予測値`（差 < 1e-6 目安） | `model_output`（log-odds か確率か）の指定を確認 |
| 相関 \|r\| > 0.8 のペア | 列挙され、重要度の分散が注記されている | グループ permutation（相関ペアを同時に置換）で再計算 |
| 重要度順位の安定性（fold / seed 間の Spearman ρ） | ρ > 0.7 | 「上位 k 個の集合」として報告し、順位を主張しない |
| 代理モデル使用時: 忠実度 | 元モデルとの R² / accuracy を報告 | 低ければ代理モデルの説明を使わない |

取得例（動作確認済み。回帰モデルの例）:

```python
import shap
from scipy.stats import spearmanr
from sklearn.inspection import permutation_importance, PartialDependenceDisplay

pi = permutation_importance(model, X_va, y_va, n_repeats=10, random_state=0)
top = list(X_va.columns[np.argsort(-pi.importances_mean)[:3]])
sv = shap.TreeExplainer(model)(X_va)  # 木以外: shap.KernelExplainer(model.predict, shap.kmeans(X_tr, 50))
additivity_gap = np.abs(sv.base_values + sv.values.sum(axis=1) - model.predict(X_va)).max()  # 加法性の検算
rho = spearmanr(pi.importances_mean, np.abs(sv.values).mean(axis=0)).statistic  # 手法間の順位一致
PartialDependenceDisplay.from_estimator(model, X_va, top, kind="both")  # PDP + ICE（deciles が rug）
```

## 落とし穴

- PDP は他特徴を固定するため、相関が強いと存在しない組合せを評価する。\|r\| > 0.8 なら ALE を併用する
- SHAP 値が大きい =「そう変えれば結果が変わる」ではない。介入効果は因果設計でしか言えない
- 線形モデルの係数を標準化せずに重要度として比較しない
  ```python
  # NG: 単位の異なる生の係数を並べて「重要度」と呼ぶ
  sorted(zip(X.columns, np.abs(lr.coef_), strict=True), key=lambda t: -t[1])
  ```
- 代理モデル（決定木で GBDT を説明する等）を使うなら忠実度（元モデルとの R² / accuracy）を必ず出す
- 分類器の SHAP は `model_output` が log-odds か確率かで値の意味が変わる。報告に明記する
