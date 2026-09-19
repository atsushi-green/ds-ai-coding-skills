# 異常検知の必須セット

短縮名: `anomaly`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_anomaly/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 教師なし異常検知（IsolationForest / LOF / OCSVM / Mahalanobis）、ラベル付きの評価（precision@k）、時系列の異常スコアリング
- 扱わない: 前処理の外れ値確認 → `references/missing-data.md` / 十分なラベルがある分類 → `predictive-modeling-diagnostics`（`references/ml-evaluation.md`） / 時系列モデルの残差診断 → `predictive-modeling-diagnostics`（`references/time-series.md`）

## ライブラリ

- scikit-learn（`IsolationForest`、`LocalOutlierFactor`、`OneClassSVM`、`EllipticEnvelope`）、pyod（多手法の統一 API）、scipy.stats（`zscore`、Mahalanobis）
- 未導入なら `uv add pyod`。無ければ sklearn の 4 手法 + z スコア / IQR で十分

## 必ず出す図

- 異常スコアのヒスト（閾値に縦破線、対数 y 軸可） — 閾値が分布の切れ目にあれば合格。切れ目がなければ閾値は業務要件で決めたと明記
- 上位 k 件の特徴量表 or ヒートマップ（各特徴の z スコアで色付け） — 「なぜ異常か」が各行で読めること。読めない報告は使えない
- 単純ベースライン（z スコア / IQR / Mahalanobis）との上位集合の重なり（ベン図 or Jaccard 表） — 複雑手法が単純法と大きく違うなら理由を説明できること
- ラベルがあれば PR 曲線（陽性率を破線） — ラベルが少数でも PR-AUC と precision@k を出す
- 時系列なら: 原系列に異常点を重ねた図（季節性除去後のスコアも） — 異常が季節ピークと一致していないか

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| 単純ベースライン（z スコア / IQR / Mahalanobis）との比較 | 複雑手法が勝つ根拠がある | 根拠がなければ単純法を採用（説明しやすい） |
| contamination の根拠 | ドメイン知識か過去ラベル | 0.5 / 1 / 5% で感度分析し、上位集合の変化を報告 |
| 閾値の根拠 | 分布の切れ目か業務要件（確認可能な件数） | — |
| ラベルあり: precision@k、再現率、PR-AUC | 業務の確認能力（1 日に見られる件数）に対する k で | — |
| ラベルなし: 手法 / seed 間の上位集合 Jaccard | > 0.5 目安 | 特徴量・手法の見直し（不安定な上位は使えない） |
| スケーリング | 距離ベース（LOF / OCSVM / Mahalanobis）なら標準化済み | `StandardScaler`（歪んだ変数は log） |
| 上位 k 件の説明（各特徴の z スコア） | 全件に付いている | — |

取得例（動作確認済み。`X` は数値列だけの polars DataFrame）:

```python
import polars as pl
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

Xs = StandardScaler().fit_transform(X.to_numpy())  # scikit-learn には配列で渡す
score = -IsolationForest(contamination=0.02, random_state=0).fit(Xs).score_samples(Xs)  # 大きいほど異常
z_max = np.abs(Xs).max(axis=1)  # 単純ベースライン（標準化済みなので |z| の最大）
k = int(0.02 * X.height); top_if, top_z = set(np.argsort(-score)[:k]), set(np.argsort(-z_max)[:k])
jaccard = len(top_if & top_z) / len(top_if | top_z)  # 上位集合の一致度（> 0.5 目安）
idx = sorted(top_if)  # 説明付き（元の値 + 各特徴の z スコア）
top_table = X.select(pl.all().gather(idx)).with_columns(
    [pl.Series(f"z_{c}", Xs[idx, i].round(1)) for i, c in enumerate(X.columns)])
```

## 落とし穴

- 距離ベース手法で標準化を忘れると単位の大きい変数だけで決まる
  ```python
  # NG: 金額（万単位）と年齢を未標準化のまま LOF にかける
  LocalOutlierFactor().fit_predict(df[["amount", "age"]])
  ```
- 時系列なら季節性を除去してからスコアリングし、閾値のドリフト（月ごとの検知率）を確認する
- 上位異常が「なぜ異常か」を説明できない報告は使えない（各特徴の z スコアを併記）
- contamination を既定値（auto / 0.1）のまま使わない。検知件数を決めているのはこのパラメータ
- 「異常 = 不正」ではない。業務担当が確認するまでは「要確認」として報告する
