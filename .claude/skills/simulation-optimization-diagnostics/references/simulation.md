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
  - simpy は等間隔の記録が自前になる。監視用プロセスを 1 本走らせて取る（`while True: log.append((env.now, 指標)); yield env.timeout(間隔)`）
- 感度分析: tornado 図（OAT）または Sobol 指数（S1 / ST）の棒 — 上位数変数で分散の大半が説明できるか
- シナリオ比較: 差の分布 + CI（共通乱数 CRN で対応づけ） — CI が 0 を含むかで判断

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| seed と乱数ストリーム | 反復ごとに独立ストリーム（`SeedSequence.spawn`）。seed を報告に明記。`np.random.seed` / `np.random.rand` などのグローバル API は使わず `default_rng` の rng を引き回す | — |
| MC 標準誤差（SD / √n）と CI 半幅 | 報告桁に対して十分小さい（例: 平均を 3 桁で報告するなら半幅 < 0.5 単位） | 反復数を増やす（半幅は 1/√n でしか縮まない） |
| 入力分布の根拠 | 実データに当てはめたなら Q-Q と GOF（KS / AD）を出す。パラメータを同じデータから推定した KS の p 値はそのまま解釈できないので、Q-Q と経験分布の重ね描きを主に見る | 当てはまりが悪ければ経験分布を直接使う。実データが無く見積りだけなら三角分布で min / mode / max を明示する |
| 検証: 解析解との比較 | 平均は解析解との差が 3 × MCSE 未満、分散は解析解との比が 0.9〜1.1（例: M/M/1 の L, W, Little の法則）。保存則（到着 = 退去 + 系内）の残差はほぼ 0 | 実装バグを疑う |
| DES: ウォームアップ除去の有無 | 除去後の平均が安定 | ウォームアップ延長 |
| DES: 独立反復数 or バッチ数 | ≥ 10（CI は反復間 or バッチ平均から）。バッチ平均法はバッチ平均の lag-1 自己相関が 0.2 未満であることを確認 | 1 本の長い run から CI を作らない。相関が残るならバッチ長を倍にする |
| 裾リスク（分位点、P(X > 閾値)） | 報告に含む。超過確率は標準誤差 √(p̂(1−p̂)/n) と CI 半幅を併記する（分位点は平均より収束が遅い。精度が要るなら順序統計量の CI を出す） | 反復数を増やす（p̂ が 0 に近いほど必要反復数は桁で増える） |
| シナリオ比較: CRN の効き | CRN あり / なしの両方で差の SD を出し、CRN 側が小さい | 縮まないなら乱数の同期が崩れている（下の落とし穴） |

取得例（`run_once(rng)` は 1 反復を返す関数）:

```python
import numpy as np
from numpy.random import SeedSequence, default_rng
ss = SeedSequence(20240915)  # 報告に明記する seed
streams = [default_rng(s) for s in ss.spawn(n_rep)]  # 反復ごとに独立ストリーム
out = np.array([run_once(rng) for rng in streams])
mean, mcse = out.mean(), out.std(ddof=1) / np.sqrt(n_rep)  # MC 標準誤差
ci_half = 1.96 * mcse  # 報告桁に対して十分小さいか
running = np.cumsum(out) / np.arange(1, n_rep + 1)  # running mean（収束確認の図）
q05, q50, q95 = np.quantile(out, [0.05, 0.5, 0.95]); p_tail = (out > threshold).mean()  # 裾リスク
p_tail_se = np.sqrt(p_tail * (1 - p_tail) / n_rep)  # 裾の MCSE。分位点は平均より収束が遅い
```

## 落とし穴

- 各反復の先頭で seed を固定し直すと全反復が同じ乱数列になる。`np.random.*` のグローバル状態に依存せず、`default_rng` で作った rng を引数で引き回す（並列化・CRN でのバグ源）
  ```python
  # NG: 反復ごとに同じ seed → 全反復が同一結果
  for i in range(n_rep): np.random.seed(0); out.append(run_once())
  ```
- 1 回の長い run から CI を作らない（系列相関で過小評価）。独立反復かバッチ平均法
- 反復数を 1,000 回と決め打ちして MCSE を見ない。MCSE が報告桁を決める
- シナリオ比較は共通乱数（CRN）で行い、差の CI を出す。**同じ rng オブジェクトを 2 つのシナリオに続けて渡すのは CRN にならない**（Generator は状態を持つので 2 本目は別の乱数列になる）。1 反復の中で引いた乱数配列を両シナリオに使うか、同じ子 seed から rng を作り直す。DES では消費本数がずれると同期が崩れるので、確率要素（到着・サービス）ごとにストリームを分ける
- 入力分布を「正規分布と仮定」で済ませない。実データがあれば当てはめ、なければ根拠を書く
