# 数理最適化（LP / MIP / メタヒューリスティクス）の必須セット

短縮名: `opt`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_opt/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: LP / MIP / CP、非線形最適化（scipy）、メタヒューリスティクス（GA・焼きなまし等）、ハイパラ探索以外の optuna 利用
- 扱わない: モンテカルロ・離散事象 → `references/simulation.md` / ML のハイパラ探索 → `predictive-modeling-diagnostics`（`references/ml-evaluation.md`） / 強化学習は本 skill の外

## ライブラリ

- pulp（HiGHS / CBC）、mip（python-mip）、ortools（`pywraplp` / `cp_model`）、pyomo、cvxpy、scipy.optimize（`linprog` / `milp`）
- 未導入なら `uv add "pulp[highs]"`（highspy 同梱）。CBC は `uv add "pulp[cbc]"`（cbcbox）で入れて `COIN_CMD` から使う。PuLP 3.x の同梱 CBC と `PULP_CBC_CMD` は非推奨（`DeprecationWarning`）で 4.0 で削除済み
- ソルバーが無ければ `scipy.optimize.milp` で代替（小規模のみ。`res.mip_gap` / `res.mip_dual_bound` が取れる）

## 必ず出す図

- 目的値 / MIP gap vs 経過時間（gap の許容値に水平破線） — gap が許容値以下で終了していれば合格。時間切れなら「最適」と書かない
  - 履歴は API では返らない。ソルバーのコールバックで記録する（HiGHS: `pulp.HiGHS(callbackTuple=(fn, store), callbacksToActivate=[highspy.cb.HighsCallbackType.kCallbackMipImprovingSolution])` で `data_out.running_time` / `mip_primal_bound` / `mip_dual_bound` / `mip_gap`、CP-SAT: solution callback）。取れなければソルバーログを出力して解析し、それも無理なら最終 gap と経過時間だけは必ず出す
- 問題に応じた解の可視化: ガントチャート（スケジューリング）、経路図（VRP）、割当ヒートマップ（割当）、在庫推移（生産計画） — 制約（納期・容量）が図上で確認できること
- パラメータを ±10〜20% 振った感度分析の tornado 図（目的値の変化幅） — 上位数パラメータで変化の大半が説明できるか。解の構造（どの変数が非ゼロか）が変わるパラメータを注記
- メタヒューリスティクス: 複数 seed の収束曲線（best-so-far vs 世代） — 全 seed が同水準で平坦化していれば合格

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| **ソルバー status と sol_status** | OPTIMAL。pulp は `prob.sol_status == LpSolutionOptimal`（`prob.status` だけでは判定できない） | 時間切れ（`Solution Found` / FEASIBLE）なら **MIP gap と経過時間を明記し「最適」と書かない** |
| 同（pulp 以外の語彙） | CP-SAT: `status == cp_model.OPTIMAL`（`FEASIBLE` は打ち切り）/ scipy: `res.status == 0`（`1` は上限到達）/ cvxpy: `prob.status == "optimal"` | `FEASIBLE`・`optimal_inaccurate` は上の行と同じ扱い |
| 制約違反量の最大値と目的値の再計算差（解を代入して独立再検証） | どちらも < 1e-6 | 整数丸め・許容誤差・単位の確認。再計算差が出るなら定式化と集計のずれ |
| ベースライン（現行運用・貪欲法・手作業）との目的値比較 | 改善率を報告 | 改善が無いなら定式化の見直し |
| 係数の最大 / 最小比 | < 1e6 目安 | スケーリング、big-M を必要最小に |
| LP: 双対値（シャドウプライス）と reduced cost | 整数条件を外した LP を**別に解いて**取得し、拘束制約の解釈（「容量を 1 増やすと目的値が X 改善」）が書ける | MIP の解から読んだ値は使わない（下の落とし穴） |
| 規模（変数数 / 制約数 / 整数変数数）とソルバー設定（名前・バージョン・`timeLimit` / `gapRel` / `random_seed`） | 報告に含む。MIP ソルバーも内部でヒューリスティクスを使うので seed を固定する | — |
| INFEASIBLE 時: 原因制約 | どの制約がどれだけ破れているかまで特定できている | 全制約にスラック変数を足して違反量の最小化で解き直す（elastic 化）。IIS が取れるソルバー（商用・highspy の `getIis`）ならそちらでも |
| メタヒューリスティクス: seed ≥ 5 の best / mean / worst | ばらつきが小さい。小規模で厳密解と比較 | 反復増、パラメータ再調整 |

取得例（PuLP 3.3.2 + HiGHS。`build(cat)` は同じ問題を指定の変数種別で組む関数）:

```python
prob, x = build("Integer")  # 変数は prob.add_variable_dicts（LpVariable.dicts は 4.0 で削除）
prob.solve(pulp.HiGHS(msg=False, timeLimit=60, gapRel=0.01, random_seed=0))  # 打ち切り条件と seed は報告に書く
assert prob.sol_status not in (pulp.LpSolutionNoSolutionFound, pulp.LpSolutionInfeasible), "解なし"
obj = pulp.value(prob.objective)
vals = {"status": pulp.LpStatus[prob.status], "sol_status": pulp.LpSolution[prob.sol_status]}  # 時間切れでも Optimal
vals["定員超過"] = max(0.0, sum(weight[i] * x[i].value() for i in items) - capacity)  # 解を代入して独立再検証
vals["目的値の再計算差"] = abs(sum(profit[i] * x[i].value() for i in items) - obj)
lp, _ = build("Continuous")  # 双対値は整数条件を外した LP を別に解く
lp.solve(pulp.HiGHS(msg=False, random_seed=0))
vals["定員の双対値"] = -lp.get_constraint_by_name("capacity").pi  # HiGHS は最大化を最小化に変換するため符号反転
```

## 落とし穴

- `prob.solve()` の status を見ずに `value(x)` を報告しない（INFEASIBLE でも値は返る）。pulp は時間切れでも `status == Optimal` になる（CBC・HiGHS とも）ので `sol_status` を見る。時間切れの incumbent を「最適解」と書かず gap と経過時間を併記する。status は診断値として表に出すもので、時間切れを `assert` で止めるのは行き過ぎ（止めるのは解が無いときだけ）
  ```python
  # NG: status を見ずに目的値を報告する（時間切れ・実行不能でも値は返る）
  prob.solve(); print("最適値:", pulp.value(prob.objective))
  ```
- MIP を解いた `prob` から双対値を読まない。`constraint.pi` は MIP でも例外にならず **0.0 が黙って返る**ため「拘束していない」と誤読する。LP 緩和を別に解く（`prob.constraints[name]` の dict アクセスも 3.x で非推奨。`get_constraint_by_name` を使う）
- big-M = 1e9 は数値不安定を招く。必要最小の M をデータから導出する
- 目的関数に円と分を足さない（単位を揃え、重みの根拠を書く）
- 「最適化した」だけで現行比の改善率を書かないのは報告として不完全
