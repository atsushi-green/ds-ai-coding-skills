---
name: predictive-modeling-diagnostics
description: >-
  予測モデリング（教師あり機械学習 / 予測モデル / 精度評価 / 交差検証 / リーク、決定木 / ランダムフォレスト / GBDT /
  LightGBM / XGBoost / CatBoost、モデル解釈 / 特徴量重要度 / SHAP / PDP / ICE、時系列 / 季節性 / ARIMA / SARIMA /
  Prophet / VAR / 変化点 / 時系列予測）を実行したら必ずセットで出す図と値のルーター。train_test_split, cross_val_score, GridSearchCV,
  Pipeline, TimeSeriesSplit, DecisionTree, RandomForest, lgb., xgb., CatBoost, dtreeviz, shap., permutation_importance,
  PartialDependenceDisplay, statsmodels.tsa, SARIMAX, STL, adfuller, plot_acf, Prophet, ruptures がコードに現れたとき、または
  ユーザーが「予測モデルを作って」「精度を出して」「どの変数が効いているか」「来月を予測して」「季節性を見て」と
  言ったときに使う。診断・リーク・ベースライン・残差に言及がなくても適用する。SKILL.md のルーティング表で手法を特定し、
  対応する references/<手法>.md を読んでから実行する。回帰係数の推論・検定は statistical-inference-diagnostics、
  効果推定は causal-inference-diagnostics を使う。
---

# 予測モデリングの必須セット（ルーター）

分析の実行と診断は不可分である。モデルを当てはめて係数やスコアだけを返すのは分析の前半でしかなく、
本スキルの適用下では未完了とみなす。ユーザーが診断・図・残差に言及しなくても、該当する references の図と値は必ず出す。

## 使い方（この順で）

1. 下のルーティング表で、**ユーザーが指示した手法**（指示がなければ分析の主目的になる手法 1 つ）の行を見つける。教師ありモデルの評価には常に `ml-evaluation` を足す（例: LightGBM で予測 → `ml-evaluation` + `tree-model`）。`model-interpretation` は重要度・寄与・効き方の説明を求められたときだけ足す
   - 他の手法の部品として使うだけのモデルは、コードに現れても該当に数えない。例: 傾向スコアのモデル、DML の nuisance モデルとしての木・GBDT（どちらも `causal-inference-diagnostics` 側で診断する）、GLM の性能指標を出すための `StratifiedKFold`
   - 同じ `LogisticRegression` / `LinearRegression` / `Lasso` でも、係数を解釈せず汎化性能を報告するならこの skill、係数・オッズ比を解釈するなら `statistical-inference-diagnostics`。両方が目的なら両方を読み、ROC・キャリブレーションなど重なる図は 1 枚で兼ねる
2. その行の `references/<手法>.md` を**読んでから**分析を実行する（読まずに当てはめない）
3. 図を保存し、報告に「出力と報告」の判定表を載せる

## ルーティング表

| 手法 | トリガー語彙（コード / 日本語） | 読むファイル |
|---|---|---|
| 教師あり ML の評価手続き（分割・CV・チューニング・ベースライン・リーク・予測区間） | `train_test_split` `cross_val_score` `cross_validate` `GridSearchCV` `Pipeline` `StratifiedKFold` `GroupKFold` `TimeSeriesSplit` `learning_curve` / 精度、汎化 | `references/ml-evaluation.md` |
| 決定木・RandomForest・GBDT（LightGBM / XGBoost / CatBoost） | `DecisionTree` `RandomForest` `GradientBoosting` `lgb.` `LGBM` `xgb.` `XGB` `CatBoost` `plot_tree` `dtreeviz` / 木、ブースティング | `references/tree-model.md` |
| モデル解釈（permutation・SHAP・PDP / ICE・ALE） | `shap.` `TreeExplainer` `KernelExplainer` `permutation_importance` `PartialDependenceDisplay` / 重要度、寄与、説明 | `references/model-interpretation.md` |
| 時系列（分解・定常性・ARIMA / 状態空間 / Prophet / VAR・変化点・予測）。系列そのものをモデル化するときだけ（特徴量を作って `TimeSeriesSplit` で評価するだけの予測は `ml-evaluation`） | `statsmodels.tsa` `SARIMAX` `ARIMA` `STL` `adfuller` `kpss` `plot_acf` `acorr_ljungbox` `Prophet` `VAR` `ruptures` / 季節性、トレンド、変化点 | `references/time-series.md` |

