# クラスタリングの必須セット

短縮名: `cluster`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_cluster/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: k-means / k-medoids、階層クラスタリング、GMM、DBSCAN / HDBSCAN、クラスタ数の選択と安定性
- 扱わない: PCA・UMAP・t-SNE の診断 → `references/dimensionality-reduction.md` / 外れ値・異常検知 → `references/anomaly-detection.md` / トピックモデル → 未作成（今後の拡張）
- 手法の指定がなければ、数値だけのデータは k-means、カテゴリ混在は k-prototypes（または Gower 距離 + 階層）を 1 つ選ぶ。他の手法は結果が悪いときの次アクションとして提案に留め、自分から当てはめない

## ライブラリ

- scikit-learn（`KMeans(n_init=20)`、`silhouette_score` / `silhouette_samples`、`adjusted_rand_score`、`GaussianMixture(...).bic`）
- scipy.cluster.hierarchy（`linkage`、`dendrogram`、`cophenet`、`fcluster`）。カテゴリ混在なら kmodes（k-prototypes）か Gower 距離。未導入なら `uv add scikit-learn`

## 必ず出す図（共通 4 パネル + 粒度の根拠 1〜2 パネル）

共通（手法によらず出す 4 パネル）。階層はデンドログラムをカットした後（`fcluster`）のラベル、DBSCAN はノイズを除いたラベルで同じものを出す:
シルエットは全点対の距離を使うので計算量が n²、帰無ベースラインはそれを（順列 × k）回繰り返す。**n が 2 万を超えたら**クラスタリングは全行のまま、シルエットと走査だけ層化サブサンプルで計算し、使った n を図に書く。

- シルエットプロット（サンプル別、クラスタごとに帯。平均に縦破線） — 負の帯が少なく、帯の幅（n）が極端に偏らなければ合格。DBSCAN はノイズ点を除いて描き、除いた割合を図に書く。ユークリッド以外の距離（Gower・マンハッタン）でクラスタリングしたなら距離行列を渡す（`silhouette_score(D, labels, metric="precomputed")`）。クラスタリングと違う距離で評価しない
- PCA 2 次元射影にクラスタ色付け — 「射影の重なりは高次元での分離を否定しない」と注記。射影で完全に混ざるなら構造の弱さを疑う。この PCA は可視化の部品なので `references/dimensionality-reduction.md` は適用しない
- クラスタプロファイル（標準化セントロイドのヒートマップ、各クラスタの n を併記） — 各クラスタを 1 行で説明できる特徴の組合せが読めれば合格。セントロイド＝クラスタ内平均は k-means では手法の定義そのものだが、階層・DBSCAN では**後付けの要約**なので、鎖状・非凸のクラスタや外れ値を含むクラスタでは中央値 + IQR（または特徴ごとの分布の重ね描き）も併記する
- 外部変数プロファイル（クラスタリングに**使わなかった**列との集計。目的変数があればその平均も） — 使っていない変数で差が出れば、内的評価だけでない裏付けになる。差がなければクラスタの業務的な意味は主張できない

粒度（k・カット高さ・eps）の根拠に出す図は手法で違う。**使った手法の行だけ**を出す。走査図には**同じ手法を列ごと順列データに当てた帰無ベースラインの帯**（20 本）を同じ軸に重ね、採用した値に破線を引く:

| 使った手法 | 粒度の根拠に出す図 | 合格の読み方 |
|---|---|---|
| k-means / k-medoids | エルボー（inertia）+ シルエット平均を k = 2〜10（既定。k が指定されている場合はその値を含む範囲）で走査 | 実データのシルエットが帰無の帯を明確に上回り、シルエット最大とエルボーの折れ点が整合する |
| GMM | BIC（+ AIC）+ シルエット平均の k 走査。inertia が無いのでエルボーは描かない | BIC 最小が、帰無の帯を上回るシルエットの k と整合する。非球状クラスタではシルエットが不利に出るので、食い違うなら BIC を主にして理由を書く |
| 階層 | デンドログラム（カット高さに水平破線）+ `fcluster` で k ごとにラベルを作ったシルエット平均の走査 | カット位置の上下で枝の長さに明確な差があり、デンドログラムとシルエット走査が同じ k を指す |
| DBSCAN / HDBSCAN | k-距離プロット（`min_samples` 番目の近傍距離を昇順に並べ、採用 eps に水平破線）+ eps を振ったときのクラスタ数とノイズ率 | 折れ点が読め、eps の小さな変化でクラスタ数・ノイズ率が急変しない |

