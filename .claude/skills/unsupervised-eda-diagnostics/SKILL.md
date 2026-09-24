---
name: unsupervised-eda-diagnostics
description: >-
  教師なし分析と EDA 前処理（欠測 / 欠損 / NaN / 補完 / imputation / 外れ値処理、クラスタリング / セグメンテーション /
  k-means / 階層クラスタリング / GMM / DBSCAN、次元削減 / PCA / 主成分分析 / 因子分析 / UMAP / t-SNE、異常検知 /
  anomaly detection / 不正検知）を実行したら必ずセットで出す図と値のルーター。fillna, dropna, fill_null,
  SimpleImputer, IterativeImputer, missingno, KMeans, AgglomerativeClustering, DBSCAN, GaussianMixture,
  silhouette_score, dendrogram, PCA, FactorAnalysis, calculate_kmo, TSNE, umap.UMAP, IsolationForest,
  LocalOutlierFactor, pyod がコードに現れたとき、またはユーザーが「欠損を埋めて」「クラスタリングして」「主成分で
  要約して」「異常を検知して」「データをきれいにして」と言ったときに使う。安定性・k の根拠・平行分析・ベースラインに
  言及がなくても適用する。SKILL.md のルーティング表で手法を特定し、対応する references/<手法>.md を読んでから実行する。
  教師あり予測は predictive-modeling-diagnostics、回帰・検定は statistical-inference-diagnostics を使う。
---

# 教師なし分析・EDA 前処理の必須セット（ルーター）

分析の実行と診断は不可分である。モデルを当てはめて係数やスコアだけを返すのは分析の前半でしかなく、
本スキルの適用下では未完了とみなす。ユーザーが診断・図・残差に言及しなくても、該当する references の図と値は必ず出す。

## 使い方（この順で）

1. 下のルーティング表で、**ユーザーが指示した手法**（指示がなければ分析の主目的になる手法 1 つ）の行を見つける。複数の行を読むのは、手法を直列に使うとき（例: PCA で圧縮してから k-means → `dimensionality-reduction` + `clustering`）と、ユーザーが手法の比較を指示したときだけ
   - 他の手法の診断図や前処理の部品として使うだけの処理は、コードに現れても該当に数えない。例: クラスタ診断図のための PCA 2 次元射影、UMAP の前に 50 次元へ落とす PCA、5% 以下の欠測行の除外、順列・サブサンプル・ブートストラップの乱数
2. その行の `references/<手法>.md` を**読んでから**分析を実行する（読まずに当てはめない）
3. 図を保存し、報告に「出力と報告」の判定表を載せる

## ルーティング表

| 手法 | トリガー語彙（コード / 日本語） | 読むファイル |
|---|---|---|
| 欠測・外れ値・EDA 前処理（削除 / 代入 / 多重代入、分布・相関の確認）。代入する / 行の除外で n の 5% 超を失う / 目的変数が欠測 / 欠測・外れ値の処理か EDA を指示された、のいずれかのときだけ | `fillna` `dropna` `fill_null` `drop_nulls` `SimpleImputer` `IterativeImputer` `KNNImputer` `MICEData` `missingno` / 欠損、補完、外れ値 | `references/missing-data.md` |
| クラスタリング（k-means・階層・GMM・DBSCAN） | `KMeans` `AgglomerativeClustering` `DBSCAN` `HDBSCAN` `GaussianMixture` `silhouette_score` `linkage` `dendrogram` / セグメント、グループ分け | `references/clustering.md` |
| 次元削減・因子分析・埋め込み（PCA・EFA・CFA / SEM・UMAP・t-SNE）。次元削減そのものが目的のときだけ（診断図の射影・前処理の PCA は除く） | `PCA` `FactorAnalysis` `FactorAnalyzer` `calculate_kmo` `TSNE` `umap.UMAP` `semopy` `TruncatedSVD` / 主成分、潜在因子、2 次元に落とす | `references/dimensionality-reduction.md` |
| 異常検知・外れ値検知（教師なし / ラベル少数） | `IsolationForest` `LocalOutlierFactor` `OneClassSVM` `EllipticEnvelope` `pyod` `score_samples` `contamination` / 異常、不正 | `references/anomaly-detection.md` |

5% 以下の欠測行を落とすだけなら `missing-data.md` は読まず、落とした件数を親の手法の報告（除外後の n）に書く。

