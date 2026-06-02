# データサイエンス分析プロジェクトテンプレート

GitHub Copilot / Copilot Agent Mode / Copilot Cloud Agent と連携し、安全かつ一貫したデータ分析作業を行うためのリポジトリテンプレートです。

## セットアップ

### 前提条件

- Python 3.11
- [uv](https://docs.astral.sh/uv/) がインストール済みであること

### インストール

```bash
uv sync
```

### 主要コマンド

```bash
uv sync                                              # 依存関係のインストール・同期
uv run pytest                                         # テスト実行
uv run ruff check .                                   # リント
uv run ruff format .                                  # フォーマット
uv run mypy src                                       # 型チェック
uv run python scripts/check_no_raw_data_commit.py     # rawデータのコミットチェック
uv run python scripts/check_no_sensitive_patterns.py   # 秘密情報パターンの検出
uv run python scripts/validate_agent_docs.py           # エージェント文書の検証
bash scripts/run_quality_checks.sh                     # 全品質チェック一括実行
```

## ディレクトリ構成

```
.
├── AGENTS.md                          # エージェント用ルーター
├── .github/
│   ├── copilot-instructions.md        # Copilot共通指示（薄いファイル）
│   ├── workflows/ci.yml               # GitHub Actions CI
│   ├── instructions/                  # パス別補助指示
│   ├── prompts/                       # 再利用プロンプト
│   └── skills/                        # 作業別スキル
├── docs/agent/                        # プロジェクト固有ドキュメント
├── data/
│   ├── raw/                           # 元データ（不変・gitignore対象）
│   ├── external/                      # 外部データ（不変・gitignore対象）
│   ├── interim/                       # 中間加工データ
│   └── processed/                     # 最終加工データ
├── notebooks/                         # 分析用Notebook
├── outputs/
│   ├── figures/                       # グラフ・図
│   ├── tables/                        # 集計テーブル
│   └── reports/                       # レポート
├── scripts/                           # CI・検証スクリプト
├── src/analysis_project/              # 再利用可能なPythonモジュール
└── tests/                             # テスト
```

## Copilot指示体系の設計

### AGENTS.md はルーター、skills は作業別手順、docs/agent はプロジェクト固有知識

このリポジトリでは、エージェント向けの指示を3層に分割しています：

1. **`.github/copilot-instructions.md`** — 薄い共通指示。全タスクで必要な最小限のルールと、詳細な指示への案内。
2. **`AGENTS.md`** — エージェント用ルーター。タスクの種類に応じて適切なskillファイルへ誘導する。
3. **`.github/skills/*/SKILL.md`** — 作業別の詳細手順。Python、SQL、データ処理、可視化など。
4. **`docs/agent/*`** — プロジェクト固有の知識。データカタログ、指標定義、分析ワークフローなど。
5. **`.github/instructions/*.instructions.md`** — パス別の補助指示。ファイルの種類に応じた自動適用ルール。
6. **`.github/prompts/*.prompt.md`** — 再利用可能なプロンプト。分析計画、SQLレビュー、レポート作成など。

この設計により、全部入りの巨大な指示ファイルを避け、トークン効率よく必要な情報だけを参照できます。

### 利用可能なスキル

| スキル | 用途 |
|--------|------|
| `python-project-ops` | 依存関係、テスト、リント、型チェック |
| `safe-data-handling` | データの安全な取り扱い |
| `sql-analysis` | SQLの作成・レビュー |
| `python-style` | Pythonコーディングスタイル |
| `dataframe-polars` | DataFrameの操作（polars優先） |
| `visualization` | グラフ・可視化 |
| `path-and-io` | ファイルパスとI/O |
| `notebook-workflow` | Notebook作業 |
| `statistical-ml-review` | 統計・ML分析 |
| `analysis-reporting` | 分析結果の報告 |

### 利用可能なプロンプト

| プロンプト | 用途 |
|------------|------|
| `plan-analysis` | 分析計画の作成 |
| `review-sql` | SQLのレビュー |
| `summarize-analysis` | 分析結果の要約 |
| `prepare-pr` | PR概要の作成 |
| `update-agent-docs` | エージェント文書の更新 |

## データの安全性ルール

- `data/raw/` と `data/external/` は不変として扱い、直接変更しない。
- rawデータ、認証情報、APIキー、トークン、顧客レベルのレコードをコミットしない。
- 加工データは `data/interim/` や `data/processed/` に出力する。
- 図表やレポートは `outputs/` に出力する。
- `.env` ファイルは `.gitignore` でコミット対象外。

## パッケージ管理

- **uv のみを使用**する。pip、conda、poetry は使わない。
- 依存関係の追加: `uv add <package>`
- 開発依存の追加: `uv add --group dev <package>`
