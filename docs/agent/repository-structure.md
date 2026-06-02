# リポジトリ構成

各ディレクトリの役割を説明します。

| ディレクトリ | 役割 |
|-------------|------|
| `src/analysis_project/` | 再利用可能なPythonモジュール |
| `notebooks/` | 探索・分析用Jupyter Notebook |
| `scripts/` | CI・検証用スクリプト |
| `tests/` | pytest用テスト |
| `data/raw/` | 元データ（不変・gitignore対象） |
| `data/external/` | 外部データ（不変・gitignore対象） |
| `data/interim/` | 中間加工データ |
| `data/processed/` | 最終加工データ |
| `outputs/figures/` | グラフ・図 |
| `outputs/tables/` | 集計テーブル |
| `outputs/reports/` | レポート |
| `docs/agent/` | エージェント向けプロジェクト文書 |
| `.github/skills/` | 作業別スキルファイル |
| `.github/instructions/` | パス別補助指示 |
| `.github/prompts/` | 再利用プロンプト |
