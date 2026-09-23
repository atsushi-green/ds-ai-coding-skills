# skill 発火テスト（skill eval）

`.claude/skills/*-diagnostics` が、分析プロンプトに対して**意図どおりに発火するか**を確かめるハーネスです。
各プロンプトについて、どの skill と references が読まれ、どんな図が出たかを一覧にします。

## 仕組み

```
run_skill_eval.py（オーケストレーター）
  └─ ケースごとに
       1. sandbox を作る（リポジトリ外。.claude/・CLAUDE.md・src/・docs/agent/・pyproject.toml と
          data/raw/train.csv・ケースが使う題材データの読み取り専用コピー。git init と uv sync まで済ませる）
       2. claude -p をその中で起動し、プロンプトを標準入力でそのまま渡す（＝サブエージェント）
       3. stream-json の transcript から、読まれた skill・references と最初の Python 実行を取り出す
       4. sandbox で新しくできた図・スクリプト・表を回収する
  └─ summary.md / index.html に一覧を書く
```

サブエージェントを Agent ツールではなく独立した `claude -p` にしているのは、次の 3 点のためです。

- 普段の使い方（新しいセッションでユーザーがプロンプトを打つ）と同じ条件で、skill の自動発火を見られる
- サブエージェント内部のツール呼び出しを、親エージェントの自己申告ではなく transcript から確認できる
- オーケストレーターの LLM がプロンプトを言い換えたり、skill 名を書き足したりしてテストを汚すことがない

skill が「読まれた」とみなす経路は、`Skill` ツールの呼び出し、`Read` での `SKILL.md` / `references/*.md` の読み込み、
Bash のコマンド（`cat` など）にそのパスが現れた場合、の 3 つです。
CLAUDE.md で `@` 取り込みされている skill（visualization など）はツール呼び出しにならないため、一覧には出ません。

## ケース定義

[cases.yaml](cases.yaml) に書きます。

| 種別 | 見るもの |
|---|---|
| `explicit` | 手法を名指ししたとき、その references まで読むか |
| `implicit` | 手法を言わず目的だけを言ったとき、正しい references に辿り着くか |
| `scope` | 部品として使う手法（傾向スコアのロジスティック回帰、クラスタ図の PCA 射影など）で、別の references まで読まないか |
| `negative` | 診断が要らない依頼で、診断 skill が発火しないか |

判定（PASS / FAIL）は**発火だけ**です。`expect` の skill・references がすべて読まれ、`forbid` に当たるものが
読まれていなければ PASS になります。実行が落ちた・タイムアウトした場合は ERROR です。
図の中身が references の要求を満たすかは、index.html で生成図と「必ず出す図」を並べて人が確認します。

プロンプトには skill 名・references 名と、分析に使うライブラリ名（cmdstanpy・simpy・LightGBM など）を書かないでください。
ライブラリの選択まで skill が導けるかを見るためです。手法名（t 検定・k-means・SHAP 値など）は書いて構いません。
どちらも `tests/test_skill_eval.py` で検査しています。

references の中で手法・条件ごとに「必ず出す図」が分かれるもの（ols の OLS / 正則化 / 分位点回帰、
clustering の k-means / GMM / 階層 / DBSCAN など）は、`cases.yaml` 冒頭の `variants` に分岐として宣言し、
各ケースの `covers` でどの分岐を試すかを書きます。テストで次を確かめています。

- すべての references に分岐の宣言があり、すべての分岐がどれかのケースの `covers` に入っている
- 「必ず出す図」を表で書いている references では、表の 1 列目がすべて `variants` にある
  （references の表に行を足すとテストが落ちるので、分岐とケースの追加漏れに気づける）
- `covers` に書いた分岐が宣言済みで、その references がケースの `expect` に入っている

箇条書きで分岐している references（hypothesis-test、ab-test、time-series、simulation、optimization など）は
自動では照合できないので、条件（「〜の場合」「〜なら」）を足したときは `variants` も手で更新してください。