## 隣接する手法（このルーターでは扱わない）

| 手法 | 使う skill |
|---|---|
| 回帰係数の推論（OLS・GLM・混合効果）、検定、生存時間、MCMC | `statistical-inference-diagnostics` |
| A/B テスト、傾向スコア、DiD・IV・RDD（効果の主張） | `causal-inference-diagnostics` |
| 欠測補完・外れ値、クラスタリング、PCA・UMAP、異常検知 | `unsupervised-eda-diagnostics` |
| シミュレーション、数理最適化 | `simulation-optimization-diagnostics` |

## 出力と報告（全手法共通）

- 図は `outputs/diagnostics/<YYYYMMDD-HHMM>_<短縮名>/` に保存する（短縮名は各 references の冒頭）。報告にはパスと下の表だけを載せ、図は貼らない
- 図は 1 手法 1 枚の複合図を基本とし、各パネルのタイトルに「何を見る図か — 何が見えれば合格か」を書く。判定基準線は破線で描く
- 乱数を使う処理は seed を固定し報告に明記する。日本語フォント・配色・保存形式は visualization skill に従う
- コードの役割は図の保存と診断値の計算まで。値は「項目名 → 数値」の表（polars の DataFrame。pandas を返すライブラリの結果はそのまま載せてよい）にまとめて表示し、必要なら CSV で保存する。判定・合格基準・次アクションの文字列はコードで組み立てない
- 報告の「診断サマリー」に次の表を載せる。実測値はコードが出した値を転記し、判定（`OK` / `要対処` / `確認`＝人間の判断待ち）と次アクションは references の合格基準と図を見て報告側で書く。`要対処` には必ず次アクションを書く。全項目 OK でも表を出す

| 診断項目 | 実測値 | 合格基準 | 判定 | 次アクション |
|---|---|---|---|---|
| 前処理の Pipeline 化 | scaler が Pipeline 外 | Pipeline 内 | 要対処 | Pipeline に入れて CV 再実行 |
| CV AUC 平均 ± SD vs Dummy | 0.83 ± 0.02 vs 0.50 | ベースラインに勝つ | OK | — |

## 全手法共通の落とし穴

- スコアだけ返して終わらない。ベースライン（Dummy / naive）との比較と、references の「必ず出す図・値」が揃うまで未完了
- test データは最後に 1 回だけ。early stopping・チューニング・閾値決定に test を使ったら、それは検証セットであり test を取り直す
- 「重要度が高い」「予測に効く」を因果と読ませない。介入効果を言うなら `causal-inference-diagnostics` へ
- 次アクションに書いた別の手法（「GBDT でも確認」など）は報告上の提案であり、ユーザーの指示なしに当てはめない。指示されていない手法の図を混ぜると、どの結果を採用したのかが読み手に伝わらない
- 判定表をコードで生成しない。基準ごとの単純な閾値分岐だけでは、図や分析目的を踏まえた判断（件数は基準内でも図に形がある、など）を十分に扱えない。解釈・次アクションの文章をスクリプトに埋め込むと、分析コードも報告文で膨らむ（前提が崩れたら処理を止める `assert` は別）
  ```python
  # NG: 判定と次アクションをコードの分岐で組み立てる
  verdict = "OK" if scores.mean() > base.mean() else "要対処"
  # OK: 値を表で出すだけ。判定と次アクションは報告に書く
  vals = {"cv_auc_mean": scores.mean(), "cv_auc_sd": scores.std(), "dummy_auc": base.mean()}
  print(pl.DataFrame({"項目": list(vals), "値": list(vals.values())}, strict=False))  # int・float・文字列が混ざっても落ちない
  ```
