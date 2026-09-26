# 準実験（DiD・IV・RDD・合成コントロール）の必須セット

短縮名: `causal-qe`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_causal-qe/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: DiD / イベントスタディ、IV / 2SLS、RDD（sharp / fuzzy）、合成コントロール
- 扱わない: 傾向スコア・IPW・DML → `references/causal-observational.md` / ランダム化実験 → `references/ab-test.md` / パネルの分散成分そのもの → `statistical-inference-diagnostics`（`references/mixed-effects.md`）
- 推定に `smf.ols` / `PanelOLS` / `feols` / `IV2SLS` を使っても、`statistical-inference-diagnostics` の ols / mixed-effects は適用しない。固定効果ダミーを含む回帰の VIF・残差の正規性は識別の妥当性と関係がなく、診断は下の識別の項目で行う

## ライブラリ

- linearmodels（`PanelOLS`、`IV2SLS`）、pyfixest（`feols`。高次元固定効果・ワイルドクラスタブートストラップ）、statsmodels（`cov_type="cluster"`）
- rdrobust・rddensity（ともに Python 版。局所多項式と最適バンド幅 / 閾値の操作検定）、pysyncon（合成コントロール）
- Python に無いもの（Callaway-Sant'Anna、Sun-Abraham、honest DiD 等）は「R 推奨（did / fixest / HonestDiD）」と 1 行書く。未導入なら `uv add linearmodels pyfixest rdrobust rddensity`

## 全設計で共通して必ず出すもの

- 識別仮定を 1 段落で言語化（並行トレンド / 除外制約 / 閾値で処置割当が変わるルールと、閾値での潜在結果の連続性 / 処置前の適合）
- クラスタ頑健 SE（クラスタ = **処置の割付単位**。個人単位にしない）とクラスタ数
- プラセボ検定 1 つ（偽の処置時点 / 偽の閾値 / in-space プラセボ）
- 推定対象（ATT / LATE / 閾値での局所効果）の明記

## 必ず出す図（設計別）

- DiD: 処置群・対照群の生平均の時系列重ね描き（処置時点に縦破線） — 処置前に 2 本が平行なら並行トレンドを支持 / イベントスタディ図（リード・ラグ係数と 95% CI、基準期 = 処置直前、0 に水平破線） — 処置前係数が 0 の周りで無構造なら合格
- IV: first stage の散布図 or 係数図 — 操作変数と内生変数の関係が明確 / 縮約形（reduced form）の係数図 — 2SLS と符号が整合
- RDD: ビン化散布図 + 閾値両側の局所線形フィット — 閾値でだけ跳びがある / 推定値 vs バンド幅（最適の 0.5〜2 倍） — バンド幅を変えても推定が安定
- 合成コントロール: 実測 vs 合成の重ね描き（処置時点に縦破線） — 処置前が重なる / in-space プラセボの全ドナー軌跡（処置ユニットを太線） — 処置ユニットの乖離がプラセボ群の裾にある

## 必ず出す値（設計別）

