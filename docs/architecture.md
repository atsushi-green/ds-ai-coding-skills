# アーキテクチャ・技術詳細

README には載せきれない技術的な詳細をここにまとめる。利用者向けの手早い使い方は
[README](../README.md) を参照。

## エージェント指示体系の設計

このリポジトリは **GitHub Copilot**・**Claude Code**・**Codex** の3つに対応しています。
どのツールを使っても同じルールが効くように、**指示の実体は1か所にしか置かない**方針を取っています。

### ルーター文書（1つの内容を2ファイルで提供）

ツールごとに読むファイル名が決まっているため、ファイルは2つありますが**内容は同一**です。
`## Hard Rules` 以降が一致しているかは `scripts/sync_agent_docs.py --check` がCIで検証します。

| ファイル | 読むツール | 役割 |
|----------|-----------|------|
| `CLAUDE.md` | Claude Code | ハードルール・共通コマンド・規約・スキルルーティング。末尾の `## Skills`（skill の `@` import）だけが Claude 固有 |
| `AGENTS.md` | GitHub Copilot（VS Code / CLI / coding agent）・Codex | 上と同内容。冒頭の導入文だけが固有 |

### スキルと補助ファイル

| パス | 読むツール | 役割 |
|------|-----------|------|
| `.claude/skills/*/SKILL.md` | 3ツール共通 | 作業別の詳細手順（Python・SQL・データ処理・可視化・診断など）。ミラーは持たない |
| `.agents/skills` | Codex | `.claude/skills` へのシンボリックリンク |
| `.github/instructions/*.instructions.md` | Copilot | パス別の補助指示（`applyTo` による自動適用）。内容はルーター文書の「File-Specific Guidelines」と対応 |
| `.github/prompts/*.prompt.md` | Copilot | 再利用可能なプロンプト。`.claude/skills/` のタスクスキルと対応 |
| `docs/agent/` | 3ツール共通 | **このリポジトリでしか通用しない知識のみ**（プロジェクト概要・データカタログ・指標定義）。作業手順や規約は skill 側が正本で、ここには重複させない |

Copilot は `.github/copilot-instructions.md` も読めますが、VS Code / CLI / coding agent はいずれも
`AGENTS.md` に対応しているため、二重管理を避けて**置いていません**。`AGENTS.md` を読まない
IDE（JetBrains・Visual Studio・Xcode・Eclipse）で使う場合は、`AGENTS.md` と同内容の
`.github/copilot-instructions.md` を追加してください。

この設計により、全部入りの巨大な指示ファイルを避け、トークン効率よく必要な情報だけを参照できます。

### 利用可能なスキル（3ツール共通）

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
| `statistical-ml-review` | 統計・ML分析のレビュー（欠けている図・値を `*-diagnostics` に照らして指摘） |
| `analysis-reporting` | 分析結果の報告 |

## 手法別診断 skill（*-diagnostics）

手法ごとに「実行したら必ずセットで出す図と値」を定義した skill 群です。LLM は「回帰したら残差を見るべき」と知っていても、頼まれたこと（当てはめて R² を報告）だけで診断を省きがちです。この skill 群は各手法について **図（何が見えれば合格か）・値（合格基準と違反時の対処）・落とし穴** を強制します。ユーザーが診断に言及しなくても、対応する手法を実行した時点で適用されます。

**2 段構成（progressive disclosure）** です。常にコンテキストに載るのは 5 つのルーターの `description` だけで、手法別の本文はルーターが選んだときにだけ読まれます。

```
.claude/skills/<family>-diagnostics/
├── SKILL.md            # 第 1 段: ルーター（約 70 行。ルーティング表・隣接 skill・「出力と報告」の共通書式）
└── references/
    └── <method>.md     # 第 2 段: 手法別（60〜140 行。適用範囲 / ライブラリ / 必ず出す図 / 必ず出す値 / 落とし穴）
```

