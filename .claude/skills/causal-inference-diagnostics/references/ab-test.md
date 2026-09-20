# A/B テストの必須セット

短縮名: `abtest`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_abtest/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: ランダム割付のオンライン実験（2 群・多群）、比率・平均・比率型指標（CTR 等）のリフト推定、CUPED
- 扱わない: 割付がランダムでない比較 → `references/causal-observational.md` / 実験でない検定 → `statistical-inference-diagnostics`（`references/hypothesis-test.md`） / 逐次検定・バンディットの設計は本 skill の外（「途中経過」と明記して扱う）

## ライブラリ

- scipy.stats（`chisquare`、`ttest_ind`）、statsmodels（`proportions_ztest`、`confint_proportions_2indep`、`stats.power`）、numpy
- statsmodels 未導入なら `uv add statsmodels`（scipy だけなら Wald CI を自前で計算し「Wald 近似」と明記）

## 必ず出す図

- 群別の指標分布（箱ひげ + ヒスト、同じ軸） — 裾の重さ・ゼロ過剰・外れ値が両群で同程度なら合格。片群だけ極端な値があれば確認
- 日次の累積リフトと 95% CI の推移（0 に水平破線） — 後半で安定していれば合格。前半だけ大きいならノベルティ効果、曜日で振れるなら期間不足
- 多群・多指標の場合: 効果量と CI のフォレストプロット（事前登録分と探索分を分けて描く） — 探索分は BH 補正後で描く

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| **SRM（割付比の χ² 検定）** | **p > 0.001** | 実験無効。結果を報告せずログ・割付・ボットを調査 |
| 割付単位と分析単位 | 一致している（ユーザー割付ならユーザー単位で集計） | ユーザー単位に集計するか、比率指標はデルタ法で分散を出す |
| 事前設計（主要指標 1 つ・MDE・必要 n・期間） | 事前に固定されている | 事後変更は「探索的」と明記 |
| 実験前期間のバランス（A/A） | 群間で差なし | 割付の欠陥を疑う |
| 絶対差・相対リフトと 95% CI | p 値単独で報告しない | — |
| 期間 | 整数週（曜日効果を含む） | 期間延長 |
| 途中で結果を見た回数 | 固定期間なら満了まで判断しない | 逐次検定に切替 or「途中経過」と明記 |
| 検定した指標 × セグメントの数 | 事前登録分と探索分が分離されている | 探索分は BH 補正（`multipletests(method="fdr_bh")`） |
| CUPED 使用時: 分散削減率 | 報告に含む（実験前指標との相関² が目安） | — |

取得例（動作確認済み。ユーザー単位の二値指標）:

```python
from scipy.stats import chisquare
from statsmodels.stats.proportion import proportions_ztest, confint_proportions_2indep

n = np.array([n_a, n_b]); srm_p = chisquare(n, f_exp=n.sum() * np.array([0.5, 0.5])).pvalue
assert srm_p > 0.001, "SRM: 割付比が設計とずれている。結果を報告せず割付ログを調査する"
conv = np.array([x_a, x_b])
diff = conv[1] / n[1] - conv[0] / n[0]  # 絶対差
lo, hi = confint_proportions_2indep(conv[1], n[1], conv[0], n[0])  # 絶対差の 95% CI
rel_lift = diff / (conv[0] / n[0])  # 相対リフト
z, p = proportions_ztest(conv, n)  # p 値は CI の後に、主要指標 1 つだけ
```

## 落とし穴

- SRM を確認せずに「有意差あり」と報告しない
- 比率指標（CTR = クリック / 表示）をセッション・表示単位の二項検定にかけない（分散を過小評価）
  ```python
  # NG: 割付はユーザー単位なのに表示単位で検定する
  proportions_ztest([clicks_a, clicks_b], [impressions_a, impressions_b])
  ```
- 3 日で有意になったから止める、をしない（固定期間なら満了まで。途中経過は「途中経過」と書く）
- 10 指標中 1 つ有意 → それを主要指標として報告しない
- 実験前指標があるなら CUPED で分散削減し、削減率を報告する
