# 時系列（ARIMA / 状態空間 / Prophet）の必須セット

短縮名: `ts`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_ts/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 単変量・多変量の時系列モデリングと予測（ARIMA / SARIMA / ETS / 状態空間 / Prophet / VAR）、分解、定常性、変化点
- 扱わない: 時系列でない教師あり ML → `references/ml-evaluation.md` / 介入効果の推定（DiD・合成コントロール）→ `causal-inference-diagnostics`（`references/causal-quasi-experimental.md`） / 時系列の異常検知 → `unsupervised-eda-diagnostics`（`references/anomaly-detection.md`）

## ライブラリ

- statsmodels（`tsa.STL`、`adfuller`、`kpss`、`plot_acf` / `plot_pacf`、`SARIMAX`、`acorr_ljungbox`）
- prophet（ユーザー指定時のみ。使う場合も季節 naive と比較する）、ruptures（変化点。任意）。未導入なら `uv add statsmodels`

## 必ず出す図（1〜4 は予測をしない場合でも必ず出す）

1. 時系列プロット（原系列。x 軸は日付として描く） — 欠測・外れ値・レベルシフト・分散変化が目で見えること。欠測タイムスタンプは明示補完（黙って落とさない）
2. コレログラム（ACF / PACF。ラグは季節周期の 3 倍以上、月次なら 36。有意帯を描く。差分後も併せて） — **周期性の確認が目的**。季節ラグにスパイクがあれば周期を読み取る
3. STL 分解（trend / seasonal / resid） — 季節成分の大きさと形が読めること。resid に構造が残らなければ合格
4. 残差の診断（残差プロット + 残差 ACF + Q-Q） — 残差 ACF が有意帯内なら合格
5. 予測する場合: 予測を原系列の時系列プロットに重ねた図 — 学習期間の実測・検証期間の実測・予測値を同じ軸に描き、**予測区間を帯で塗る**。予測だけを別の軸に描かない

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| ADF p / KPSS p（併記） | 両検定の結論が整合（ADF p < 0.05 かつ KPSS p > 0.05 で定常） | 差分・対数変換・トレンド除去 |
| 季節周期（コレログラムから読んだ値） | データの粒度と整合（月次なら 12、日次なら 7 等） | 周期の再検討。決め打ちしない |
| Ljung-Box p（複数ラグ。`model_df = p + q`） | > 0.05 | 次数追加、季節項追加 |
| 選んだ次数 (p,d,q)(P,D,Q,s) の根拠 | ACF / PACF の型と整合 | AIC / BIC で補強（情報量基準単独で決めない） |
| 予測時: 分割方法 | 時間順（ランダム分割・shuffle は禁止）。前処理も学習区間のみで fit | `TimeSeriesSplit` かローリング原点 |
| 予測時: MAE / RMSE / MASE と**ベースライン**（naive・季節 naive） | ベースラインに勝つ（MASE < 1） | モデル再考。負けたと報告する |
| 予測時: 予測区間の実測カバレッジ | 名目 ± 5% 程度 | 区間の作り方を見直す |

取得例（動作確認済み。月次系列 `y` は DatetimeIndex 付きの pandas Series）。
statsmodels.tsa は日付インデックスから周期を読むため、時系列そのものは pandas で持つ。前段の集計・結合は polars で行い、
`to_pandas().set_index("date")["y"]` のようにモデルへ渡す直前で変換する:

```python
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

adf_p, kpss_p = adfuller(y)[1], kpss(y, regression="c", nlags="auto")[1]  # KPSS p は表の範囲で切り詰め
stl = STL(y, period=12).fit()  # trend / seasonal / resid
res = SARIMAX(y, order=(1, 1, 1), seasonal_order=(0, 1, 1, 12)).fit(disp=0)
lb = acorr_ljungbox(res.resid[13:], lags=[12, 24, 36], model_df=2)  # model_df = p + q
mase = np.mean(np.abs(y_test - fc)) / np.mean(np.abs(y_train[12:].to_numpy() - y_train[:-12].to_numpy()))  # 季節 naive 比
```

## 落とし穴

- 評価分割は必ず時間順。前処理（スケーリング・欠損補完）も学習区間のみで fit する
  ```python
  # NG: 時系列をランダム分割して評価する
  train_test_split(X, y, test_size=0.2, shuffle=True)
  ```
- ベースライン（naive・季節 naive）比較なしに MAE / RMSE を報告しない。季節 naive に負ける複雑モデルは珍しくない
- コレログラムを見ずに季節周期を決め打ちしない。KPSS の p 値は表の範囲で切り詰められる（`p > 0.1` のように報告）
- 対数変換して予測したら逆変換時のバイアス（単純な exp は中央値予測）に言及する
- 外生変数は「予測時点で入手可能か」を確認する（実績気温は使えない。予報なら可）。これもリーク