- 置き場は `.claude/skills/` の 1 か所だけです。Claude Code と Copilot は `.claude/skills/` を直接読み、Codex は `.agents/skills`（`.claude/skills` へのシンボリックリンク）から読むので、3 ツールで同じ内容が使われます
- 各ディレクトリは他ファイルを参照しません。**他リポジトリへは `.claude/skills/<family>-diagnostics/` をディレクトリごとコピーするだけ**で使えます
- 図は `outputs/diagnostics/<YYYYMMDD-HHMM>_<短縮名>/` に保存し（gitignore 済み）、報告には `| 診断項目 | 実測値 | 合格基準 | 判定 | 次アクション |` の表だけを載せます（判定は `OK` / `要対処` / `確認`）
- 手法やルーターを追加する手順と雛形は [docs/agent/diagnostics-reference-template.md](agent/diagnostics-reference-template.md)
- 5 つのルーターは、Claude Code の plugin `ds-diagnostics` としても配っています（定義は [.claude-plugin/marketplace.json](../.claude-plugin/marketplace.json)。plugin の中身はリポジトリ直下を指し、`skills` に 5 つのディレクトリを列挙しているので、基本 skill やタスク実行用 skill は plugin に入りません）。plugin の skill はプロジェクトの外に置かれるため、references の読み込みに読み取りの許可が要ります。プロジェクト外のディレクトリから plugin として読み込んで確かめたところ、ルーターは発火しましたが、無人実行（`claude -p`）では `references/*.md` の読み込みが権限で拒否されました。plugin の置き場所に対する `Read(...)` の許可ルールを足すと読めます。ルーターの frontmatter に `allowed-tools` を足す方法は、skill の呼び出し自体に承認が要るようになるので採っていません
- skill を外しても同じ図と値が出るのかは、[docs/skill-ablation.md](skill-ablation.md) で比べています
- skill が意図どおりに発火するか（頼んだ手法の references を読み、頼んでいない references は読まないか）は、[scripts/skill_eval/](../scripts/skill_eval/README.md) のハーネスで確かめられます。ケースごとに `claude -p` を起動するので手動で実行します（費用の目安は同 README）。CI では `cases.yaml` と references の整合性を見るテストだけが走ります
- 各 reference が「必ず出す」と定めた図を実データで出力したギャラリーを [GitHub Pages](https://atsushi-green.github.io/ds-ai-coding-skills/) で公開しています（5 スキル・17 手法・45 図。ソースは [docs/gallery/](gallery/)）。`.github/workflows/pages.yml` でデプロイします
- references 内のコード抜粋が使うライブラリ（statsmodels / scikit-learn 1.8 / lifelines / cmdstanpy 1.3（CmdStan 2.40）など）は本リポジトリの `pyproject.toml` に含めていないので、使う手法に応じて `uv add` してください

| ルーター（第 1 段） | 家族 | references（第 2 段） |
|---|---|---|
| `statistical-inference-diagnostics` | 統計的推論 | `ols`（線形・正則化・分位点回帰）, `glm`（ロジスティック・ポアソン・負の二項）, `mixed-effects`（混合効果・パネル）, `hypothesis-test`（検定。**安易に検定させないことが主目的**）, `survival`（KM・Cox・AFT・競合リスク）, `bayesian-mcmc`（cmdstanpy + ArviZ） |
| `predictive-modeling-diagnostics` | 予測モデリング | `ml-evaluation`（分割・CV・リーク・ベースライン）, `tree-model`（決定木・RF・GBDT）, `model-interpretation`（SHAP・permutation・PDP/ICE）, `time-series`（ARIMA・状態空間・Prophet・VAR・変化点） |
| `causal-inference-diagnostics` | 因果推論・効果検証 | `ab-test`（A/B テスト・SRM・CUPED）, `causal-observational`（傾向スコア・IPW・DML）, `causal-quasi-experimental`（DiD・IV・RDD・合成コントロール） |
| `unsupervised-eda-diagnostics` | 教師なし・EDA 前処理 | `missing-data`（欠測・外れ値）, `clustering`（k-means・階層・GMM・DBSCAN）, `dimensionality-reduction`（PCA・因子分析・CFA/SEM・UMAP/t-SNE）, `anomaly-detection`（異常検知） |
| `simulation-optimization-diagnostics` | シミュレーション・OR | `simulation`（モンテカルロ・離散事象）, `optimization`（LP/MIP・メタヒューリスティクス） |

今後の拡張候補（未作成）: トピックモデル（LDA・BERTopic）、深層学習の学習診断。推薦評価・公平性指標・ドリフト監視・データ品質検証は対象外です。

注意: Codex を使う場合、Windows で clone するときはシンボリックリンクを有効にしてください（`git config core.symlinks true` と開発者モード）。無効の環境では `.agents/skills` がリンク先パスを書いたテキストファイルになります。Claude Code と Copilot は `.claude/skills/` を直接読むため影響ありません。

## タスク実行用スキル（旧コマンド / プロンプト）

Claude Code では `.claude/skills/*/SKILL.md` として（`/plan-analysis` のようにスラッシュでも起動可能）、Copilot では引き続き `.github/prompts/*.prompt.md` として提供されるタスク実行用スキル。

| スキル | Claude Code | Copilot | 用途 |
|--------|:-----------:|:-------:|------|
| `plan-analysis` | `/plan-analysis` | prompt | 分析計画の作成 |
| `review-sql` | `/review-sql` | prompt | SQLのレビュー |
| `summarize-analysis` | `/summarize-analysis` | prompt | 分析結果の要約 |
| `prepare-pr` | `/prepare-pr` | prompt | PR概要の作成 |
| `update-agent-docs` | `/update-agent-docs` | prompt | エージェント文書の更新 |
| `sync-agent-docs` | `/sync-agent-docs` | prompt | Claude/Copilot間のスキル差分の同期 |
| `run-eda` | `/run-eda` | — | EDAの実装・実行 |
| `run-modeling` | `/run-modeling` | — | 予測モデリングの実装・評価 |

## エージェント文書の同期

skill 本体はミラーを持たないため、同期が必要なのは次の2種類だけです。

- **ルーター文書**: `CLAUDE.md` ⇔ `AGENTS.md`。`## Hard Rules` 以降の本文が完全に同一であること。冒頭の導入文と、`CLAUDE.md` にだけある `## Skills`（skill の `@` import）は各ファイル固有として比較対象外。
- **タスク実行スキル**（frontmatter に `disable-model-invocation: true`）: `.claude/skills/<name>/SKILL.md` ⇔ `.github/prompts/<name>.prompt.md`。frontmatter 形式を変換し、Copilot の `${input:...}` プレースホルダや `CLAUDE.md`⇔`AGENTS.md` の相互参照を保持・変換しながら同期。

片方を編集すると差分が生じるため、以下の仕組みで検出・解消します。

- `uv run python scripts/sync_agent_docs.py --check` — 書き込みせず差分の有無だけを判定する（`run_quality_checks.sh` / CIに組み込み済み。ルーター文書の差分のみ終了コード1）。
- `uv run python scripts/sync_agent_docs.py --from claude`（または `--from github`） — **編集した側を明示して**もう一方へ反映する。方向は必須（mtime による自動判定はしない）。元ファイルの改行コードは保持されます。
- `/sync-agent-docs`（Claude Code）・prompt（Copilot） — 上記スクリプトを実行した上で、対応するタスクスキルが無い prompt など、判断が必要な差分をエージェントが解消する。
- ロジックのテスト: `uv run pytest tests/test_sync_agent_docs.py`。

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
