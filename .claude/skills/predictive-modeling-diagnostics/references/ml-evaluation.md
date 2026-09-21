# 教師あり ML 評価の必須セット

短縮名: `mleval`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_mleval/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 教師あり ML の評価手続き全般（分割・CV・チューニング・ベースライン・リーク検査・予測区間）
- 扱わない: モデル固有の診断 → `references/tree-model.md` / `statistical-inference-diagnostics`（`references/glm.md`） / 時系列予測の分割と季節 naive → `references/time-series.md` / 解釈 → `references/model-interpretation.md`

## ライブラリ

- scikit-learn（`Pipeline`、`ColumnTransformer`、`cross_validate`、`learning_curve`、`DummyClassifier` / `DummyRegressor`、`calibration_curve`）
- mapie（予測区間・conformal prediction。任意。未導入なら `uv add mapie`。無ければ分位点回帰で代替し「近似」と明記）

## 必ず出す図

- 学習曲線（train / validation スコア vs データ量） — 両者が収束していれば合格。乖離が残るなら過学習、両方低いなら表現力不足
- CV スコアの fold 別分布（箱ひげ）+ ベースライン（Dummy）を同じ軸に並置 — 箱がベースラインと重ならなければ合格
- 分類: 混同行列（閾値明記）+ PR / ROC 曲線（陽性率を併記） / 回帰: 予測 vs 実測（対角線）+ 残差プロット — 無構造なら合格
- 確率を使う場合: キャリブレーションプロット — 対角線に沿えば合格
- 予測区間を出す場合: 実測カバレッジ vs 名目（例 90% 区間が 85〜95% を覆う） — 名目 ± 5% 以内なら合格

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| 前処理が Pipeline 内か | スケーラ・エンコーダ・代入・SMOTE がすべて Pipeline 内 | リーク。Pipeline に入れて CV をやり直す |
| 分割方法とその理由 | グループ有 → GroupKFold、時間有 → TimeSeriesSplit、不均衡 → Stratified | 分割し直し |
| CV スコア 平均 ± SD | ベースライン（Dummy）に明確に勝つ | 問題設定・特徴量の見直し |
| test 評価の回数 | 1 回のみ | 複数回見たならそれは検証セット。test を取り直す |
| チューニング時の分割 | nested CV または train / val / test の 3 分割 | 分割し直し（CV で選んだ設定を同じ CV で評価しない） |
| 不均衡時: 陽性率 | 主指標より先に報告 | accuracy を主指標にしない（PR-AUC / F1 / 再現率@精度） |

取得例（動作確認済み）:

```python
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

## 落とし穴

- `fit_transform` をデータ全体にかけてから分割するのが最頻出のリーク
  ```python
  # NG: 全データでスケーラを fit してから分割する
  X_scaled = StandardScaler().fit_transform(X); train_test_split(X_scaled, y)
  ```
- 同一人物・同一店舗が train / test をまたぐとスコアが水増しされる（GroupKFold）
- 不均衡データで accuracy を主指標にしない。まず陽性率を報告する
- `cv_scores.std()` を真の SE として有意差を主張しない（fold は独立でない）
- 予測区間が要るなら conformal prediction（mapie）で実測カバレッジ vs 名目を確認する