Titanic 以外の題材（rossi 再犯データ、CO2 濃度、A/B テスト、店舗パネル）は、ケースの `datasets` に名前を書くと
ハーネスが [datasets.py](datasets.py) で CSV を作り、sandbox の `data/raw/<name>.csv` に置きます。
「lifelines 同梱の」「numpy で作って」とプロンプトに書かずに済ませるための仕組みです。
生成は 1 回の実行につき 1 度だけで、追加パッケージは `uv run --with` で一時的に重ねます（pyproject.toml は変えません）。

## 実行

リポジトリ直下で実行します。`claude` にログイン済みであることが前提です。

```bash
# ケース一覧
uv run python scripts/run_skill_eval.py list

# 実行計画と claude の起動コマンドを表示するだけ（API は呼ばない）
uv run python scripts/run_skill_eval.py run --dry-run

# 基本セット（最初に作った 25 ケース。slow の mcmc-hier を除くと 24 件）だけ
uv run python scripts/run_skill_eval.py run --core

# 2 ケースだけ試す
uv run python scripts/run_skill_eval.py run --only glm-explicit,neg-barchart

# 全ケース（slow を除く）を 2 並列で
uv run python scripts/run_skill_eval.py run --jobs 2

# 発火のばらつきを見る（各ケース 3 回）
uv run python scripts/run_skill_eval.py run --kind implicit scope --repeat 3

# モデルを変えて比較
uv run python scripts/run_skill_eval.py run --model sonnet --run-id sonnet-baseline

# MCMC（slow）は明示実行。エージェントが cmdstanpy を選んだときのために CmdStan の場所を渡しておく
CMDSTAN=/path/to/cmdstan uv run python scripts/run_skill_eval.py run --only mcmc-hier

# レポートだけ作り直す
uv run python scripts/run_skill_eval.py report outputs/skill_eval/<run_id>
```

費用の目安は 1 ケースあたり数ドル・数分〜数十分です（全 67 ケースを 1 回ずつ回すと、上限いっぱいなら 300 ドル超）。
まず `--only` や `--kind` で数件に絞って試してください。`cases.yaml` の `max_budget_usd`（既定 5 ドル）と
`timeout_min`（既定 40 分）で 1 ケースごとに上限を掛けています。

## 出力

`outputs/skill_eval/<run_id>/`（gitignore 対象）に書き出します。

| パス | 内容 |
|---|---|
| `index.html` | 一覧表 + ケースごとのカード（プロンプト、読んだ順、生成図のサムネイル、references の「必ず出す図」、最終応答） |
| `summary.md` | 同じ一覧の Markdown 版 |
| `run.json` | 実行条件（claude のバージョン、モデル、git HEAD、skills の内容ハッシュ、起動コマンド） |
| `skills_snapshot/`・`cases.yaml` | 実行時点の skill とケース定義（後で skill を直してもレポートを再現できる） |
| `<case>/r<n>/transcript.jsonl` | stream-json の全記録 |
| `<case>/r<n>/result.json` | 判定と集計値 |
| `<case>/r<n>/files/` | sandbox で作られた図・スクリプト・表（sandbox 内の相対パスのまま） |
| `<case>/r<n>/pyproject.diff` | `uv add` で足された依存 |

一覧の列:

- **発火した skill**: 括弧内は経路（`Skill` ツール / `Read` / `Bash`）
- **読了→実行**: references を読んでから最初の Python を実行したか（○ 守った / × 実行が先 / − 未読か未実行）
- **判定表**: 最終応答に `| 診断項目 |` の表があるか

## 権限

sandbox はリポジトリ外の一時ディレクトリですが、`claude` の Bash は sandbox の外にも届きます。
そのため `--permission-mode acceptEdits` と Bash の許可リスト（`cases.yaml` の `allowed_tools`）で動かし、
許可リストにないコマンドは確認なしで拒否します（`--permission-prompts none`）。
拒否されたツールはレポートの「権限で拒否」に出るので、必要なものだけ `allowed_tools` に足してください。
`AskUserQuestion`・`WebFetch`・`WebSearch` は外しています（無人実行のため、また skill の本文だけで完結するかを見るため）。

## テスト

ハーネス自体のユニットテストは claude を起動しません。

```bash
uv run pytest tests/test_skill_eval.py
```
