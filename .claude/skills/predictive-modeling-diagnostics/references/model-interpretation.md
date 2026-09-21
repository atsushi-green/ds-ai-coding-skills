# モデル解釈（SHAP・permutation・PDP/ICE）の必須セット

短縮名: `interp`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_interp/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: permutation importance、SHAP（Tree / Kernel / Linear）、PDP / ICE、ALE、代理モデル
- 扱わない: 因果効果の推定 → `causal-inference-diagnostics`（references/causal-observational.md・causal-quasi-experimental.md） / 木の構造診断 → `references/tree-model.md` / 線形モデルの係数推論 → `statistical-inference-diagnostics`（references/ols.md・glm.md）

## ライブラリ

- shap（`TreeExplainer`、`KernelExplainer` + `shap.kmeans`、`plots.beeswarm` / `plots.bar`）。未導入なら `uv add shap`
- scikit-learn（`permutation_importance`、`PartialDependenceDisplay.from_estimator(kind="both")`）
- ALE: PyALE（`from PyALE import ale`）または alibi（任意）。未導入なら `uv add PyALE`。ALE が無ければ「相関が強い特徴の PDP は参考値」と明記

## 必ず出す図

特徴量が多いときは、どの図も**上位 15〜20 特徴に絞って描き**、全特徴の重要度は図ではなく表で出す（図から外した特徴数を図中か注記に書く）。20 本を超える横棒・beeswarm は軸ラベルが潰れて読めず、「読めれば合格」の判定ができない。

- permutation importance（validation / test 側、`n_repeats ≥ 10`、分類は `scoring` を明示）の棒 + エラーバー — エラーバーが重ならない上位が読めれば合格。特徴量が多いなら平均重要度の降順で上位 15〜20 本だけ描く
- SHAP summary（beeswarm）+ bar — 上位特徴の符号と分布が読めれば合格。木系は `TreeExplainer`、それ以外は背景データを k-means で 50〜100 点に要約した `KernelExplainer`。`max_display`（既定 10）を 15〜20 に設定する — 残りは「Sum of N other features」に畳まれるので、その N を報告に書く
- 上位 3〜5 特徴の PDP に ICE を重ね、x 軸に rug（データ密度）を描く — ICE が PDP と平行なら交互作用小。密度の薄い領域の PDP は読まない。ICE は `subsample`（既定 1000 本）を 50〜200 に落とす。全件描くと線が黒く潰れて平行性も分布も読めない
- 特徴量間相関ヒートマップ — \|r\| > 0.8 のペアを列挙し、その特徴の重要度は「分散して見える」と注記。特徴量が 20 を超えるなら図に出すのは上位 15〜20 特徴分の小行列にとどめ（`annot` は切る）、全体は \|r\| > 0.8 のペア表で代替する

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| 「解釈 ≠ 因果」の 1 文 | 報告冒頭にある | 因果を主張するなら `causal-inference-diagnostics` へ |
| permutation importance の `scoring` | 運用で使う指標を明示する（順位で使うなら `roc_auc` / `average_precision`、閾値を決めて使うなら `f1` / `recall` / `precision`、回帰は `neg_root_mean_squared_error` など）。報告にも指標名を書く | `scoring` を省くと推定器の `score()`（分類器 = accuracy、回帰 = R²）が使われる。不均衡データの accuracy は少数派を全部外しても下がらず、重要度が 0 付近に潰れて順位が読めない。指標を指定して再計算する。指標が変われば重要度の順位も変わるので、指標名のない重要度は解釈しない |
| SHAP 加法性の検算（数件） | `base_value + Σshap ≒ 予測値`（差 < 1e-6 目安） | 分類器の `TreeExplainer` は既定が対数オッズ（`model_output="raw"`）なので `predict_proba` と比べない。対数オッズのまま検算して報告に明記するか、確率で解釈したいなら下記の `model_output="probability"` に切り替える |
| 図に描いた特徴数 / 全特徴数 | 上位に絞ったなら、全特徴の重要度（PI 平均・SD・平均 \|SHAP\|）の表を別に出す | 図に写っている特徴だけで「効いている変数はこれ」と言わない |
| 相関 \|r\| > 0.8 のペア | 列挙され、重要度の分散が注記されている | グループ permutation（相関ペアを同時に置換）で再計算 |
| 重要度順位の安定性（fold / seed 間の Spearman ρ） | ρ > 0.7 | 「上位 k 個の集合」として報告し、順位を主張しない |
| 代理モデル使用時: 忠実度 | 元モデルとの R² / accuracy を報告 | 低ければ代理モデルの説明を使わない |

取得例（回帰モデルの例）:

```python
import shap
from scipy.stats import spearmanr
from sklearn.inspection import permutation_importance, PartialDependenceDisplay

pi = permutation_importance(model, X_va, y_va, n_repeats=10, random_state=0, scoring="r2")  # 分類は運用指標（"roc_auc" / "average_precision" / "f1" 等）を明示。既定は accuracy
top = list(X_va.columns[np.argsort(-pi.importances_mean)[:3]])
sv = shap.TreeExplainer(model)(X_va)  # 木以外: shap.KernelExplainer(model.predict, shap.kmeans(X_tr, 50))
# 分類で確率空間の SHAP が要るなら背景データ付きで（背景なしの probability は tree_path_dependent と両立せずエラー）:
#   shap.TreeExplainer(model, data=shap.sample(X_tr, 100, random_state=0),
#                      model_output="probability", feature_perturbation="interventional")
additivity_gap = np.abs(sv.base_values + sv.values.sum(axis=1) - model.predict(X_va)).max()  # 加法性の検算
rho = spearmanr(pi.importances_mean, np.abs(sv.values).mean(axis=0)).statistic  # 手法間の順位一致
PartialDependenceDisplay.from_estimator(model, X_va, top, kind="both", subsample=100, random_state=0)  # PDP + ICE（deciles が rug、ICE は間引く）
```

## 落とし穴

- PDP は他特徴を固定するため、相関が強いと存在しない組合せを評価する。\|r\| > 0.8 なら ALE を併用する
- SHAP 値が大きい =「そう変えれば結果が変わる」ではない。介入効果は因果設計でしか言えない
- one-hot に展開したカテゴリ変数は重要度が水準ごとのダミー列に分散し、単独では不当に低く見える。SHAP は加法的なので同じ変数由来のダミー列の SHAP 値を足して 1 変数として扱い、permutation はダミー列をまとめて同時に置換する（相関ペアと同じグループ permutation）
- 線形モデルの係数を標準化せずに重要度として比較しない
  ```python
  # NG: 単位の異なる生の係数を並べて「重要度」と呼ぶ
  sorted(zip(X.columns, np.abs(lr.coef_), strict=True), key=lambda t: -t[1])
  ```
- 代理モデル（決定木で GBDT を説明する等）を使うなら忠実度（元モデルとの R² / accuracy）を必ず出す
- 分類器の SHAP は `model_output` が log-odds か確率かで値の意味が変わる。報告に明記する。対数オッズの SHAP 値を後から確率に変換しても加法性は保たれない（変換が非線形）ので、確率で足し合わせたいなら最初から `model_output="probability"` で計算する
