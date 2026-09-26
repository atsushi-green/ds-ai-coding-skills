# 欠測・外れ値・EDA 前処理の必須セット

短縮名: `missing`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_missing/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 適用条件: 代入する / 行の除外で n の 5% 超を失う / 目的変数に欠測がある / ユーザーが欠測・外れ値の処理か EDA を指示した、のいずれか。5% 以下の欠測行を落とすだけなら読まず、落とした件数を親の手法の報告（除外後の n）に書く
- 扱う: 欠測パターンの把握と機構の見立て、削除 / 単一代入 / 多重代入の選択、外れ値の確認と感度分析、分布と相関の事前確認
- 扱わない: 異常検知モデル → `references/anomaly-detection.md` / 補完を含むパイプラインの CV → `predictive-modeling-diagnostics`（`references/ml-evaluation.md`） / 生データの変更は禁止（派生データとして保存）

## ライブラリ

- missingno（`msno.matrix`、`msno.heatmap`。pandas 入力）、scikit-learn（`IterativeImputer`、`KNNImputer`）、statsmodels（`MICEData` / `MICE`）、scipy.stats
- 欠測率・歪度・相関は polars（`null_count()` / `skew(bias=False)` / `corr()`）で出し、`to_pandas()` / `to_numpy()` は missingno・scikit-learn に渡す直前だけにする。未導入なら `uv add missingno`

## 必ず出す図

扱った内容の行だけを出す（欠測だけを扱ったなら外れ値・EDA の行は出さない）:

| 扱った内容 | 出す図 | 合格の読み方 |
|---|---|---|
| 欠測 | 欠測マトリクス（`msno.matrix`。行を時間や ID でソート） | 欠測が特定の期間・行群に固まっていない。固まっていれば MCAR ではない |
| 欠測（欠測のある列が 2 つ以上のときだけ） | 欠測相関ヒートマップ（`msno.heatmap`） | 欠測の共起（同時に欠ける列の組）が読める |
| 代入 | 観測値 vs 代入値の分布比較（変数ごとにヒスト or KDE を重ねる） | 代入値の分布が観測値と大きくずれていない。平均値代入は必ずずれる |
| 外れ値 | 対象変数のヒスト / KDE（外れ値候補に印） | 候補が分布のどこにあり、何件あるかが読める |
| EDA（分布・相関の確認を指示されたとき） | 主要変数のヒスト / KDE と相関行列ヒートマップ | \|歪度\| > 2 の変数、\|r\| > 0.9 のペアが図から特定できる |

## 必ず出す値

| 区分 | 項目 | 合格基準 | 違反時の対処 |
|---|---|---|---|
| 欠測 | 変数別欠測率 | 5% 超の変数を列挙 | 50% 超は変数として使うか再検討 |
| 欠測 | 欠測機構の見立て（MCAR / MAR / MNAR） | 根拠付きで明記（欠測フラグと他変数の関連、時期との関連） | MNAR の疑いなら感度分析（欠測を変数化、pattern-mixture） |
| 欠測 | 採用した処理と失う n | リストワイズ削除なら失う割合を報告 | 推論目的なら多重代入（MICE、m ≥ 20）を第一候補に |
| 外れ値 | 外れ値候補の件数と実データ確認 | 入力ミス・単位違い・別母集団のどれかを判定 | 除外するなら基準・件数・感度分析（あり / なし両方）を報告 |
| 外れ値・EDA | 歪度 | \|歪度\| > 2 で変換検討 | log1p / Yeo-Johnson（変換の有無を報告） |
| EDA | \|r\| > 0.9 の変数ペア | 列挙（後段の共線性の予告） | — |
| 共通 | 除外・変換・代入の操作ログ | 件数付きで報告に含む | — |

取得例（`df` は polars、`X_train` は数値列だけの polars DataFrame）:

```python
import missingno as msno
import polars as pl
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer

# 欠測
miss_rate = (df.null_count().transpose(include_header=True, header_name="列", column_names=["n"])
             .with_columns(rate=pl.col("n") / df.height).sort("rate", descending=True))  # 5% 超を列挙
df_pd = df.to_pandas()  # missingno は pandas 入力のみ
msno.matrix(df_pd)  # 欠測パターン
if (miss_rate["n"] > 0).sum() >= 2:
    msno.heatmap(df_pd)  # 欠測相関は欠測のある列が 2 つ以上のときだけ描ける
# 代入: train のみで fit（リーク防止）
imp = IterativeImputer(random_state=0, sample_posterior=True).fit(X_train.to_numpy())
X_imp = pl.DataFrame(imp.transform(X_train.to_numpy()), schema=X_train.columns)
```

外れ値・EDA を扱う場合:

```python
# 外れ値候補（IQR の 1.5 倍の外側）の件数。除外するかは実データを見て人間が決める
outlier_n = X_train.select(
    ((pl.col(c) < pl.col(c).quantile(0.25) - 1.5 * (pl.col(c).quantile(0.75) - pl.col(c).quantile(0.25)))
     | (pl.col(c) > pl.col(c).quantile(0.75) + 1.5 * (pl.col(c).quantile(0.75) - pl.col(c).quantile(0.25))))
    .sum() for c in X_train.columns)
skew = X_train.select(pl.all().skew(bias=False))  # polars の既定は母集団歪度。pandas と同じ標本歪度は bias=False
# EDA のみ: |r| > 0.9 のペア（後段の共線性の予告）
corr = X_train.drop_nulls().corr().to_numpy()  # null を含む列の相関は NaN になり見逃すので、完全ケースで計算する
high_corr = [(a, b) for i, a in enumerate(X_train.columns) for j, b in enumerate(X_train.columns)
             if i < j and abs(corr[i, j]) > 0.9]
```

## 落とし穴

- 平均値代入は分散を縮め相関を歪める。既定の選択肢にしない
  ```python
  # NG: 全列を平均で埋めて先へ進む（分散が縮み、欠測の情報も消える）
  df = df.with_columns(pl.all().fill_null(pl.all().mean()))
  ```
- 代入は train / test 分割の内側で行う（test の情報で train を埋めない）
- 「外れ値 = 削除」ではない。入力ミス・単位違い・別母集団を実データで確認し、感度分析（あり / なし両方）が最も誠実
- 目的変数の欠測を安易に代入しない（除外して母集団の変化を報告）
- 推論目的の多重代入は m ≥ 20 で、Rubin のルールで統合する（代入 1 回の SE は過小）
