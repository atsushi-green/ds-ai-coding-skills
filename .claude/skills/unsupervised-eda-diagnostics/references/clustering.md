# クラスタリングの必須セット

短縮名: `cluster`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_cluster/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: k-means / k-medoids、階層クラスタリング、GMM、DBSCAN / HDBSCAN、クラスタ数の選択と安定性
- 扱わない: PCA・UMAP・t-SNE の診断 → `references/dimensionality-reduction.md` / 外れ値・異常検知 → `references/anomaly-detection.md` / トピックモデル → 未作成（今後の拡張）

## ライブラリ

- scikit-learn（`KMeans(n_init=20)`、`silhouette_score` / `silhouette_samples`、`adjusted_rand_score`、`GaussianMixture(...).bic`）
- scipy.cluster.hierarchy（`linkage`、`dendrogram`、`cophenet`、`fcluster`）。カテゴリ混在なら kmodes（k-prototypes）か Gower 距離。未導入なら `uv add scikit-learn`

## 必ず出す図（1 枚 4 パネル。階層クラスタリングならデンドログラムを追加）

- エルボー（inertia）+ シルエット平均を k = 2〜10 で走査（採用した k に縦破線） — シルエット最大とエルボーの折れ点が整合すれば合格
- シルエットプロット（サンプル別、クラスタごとに帯。平均に縦破線） — 負の帯が少なく、帯の幅（n）が極端に偏らなければ合格
- PCA 2 次元射影にクラスタ色付け — 「射影の重なりは高次元での分離を否定しない」と注記。射影で完全に混ざるなら構造の弱さを疑う
- クラスタプロファイル（標準化セントロイドのヒートマップ、各クラスタの n を併記） — 各クラスタを 1 行で説明できる特徴の組合せが読めれば合格
- 階層: デンドログラム（カット高さに水平破線） — カット位置の上下で枝の長さに明確な差があれば合格

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| スケーリングの有無 | 単位が異なる変数は標準化済み | `StandardScaler`（歪んだ変数は事前に log 変換） |
| 採用した k とその根拠 | シルエット最大とエルボーが整合 | GMM なら BIC 最小、DBSCAN なら k-距離プロットの折れ点 |
| シルエット平均 | > 0.25 目安（> 0.5 で明瞭） | 全 k で低いなら手法（GMM / DBSCAN）かクラスタ構造の不在を疑う |
| 各クラスタの n（割合） | 極小クラスタ（< 5%）に注記 | k 削減、外れ値処理（極小は外れ値の吹き溜まりであることが多い） |
| 安定性（seed / サブサンプル間の ARI） | > 0.7 目安 | 不安定なら報告し k・手法を再考。運用ルールにしない |
| 階層: cophenetic 相関 | > 0.7 目安 | linkage（ward / average / complete）を変更 |
| `n_init` と `random_state` | `n_init ≥ 20`、seed を報告に明記 | — |

取得例（動作確認済み）:

```python
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, adjusted_rand_score
from sklearn.preprocessing import StandardScaler

Xs = StandardScaler().fit_transform(X)  # 単位が異なる変数は標準化
ks = range(2, 11)
fits = {k: KMeans(k, n_init=20, random_state=0).fit(Xs) for k in ks}
inertia = [fits[k].inertia_ for k in ks]  # エルボー
sil = [silhouette_score(Xs, fits[k].labels_) for k in ks]  # シルエット平均（> 0.25 目安）
k_best = list(ks)[int(np.argmax(sil))]
ari = adjusted_rand_score(fits[k_best].labels_, KMeans(k_best, n_init=20, random_state=1).fit_predict(Xs))  # 安定性
```

## 落とし穴

- k-means は球状・等サイズを仮定する。全 k でシルエットが低いなら GMM・DBSCAN・「構造がない」を疑う
- カテゴリ混在データにユークリッド距離の k-means を使わない（Gower 距離・k-prototypes）
  ```python
  # NG: カテゴリのコード値と未標準化の金額を混ぜて k-means
  KMeans(4).fit(df[["category_code", "annual_income", "age"]])
  ```
- 極小クラスタは外れ値の吹き溜まりであることが多い。n を必ず併記する
- t-SNE / UMAP の座標でクラスタリングしない（元空間か PCA 空間で）
- 「クラスタに名前を付けた」＝「解釈できた」ではない。プロファイルの数値で裏付ける