| 設計 | 項目 | 合格基準 | 違反時の対処 |
|---|---|---|---|
| DiD | 処置前（リード）係数 | 0 の周りで無構造（\|t\| < 2 目安） | 対照群の再選択、群別トレンド項、合成コントロールへ |
| DiD | クラスタ数 | ≥ 30〜50 | `pyfixest` の `wildboottest` でワイルドクラスタブートストラップ |
| DiD | プラセボ効果（偽の処置時点） | 推定値 ≈ 0（p 値ではなく推定値と CI で読む） | 識別仮定を疑う |
| DiD | 段階的処置（staggered）の扱い | TWFE の負の重みを回避した推定量（Callaway-Sant'Anna 等）と併記 | 「R 推奨（did）」と書く |
| IV | 頑健 first-stage F | **> 10**（最低線）。`res.first_stage.diagnostics` の `f.stat` は頑健・クラスタ指定だと chi2(k) が返るので、**操作変数の数 k で割って**から比べる | 弱操作変数。AR 信頼区間を主結果に（β をグリッドで動かして検定を反転して作る。linearmodels の `res.anderson_rubin` は過剰識別検定で別物） |
| IV | OLS と 2SLS の並置、過剰識別なら Hansen J p | 併記 / J p > 0.05（2SLS 頑健は `res.wooldridge_overid`、J そのものは `IVGMM(...).fit().j_stat`） | 除外制約を言葉で正当化し直す |
| RDD | 処置割当の根拠 | 閾値の前後で処置（fuzzy なら処置確率）が不連続に変わるルール（制度・規則・運用）を資料で示せる | 示せなければ因果効果として解釈しない（跳びは記述として扱う）。fuzzy なら処置確率の跳び（first stage）を図と値で出す |
| RDD | McCrary 密度検定 p（`rddensity(X=x - c, c=0).test["p_jk"]`） | > 0.05 | running variable の操作を疑う。閾値近傍の質量点・申請フローを確認 |
| RDD | 推定値と CI の行 | `rdrobust` の `coef` / `ci` は Conventional / Bias-Corrected / **Robust** の 3 行。MSE 最適バンド幅なら Robust（点推定はバイアス補正値、CI は広い方）を主結果にする | 最適バンド幅と Conventional CI の組み合わせで報告していたら出し直す |
| RDD | 共変量の閾値での跳び（共変量ごとに `rdrobust`） | 跳びの推定値と 95% CI を出し、CI が「無視できる跳びの大きさ」（人間判断）の範囲に収まる。p > 0.05 だけで「跳びなし」としない | CI が 0 から明確に離れたら設計を疑う。CI が広くて範囲をはみ出すなら「バランスは確かめられない」として `確認` |
| RDD | 閾値両側の有効 n、多項式次数 | n と次数（局所線形なら p=1）を報告 | 有効 n が少ないなら、効果の推定も上の診断も精度が足りないと報告する |
| RDD | プラセボ（偽の閾値） | 偽の閾値は本当の閾値の片側に置き、その側の観測だけで推定する。推定値 ≈ 0（p 値ではなく推定値と CI で読む） | 識別仮定を疑う |
| 合成コントロール | 処置前 RMSPE、ドナー重みの表 | 処置前 RMSPE が小さい（対 処置後 RMSPE 比を併記） | ドナープール再選択 |
| 合成コントロール | 順列 p 値、leave-one-out | 処置ユニットの比が上位 / 安定 | 効果を主張しない |

取得例（DiD イベントスタディ + クラスタ頑健 SE）:

```python
import polars as pl
import statsmodels.formula.api as smf
# rel = 処置時点からの相対期。基準期 = -1（処置直前）。対照群は全期間 0
rel = pl.when(pl.col("treated") == 1).then(pl.col("rel")).otherwise(-1)
periods = [p for p in sorted(df.select(rel).to_series().unique()) if p != -1]  # 基準期はダミーから外す
df2 = df.with_columns([rel.eq(p).cast(pl.Int8).alias(f"rel_{p}") for p in periods])
rhs = " + ".join(f'Q("rel_{p}")' for p in periods)
pdf = df2.to_pandas()  # statsmodels の式 API は pandas を前提とする
es = smf.ols(f"y ~ {rhs} + C(unit) + C(period)", data=pdf).fit(
    cov_type="cluster", cov_kwds={"groups": pdf["cluster_id"]})  # クラスタ = 処置の割付単位
coefs = es.params[[f'Q("rel_{p}")' for p in periods]]; ci = es.conf_int().loc[coefs.index]  # リード・ラグ係数と CI
print("clusters =", df2["cluster_id"].n_unique(), "(< 30〜50 ならワイルドクラスタブートストラップ)")
```

## 落とし穴

- 段階的処置（staggered）を TWFE で推定して終わらない（負の重み問題）
  ```python
  # NG: 処置時期がユニットごとに違うのに 2×2 の TWFE だけで ATT を主張する
  smf.ols("y ~ treat:post + C(unit) + C(time)", data=df).fit()
  ```
- IV で first-stage F を報告せず 2SLS の係数だけ出さない。除外制約は検定できないので言葉で正当化する
- RDD で全データに高次多項式（≥ 3 次）を当てない。局所線形 + 最適バンド幅が基本
- RDD の閾値を、呼称や分布の切れ目から後付けで決めない。閾値で処置が変わるルールが先にあり、閾値はそこから決まる。ルールを示せないまま推定した跳びを効果と呼ばない
- 識別の確認が有意でないことを「仮定が成立した」と読み替えない（DiD の処置前係数、RDD の共変量の跳び・密度検定・プラセボ）。検出力が低いだけのことが多い（CI が推定したい効果量を含むなら何も言えていない。honest DiD は R 推奨）
- クラスタを個人単位にしない（処置が都道府県単位なら都道府県でクラスタ）
- 合成コントロールで処置前 RMSPE が大きいドナー構成のまま処置後の乖離を「効果」と呼ばない
