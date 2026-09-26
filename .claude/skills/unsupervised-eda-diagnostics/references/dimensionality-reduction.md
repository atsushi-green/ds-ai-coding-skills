# 次元削減（PCA・因子分析・UMAP/t-SNE）の必須セット

短縮名: `dimred`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_dimred/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: PCA（縮約）、探索的因子分析 EFA（潜在構造）、CFA / SEM（構造の検証）、UMAP / t-SNE（可視化用埋め込み）
- 扱わない: 埋め込み後のクラスタリング → `references/clustering.md` / 表現学習（オートエンコーダ等）→ 未作成（今後の拡張）
- 次元削減そのものが目的のときだけ適用する。他の手法の部品として PCA を使うだけ（クラスタ診断図の 2 次元射影、UMAP / t-SNE の前に 50 次元へ落とす前処理）なら、下の PCA の図・値は出さず、使った成分数と累積寄与率だけを親の手法の報告に書く
- PCA（次元圧縮）と EFA（潜在構造の解釈）は目的が違う。どちらが目的かを先に確認する

## ライブラリ

- factor_analyzer（`calculate_kmo`、`calculate_bartlett_sphericity`）、scikit-learn（`PCA`、`FactorAnalysis(rotation="varimax")`、`TSNE`）、umap-learn、semopy（CFA / SEM）
- 未導入なら `uv add factor-analyzer umap-learn semopy`。factor_analyzer 0.5.x の `FactorAnalyzer` は scikit-learn ≥ 1.8 で動かないため、EFA 本体は sklearn の `FactorAnalysis` で行う。平行分析はライブラリ不要

## 必ず出す図

平行分析は乱数データへの PCA を 100 回、UMAP / t-SNE のグリッドは埋め込みを 3〜9 回作り直す。n・p が大きいと 1 枚に数時間かかるので、埋め込みと平行分析は層化サブサンプルで作り、使った n と反復数を図に書く。

**使った手法の行だけ**を出す:

| 使った手法 | 出す図 | 合格の読み方 |
|---|---|---|
| PCA | スクリープロットに**平行分析**のランダム固有値（95 パーセンタイル）を重ねる（採用成分数に縦破線）/ バイプロット（スコアの散布 + 負荷ベクトル） | 実データの固有値がランダムを上回る数が成分数の根拠 / 変数ベクトルの向きで軸の意味が読める |
| EFA | スクリープロット + 平行分析（PCA と同じ図）/ バイプロット（因子得点の散布 + 負荷ベクトル）/ 回転後負荷量のヒートマップ | 同上 / 変数ベクトルの向きで因子の意味が読める / 各変数の主負荷 ≥ 0.4 かつ交差負荷 < 0.3 |
| CFA / SEM | 標準化負荷量（パス係数）の表かパス図 / 残差相関（標本とモデルが含意する共分散の差を標本 SD で標準化）のヒートマップ | 各観測変数が想定した因子に載っている / \|残差相関\| > 0.1 のセルが局所的な不適合の場所として読める |
| UMAP / t-SNE | ハイパラを変えた 3 枚以上のグリッド（perplexity 5 / 30 / 50 または n_neighbors 5 / 15 / 50。各パネルに trustworthiness を併記） | 大域構造が設定間で保たれる。「クラスタの大きさと距離は意味を持たない」を図に注記 |

## 必ず出す値

| 区分 | 項目 | 合格基準 | 違反時の対処 |
|---|---|---|---|
| PCA / EFA | 因子数・成分数の根拠 | **平行分析が主**（Kaiser 基準単独は使わない） | — |
| PCA | 累積寄与率 | 用途依存（縮約なら 70〜80%） | 低ければ「圧縮の価値が薄い」と報告 |
| PCA | 標準化の有無（= 相関行列 PCA か共分散行列 PCA か） | どちらを使ったか報告に明記。単位が混在するなら標準化（相関行列） | 未標準化だと第 1 主成分が分散の大きい変数に支配される。全列が同一単位で分散差が情報なら素のままを選び、その理由を書く |
| EFA | KMO（全体） | > 0.6（良好 > 0.8） | MSA の低い変数を除外 |
| EFA | Bartlett p | < 0.05 | 因子分析に不適（変数間相関が弱い） |
| EFA | 共通性 | > 0.3 | 低い変数の除外を検討 |
| CFA / SEM | 適合度 | CFI / TLI ≥ 0.95、RMSEA ≤ 0.06（90% CI 併記）、SRMR ≤ 0.08 を全部併記 | モデル再指定（修正指数を機械的に採用しない） |
| CFA / SEM | \|残差相関\| > 0.1 のペア数 | 0 目安 | 該当ペアの項目内容を確認し、理論的な理由がある場合だけモデルを直す |
| UMAP / t-SNE | trustworthiness（近傍保存率） | > 0.9 目安（`n_neighbors` を明記） | perplexity / n_neighbors を変える。それでも低ければ埋め込みの図で構造を語らない |
| UMAP / t-SNE | seed 3 本で構造が同じか | 安定 | 「設定依存」と明記 |

