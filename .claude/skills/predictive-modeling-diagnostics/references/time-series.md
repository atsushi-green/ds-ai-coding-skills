# 時系列（ARIMA / 状態空間 / Prophet）の必須セット

短縮名: `ts`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_ts/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 単変量・多変量の時系列モデリングと予測（ARIMA / SARIMA / ETS / 状態空間 / Prophet / VAR）、分解、定常性、変化点
- 扱わない: 時系列でない教師あり ML → `references/ml-evaluation.md` / 介入効果の推定（DiD・合成コントロール）→ `causal-inference-diagnostics`（`references/causal-quasi-experimental.md`） / 時系列の異常検知 → `unsupervised-eda-diagnostics`（`references/anomaly-detection.md`）

## 系列の前提を先に整える（図を描く前に）

時系列の診断はすべて「隣り合う行が 1 期」という等間隔の仮定の上に載っている。ここが崩れていると ACF のラグも
STL の `period` も差分も意味を失うので、可視化より前に次を確認し、結果を報告に書く。

1. **頻度と時点ラベルを宣言する** — 毎時 / 日次 / 週次 / 月次のどれか、各期に貼る日付は期間の先頭か末尾か（月次なら 1 月の行が `2024-01-01` か `2024-01-31` か。pandas では `MS` と `ME`）。以降の `period`・季節次数 `s`・グリッド整形の頻度をこれに揃える。末尾スタンプの系列に `asfreq("MS")` をかけると、日付が一つも一致せず警告なしに全行が欠測になる
2. **欠測している期を行として起こす** — 欠測は `NaN` ではなく**行の不在**として現れる。等間隔グリッドに整形して顕在化させ、欠測期間数を報告する
3. **同じ時点に複数行がないか数える** — あるなら、系列の粒度が意図とずれている（店舗別の行を全社の系列として扱っている等）か、結合で行が増えている。合算してよいのは前者だけで、後者を合算すると増えた分だけ値が水増しされる。原因を確かめてから合算・重複除去・結合の修正を選ぶ
4. **末尾の期が完結しているか確認する** — 締まっていない当月・当週を含めると末尾が必ず下がり、存在しない減少トレンドが出る。未完結の期は除外し、除外したと書く
5. **値を埋めるかは別に決める** — 「イベントが起きなかった（＝0）」と「観測できなかった（＝欠測）」は違う。前者を補間すると実態のない山が、後者を 0 で埋めると実態のない急落ができる。補間したなら方法を報告に書く

```python
n_dup = df.height - df["date"].n_unique()  # 先に数える。upsample は重複行をそのまま残す
full = df.sort("date").upsample(time_column="date", every="1mo")  # polars。time_column は Datetime 型
n_missing = full["y"].null_count()  # 欠けていた期の数（値を埋めるかどうかは別の判断）
```

## ライブラリ

- statsmodels（`tsa.STL`、`adfuller`、`kpss`、`plot_acf` / `plot_pacf`、`SARIMAX`、`acorr_ljungbox`）
- prophet（ユーザー指定時のみ。使う場合も季節 naive と比較する）、ruptures（変化点。任意）。未導入なら `uv add statsmodels`

## 必ず出す図（1〜4 は予測をしない場合でも必ず出す）

1. 時系列プロット（原系列。x 軸は時間軸として描く。行番号や連番を x にすると、間隔の乱れと欠測が詰まって見えなくなる） — 欠測・外れ値・レベルシフト・分散変化が目で見えること（欠測期間は穴として見えること）。トレンドや分散の変化がある系列は、差分（必要なら対数差分）後の系列も同じ図に並べ、変換で水準と分散が落ち着くかを目で確認する
   - **点数が多い系列は生の折れ線が塗り潰しになる**（描画幅のピクセル数が上限。日次 3 年・毎時 1 か月が目安）。「全体の形」と「細部の形」を 1 枚に詰めず、次のいずれかで分ける
     - **上下 2 段**: 上段に全期間（粗い粒度に集計、または移動平均）、下段に直近数周期の生データ
     - **重ね描き**: 生データを薄く（`alpha=0.3`）、季節周期と同じ窓の移動平均（`center=True`）を濃く重ねる
     - **季節で折り返す**: 年ごとに線を重ねる、または `month_plot` / `quarter_plot` で期ごとのサブ系列にする（周期と季節パターンの変化はこちらが速い）
   - 粗い粒度に集計するときは平均だけにせず **min–max を帯で添える**（`resample("W").agg(["mean", "min", "max"])`）。平均だけだとスパイクと外れ値が消える
   - **平滑化した図だけを載せない**。外れ値・レベルシフト・欠測はこの図の主目的で、移動平均をかけると真っ先に消える。移動平均は両端が欠けることにも注意
