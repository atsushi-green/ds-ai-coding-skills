# 数理最適化（LP / MIP / メタヒューリスティクス）の必須セット

短縮名: `opt`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_opt/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: LP / MIP / CP、非線形最適化（scipy）、メタヒューリスティクス（GA・焼きなまし等）、ハイパラ探索以外の optuna 利用
- 扱わない: モンテカルロ・離散事象 → `references/simulation.md` / ML のハイパラ探索 → `predictive-modeling-diagnostics`（`references/ml-evaluation.md`） / 強化学習は本 skill の外

## ライブラリ

- pulp（CBC / HiGHS）、mip（python-mip）、ortools（`pywraplp` / `cp_model`）、pyomo、cvxpy、scipy.optimize（`linprog` / `milp`）
- 未導入なら `uv add "pulp[highs]"`（HiGHS ソルバー込み。PuLP 3.x で同梱 CBC の `PULP_CBC_CMD` は非推奨、4.0 で削除予定）。ソルバーが無ければ scipy の `milp` で代替（小規模のみ）

## 必ず出す図

- 目的値 / MIP gap vs 経過時間（gap の許容値に水平破線） — gap が許容値以下で終了していれば合格。時間切れなら「最適」と書かない
- 問題に応じた解の可視化: ガントチャート（スケジューリング）、経路図（VRP）、割当ヒートマップ（割当）、在庫推移（生産計画） — 制約（納期・容量）が図上で確認できること
- パラメータを ±10〜20% 振った感度分析の tornado 図（目的値の変化幅） — 上位数パラメータで変化の大半が説明できるか。解の構造（どの変数が非ゼロか）が変わるパラメータを注記
- メタヒューリスティクス: 複数 seed の収束曲線（best-so-far vs 世代） — 全 seed が同水準で平坦化していれば合格

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| **ソルバー status と sol_status** | OPTIMAL（pulp なら `prob.sol_status == LpSolutionOptimal`） | 時間切れ（`Solution Found` / FEASIBLE）なら **MIP gap と経過時間を明記し「最適」と書かない** |
| 制約違反量の最大値（解を代入して独立再検証） | < 1e-6 | 整数丸め・許容誤差・単位の確認 |
| ベースライン（現行運用・貪欲法・手作業）との目的値比較 | 改善率を報告 | 改善が無いなら定式化の見直し |
| 係数の最大 / 最小比 | < 1e6 目安 | スケーリング、big-M を必要最小に |
| LP: 双対値（シャドウプライス）と reduced cost | 拘束制約の解釈（「容量を 1 増やすと目的値が X 改善」）が書ける | — |
| 変数数 / 制約数 / 整数変数数 | 報告に含む | — |
| INFEASIBLE 時: 原因制約 | IIS か、制約を 1 つずつ緩和して特定 | — |
| メタヒューリスティクス: seed ≥ 5 の best / mean / worst | ばらつきが小さい。小規模で厳密解と比較 | 反復増、パラメータ再調整 |

取得例（動作確認済み。PuLP 3.3 + HiGHS のナップサック。PuLP 4.0 で削除予定の API は不使用）:

```python
import pulp
prob = pulp.LpProblem("plan", pulp.LpMaximize)
x = prob.add_variable_dicts("x", items, lowBound=0, cat="Integer")
prob += pulp.lpSum(profit[i] * x[i] for i in items)
prob += pulp.lpSum(weight[i] * x[i] for i in items) <= capacity, "capacity"
prob.solve(pulp.HiGHS(msg=False, timeLimit=60, gapRel=0.01))
assert prob.sol_status == pulp.LpSolutionOptimal, f"{pulp.LpSolution[prob.sol_status]}: gap と時間を明記し最適と書かない"
viol = max(0.0, sum(weight[i] * x[i].value() for i in items) - capacity)  # 解を代入して独立再検証
shadow = prob.get_constraint_by_name("capacity").pi  # 双対値（MIP では参考値）
```

## 落とし穴

- `prob.solve()` の戻り値を見ずに `value(x)` を報告しない（INFEASIBLE でも値が返る）。pulp は時間切れでも `status == Optimal` になる（CBC・HiGHS とも）ので `sol_status` を見る
  ```python
  # NG: status を見ずに目的値を報告する（時間切れ・実行不能でも値は返る）
  prob.solve(); print("最適値:", pulp.value(prob.objective))
  ```
- 時間切れの incumbent を「最適解」と書かない。gap と経過時間を併記する
- big-M = 1e9 は数値不安定を招く。必要最小の M を導出する
- 目的関数に円と分を足さない（単位を揃え、重みの根拠を書く）
- 「最適化した」だけで現行比の改善率を書かないのは報告として不完全
