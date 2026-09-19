# 混合効果・パネル固定効果の必須セット

短縮名: `mixed`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_mixed/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 線形混合効果（ランダム切片・傾き）、パネル固定効果、反復測定、ネストした群構造
- 扱わない: ベイズ階層モデル → `references/bayesian-mcmc.md` / DiD・イベントスタディの識別 → `causal-inference-diagnostics`（`references/causal-quasi-experimental.md`） / 群構造のない回帰 → `references/ols.md`

## ライブラリ

- statsmodels（`smf.mixedlm(..., groups=, re_formula=, vc_formula=)`）、linearmodels（`PanelOLS(entity_effects=True)`）
- 交差ランダム効果や GLMM が本格的に必要なら pymer4 か bambi。無ければ「R 推奨（lme4 / glmmTMB）」と 1 行書く。未導入なら `uv add statsmodels linearmodels`

## 必ず出す図

- 群別軌跡（スパゲッティプロット。群は無作為に最大 30 に絞り、全体平均を太線） — 群ごとの切片・傾きのばらつきが目視でき、ランダム傾きの要否が判断できる
- 条件付き残差 vs 予測値 + 残差 Q-Q — 無構造・直線上なら合格。群ごとに残差の分散が違えば注記
- ランダム効果（BLUP）の Q-Q（切片・傾きそれぞれ） — 概ね直線なら合格。極端な群は実データを確認
- 固定効果の係数と 95% CI のフォレストプロット（0 に縦破線） — 単純 OLS の係数も並べ、群構造を無視した場合との差を見せる

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| **ICC**（切片のみの null モデルから） | > 0.05〜0.1 で混合効果を推奨 | 小さければ通常回帰 + クラスタ頑健 SE も選択肢（理由を書く） |
| 収束フラグ | `converged = True`、警告なし | 変数のスケーリング、ランダム効果構造の簡略化 |
| ランダム効果分散の最小値 | 0 近傍に張り付いていない | singular fit。構造を簡略化し理由を報告 |
| 群数 | ≥ 10（< 10 なら推定が不安定と明記） | 群を固定効果にする、ベイズ化 |
| 群あたりの観測数 | 分布を報告（1 件のみの群の割合） | ランダム傾きは群あたり ≥ 5 件目安 |
| 固定効果 + 95% CI | 自由度近似の限界に言及 | 重要な推論はブートストラップ（群単位で再抽出） |
| REML / ML の使い分け | 固定効果の比較（LRT / AIC）は ML、最終報告は REML | — |

取得例（動作確認済み。`df` は polars。列 `y`, `x`, `group`）:

```python
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

## 落とし穴

- REML 同士で固定効果の LRT 比較をしない（固定効果比較は ML で再推定）
  ```python
  # NG: REML で当てはめた 2 モデルの固定効果を LRT で比較する
  lr = 2 * (m_full_reml.llf - m_null_reml.llf)
  ```
- ネストした群（生徒 ⊂ 学級 ⊂ 学校）を単一の `groups` で潰さない（`vc_formula` で階層を表現）
- 群レベル変数と個体レベル変数の効果を混同しない（生態学的誤謬）。within / between を分けるなら群平均中心化
- 収束警告を無視して係数を報告しない。スケーリングと構造簡略化を先に試す
- 群数が少ない（< 10）のにランダム効果の分散を「推定できた」と書かない
