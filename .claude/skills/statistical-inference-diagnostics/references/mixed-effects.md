# 混合効果・パネル固定効果の必須セット

短縮名: `mixed`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_mixed/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 線形混合効果（ランダム切片・傾き）、パネル固定効果、反復測定、ネストした群構造
- 扱わない: ベイズ階層モデル → `references/bayesian-mcmc.md` / DiD・イベントスタディの識別 → `causal-inference-diagnostics`（`references/causal-quasi-experimental.md`。処置と効果の主張があるなら `PanelOLS` で推定していても本ファイルは適用しない） / 群構造のない回帰 → `references/ols.md`

## ライブラリ

- statsmodels（`smf.mixedlm(..., groups=, re_formula=, vc_formula=)`）、linearmodels（`PanelOLS(entity_effects=True)`、`.fit(cov_type="clustered", cluster_entity=True)`）、pyfixest（高次元固定効果と `wildboottest`）
- 交差ランダム効果や GLMM が本格的に必要なら pymer4 か bambi。無ければ「R 推奨（lme4 / glmmTMB）」と 1 行書く。未導入なら `uv add statsmodels linearmodels`

## 必ず出す図（共通 4 パネル + 手法別 1 パネル）

共通（群構造を扱うなら手法を問わず）:

- 群別軌跡（スパゲッティプロット。群は無作為に最大 30 に絞り、全体平均を太線） — 群ごとの切片・傾きのばらつきが目視でき、ランダム傾きの要否が判断できる
- 残差 vs 予測値 と 残差 Q-Q の 2 枚（混合効果は条件付き残差、固定効果は群内（within）残差） — 無構造・直線上なら合格。群ごとに残差の分散が違えば注記
- 回帰係数と 95% CI のフォレストプロット（0 に縦破線） — 群構造を無視した単純 OLS の係数も並べ、差を見せる

群効果の形は手法で違う。**使った手法の行だけ**を出す:

| 使った手法 | 出す図 | 合格の読み方 |
|---|---|---|
| 混合効果（`mixedlm`） | ランダム効果（BLUP）の Q-Q（切片・傾きそれぞれ） | 概ね直線。外れる群は実データを確認する |
| 固定効果（`PanelOLS` / `pyfixest`） | 推定された個体効果の分布（ヒスト or Q-Q。`res.estimated_effects` を群ごとに 1 点へ畳む） | 少数の群に極端な効果が偏っていない。偏るなら該当群の実データを確認する |

## 必ず出す値

| 区分 | 項目 | 合格基準 | 違反時の対処 |
|---|---|---|---|
| 共通 | 群数 | ≥ 10（< 10 なら推定が不安定と明記） | 群を固定効果にする、ベイズ化 |
| 共通 | 群あたりの観測数 | 分布を報告（1 件のみの群の割合） | ランダム傾きは群あたり ≥ 5 件目安 |
| 共通 | 回帰係数 + 95% CI | 群構造を無視した OLS と並置 | — |
| 共通 | **固定効果（FE）と変量効果（RE）のどちらを選んだかと理由** | 群効果と説明変数の相関、推定対象（群内の効果か群間の差か）を 1 段落で書く | 相関が疑われるのに RE を使っているなら FE か群平均中心化（Mundlak）へ。Hausman 検定を根拠にするなら不均一分散下では壊れることも書く |
| 混合効果 | **ICC**（切片のみの null モデルから） | > 0.05〜0.1 で混合効果を推奨 | 小さければ通常回帰 + クラスタ頑健 SE も選択肢（理由を書く） |
| 混合効果 | 収束フラグ | `converged = True`、警告なし | 変数のスケーリング、ランダム効果構造の簡略化 |
| 混合効果 | ランダム効果分散の最小値 | 0 近傍に張り付いていない | singular fit。構造を簡略化し理由を報告 |
| 混合効果 | 係数の自由度近似 | 限界に言及 | 重要な推論はブートストラップ（群単位で再抽出） |
| 混合効果 | REML / ML の使い分け | 固定効果の比較（LRT / AIC）は ML、最終報告は REML | — |
| 固定効果 | クラスタ数とクラスタ頑健 SE の種類 | クラスタ = 群。クラスタ数 ≥ 30〜50 | 少なければワイルドクラスタブートストラップ（`pyfixest` の `wildboottest`） |
| 固定効果 | within / between / overall R² | 3 つ併記 | within だけを見て「説明できた」と書かない |
| 固定効果 | 時間不変変数の扱い | 固定効果に吸収されて推定できないことを明記 | linearmodels は `AbsorbingEffectError` で落ちる。群間差を見たいなら RE・Mundlak か、時間変数との交互作用にする |

取得例（`df` は polars。列 `y`, `x`, `group`）:

```python
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

df_pd = df.to_pandas()  # statsmodels の式 API は pandas を前提とする
null = smf.mixedlm("y ~ 1", df_pd, groups=df_pd["group"]).fit(reml=True)
icc = null.cov_re.iloc[0, 0] / (null.cov_re.iloc[0, 0] + null.scale)  # ICC（切片のみモデル）
m = smf.mixedlm("y ~ x", df_pd, groups=df_pd["group"], re_formula="~x").fit(reml=True)
print(m.converged, np.diag(m.cov_re).min())  # 収束フラグ、ランダム効果分散の最小値（0 近傍は singular）
blup = pd.DataFrame(m.random_effects).T  # BLUP（Q-Q 用）。random_effects は pandas Series の dict
ci = m.conf_int().loc[["x"]]  # 固定効果の 95% CI
ml_full, ml_null = [smf.mixedlm(f, df_pd, groups=df_pd["group"]).fit(reml=False) for f in ("y ~ x", "y ~ 1")]  # LRT は ML で
```

固定効果（`panel` は `unit`・`time` の 2 段 index を持つ pandas）:

```python
from linearmodels.panel import PanelOLS

res = PanelOLS(panel["y"], panel[["x"]], entity_effects=True).fit(cov_type="clustered", cluster_entity=True)
r2 = (res.rsquared_within, res.rsquared_between, res.rsquared_overall)  # 3 つ併記する
eff = res.estimated_effects.groupby(level=0).first().iloc[:, 0]  # 群ごとの個体効果（分布の図用）
n_cluster = panel.index.get_level_values(0).nunique()  # < 30〜50 ならワイルドクラスタブートストラップ
# 時間不変変数を入れると AbsorbingEffectError で落ちる（固定効果に吸収されるため推定できない）
```

## 落とし穴

- REML 同士で固定効果の LRT 比較をしない（固定効果比較は ML で再推定）
  ```python
  # NG: REML で当てはめた 2 モデルの固定効果を LRT で比較する
  lr = 2 * (m_full_reml.llf - m_null_reml.llf)
  ```
- ネストした群（生徒 ⊂ 学級 ⊂ 学校）を単一の `groups` で潰さない（`vc_formula` で階層を表現）
- 群レベル変数と個体レベル変数の効果を混同しない（生態学的誤謬）。within / between を分けるなら群平均中心化
- 固定効果は群内の変動だけを使う。問いが群間の差（地域そのものの違い）なら、FE はその変動を捨てているので答えられない
- 収束警告を無視して係数を報告しない。スケーリングと構造簡略化を先に試す
- 群数が少ない（< 10）のにランダム効果の分散を「推定できた」と書かない
