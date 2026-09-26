# 木系モデル（決定木・RF・GBDT）の必須セット

短縮名: `tree`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_tree/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 単一決定木、RandomForest / ExtraTrees、GBDT（LightGBM / XGBoost / CatBoost / sklearn HistGradientBoosting）
- 扱わない: 分割設計・CV・リーク検査 → `references/ml-evaluation.md` / SHAP・PDP・ALE → `references/model-interpretation.md` / 線形モデル → `statistical-inference-diagnostics`（references/ols.md・glm.md） / 教師なしの木（IsolationForest）→ `unsupervised-eda-diagnostics`（references/anomaly-detection.md） / DML・傾向スコアの nuisance モデルとして使う木・GBDT → `causal-inference-diagnostics`（`references/causal-observational.md` の nuisance 性能で見るので本ファイルは適用しない）
- 分割器（`GroupKFold` / `TimeSeriesSplit` / `Stratified*`）と評価指標は `ml-evaluation.md` で決めたものを使う。本ファイルの枝刈り α の選択・OOB・early stopping・permutation importance もその分割と指標に従う

## ライブラリ

- scikit-learn（`cost_complexity_pruning_path`、`permutation_importance`）、lightgbm / xgboost / catboost
- **dtreeviz は必須**（単一木の可視化）。未導入なら `uv add dtreeviz lightgbm` で入れ、graphviz バイナリ（`dot`）も用意する（macOS: `brew install graphviz` / Debian: `apt install graphviz`）
- `plot_tree` / `export_text` で代替しない。分岐条件は読めても各ノードのクラス分布・葉の n・代表サンプルの予測パスが読めず、下の図の合格判定ができない
- dtreeviz の出力は SVG。報告に PNG が要るなら `rsvg-convert -z 2 -b white`（librsvg）で変換する

## 必ず出す図

- 単一木: dtreeviz による木の可視化 — 深さ ≤ 4 は全体、それ以上は上位 3 階層 + 代表サンプル 1 件の予測パス。葉の n が読めること
- 単一木: cost-complexity pruning path（`ccp_alpha` vs CV スコアの平均 ± SD、最良 α に縦破線、α = 0 と最良 α の葉の数を注記） — 最良 α の位置と、α = 0 からのスコアの動きが読めれば合格。最良 α が 0 でないことだけでは枝刈りの効果と言えない（下の「必ず出す値」の α = 0 との差で判断する）
- RF: OOB error vs `n_estimators`（`oob_score=True` + `warm_start=True` で木を足しながら記録） — 曲線が平坦化していれば合格（伸び続けるなら本数不足）。OOB は**木の本数が足りているかを見るためだけに使う**。無作為ブートストラップの残りなので、グループ構造・時間順序があるデータでは同一グループ・近接時点の行が in-bag と OOB に分かれて楽観的に出る。汎化スコアは `ml-evaluation.md` の分割で測った値を並べて報告し、OOB を汎化スコアとして読まない。ExtraTrees は既定 `bootstrap=False` で OOB が取れない
- GBDT: train / valid loss vs iteration（`best_iteration` に縦破線） — valid が反転する前で止まり、かつ train / valid ともに下がりきっていれば合格（両方が高止まりなら未学習。木を深く / 学習率を上げる / 正則化を緩める）。`ml-evaluation.md` の「過学習を見る曲線」と同じ図なので 1 枚で兼ねる
- permutation importance（validation 側、`n_repeats ≥ 10`、`scoring` を明示）の棒 + エラーバー — 上位がドメイン知識と整合すれば合格。`model-interpretation.md` も適用するなら図の描き方（上位 15〜20 本に絞る）はそちらに従い、二重に描かない

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| train / valid スコア | ギャップが小さい（目安: 主張したい差より小さい） | 枝刈り・`min_samples_leaf`・正則化・データ増 |
| GBDT: best_iteration と `learning_rate` | 反復上限で止まっていない（上限に張り付いたら打ち切られている） | `learning_rate` を下げ、反復上限を増やす |
| 単一木: 最小葉のサンプル数 | n ≥ 全体の 1% かつ ≥ 5 件（解釈に使う木の前提。n が 1 桁の葉を「セグメント」として報告しない） | `min_samples_leaf` を上げるか枝刈りを強める |
| 単一木: 枝刈りの効果 | α = 0（枝刈りなし）との CV スコア差を同じ fold で対にして並べ（fold ごとの差と平均）、両者の葉の数も並べる。全 fold で最良 α が上回るときだけ「枝刈りで性能が上がった」と書く | 符号が揃わなければ「性能は同程度のまま木が小さくなった」と書く（解釈用の木ならそれで十分）。最良 α が 0 でないことだけを根拠にしない |
| RF / GBDT: 葉サイズの下限設定 | `min_samples_leaf` / `min_child_samples`（LightGBM 既定 20）の設定値を報告。RF は既定 1 で葉 n = 1 まで伸びる（平均で打ち消すので単独では異常ではない） | train / valid のギャップが大きいときに引き上げる |
| permutation importance 上位 | ドメイン知識と整合 | 不整合（ID・日付連番・目的変数由来の列）ならリークを疑う |
| seed 3〜5 本のスコア SD | 主張したい差より小さい | seed 固定のまま「差がある」と言わない |
| カテゴリ変数の入れ方 | one-hot / native categorical / target encoding を明記 | target encoding は CV 内で（リーク） |

