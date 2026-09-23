# 教師あり ML 評価の必須セット

短縮名: `mleval`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_mleval/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 教師あり ML の評価手続き全般（分割・CV・チューニング・ベースライン・リーク検査・予測区間）
- 扱わない: モデル固有の診断 → `references/tree-model.md` / `statistical-inference-diagnostics`（`references/glm.md`） / 時系列予測固有の評価（季節 naive ベースライン・MASE・ローリング原点）→ `references/time-series.md` / 解釈 → `references/model-interpretation.md`
- 時間の順序を持つデータを時間順に分割すること自体（`TimeSeriesSplit`）はリーク対策なので本ファイルで扱う。時系列モデルを当てはめない予測タスクでも適用する（`references/time-series.md` は系列そのものをモデル化するときだけ）
- モデルが `LogisticRegression`・線形回帰でも、係数を解釈せず汎化性能を報告するならここだけで足りる（`statistical-inference-diagnostics` の glm / ols は読まない）

## ライブラリ

- scikit-learn（`Pipeline`、`ColumnTransformer`、`cross_validate`、`learning_curve`、`DummyClassifier` / `DummyRegressor`、`calibration_curve`）
- mapie（conformal prediction。回帰の予測区間・分類の予測集合を出すときに使う。未導入なら `uv add mapie`）

## 必ず出す図

図の形は評価設計（CV / 単一分割）と学習の形（反復 / 非反復）で変わる。変わるのは形だけで、何を見る図かは省略しない。

- 過学習を見る曲線 — 反復学習（NN・GBDT）は epoch / iteration vs train・validation 損失（1 回の学習の副産物。validation が反転する前で止まっていれば合格）、非反復は `learning_curve` でデータ量 vs スコア（両者が収束していれば合格。乖離が残るなら過学習、両方低いなら表現力不足）
- ベースラインとの比較（幅つき） — CV なら fold 別スコアの箱ひげ、単一分割なら test 予測のブートストラップ CI（再学習不要）。どちらも Dummy を同じ軸に並置し、重ならなければ合格
- 分類: 混同行列（閾値明記）+ PR / ROC 曲線（陽性率を併記） / 回帰: 予測 vs 実測（対角線）+ 残差プロット — 無構造なら合格
- 確率を使う場合: キャリブレーションプロット — 対角線に沿えば合格
- 予測区間・予測集合を出す場合: 実測カバレッジ vs 名目（例 90% 区間が 85〜95% を覆う） — 名目 ± 5% 以内なら合格。分類の予測集合は平均集合サイズも併記する（カバレッジだけなら全クラスを返せば満たせてしまう）

1 回の学習が高コストで、どちらの形の曲線も現実的でない場合に限り 1 つ目を省いてよい。省いたら理由（1 回の学習時間）と train / validation スコアのギャップを値で報告する。

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| 前処理が Pipeline 内か | スケーラ・エンコーダ・代入・（使うなら）再標本化がすべて Pipeline 内 | リーク。Pipeline に入れて CV をやり直す |
| 分割方法とその理由 | グループ有 → GroupKFold、時間有 → TimeSeriesSplit、不均衡 → Stratified。CV を使わないなら理由（学習コスト）と hold-out の件数 | 分割し直し |
| 汎化スコアと幅（CV: 平均 ± SD / 単一分割: ブートストラップ CI） | ベースライン（Dummy）に明確に勝つ | 問題設定・特徴量の見直し |
| train / validation スコアのギャップ | 主張したい差より小さい | 正則化・データ増。曲線を省いたときは必ずこの値を出す |
| test 評価の回数 | 1 回のみ | 複数回見たならそれは検証セット。test を取り直す |
| チューニング時の分割 | nested CV または train / val / test の 3 分割 | 分割し直し（CV で選んだ設定を同じ CV で評価しない） |
| 不均衡時: 陽性率 | 主指標より先に報告 | accuracy を主指標にしない（PR-AUC / F1 / 再現率@精度） |
| 平均予測確率 ÷ 実際の陽性率 | 1.0 付近（再標本化・`class_weight` を使うと陽性側にずれる） | 確率を判断に使うなら事前確率で補正するか、再標本化をやめる |
| 回帰: 目的変数の SD と分位点 | 誤差指標（RMSE / MAE）と並べて報告 | スケール抜きの「RMSE 5.2」は解釈できない。対数変換したなら元スケールに戻して評価する |

取得例:

```python
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score, learning_curve

cv = StratifiedKFold(5, shuffle=True, random_state=0)
pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))  # 前処理は Pipeline 内
base = cross_val_score(DummyClassifier(strategy="prior"), X, y, cv=cv, scoring="roc_auc")
scores = cross_val_score(pipe, X, y, cv=cv, scoring="roc_auc")  # 平均 ± SD をベースラインと並べる
sizes, tr, va = learning_curve(pipe, X, y, cv=cv, scoring="roc_auc", train_sizes=np.linspace(0.1, 1, 5))
```

CV を回さない場合（NN など 1 回の学習が高コスト）は、test 予測の再標本化で幅を出す:

```python
from sklearn.metrics import roc_auc_score

rng = np.random.default_rng(0)
idx = [i for i in rng.integers(0, len(y_te), (1000, len(y_te))) if len(np.unique(y_te[i])) == 2]
ci = np.percentile([roc_auc_score(y_te[i], proba_te[i]) for i in idx], [2.5, 97.5])  # 再学習なし
```

## 落とし穴

- `fit_transform` をデータ全体にかけてから分割するのが最頻出のリーク
  ```python
  # NG: 全データでスケーラを fit してから分割する
  X_scaled = StandardScaler().fit_transform(X); train_test_split(X_scaled, y)
  ```
- 同一人物・同一店舗が train / test をまたぐとスコアが水増しされる（GroupKFold）
- 不均衡データで accuracy を主指標にしない。まず陽性率を報告する
- 不均衡を再標本化で「直さない」。SMOTE・過小抽出・`class_weight` を既定にしない — 識別性能（ROC / PR-AUC）は改善しないまま予測確率が陽性側に寄り、閾値を調整した後の F1 でも素のモデルに負けることが多い。対処は閾値の調整と指標の選択が先。使うのは順位しか使わない用途か、事前確率で補正する場合に限る
- `cv_scores.std()` を真の SE として有意差を主張しない（fold は独立でない）。単一分割でも 1 点だけで「ベースラインに勝った」と言わず幅を添える
- ブートストラップ CI は少数派クラスの件数が少ないと名目より狭く出る。陽性数を必ず併記する
- 予測区間が要るなら conformal prediction（mapie）で実測カバレッジ vs 名目を確認する