取得例（`X` は数値列だけの polars DataFrame）。PCA:

```python
import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

Xm = X.to_numpy()  # factor_analyzer・sklearn には配列で渡す
Xs = StandardScaler().fit_transform(Xm)
pca = PCA().fit(Xs)
eig, cum_ratio = pca.explained_variance_, np.cumsum(pca.explained_variance_ratio_)
rng = np.random.default_rng(0)  # 平行分析: 同形の乱数データの固有値（95 パーセンタイル）と比較
rand_eig = np.array([PCA().fit(rng.standard_normal(Xs.shape)).explained_variance_ for _ in range(100)])
n_factors = int((eig > np.percentile(rand_eig, 95, axis=0)).sum())
```

EFA（平行分析までは PCA と同じ）:

```python
from factor_analyzer.factor_analyzer import calculate_bartlett_sphericity, calculate_kmo
from sklearn.decomposition import FactorAnalysis

kmo_per, kmo_all = calculate_kmo(Xm)  # 返り値は（変数ごとの MSA, 全体の KMO）の順。逆に受けると判定を誤る
bart_chi2, bart_p = calculate_bartlett_sphericity(Xm)
fa = FactorAnalysis(n_components=n_factors, rotation="varimax", random_state=0).fit(Xs)  # seed を固定
loadings = fa.components_.T
communalities = (loadings**2).sum(axis=1)  # 主負荷 ≥ 0.4、共通性 > 0.3
```

UMAP / t-SNE:

```python
from sklearn.manifold import TSNE, trustworthiness

emb = {p: TSNE(2, perplexity=p, random_state=0, init="random").fit_transform(Xs) for p in (5, 30, 50)}
trust = {p: trustworthiness(Xs, e, n_neighbors=10) for p, e in emb.items()}  # 近傍保存率（> 0.9 目安）
```

CFA / SEM（semopy は SRMR と RMSEA の CI を返さないので、標本と含意の共分散から計算する）:

```python
import semopy
from scipy.optimize import brentq
from scipy.stats import ncx2

cfa = semopy.Model("F1 =~ x1 + x2 + x3\nF2 =~ y1 + y2 + y3")  # 想定した因子構造を式で書く
cfa.fit(X.to_pandas())  # semopy は pandas 入力
fit = semopy.calc_stats(cfa).T["Value"]  # chi2・DoF・CFI・TLI・RMSEA
std_load = cfa.inspect(std_est=True).query("op == '~'")[["lval", "rval", "Est. Std"]]  # 標準化負荷量
S, sigma = cfa.mx_cov, cfa.calc_sigma()[0]  # 標本共分散と含意の共分散（変数順は cfa.vars["observed"]）
resid_r = (S - sigma) / np.outer(np.sqrt(np.diag(S)), np.sqrt(np.diag(S)))  # 残差相関（ヒートマップ用）
srmr = np.sqrt(np.mean(resid_r[np.tril_indices_from(resid_r)] ** 2))
n_resid_gt = int((np.abs(resid_r[np.tril_indices_from(resid_r, -1)]) > 0.1).sum())
chi2, dof, n = fit["chi2"], fit["DoF"], X.height


def rmsea_bound(q: float) -> float:
    """P(χ²(dof, λ) ≤ chi2) = q となる非心度 λ から RMSEA を出す。"""
    if ncx2.cdf(chi2, dof, 1e-9) <= q:  # λ = 0 でも届かないなら 0
        return 0.0
    lam = brentq(lambda nc: ncx2.cdf(chi2, dof, nc) - q, 1e-9, 10 * chi2 + 100)
    return float(np.sqrt(lam / (dof * (n - 1))))


rmsea_ci = (rmsea_bound(0.95), rmsea_bound(0.05))  # RMSEA の 90% CI
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
- 高次元（> 50）は PCA で 50 次元程度に落としてから UMAP / t-SNE にかける（この PCA は前処理なので PCA の図は出さない）
- CFA で適合度が悪いとき、修正指数の大きい順に誤差相関を足して通さない。データに合わせた構造は検証になっていない