k が走査の対象にならない DBSCAN では、帰無比較は「同じ eps・min_samples を順列データに当てたときのクラスタ数とノイズ率」で行う。
ユーザーが複数の手法の比較を指示したときだけ、該当行を全部出す。共通 4 パネルは採用した手法のラベルで 1 組だけ描き、粒度の根拠は手法ごとに出す（例: k-means + 階層なら共通 4 + k-means の走査 + デンドログラム + 階層のシルエット走査。2 つのシルエット走査は 1 枚に重ねてよい）。そのときは手法間のラベル一致（ARI）も値として報告する。

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| スケーリングの方針 | 方針と理由が報告にある（単位が混在 → 標準化、全列が同一単位で分散差が情報 → 素のまま） | 歪み・外れ値が理由なら標準化では直らない。log1p か `RobustScaler` を先に使う |
| 採用した粒度（k / カット高さ / eps）とその根拠 | 使った手法の指標で書く（k-means: シルエット最大とエルボーの整合、GMM: BIC 最小、階層: カット高さ、DBSCAN: k-距離の折れ点と `min_samples`）。業務要件で指定された値ならそう明記 | 指標が割れるなら両方の値を並べ、どちらを採用したかを理由付きで書く |
| 帰無ベースライン（列ごと順列 20 本に同じ手法を当てる） | 実データのシルエットが帰無の 95 パーセンタイルを超える（DBSCAN はクラスタ数・ノイズ率で比較） | 超えないなら「この特徴量では構造なし」と結論する。k を増やして値を上げない |
| シルエット平均 | > 0.25 目安（> 0.5 で明瞭）。固定閾値より上の帰無比較が主。DBSCAN はノイズ点を除いて計算し、ノイズ率を併記 | 全 k で低いならクラスタ構造の不在を報告し、別の手法（GMM / DBSCAN）は次アクションとして提案する |
| 各クラスタの n（割合） | 極小クラスタ（< 5%）に注記 | k 削減、外れ値処理（極小は外れ値の吹き溜まりであることが多い） |
| 安定性（seed / サブサンプルの ARI） | > 0.7 目安。k-means は `n_init` を増やすと seed 間の ARI がほぼ 1 になるので、サブサンプル（80% × 10 回）を主に見る。階層・DBSCAN は決定的なのでサブサンプルだけ | 不安定なら報告し k を再考。運用ルールにしない |
| 階層: cophenetic 相関 | > 0.7 目安 | linkage（ward / average / complete）を変更 |
| DBSCAN: ノイズ点の割合 | 報告に明記し、業務上許容できる水準か書く | 過半がノイズなら eps / `min_samples` を見直すか、密度ベースが不適と結論する |
| k-means / GMM: `n_init` と `random_state` | `n_init ≥ 20`、seed を報告に明記 | 階層・DBSCAN は決定的なので不要。代わりに linkage 法、または eps と `min_samples` を明記する |

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
labels = fits[k_best].labels_
ari_seed = adjusted_rand_score(labels, KMeans(k_best, n_init=20, random_state=1).fit_predict(Xs))
rng = np.random.default_rng(0)  # 安定性: 80% サブサンプルで学習し、全行に当てはめたラベルと比べる
ari_sub = [adjusted_rand_score(labels, KMeans(k_best, n_init=20, random_state=0)
                               .fit(Xs[rng.choice(len(Xs), int(0.8 * len(Xs)), replace=False)]).predict(Xs))
           for _ in range(10)]
null_sil = []  # 帰無ベースライン: 列ごとに別々に順列し、変数間の構造だけ壊す（ギャップ統計量と同じ発想）
for s in range(20):
    rng = np.random.default_rng(s)  # rng は列間で使い回す（列ごとに作ると全列が同じ順列になる）
    Xp = np.column_stack([rng.permutation(c) for c in Xs.T])
    null_sil.append(silhouette_score(Xp, KMeans(k_best, n_init=20, random_state=0).fit_predict(Xp)))
# 合格判定は sil[k_best - 2] > np.percentile(null_sil, 95) を報告側で読む
```

手法を変える場合の差分（走査とその根拠、安定性の取り方が変わる。共通 4 パネルはそのまま）:

```python
from scipy.cluster.hierarchy import cophenet, fcluster, linkage
from scipy.spatial.distance import pdist
from sklearn.mixture import GaussianMixture
from sklearn.neighbors import NearestNeighbors

# 階層: linkage → fcluster でラベルを作り、同じ k 走査を回す（inertia は無いのでエルボーは描かない）
Z = linkage(Xs, "ward")
coph = cophenet(Z, pdist(Xs))[0]  # > 0.7 目安
sil_h = [silhouette_score(Xs, fcluster(Z, k, "maxclust")) for k in ks]
idx = np.random.default_rng(0).choice(len(Xs), int(0.8 * len(Xs)), replace=False)  # 決定的なので安定性はサブサンプルで
ari_h = adjusted_rand_score(fcluster(Z, k_best, "maxclust")[idx], fcluster(linkage(Xs[idx], "ward"), k_best, "maxclust"))
# GMM: BIC 最小を根拠にする（シルエットも併記して食い違いを報告する）
bic = [GaussianMixture(k, n_init=20, random_state=0).fit(Xs).bic(Xs) for k in ks]
# DBSCAN: 自分自身を含めて min_samples 個目の近傍までの距離を昇順に並べた k-距離。折れ点が eps の候補
min_samples = 5
kdist = np.sort(NearestNeighbors(n_neighbors=min_samples).fit(Xs).kneighbors(Xs)[0][:, -1])
```

## 落とし穴

- k-means は球状・等サイズを仮定する。全 k でシルエットが低いなら GMM・DBSCAN・「構造がない」を疑う（別の手法を試すのは提案に留める）
- シルエットも凸・等方なクラスタを前提にした指標なので、鎖状・非凸の構造では正しく分かれていても低く出る（two moons で single linkage は ARI 1.00 / シルエット 0.33、Ward は ARI 0.24 / シルエット 0.48）。手法・linkage の優劣をシルエットだけで決めない。同じ手法の中で k を比べる、帰無ベースラインと比べる、の 2 つに用途を限る
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