取得例:

```python
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.model_selection import cross_val_score
from sklearn.tree import DecisionTreeClassifier

path = DecisionTreeClassifier(random_state=0).cost_complexity_pruning_path(X_tr, y_tr)
alphas = np.unique(path.ccp_alphas[:-1])  # 最後の α は根だけの木なので除く。先頭は 0（枝刈りなし）
cv_res = np.array([cross_val_score(DecisionTreeClassifier(ccp_alpha=a, random_state=0), X_tr, y_tr,
                                   groups=g_tr, cv=cv, scoring="roc_auc")  # cv・scoring は mleval で決めたもの（既定の accuracy に任せない）
                   for a in alphas])  # (α の数, fold 数)。cv は毎回同じ分割になるもの（shuffle なら random_state を固定）
best = int(np.argmax(cv_res.mean(axis=1)))  # 平均 ± SD を ccp_alpha に対して描き、最良 α に縦線
clf = DecisionTreeClassifier(ccp_alpha=alphas[best], random_state=0).fit(X_tr, y_tr)
gain = cv_res[best] - cv_res[0]  # fold ごとの α = 0 との差。符号が揃わなければ性能差と言わない
leaves = {"α=0": DecisionTreeClassifier(random_state=0).fit(X_tr, y_tr).get_n_leaves(), "最良 α": clf.get_n_leaves()}
leaf_n = clf.tree_.n_node_samples[clf.tree_.children_left == -1]  # children_left == -1 が葉ノード
pi = permutation_importance(clf, X_va, y_va, n_repeats=10, random_state=0, scoring="roc_auc")  # validation 側・指標を明示

rf = RandomForestClassifier(oob_score=True, warm_start=True, min_samples_leaf=3, random_state=0)
oob_err = []
for n in (50, 100, 200, 400):  # warm_start なので木を足しながら OOB を記録できる
    rf.set_params(n_estimators=n).fit(X_tr, y_tr)
    oob_err.append(1 - rf.oob_score_)  # oob_score_ は accuracy 固定（callable を渡してもハードラベル）。不均衡なら rf.oob_decision_function_[:, 1] から AUC を計算する
```

## 落とし穴

- `feature_importances_`（不純度ベース）を単独で報告しない。高カーディナリティ・連続変数に偏る
  ```python
  # NG: 不純度重要度だけで「重要な変数」を結論づける
  ax.barh(X.columns, model.feature_importances_)
  ```
- RF / GBDT の 1 本目の木を可視化して「モデルの判断ロジック」として説明しない。本数分の平均・加算がモデルなので 1 本は代表ではない。木の形で説明したいなら枝刈り済みの単一木を別に学習し、元モデルとの忠実度を出す（`model-interpretation.md` の代理モデル）
- test データで early stopping しない。渡すのは validation（LightGBM は `eval_X` / `eval_y`。4.7 で `eval_set` は非推奨、打ち切りは `callbacks=[lgb.early_stopping(n)]`）。test は最後に 1 回。sklearn の HistGradientBoosting は `early_stopping="auto"`（n > 10,000 で自動 ON）が学習データから無作為に `validation_fraction=0.1` を切るため、グループ・時間構造があるとここがリーク源になる（`early_stopping=False` にして外で検証集合を作る）
- ID・日付連番・目的変数と同時に生成される列が重要度上位に来たらリーク
- 学習データ範囲外では予測が平坦になる。外挿の限界を報告に 1 行入れる
