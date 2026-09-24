# MCMC（cmdstanpy + ArviZ）の必須セット

短縮名: `mcmc`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_mcmc/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: MCMC（NUTS/HMC）によるベイズ推定全般。階層モデル、状態空間、ベイズ回帰
- 扱わない: 頻度論の混合効果 → `references/mixed-effects.md` / 変分近似・pathfinder は探索用途のみ（最終結果には使わない）

## ライブラリ

- **cmdstanpy**（サンプリング）+ **ArviZ**（診断）を標準とする。Stan モデルは `.stan` ファイルに書き `CmdStanModel(stan_file=...)` でコンパイル
- 診断は `az.from_cmdstanpy(fit)` で ArviZ に一元化。**ArviZ 1.x で関数名と戻り値が変わった**（`plot_ppc` → `plot_ppc_dist`、`plot_trace` → `plot_trace_dist` ほか。図は PlotCollection を返し `pc.savefig(path)` で保存、Figure は `pc.viz["figure"].item()`）。下の取得例は 1.x。0.x のコードを動かすなら `arviz<1` に固定する
- 未導入なら `uv add cmdstanpy arviz` の後 `uv run install_cmdstan`（初回は CmdStan の C++ ビルドが要る）

```python
from cmdstanpy import CmdStanModel
import arviz as az  # 1.x

fit = CmdStanModel(stan_file="model.stan").sample(
    data=data, chains=4, iter_warmup=1000, iter_sampling=2000, adapt_delta=0.9, seed=0
)
print(fit.diagnose())  # cmdstanpy の組み込み診断を必ず実行し、出力をそのまま報告に貼る
idata = az.from_cmdstanpy(  # 事後予測の図は観測と同じ変数名・次元を要求するので dims をそろえる
    fit, posterior_predictive="y_rep", log_likelihood="log_lik", observed_data={"y": data["y"]},
    dims={"y": ["obs_id"], "y_rep": ["obs_id"], "log_lik": ["obs_id"]},
)
idata["posterior_predictive"] = idata["posterior_predictive"].to_dataset().rename({"y_rep": "y"})
s = az.summary(idata)
n_div = int(idata.sample_stats["diverging"].sum())
print(s["r_hat"].max(), s["ess_bulk"].min(), s["ess_tail"].min(), n_div, float(az.bfmi(idata)["energy"].min()))
```

## 必ず出す図

- トレースプロット（1.x: `az.plot_trace_dist` / 0.x: `az.plot_trace`） — 全 chain が毛虫状に重なれば合格。chain が別の場所に張り付けば多峰性
- ランクプロット（1.x: `az.plot_rank_dist` / 0.x: `az.plot_rank`） — 一様なら合格。chain 数が多いときはトレースより読みやすい
- エネルギープロット（`az.plot_energy`） — 2 つの分布が重なれば合格（BFMI 低下の可視化）
- 事後予測チェック（1.x: `az.plot_ppc_dist`、二値・カウントは `az.plot_ppc_pava` / `az.plot_ppc_rootogram` / 0.x: `az.plot_ppc(idata, data_pairs={"y": "y_rep"})`） — 観測が予測分布の典型域に入れば合格。収束診断の代替ではない
- divergence がある場合のみ 1.x: `az.plot_pair_focus(idata, focus_var="tau", visuals={"divergence": True})` / 0.x: `az.plot_pair(divergences=True)` — 発散点が漏斗（分散パラメータが小さい領域）に集中していないか

## 必ず出す値（**これが全部 OK になるまで事後分布の要約を報告しない**）

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| R-hat (max) | < 1.01（1.1 は古い基準） | warmup 延長、反復増、再パラメータ化 |
| ESS bulk (min) | > 400 | 反復増。自己相関の原因（パラメータ間の強相関）を直す |
| ESS tail (min) | > 400 | 同上。区間を報告するなら必須 |
| divergent transitions | 0 | 非中心化パラメータ化 → 事前分布を絞る → `adapt_delta` 0.9→0.95→0.99 の順（Stan の診断ガイドも `adapt_delta` は最後の手段としている）。事前分布を絞るのはサンプラーの設定ではなく事後分布そのものを変える操作なので、診断を通すためだけに絞らない。絞るなら領域知識の根拠を書き、事前予測チェックで妥当性を確かめ、事前分布を変える前後の事後要約を並べて感度を報告する。根拠がなければ飛ばして `adapt_delta` へ進む。`adapt_delta` を上げた後も全項目を診断し直す |
| BFMI (min) | > 0.3 | 再パラメータ化 |
| `fit.diagnose()` の出力 | 警告なし | 出力をそのまま報告に貼る |
| モデル比較時: Pareto k（`az.loo`） | < 0.7（全観測） | k > 0.7 の観測を個別確認 |
| サンプラー設定 | chains ≥ 4、warmup / sampling 反復数、adapt_delta、seed を明記 | — |

## 落とし穴

- divergence は「数個なら無視」ではない。階層モデルの漏斗を探索できていないサインで、事後分布に偏りが残りうる
- `adapt_delta` を上げて警告を消すだけの対処は誤り（発散が減っても、探索できていない領域が残ることがある）。まず非中心化（`theta = mu + sigma * theta_raw`）
- thinning は基本不要。ESS が足りないなら反復を増やすか、パラメータ化を直す
- 事後予測チェックは収束診断の代替ではない。両方必要
- `fit.diagnose()` を実行せずに `fit.summary()` だけ見ない

  ```python
  # NG: 診断を飛ばして要約だけ報告する
  print(fit.summary())
  print(az.hdi(idata))
  ```

- cmdstanpy は初回に Stan のコンパイルが要る。CI や共有環境ではコンパイル済みバイナリの有無を確認する
