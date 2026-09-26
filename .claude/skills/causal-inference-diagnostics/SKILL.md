---
name: causal-inference-diagnostics
description: >-
  因果推論・効果検証（A/B テスト / ABテスト / オンライン実験 / リフト / SRM / CUPED、観察データの処置効果 / ATE / ATT /
  CATE / 傾向スコア / propensity score / IPW / 二重頑健 / DML / causal forest、準実験 / 差の差 / DiD / イベントスタディ /
  操作変数 / IV / 2SLS / 回帰不連続 / RDD / 合成コントロール）を実行したら必ずセットで出す図と値のルーター。
  proportions_ztest, chisquare, statsmodels.stats.power, dowhy, econml, causalml, doubleml, propensity, LinearDML,
  IV2SLS, rdrobust, rddensity, pysyncon, treat*post がコードに現れたとき、またはユーザーが「ABテストの結果を
  見て」「施策の効果を推定して」「差の差で」「傾向スコアで揃えて」「閾値前後で比較して」と言ったときに使う。SRM・
  バランス・並行トレンド・first-stage に言及がなくても適用する。SKILL.md のルーティング表で設計を特定し、対応する
  references/<設計>.md を読んでから実行する。実験でない群間比較の検定は statistical-inference-diagnostics、
  予測モデルの解釈（SHAP 等）は predictive-modeling-diagnostics を使う。
---

# 因果推論・効果検証の必須セット（ルーター）

分析の実行と診断は不可分である。モデルを当てはめて係数やスコアだけを返すのは分析の前半でしかなく、
本スキルの適用下では未完了とみなす。ユーザーが診断・図・残差に言及しなくても、該当する references の図と値は必ず出す。

## 使い方（この順で）

1. まず **割付がランダムか** を確認し、下の表で設計を特定する（ランダム → A/B、非ランダムで共変量調整 → 観察データ、制度・閾値・時点の変化を使う → 準実験）。読むのは**使った設計の行だけ**。ユーザーが設計の比較（例: IPW と DiD の両方で）を指示したときだけ複数読む
   - 推定の部品として使うモデルには、他の skill の references を適用しない。傾向スコアのモデルの `LogisticRegression` は `glm.md`、DML の nuisance モデルの木・GBDT は `tree-model.md` / `ml-evaluation.md`、イベントスタディを推定する `smf.ols` / `PanelOLS` / `feols` は `ols.md` / `mixed-effects.md` の対象にならない。部品の良し悪しは各 references の表（PS の AUC、nuisance の out-of-fold 性能、クラスタ頑健 SE）で見る
   - 処置（施策・介入）と効果の主張がない固定効果回帰・パネル回帰は、`PanelOLS` を使っていても `statistical-inference-diagnostics`（`references/mixed-effects.md`）
2. その行の `references/<設計>.md` を**読んでから**分析を実行する（読まずに推定しない）
3. 図を保存し、報告に「出力と報告」の判定表を載せる。推定対象（ATE / ATT / LATE）と識別仮定を必ず 1 段落で書く

## ルーティング表

| 設計 | トリガー語彙（コード / 日本語） | 読むファイル |
|---|---|---|
| A/B テスト・オンライン実験（ランダム割付） | `proportions_ztest` `confint_proportions_2indep` `chisquare` `statsmodels.stats.power` `variant` / リフト、バリアント、SRM、CUPED | `references/ab-test.md` |
| 観察データ: 傾向スコア（マッチング / IPW）・二重頑健・DML・causal forest | `dowhy` `CausalModel` `econml` `LinearDML` `CausalForestDML` `doubleml` `DoubleMLPLR` `causalml` `propensity` `ipw` / 処置効果、ATE、ATT、CATE | `references/causal-observational.md` |
| 準実験: DiD・イベントスタディ・IV / 2SLS・RDD・合成コントロール | `IV2SLS` `IVGMM` `rdrobust` `rddensity` `pysyncon` `treat*post` / 差の差、並行トレンド、操作変数、閾値、施策の前後 | `references/causal-quasi-experimental.md` |

## 隣接する手法（このルーターでは扱わない）

| 手法 | 使う skill |
|---|---|
| 実験でない群間比較の検定、回帰係数の推論、混合効果、処置のない固定効果回帰 | `statistical-inference-diagnostics` |
| 予測モデルの評価・解釈（SHAP・重要度は因果ではない） | `predictive-modeling-diagnostics` |
| 欠測・外れ値の前処理、クラスタリング | `unsupervised-eda-diagnostics` |
| シミュレーションによる what-if、最適化 | `simulation-optimization-diagnostics` |

## 出力と報告（全設計共通）

- 図は `outputs/diagnostics/<YYYYMMDD-HHMM>_<短縮名>/` に保存する（短縮名は各 references の冒頭）。報告にはパスと下の表だけを載せ、図は貼らない
- 図は 1 手法 1 枚の複合図を基本とし、各パネルのタイトルに「何を見る図か — 何が見えれば合格か」を書く。判定基準線は破線で描く
- 乱数を使う処理は seed を固定し報告に明記する。日本語フォント・配色・保存形式は visualization skill に従う
- コードの役割は図の保存と診断値の計算まで。値は「項目名 → 数値」の表（polars の DataFrame。pandas を返すライブラリの結果はそのまま載せてよい）にまとめて表示し、必要なら CSV で保存する。判定・合格基準・次アクションの文字列はコードで組み立てない
- 報告の「診断サマリー」に次の表を載せる。実測値はコードが出した値を転記し、判定（`OK` / `要対処` / `確認`＝人間の判断待ち）と次アクションは references の合格基準と図を見て報告側で書く。`要対処` には必ず次アクションを書く。全項目 OK でも表を出す

| 診断項目 | 実測値 | 合格基準 | 判定 | 次アクション |
|---|---|---|---|---|
| SRM p | 0.42 | > 0.001 | OK | — |
| \|SMD\| max（調整後） | 0.18 | < 0.1 | 要対処 | PS モデルに age² と交互作用を追加 |

## 全設計共通の落とし穴

- 効果の点推定だけ返して終わらない。ナイーブ比較との併置、95% CI、識別仮定、プラセボ / 感度分析が揃うまで未完了
- 観察データ・準実験の結論には必ず「（識別仮定）の下で」を付ける。仮定が検定で確認できないものは言葉で正当化する
- 予測モデルの作法（train/test 分割で「テスト」する、AUC を上げる）を効果推定に持ち込まない。PS の目的はバランスであって予測精度ではない（DML の cross-fitting は推定量の一部なので別）
- 次アクションに書いた別の設計（「合成コントロールでも確認」など）は報告上の提案であり、ユーザーの指示なしに当てはめない。指示されていない設計の図を混ぜると、どの推定を採用したのかが読み手に伝わらない
- 判定表をコードで生成しない。基準ごとの単純な閾値分岐だけでは、図や分析目的を踏まえた判断（件数は基準内でも図に形がある、など）を十分に扱えない。解釈・次アクションの文章をスクリプトに埋め込むと、分析コードも報告文で膨らむ（前提が崩れたら処理を止める `assert` は別）
  ```python
  # NG: 判定と次アクションをコードの分岐で組み立てる
  verdict = "OK" if smd_max < 0.1 else "要対処"
  # OK: 値を表で出すだけ。判定と次アクションは報告に書く
  vals = {"smd_max_after": smd_max, "ps_auc": ps_auc, "kish_ess": ess}
  print(pl.DataFrame({"項目": list(vals), "値": list(vals.values())}, strict=False))  # int・float・文字列が混ざっても落ちない
  ```
