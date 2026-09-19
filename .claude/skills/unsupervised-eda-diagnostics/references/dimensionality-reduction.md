# 次元削減（PCA・因子分析・UMAP/t-SNE）の必須セット

短縮名: `dimred`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_dimred/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: PCA（縮約）、探索的因子分析 EFA（潜在構造）、CFA / SEM（構造の検証）、UMAP / t-SNE（可視化用埋め込み）
- 扱わない: 埋め込み後のクラスタリング → `references/clustering.md` / 表現学習（オートエンコーダ等）→ 未作成（今後の拡張）
- PCA（次元圧縮）と EFA（潜在構造の解釈）は目的が違う。どちらが目的かを先に確認する

## ライブラリ

- factor_analyzer（`calculate_kmo`、`calculate_bartlett_sphericity`）、scikit-learn（`PCA`、`FactorAnalysis(rotation="varimax")`、`TSNE`）、umap-learn、semopy（SEM / CFA）
- 未導入なら `uv add factor-analyzer umap-learn`。factor_analyzer 0.5.x の `FactorAnalyzer` は scikit-learn ≥ 1.8 で動かないため、EFA 本体は sklearn の `FactorAnalysis` で行う。平行分析はライブラリ不要

## 必ず出す図

- PCA / EFA: スクリープロットに**平行分析**のランダム固有値（95 パーセンタイル）を重ねる（推奨因子数に縦破線） — 実データの固有値がランダムを上回る数が因子数
- PCA / EFA: バイプロット（スコアの散布 + 負荷ベクトル） — 変数ベクトルの向きで軸の意味が読めれば合格
- EFA: 回転後負荷量のヒートマップ — 各変数の主負荷 ≥ 0.4 かつ交差負荷 < 0.3 なら合格
- UMAP / t-SNE: ハイパラを変えた 3 枚以上のグリッド（perplexity 5 / 30 / 50 または n_neighbors 5 / 15 / 50） — 大域構造が設定間で保たれれば合格。「クラスタの大きさと距離は意味を持たない」を図に注記

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| EFA: KMO（全体） | > 0.6（良好 > 0.8） | MSA の低い変数を除外 |
| EFA: Bartlett p | < 0.05 | 因子分析に不適（変数間相関が弱い） |
| 因子数・成分数の根拠 | **平行分析が主**（Kaiser 基準単独は使わない） | — |
| EFA: 共通性 | > 0.3 | 低い変数の除外を検討 |
| 累積寄与率 | 用途依存（縮約なら 70〜80%） | 低ければ「圧縮の価値が薄い」と報告 |
| SEM / CFA: 適合度 | CFI / TLI ≥ 0.95、RMSEA ≤ 0.06（90% CI 併記）、SRMR ≤ 0.08 を全部併記 | モデル再指定（修正指数を機械的に採用しない） |
| UMAP / t-SNE: seed 3 本で構造が同じか | 安定 | 「設定依存」と明記 |
| 標準化の有無 | 単位が異なる変数は標準化済み | 未標準化だと第 1 主成分が単位の大きい変数に支配される |

取得例（動作確認済み。平行分析と EFA）:

```python
from factor_analyzer import calculate_kmo, calculate_bartlett_sphericity
from sklearn.decomposition import PCA, FactorAnalysis

kmo_all, kmo_model = calculate_kmo(X); bart_chi2, bart_p = calculate_bartlett_sphericity(X)
Xs = StandardScaler().fit_transform(X)
eig = PCA().fit(Xs).explained_variance_
rng = np.random.default_rng(0)  # 平行分析: 同形の乱数データの固有値（95 パーセンタイル）と比較
rand_eig = np.array([PCA().fit(rng.standard_normal(Xs.shape)).explained_variance_ for _ in range(100)])
n_factors = int((eig > np.percentile(rand_eig, 95, axis=0)).sum())
fa = FactorAnalysis(n_components=n_factors, rotation="varimax").fit(Xs)
loadings = fa.components_.T; communalities = (loadings**2).sum(axis=1)  # 主負荷 ≥ 0.4、共通性 > 0.3
```

## 落とし穴

- Kaiser 基準（固有値 > 1）だけで因子数を決めない。過大抽出しやすい
  ```python
  # NG: 固有値 > 1 の数をそのまま因子数にする
  n_factors = int((eig > 1).sum())
  ```
- PCA（次元圧縮）と EFA（潜在構造の解釈）を混同しない。目的を先に確認する
- t-SNE / UMAP の図には「クラスタの大きさとクラスタ間距離は意味を持たない」を注記する
- t-SNE / UMAP の座標でクラスタリングや距離計算をしない（元空間か PCA 空間で）
- 高次元（> 50）は PCA で 50 次元程度に落としてから UMAP / t-SNE にかける
