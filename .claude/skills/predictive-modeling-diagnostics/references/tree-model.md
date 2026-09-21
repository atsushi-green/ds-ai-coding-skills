# 木系モデル（決定木・RF・GBDT）の必須セット

短縮名: `tree`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_tree/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 単一決定木、RandomForest / ExtraTrees、GBDT（LightGBM / XGBoost / CatBoost / sklearn HistGradientBoosting）
- 扱わない: 分割設計・CV・リーク検査 → `references/ml-evaluation.md` / SHAP・PDP・ALE → `references/model-interpretation.md` / 線形モデル → `statistical-inference-diagnostics`（references/ols.md・glm.md）

## ライブラリ

- scikit-learn（`cost_complexity_pruning_path`、`permutation_importance`、`plot_tree`、`export_text`）、lightgbm / xgboost / catboost
- **dtreeviz**（単一木の可視化。graphviz バイナリが必要）。無ければ `plot_tree(max_depth=3)` + `export_text` にフォールバック
- 未導入なら `uv add dtreeviz lightgbm`

## 必ず出す図

- 単一木: dtreeviz による木の可視化 — 深さ ≤ 4 は全体、それ以上は上位 3 階層 + 代表サンプル 1 件の予測パス。葉の n が読めること
- 単一木: cost-complexity pruning path（`ccp_alpha` vs CV スコア、最良 α に縦破線） — 最良 α が 0 でなければ枝刈りの効果あり
- RF: OOB error vs `n_estimators` — 曲線が平坦化していれば合格（伸び続けるなら本数不足）
- GBDT: train / valid loss vs iteration（`best_iteration` に縦破線） — valid が反転する前で止まっていれば合格
- permutation importance（validation 側、`n_repeats ≥ 10`）の棒 + エラーバー — 上位がドメイン知識と整合すれば合格

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| train / valid スコア | ギャップが小さい（目安: 主張したい差より小さい） | 枝刈り・`min_samples_leaf`・正則化・データ増 |
| GBDT: best_iteration | 反復上限で止まっていない | `learning_rate` を下げ、反復上限を増やす |
| 最小葉のサンプル数 | n ≥ 全体の 1% かつ ≥ 5 件 | `min_samples_leaf` / `min_child_samples` を引き上げ |
| permutation importance 上位 | ドメイン知識と整合 | 不整合（ID・日付連番・目的変数由来の列）ならリークを疑う |
| seed 3〜5 本のスコア SD | 主張したい差より小さい | seed 固定のまま「差がある」と言わない |
| カテゴリ変数の入れ方 | one-hot / native categorical / target encoding を明記 | target encoding は CV 内で（リーク） |

取得例（動作確認済み）:

```python
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import cross_val_score
from sklearn.inspection import permutation_importance

path = DecisionTreeClassifier(random_state=0).cost_complexity_pruning_path(X_tr, y_tr)
cv_scores = [cross_val_score(DecisionTreeClassifier(ccp_alpha=a, random_state=0), X_tr, y_tr, cv=5).mean()
             for a in path.ccp_alphas]  # ccp_alpha vs CV スコア。最良 α に縦線
clf = DecisionTreeClassifier(ccp_alpha=path.ccp_alphas[int(np.argmax(cv_scores))], random_state=0).fit(X_tr, y_tr)
min_leaf = int(clf.tree_.n_node_samples[clf.tree_.children_left == -1].min())  # 最小葉のサンプル数
pi = permutation_importance(clf, X_va, y_va, n_repeats=10, random_state=0)  # validation 側で
```

## 落とし穴

- `feature_importances_`（不純度ベース）を単独で報告しない。高カーディナリティ・連続変数に偏る
  ```python
  # NG: 不純度重要度だけで「重要な変数」を結論づける
  ax.barh(X.columns, model.feature_importances_)
  ```
- test データで early stopping しない（評価データの `eval_set`、LightGBM 4.7 以降は `eval_X` / `eval_y` には validation を渡す。test は最後に 1 回）
- ID・日付連番・目的変数と同時に生成される列が重要度上位に来たらリーク
- カテゴリ変数の入れ方（one-hot / native categorical / target encoding）を報告に明記する
- 学習データ範囲外では予測が平坦になる。外挿の限界を報告に 1 行入れる