2. コレログラム（ACF / PACF。ラグは季節周期の 3 倍以上、月次なら 36。ただし `lags < n`（系列長。`lags = n` は ValueError で落ちる）。3 周期に満たない短い系列では 2 周期までに留め、周期の判断が弱いと書く。有意帯を描く。差分後も併せて） — **周期性の確認が目的**。季節ラグにスパイクがあれば周期を読み取る
3. STL 分解（trend / seasonal / resid） — 季節成分の大きさと形が読めること。resid に構造が残らなければ合格
4. 残差の診断（残差プロット + 残差 ACF + Q-Q） — 残差 ACF が有意帯内なら合格
5. **予測する場合: 実測と予測を同じ時間軸に並べた図（この図なしに予測結果を報告しない）**
   - 学習期間の実測・検証期間の実測・予測値を**ひとつの軸に時系列として**描く。予測値だけを別図・別軸に描かない
   - **予測区間を帯（`fill_between`）で塗り**、凡例に名目被覆率（95% など）を書く
   - 学習と検証の境界（予測の起点）を縦の破線で示す
   - ベースライン（季節 naive）の予測も同じ軸に重ねる — 本当にベースラインより実測に近いかを目で確かめるため
   - 学習期間の当てはめ値（in-sample の 1 期先予測）を予測と同じ線種で描かない。描くなら別パネルにし「当てはめ」と明記する
   - 学習期間が長いときは全期間を描かず、**直近数周期 + 予測期間**に絞る（全期間を入れると予測と区間が右端で潰れて読めない）。全期間の図が要るなら別パネルにする

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| 系列の整形（頻度 / 欠測期間数 / 同一時点の重複行数 / 末尾の期の完結性） | 重複 0、未完結の期は除外済み。欠測があるなら件数と扱い（null のまま / 補間 / 0）を明記 | グリッド整形と重複の解消。集計元まで遡る |
| ADF p / KPSS p（併記） | 両検定の結論が整合（ADF p < 0.05 かつ KPSS p > 0.05 で定常）。トレンドを含む系列は両検定とも `regression="ct"` に揃える | 差分・対数変換・トレンド除去 |
| 季節周期（コレログラムから読んだ値） | データの粒度と整合（月次なら 12、日次なら 7 等） | 周期の再検討。決め打ちしない |
| Ljung-Box p（複数ラグ。`model_df` = 推定した ARMA パラメータ数 = p + q + P + Q） | > 0.05 | 次数追加、季節項追加 |
| 選んだ次数 (p,d,q)(P,D,Q,s) の根拠 | ACF / PACF の型と整合 | AIC / BIC で補強（情報量基準単独で決めない） |
| 予測時: 分割方法と指標の集計単位 | 時間順（ランダム分割・shuffle は禁止）。前処理も学習区間のみで fit。ローリング原点 / `TimeSeriesSplit` を使うなら各 fold の指標の**平均 ± SD と fold 数**を報告し、単発ホールドアウトか CV 平均かを明記する | `TimeSeriesSplit` かローリング原点 |
| 予測時: 予測の地平 h | 運用と同じ h 期先の多段先予測で評価する（1 期先の精度を h 期先の精度として報告しない） | h 期先で評価し直す |
| 予測時: MAE / RMSE / MASE と**ベースライン**（naive・季節 naive） | ベースラインに勝つ（MASE < 1） | モデル再考。負けたと報告する |
| 予測時: 予測区間の実測カバレッジ（区間に入った点数 / 検証点数を分母ごと併記） | 名目 ± 5% 程度。n < 20 では推定が不安定なので「参考値」と明記する | 区間の作り方を見直す |

