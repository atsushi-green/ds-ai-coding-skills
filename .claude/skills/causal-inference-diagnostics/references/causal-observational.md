# 観察データ因果推論（傾向スコア・IPW・DML）の必須セット

短縮名: `causal-obs`（図の保存先 `outputs/diagnostics/<YYYYMMDD-HHMM>_causal-obs/`）。報告の書式と判定表はルーター SKILL.md の「出力と報告」に従う。

## 適用範囲

- 扱う: 傾向スコア（マッチング / IPW / 層別）、二重頑健（AIPW）、DML、causal forest、回帰調整による処置効果推定
- 扱わない: ランダム化実験 → `references/ab-test.md` / DiD・IV・RDD・合成コントロール → `references/causal-quasi-experimental.md` / 予測モデルの解釈 → `predictive-modeling-diagnostics`（`references/model-interpretation.md`）

## ライブラリ

- dowhy（識別 → 推定 → 反駁の骨格）、econml（`LinearDML`、`CausalForestDML`）、doubleml（`DoubleMLPLR`）、statsmodels（回帰調整・WLS）
- scikit-learn（PS モデル。love plot・重み分布は matplotlib で自前）。未導入なら `uv add dowhy econml`。無ければ sklearn + statsmodels で PS と IPW を自前実装

## 必ず出す図

- 群別の傾向スコア分布の重ね描き（ヒスト or KDE） — 両群が重なれば合格。共通サポート外（片群にしか無い PS 域）の件数を注記
- love plot（全共変量の標準化平均差 SMD を調整前・後で並べ、\|SMD\| = 0.1 に縦破線） — 調整後の全点が破線内なら合格
- IPW の場合: 重みの分布（ヒスト。max と上位 1% を注記） — 極端な重みが無ければ合格。あれば安定化・トリミング
- CATE を出す場合: 推定 CATE の分布 + 主要サブグループ別の点推定と CI — CI が 0 をまたぐサブグループを「差あり」と書かない

## 必ず出す値

| 項目 | 合格基準 | 違反時の対処 |
|---|---|---|
| 調整セットの列挙と根拠 | 処置後変数・媒介・コライダーが入っていない（DAG か 1 段落の説明） | 調整セット再設計 |
| 推定対象（ATE / ATT / CATE）と識別仮定 | 明記されている（無交絡・正値性・SUTVA） | — |
| ナイーブ比較 vs 調整後推定（+ 95% CI） | 両方報告 | — |
| \|SMD\| (max)（調整後） | < 0.1（緩くは 0.25） | PS モデル再指定（交互作用・二乗項）、キャリパー変更 |
| PS モデルの AUC | **極端に高くない（> 0.9 は警戒）** | 高 AUC はオーバーラップ不良のサイン。処置を予測しすぎる変数を疑う |
| トリミング範囲と除外 n | 明記（推定対象の母集団が変わることも明記） | — |
| IPW: 有効サンプルサイズ（Kish） | n の半分以上目安 | 安定化重み、トリミング（PS 0.05〜0.95 等） |
| マッチング: マッチ率・マッチ後 n・キャリパー・復元の有無 | 全て報告（脱落が大きいと推定対象の母集団が変わる） | キャリパー緩和、1:k マッチ、IPW へ切替 |
| DML / causal forest: cross-fitting の分割数と seed | 明記（分割なしで推定しない。2〜5 が目安） | `cv=` を指定して再推定 |
| DML / causal forest: nuisance モデルの out-of-fold 性能 | 結果モデル・処置モデルの両方を報告（R² / AUC） | 処置 AUC が極端に高いならオーバーラップ不良、低すぎるなら効果の識別情報が無い |
| 感度分析（E-value、Rosenbaum Γ 等） | 効果を覆すのに必要な未観測交絡の強さ > 観測された最強の交絡 | 結論を弱める（「仮定の下で」を強調） |

取得例（ATE の IPW とバランス）:

```python
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

ps = LogisticRegression(max_iter=1000).fit(X, t).predict_proba(X)[:, 1]
print("PS AUC", roc_auc_score(t, ps))  # > 0.9 はオーバーラップ不良の警戒サイン
w = np.where(t == 1, 1 / ps, 1 / (1 - ps))  # ATE の IPW（ATT なら対照群に ps/(1-ps)）
ess = w.sum() ** 2 / (w**2).sum()  # 有効サンプルサイズ（Kish）
def smd(x, t, w):  # 重み付き標準化平均差（love plot 用。w=1 で調整前）
    m1, m0 = np.average(x[t == 1], weights=w[t == 1]), np.average(x[t == 0], weights=w[t == 0])
    return (m1 - m0) / np.sqrt((x[t == 1].var() + x[t == 0].var()) / 2)
```

## 落とし穴

- 処置後に決まる変数を調整に入れると効果を説明し切ってゼロにする（媒介・コライダー）
  ```python
  # NG: 処置後に観測される変数（処置後の来店回数）を共変量に入れる
  X = df[["age", "income", "visits_after_treatment"]]
  ```
- PS モデルを予測モデルとして最適化して AUC を上げるとオーバーラップが消える。PS の目的はバランス
- 予測精度を測るための `train_test_split` は要らない（予測タスクではない）。ただし DML の cross-fitting は推定量の一部なので必須。この 2 つを混同しない
- ATE と ATT を混同しない。トリミング後の母集団が推定対象であることを報告する
- 観察データの結論には必ず「（無交絡などの）仮定の下で」を付ける