## 隣接する手法（このルーターでは扱わない）

| 手法 | 使う skill |
|---|---|
| 教師あり予測・木モデル・SHAP、時系列予測 | `predictive-modeling-diagnostics` |
| 回帰・GLM・検定・生存時間・MCMC | `statistical-inference-diagnostics` |
| A/B テスト・傾向スコア・DiD | `causal-inference-diagnostics` |
| シミュレーション・最適化 | `simulation-optimization-diagnostics` |

## 出力と報告（全手法共通）

- 図は `outputs/diagnostics/<YYYYMMDD-HHMM>_<短縮名>/` に保存する（短縮名は各 references の冒頭）。報告にはパスと下の表だけを載せ、図は貼らない
- 図は 1 手法 1 枚の複合図を基本とし、各パネルのタイトルに「何を見る図か — 何が見えれば合格か」を書く。判定基準線は破線で描く
- 乱数を使う処理は seed を固定し報告に明記する。日本語フォント・配色・保存形式は visualization skill に従う
- 報告の冒頭に n（行数）・p（列数）と除外後の n を書く。シルエットも欠測率も n と p が分からなければ読めない
- コードの役割は図の保存と診断値の計算まで。値は「項目名 → 数値」の表（polars の DataFrame。pandas を返すライブラリの結果はそのまま載せてよい）にまとめて表示し、必要なら CSV で保存する。判定・合格基準・次アクションの文字列はコードで組み立てない
- 報告の「診断サマリー」に次の表を載せる。実測値はコードが出した値を転記し、判定（`OK` / `要対処` / `確認`＝人間の判断待ち）と次アクションは references の合格基準と図を見て報告側で書く。`要対処` には必ず次アクションを書く。全項目 OK でも表を出す

| 診断項目 | 実測値 | 合格基準 | 判定 | 次アクション |
|---|---|---|---|---|
| シルエット平均 (k=4) | 0.18（帰無 95% = 0.30） | 帰無ベースラインを上回る | 要対処 | この特徴量では構造なしと報告。特徴量の見直しか GMM / DBSCAN の試行を提案する |
| リストワイズ削除で失う n | 31% | 報告 | 要対処 | MICE（m=20）に切替 |

## 全手法共通の落とし穴

- 標準化は中立な前処理ではなく「どの変数を対等に扱うか」という重み付けの決定である。距離ベースの手法（k-means・LOF・PCA）にかける前に決めて報告に書く。単位が違うまま入れれば分散の大きい変数だけで結果が決まり、歪んだ変数は先に log 変換する
- 「クラスタに名前を付けた」「上位 k 件を出した」で終わらない。安定性（seed / サブサンプル）と、人間が確認できる形（プロファイル表・z スコア）まで出す
- 次アクションに書いた別の手法（「GMM でも確認」など）は報告上の提案であり、ユーザーの指示なしに当てはめない。指示されていない手法の図を混ぜると、どの結果を採用したのかが読み手に伝わらない
- 「構造が見つからなかった」は失敗ではなく結論である。帰無ベースライン（列ごと順列・乱数固有値・単純法）に勝てなかったなら、勝てなかったと報告する
- 教師なしの出力（クラスタ ID・主成分・異常スコア）を後段の教師あり学習の特徴量にするなら、CV の分割の内側で作る。全データで作ってから分割するとリークする（`predictive-modeling-diagnostics` の `references/ml-evaluation.md`）
- 生データは変更しない。除外・変換・代入は件数付きで操作ログに残し、派生データとして保存する
- 判定表をコードで生成しない。基準ごとの単純な閾値分岐だけでは、図や分析目的を踏まえた判断（件数は基準内でも図に形がある、など）を十分に扱えない。解釈・次アクションの文章をスクリプトに埋め込むと、分析コードも報告文で膨らむ（前提が崩れたら処理を止める `assert` は別）
  ```python
  # NG: 判定と次アクションをコードの分岐で組み立てる
  verdict = "OK" if sil > 0.25 else "要対処"
  # OK: 値を表で出すだけ。判定と次アクションは報告に書く
  vals = {"silhouette": sil, "ari_seed": ari, "min_cluster_share": min_share}
  print(pl.DataFrame({"項目": list(vals), "値": list(vals.values())}, strict=False))  # int・float・文字列が混ざっても落ちない
  ```