取得例（月次系列 `y` は DatetimeIndex 付きの pandas Series。`y_train` / `y_test` は時間順に分割済み）。
statsmodels.tsa は `DatetimeIndex` から周期を読むため、時系列そのものは pandas で持つ。前段の集計・結合は polars で行い、
`to_pandas().set_index("date")["y"]` のようにモデルへ渡す直前で変換する:

```python
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

y = y.asfreq("MS")  # 頻度を明示（欠測は NaN として顕在化し、予測結果にも時点ラベルが付く）
y_f = y.interpolate(limit_area="inside")  # adfuller / kpss は NaN を受け付けない。補間したことを報告する（落とすと等間隔が崩れる）
adf_p, kpss_p = adfuller(y_f)[1], kpss(y_f, regression="c", nlags="auto")[1]  # KPSS p は表の範囲で切り詰め
stl = STL(y, period=12).fit()  # STL と SARIMAX は欠測を許容するので原系列のまま渡す
res = SARIMAX(y_train, order=(1, 1, 1), seasonal_order=(0, 1, 1, 12)).fit(disp=0)
lb = acorr_ljungbox(res.resid[13:], lags=[12, 24, 36], model_df=3)  # model_df = p+q+P+Q = 1+1+0+1、先頭は d+D*s 分を捨てる

# 予測と予測区間（h 期先の多段先予測）
fcast = res.get_forecast(steps=len(y_test))
fc, ci = fcast.predicted_mean, fcast.conf_int(alpha=0.05)  # ci: [lower, upper]
snaive = np.resize(y_train.to_numpy()[-12:], len(y_test))  # 季節 naive ベースライン
mae_scale = np.mean(np.abs(y_train.to_numpy()[12:] - y_train.to_numpy()[:-12]))  # 学習期間の季節 naive MAE
mase = np.mean(np.abs(y_test.to_numpy() - fc.to_numpy())) / mae_scale
cover = np.mean((y_test.to_numpy() >= ci.iloc[:, 0].to_numpy()) & (y_test.to_numpy() <= ci.iloc[:, 1].to_numpy()))

# 図 5: 実測（学習・検証）・予測・予測区間・ベースラインを同じ軸に並べる
fig, ax = plt.subplots(figsize=(12, 4), constrained_layout=True)
ax.plot(y_train.index, y_train, label="実測（学習）")
ax.plot(y_test.index, y_test, label="実測（検証）")
ax.plot(fc.index, fc, label="SARIMA 予測")
ax.fill_between(ci.index, ci.iloc[:, 0], ci.iloc[:, 1], alpha=0.2, label="95% 予測区間")
ax.plot(y_test.index, snaive, ls=":", label="季節 naive")
ax.axvline(y_train.index[-1], ls="--", color="gray")  # 予測の起点
ax.legend()
```

## 落とし穴

- 評価分割は必ず時間順。前処理（スケーリング・欠損補完）も学習区間のみで fit する
  ```python
  # NG: 時系列をランダム分割して評価する
  train_test_split(X, y, test_size=0.2, shuffle=True)
  ```
- 学習期間の当てはめ値（in-sample 1 期先予測）を「予測」として見せない。実測にぴたりと重なるのは当然で、汎化性能の証拠にならない
- ベースライン（naive・季節 naive）比較なしに MAE / RMSE を報告しない。季節 naive に負ける複雑モデルは珍しくない
- コレログラムを見ずに季節周期を決め打ちしない。KPSS の p 値は表の範囲で切り詰められる（`p > 0.1` のように報告）
- Prophet のデフォルト予測区間はトレンドの不確実性と観測ノイズしか含まず、季節性の不確実性は入らない（入れるには `mcmc_samples > 0` で完全ベイズ推定）。狭く出やすいので、必ず実測カバレッジで確かめる
- 欠測への耐性はライブラリで揃っていない。`STL` と `SARIMAX` は NaN を含む系列をそのまま扱えるが、`adfuller` は `MissingDataError`、`kpss` は「cannot convert float NaN to integer」という原因の読めない例外で落ちる。検定に渡す前に欠測の扱いを決める
- 対数変換して予測したら逆変換時のバイアス（単純な exp は中央値予測）に言及する
- 外生変数は「予測時点で入手可能か」を確認する（実績気温は使えない。予報なら可）。これもリーク
