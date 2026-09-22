# シミュレーション（モンテカルロ・離散事象）の必須セット

短縮名: `sim`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_sim/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: モンテカルロ（リスク・不確実性の伝播）、離散事象シミュレーション（待ち行列・在庫・工程）、シナリオ比較、感度分析
- 扱わない: MCMC によるベイズ推定 → `statistical-inference-diagnostics`（`references/bayesian-mcmc.md`） / 最適化ソルバー → `references/optimization.md` / ブートストラップによる CI は各手法の skill

## ライブラリ

- numpy（`default_rng`、`SeedSequence.spawn`）、scipy.stats（入力分布の当てはめと GOF）、simpy（DES）、SALib（Sobol 感度）
- 未導入なら `uv add simpy SALib`。SALib が無ければ OAT（1 変数ずつ ±10〜20%）の tornado 図で代替し「一次の感度」と明記

## 必ず出す図

- running mean ± 95% CI vs 反復数（対数軸可） — 後半で平坦化し CI 幅が報告桁より狭ければ合格
- 出力の分布（ヒスト + 5 / 50 / 95 パーセンタイルに縦破線） — 平均だけで報告しない。裾の重さ・多峰性を見る
- DES: ウォームアップ判定図（時間 vs 移動平均、定常到達点に縦破線） — 定常到達後だけを集計していれば合格
- 感度分析: tornado 図（OAT）または Sobol 指数（S1 / ST）の棒 — 上位数変数で分散の大半が説明できるか
- シナリオ比較: 差の分布 + CI（共通乱数 CRN で対応づけ） — CI が 0 を含むかで判断

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| seed と乱数ストリーム | 反復ごとに独立ストリーム（`SeedSequence.spawn`）。seed を報告に明記 | — |
| MC 標準誤差（SD / √n）と CI 半幅 | 報告桁に対して十分小さい（例: 平均を 3 桁で報告するなら半幅 < 0.5 単位） | 反復数を増やす（半幅は 1/√n でしか縮まない） |
| 入力分布の根拠 | 実データに当てはめたなら Q-Q と GOF（KS / AD）を出す | 当てはまりが悪ければ経験分布を直接使う |
| 検証: 解析解との比較 | 一致（例: M/M/1 の L, W, Little の法則）。保存則（到着 = 退去 + 系内） | 実装バグを疑う |
| DES: ウォームアップ除去の有無 | 除去後の平均が安定 | ウォームアップ延長 |
| DES: 独立反復数 or バッチ数 | ≥ 10（CI は反復間 or バッチ平均から） | 1 本の長い run から CI を作らない |
| 裾リスク（分位点、P(X > 閾値)） | 報告に含む | — |

取得例（動作確認済み。`run_once(rng)` は 1 反復を返す関数）:

```python
from numpy.random import SeedSequence, default_rng
ss = SeedSequence(20240915)  # 報告に明記する seed
streams = [default_rng(s) for s in ss.spawn(n_rep)]  # 反復ごとに独立ストリーム
out = np.array([run_once(rng) for rng in streams])
mean, mcse = out.mean(), out.std(ddof=1) / np.sqrt(n_rep)  # MC 標準誤差
ci_half = 1.96 * mcse  # 報告桁に対して十分小さいか
running = np.cumsum(out) / np.arange(1, n_rep + 1)  # running mean（収束確認の図）
q05, q50, q95 = np.quantile(out, [0.05, 0.5, 0.95]); p_tail = (out > threshold).mean()  # 裾リスク
```

## 落とし穴

- 各反復の先頭で seed を固び直すと全反復が同じ乱数列になる
  ```python
  # NG: 反復ごとに同じ seed → 全反復が同一結果
  for i in range(n_rep): np.random.seed(0); out.append(run_once())
  ```
- 1 回の長い run から CI を作らない（系列相関で過小評価）。独立反復かバッチ平均法
- 反復数を 1,000 回と決め打ちして MCSE を見ない。MCSE が報告桁を決める
- シナリオ比較は共通乱数（CRN。同じ seed 列を両シナリオに）で行い、差の CI を出す
- 入力分布を「正規分布と仮定」で済ませない。実データがあれば当てはめ、なければ根拠を書く
