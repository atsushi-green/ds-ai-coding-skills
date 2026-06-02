# 報告ガイドライン

分析結果の報告テンプレートです。詳細は `.github/skills/analysis-reporting/SKILL.md` を参照してください。

## 報告テンプレート

### タイトル

**分析者**: （名前）
**期間**: YYYY-MM-DD 〜 YYYY-MM-DD
**ステータス**: ドラフト / レビュー中 / 完了

---

### 結論

<!-- 最も重要な発見を最初に書く -->

### 分析の背景と目的

<!-- なぜこの分析を行ったか -->

### データと手法

- **データソース**: <!-- 使用したデータのパスと説明 -->
- **対象期間**: <!-- 分析対象期間 -->
- **サンプルサイズ**: <!-- レコード数 -->
- **手法**: <!-- 使用した分析手法 -->

### 結果

<!-- 事実に基づく結果を記述 -->

### 解釈と提言

<!-- 結果の解釈と推奨アクション -->

### 制約・注意点

<!-- 限界、バイアス、注意すべき点 -->

### 再現手順

- **入力データ**: `data/raw/xxx.parquet`
- **分析スクリプト**: `notebooks/NNN_analysis.ipynb`
- **出力**: `outputs/figures/xxx.png`, `outputs/tables/xxx.csv`
- **実行コマンド**: `uv run papermill notebooks/NNN_analysis.ipynb notebooks/NNN_output.ipynb`
