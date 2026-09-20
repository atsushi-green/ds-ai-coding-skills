# クラスタリングの必須セット

短縮名: `cluster`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_cluster/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: k-means / k-medoids、階層クラスタリング、GMM、DBSCAN / HDBSCAN、クラスタ数の選択と安定性
- 扱わない: PCA・UMAP・t-SNE の診断 → `references/dimensionality-reduction.md` / 外れ値・異常検知 → `references/anomaly-detection.md` / トピックモデル → 未作成（今後の拡張）

## ライブラリ

- scikit-learn（`KMeans(n_init=20)`、`silhouette_score` / `silhouette_samples`、`adjusted_rand_score`、`GaussianMixture(...).bic`）
- scipy.cluster.hierarchy（`linkage`、`dendrogram`、`cophenet`、`fcluster`）。カテゴリ混在なら kmodes（k-prototypes）か Gower 距離。未導入なら `uv add scikit-learn`

## 必ず出す図（1 枚 5 パネル）

- エルボー（inertia）+ シルエット平均を k = 2〜10（既定。k が指定されている場合はその値を含む範囲）で走査し、**列ごと順列データのシルエット（帰無ベースライン）の帯を同じ軸に重ねる**（採用した k に縦破線） — 実データの曲線が帯を明確に上回り、シルエット最大とエルボーの折れ点が整合すれば合格
- シルエットプロット（サンプル別、クラスタごとに帯。平均に縦破線） — 負の帯が少なく、帯の幅（n）が極端に偏らなければ合格
- PCA 2 次元射影にクラスタ色付け — 「射影の重なりは高次元での分離を否定しない」と注記。射影で完全に混ざるなら構造の弱さを疑う
- クラスタプロファイル（標準化セントロイドのヒートマップ、各クラスタの n を併記） — 各クラスタを 1 行で説明できる特徴の組合せが読めれば合格
- 外部変数プロファイル（クラスタリングに**使わなかった**列との集計。目的変数があればその平均も） — 使っていない変数で差が出れば、内的評価だけでない裏付けになる。差がなければクラスタの業務的な意味は主張できない
- 階層: デンドログラム（カット高さに水平破線） — カット位置の上下で枝の長さに明確な差があれば合格

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| スケーリングの方針 | 方針と理由が報告にある（単位が混在 → 標準化、全列が同一単位で分散差が情報 → 素のまま） | 歪み・外れ値が理由なら標準化では直らない。log1p か `RobustScaler` を先に使う |
| 採用した k とその根拠 | シルエット最大とエルボーが整合、または業務要件で指定された k だと明記 | GMM なら BIC 最小、DBSCAN なら k-距離プロットの折れ点 |
| 帰無ベースライン（列ごと順列 20 本）のシルエット | 実データが帰無の 95 パーセンタイルを超える | 超えないなら「この特徴量では構造なし」と結論する。k を増やして値を上げない |
| シルエット平均 | > 0.25 目安（> 0.5 で明瞭）。固定閾値より上の帰無比較が主 | 全 k で低いなら手法（GMM / DBSCAN）かクラスタ構造の不在を疑う |
| 各クラスタの n（割合） | 極小クラスタ（< 5%）に注記 | k 削減、外れ値処理（極小は外れ値の吹き溜まりであることが多い） |
| 安定性（seed / サブサンプル間の ARI） | > 0.7 目安 | 不安定なら報告し k・手法を再考。運用ルールにしない |
| 階層: cophenetic 相関 | > 0.7 目安 | linkage（ward / average / complete）を変更 |
| `n_init` と `random_state` | `n_init ≥ 20`、seed を報告に明記 | — |

取得例（`X` は数値列だけの polars DataFrame）:

```python
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, adjusted_rand_score
from sklearn.preprocessing import StandardScaler

Xs = StandardScaler().fit_transform(X.to_numpy())  # 単位が混在する場合の既定。全列が同じ単位なら素のままも選択肢（sklearn には配列で渡す）
ks = range(2, 11)
fits = {k: KMeans(k, n_init=20, random_state=0).fit(Xs) for k in ks}
inertia = [fits[k].inertia_ for k in ks]  # エルボー
sil = [silhouette_score(Xs, fits[k].labels_) for k in ks]  # n が大きいなら sample_size= を指定
k_best = list(ks)[int(np.argmax(sil))]  # 候補。k の確定は指標だけで決めず報告側で判断する
# k が指定されているならここを指定値にし、以降（帰無・ARI・シルエットプロット）も同じ k で計算する
ari = adjusted_rand_score(fits[k_best].labels_, KMeans(k_best, n_init=20, random_state=1).fit_predict(Xs))  # 安定性
null_sil = []  # 帰無ベースライン: 列ごとに別々に順列し、変数間の構造だけ壊す（ギャップ統計量と同じ発想）
for s in range(20):
    rng = np.random.default_rng(s)  # rng は列間で使い回す（列ごとに作ると全列が同じ順列になる）
    Xp = np.column_stack([rng.permutation(c) for c in Xs.T])
    null_sil.append(silhouette_score(Xp, KMeans(k_best, n_init=20, random_state=0).fit_predict(Xp)))
# 合格判定は sil[k_best - 2] > np.percentile(null_sil, 95) を報告側で読む
```

## 落とし穴

- k-means は球状・等サイズを仮定する。全 k でシルエットが低いなら GMM・DBSCAN・「構造がない」を疑う
- 「スケールが違う ＝ 標準化する」ではない。標準化は全変数を分散 1 に揃える＝距離への寄与を対等にする決定なので、分散の差が単位の恣意性（円・歳・回数）から来るなら揃え、分散の差そのものが情報（全列が同一単位・同一尺度。例: カテゴリ別の購買金額、同じ尺度の設問群）なら揃えない。後者で z 化すると、ほとんど動かない列のノイズが主要な列と同じ重みまで増幅される。二値ダミーの z 化も希少カテゴリの距離寄与を跳ね上げる
- スケーリングの選び方で結論が変わるか分からないときは、両方で回して ARI を比較する。変われば「スケーリングの選択で結論が動く」こと自体が報告すべき結果で、どちらを採用したかを理由付きで書く
- カテゴリ混在データにユークリッド距離の k-means を使わない（Gower 距離・k-prototypes）
  ```python
  # NG: カテゴリのコード値と未標準化の金額を混ぜて k-means
  KMeans(4).fit(df[["category_code", "annual_income", "age"]])
  ```
- k が業務要件やユーザー指定で決まっていても、走査図と帰無ベースラインは省かない。指定 k に縦破線を引いて採用はその k のままにし、指標上の最適 k と食い違うなら両方のシルエットを並べて報告する（例:「k=5 を採用（業務要件）。シルエット 0.22、指標最大は k=3 で 0.31」）。指定 k が帰無ベースラインを超えないなら「その k では構造を裏付けられない」と書く
- 極小クラスタは外れ値の吹き溜まりであることが多い。n を必ず併記する
- t-SNE / UMAP の座標でクラスタリングしない（元空間か PCA 空間で）
- 「クラスタに名前を付けた」＝「解釈できた」ではない。プロファイルの数値で裏付ける
