---
name: statistical-inference-diagnostics
description: >-
  統計的推論（線形回帰 / 重回帰 / OLS / Lasso / Ridge / 分位点回帰、ロジスティック回帰 / ポアソン / GLM / オッズ比、
  混合効果 / マルチレベル / パネル固定効果、仮説検定 / t 検定 / χ² / ANOVA / 有意差、生存時間分析 / Kaplan-Meier / Cox、
  ベイズ推定 / MCMC / Stan）を実行したら必ずセットで出す図と値のルーター。statsmodels, sm.OLS, smf.ols, LinearRegression,
  LassoCV, sm.Logit, sm.GLM, LogisticRegression, mixedlm, PanelOLS, scipy.stats, ttest_ind, mannwhitneyu, chi2_contingency,
  pingouin, lifelines, CoxPHFitter, cmdstanpy, arviz がコードに現れたとき、またはユーザーが「回帰して」「検定して」
  「有意差はあるか」「生存曲線を描いて」「ベイズで推定して」と言ったときに使う。診断・残差・図に言及がなくても適用する。
  SKILL.md のルーティング表で手法を特定し、対応する references/<手法>.md を読んでから実行する。A/B テスト・因果推論は
  causal-inference-diagnostics、予測 ML・時系列は predictive-modeling-diagnostics を使う。
---

# 統計的推論の必須セット（ルーター）

分析の実行と診断は不可分である。モデルを当てはめて係数やスコアだけを返すのは分析の前半でしかなく、
本スキルの適用下では未完了とみなす。ユーザーが診断・図・残差に言及しなくても、該当する references の図と値は必ず出す。

## 使い方（この順で）

1. 下のルーティング表で、これから書く（またはコードにある）手法の行を見つける。複数該当なら全部
2. その行の `references/<手法>.md` を**読んでから**分析を実行する（読まずに当てはめない）
3. 図を保存し、報告に「出力と報告」の判定表を載せる

## ルーティング表

| 手法 | トリガー語彙（コード / 日本語） | 読むファイル |
|---|---|---|
| 線形回帰・重回帰・Lasso / Ridge・分位点回帰 | `sm.OLS` `smf.ols` `LinearRegression` `LassoCV` `RidgeCV` `QuantReg` / 回帰、最小二乗 | `references/ols.md` |
| ロジスティック・ポアソン・負の二項・GLM | `sm.Logit` `sm.GLM` `smf.glm` `family=` `LogisticRegression` `PoissonRegressor` / オッズ比、件数の回帰 | `references/glm.md` |
| 混合効果・マルチレベル・パネル固定効果 | `mixedlm` `MixedLM` `groups=` `re_formula` `PanelOLS` `entity_effects` / 店舗ごとの効果、反復測定 | `references/mixed-effects.md` |
| 仮説検定・多重比較（**既定では検定せず推定で答える**） | `ttest_ind` `ttest_rel` `mannwhitneyu` `chi2_contingency` `f_oneway` `anova_lm` `pingouin` `multipletests` / 有意差、p 値 | `references/hypothesis-test.md` |
| 生存時間・Kaplan-Meier・Cox・AFT | `lifelines` `KaplanMeierFitter` `CoxPHFitter` `logrank_test` / 打ち切り、ハザード比、解約までの時間 | `references/survival.md` |
| ベイズ推定・MCMC・階層モデル | `cmdstanpy` `CmdStanModel` `.sample(` `arviz` `az.` `pm.sample` / 事後分布、Stan | `references/bayesian-mcmc.md` |

## 隣接する手法（このルーターでは扱わない）

| 手法 | 使う skill |
|---|---|
| A/B テスト、傾向スコア・IPW・DML、DiD・IV・RDD・合成コントロール | `causal-inference-diagnostics` |
| 予測モデルの評価・木モデル・SHAP、時系列（ARIMA・季節性・予測） | `predictive-modeling-diagnostics` |
| 欠測・外れ値、クラスタリング、PCA・因子分析、異常検知 | `unsupervised-eda-diagnostics` |
| モンテカルロ・離散事象シミュレーション、数理最適化 | `simulation-optimization-diagnostics` |

## 出力と報告（全手法共通）

- 図は `outputs/diagnostics/<YYYYMMDD-HHMM>_<短縮名>/` に保存する（短縮名は各 references の冒頭）。報告にはパスと下の表だけを載せ、図は貼らない
- 図は 1 手法 1 枚の複合図を基本とし、各パネルのタイトルに「何を見る図か — 何が見えれば合格か」を書く。判定基準線は破線で描く
- 乱数を使う処理は seed を固定し報告に明記する。日本語フォント・配色・保存形式は visualization skill に従う
- コードの役割は図の保存と診断値の計算まで。値は「項目名 → 数値」の表（polars の DataFrame。pandas を返すライブラリの結果はそのまま載せてよい）にまとめて表示し、必要なら CSV で保存する。判定・合格基準・次アクションの文字列はコードで組み立てない
- 報告の「診断サマリー」に次の表を載せる。実測値はコードが出した値を転記し、判定（`OK` / `要対処` / `確認`＝人間の判断待ち）と次アクションは references の合格基準と図を見て報告側で書く。`要対処` には必ず次アクションを書く。全項目 OK でも表を出す

| 診断項目 | 実測値 | 合格基準 | 判定 | 次アクション |
|---|---|---|---|---|
| Breusch-Pagan p | 0.003 | > 0.05 | 要対処 | HC3 ロバスト SE で再推定 |
| VIF (max) | 3.2 | < 10 | OK | — |

## 全手法共通の落とし穴

- 係数・p 値・スコアだけ返して終わらない。references の「必ず出す図・値」が揃うまで未完了
- 合格基準を満たさない項目を黙って除外・変換して通さない。判定表に `要対処` / `確認` として残し、人間判断が要るものは実データを見せる
- references に無い手法を使うときも、この「出力と報告」の書式で診断表を作り、根拠にした基準を明記する
- 判定表をコードで生成しない。基準ごとの if 分岐や解釈・次アクションの文章をスクリプトに埋め込むと、分析コードが報告文で膨らみ、人間の判断を自動化したように見せてしまう（前提が崩れたら処理を止める `assert` は別）
  ```python
  # NG: 判定と次アクションをコードの分岐で組み立てる
  verdict = "OK" if bp_p > 0.05 else "要対処"
  # OK: 値を表で出すだけ。判定と次アクションは報告に書く
  vals = {"bp_p": bp_p, "vif_max": vif_max, "cooks_n": cooks_n, "dw": dw}
  print(pl.DataFrame({"項目": list(vals), "値": list(vals.values())}))
  ```
