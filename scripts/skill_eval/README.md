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

リポジトリ直下で実行します。前提は次の 2 つです。

- `claude` にログイン済みであること
- Titanic の `train.csv`（[Kaggle](https://www.kaggle.com/competitions/titanic/data)）を `data/raw/train.csv` に置いてあること。
  生データなのでリポジトリには含めていません。無いと sandbox を作る段階で `FileNotFoundError` になります

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

費用の目安は 1 ケースあたり数ドル・数分〜数十分です（全 68 ケースを 1 回ずつ回すと、上限いっぱいなら 300 ドル超）。
まず `--only` や `--kind` で数件に絞って試してください。`cases.yaml` の `max_budget_usd`（既定 5 ドル）と
`timeout_min`（既定 40 分）で 1 ケースごとに上限を掛けています。

モデルと effort は `--model`・`--effort`（または `cases.yaml` の `config`）で指定します。指定しなければ、
手元の Claude Code の設定（`~/.claude/settings.json` の `model`・`effortLevel` など）で動きます。
Claude Code の中（Bash ツールや VS Code 拡張）からハーネスを実行しても、親セッションの effort などは
引き継ぎません（親が渡してくる `CLAUDE_EFFORT` などの環境変数を、起動する `claude` には渡さない）。

### プロジェクトの外にある同名の skill を見えなくする

Claude Code は、プロジェクトの `.claude/skills` のほかに、ユーザーレベル（`~/.claude/skills`）の skill と、
アカウントに登録した skill（claude.ai にアップロードしたもの。`anthropic-skills:<名前>` として見える）も読み込みます。
このリポジトリの skill をそこにも入れていると、skill を外した条件でも外したはずの skill が見えてしまい、
比較が成り立ちません。フルの条件でも、同じ名前の skill が 2 つ見えます。

`run` は、始める前に空のディレクトリで短い問い合わせを送り、プロジェクトの外から見えている skill を調べます。

- 名前空間つきの同名 skill（`anthropic-skills:statistical-inference-diagnostics` など）は、settings の
  `skillOverrides` で `off` にして、どの条件でも見えなくします。見えなくなったことも、もう 1 回の問い合わせで確かめます
- 名前空間の無い同名 skill（`~/.claude/skills` に置いたもの）は、`off` にするとプロジェクトの skill まで
  消えるので、実行を始めずに知らせます。その skill を一時的に別の場所へ移してください
- 実行ごとの `result.json` の `outside_skill_copies` に、その実行で見えていた同名の skill が残ります。
  1 つでも見えていたら、残りの実行は始めません。skill を外した条件でそうなった実行は、`score` でも数えません

### 利用枠の上限に当たらないようにする

サブスクリプションの利用枠（5 時間枠・7 日枠）の上限に達すると、実行は途中でも打ち切られ、そこまでの分が
無駄になります。`run` は、使用率が目安（`--max-utilization`、既定 0.85）以上になったら次の実行を始めません。

- 始める前の問い合わせ（上と同じもの）で使用率を読みます。目安以上なら、何も作らずに終了します
- 1 件終わるたびに、その実行の記録から使用率を読みます。目安以上なら、残りは始めません
- 止まったら、同じコマンドに `--run-id <出力ディレクトリ名> --resume` を付けて実行すると、終わっていない
  実行だけを続きから行います。上限で打ち切られた実行（ERROR）はやり直し、元の出力は `_interrupted/` に残します

```bash
# いまの使用率を見る
uv run python scripts/run_skill_eval.py quota

# 1 件ずつ実行し、止まっても同じコマンドで続きから実行できるようにしておく
uv run python scripts/run_skill_eval.py run --only glm-explicit --repeat 3 --jobs 1 \
  --run-id glm-full --resume
```

1 件ずつ（`--jobs 1`）にすると、上限で打ち切られるのは多くても実行中の 1 件です。使用率で止めたくないときは
`--max-utilization 0` を指定します（上限に達して断られたときは、この場合も残りを始めません）。

## skill 要否テスト（skill を外して同じプロンプトを実行する）

発火テストで分かるのは「skill が読まれるか」までです。その skill が無くても同じ図と値が出るのなら、
skill に書く必要はありません。これを確かめるために、skill を間引いた sandbox で同じケースを実行できます。

```bash
# 現行の skill で実行（いつもの発火テスト）
uv run python scripts/run_skill_eval.py run --only glm-explicit --model claude-opus-5-5
# *-diagnostics だけを外して、同じケース・同じモデルで実行
uv run python scripts/run_skill_eval.py run --only glm-explicit --model claude-opus-5-5 --arm no-diagnostics
```

2 つの実行を、ケースごとに横に並べたレポートにします（API は呼びません）。

```bash
uv run python scripts/run_skill_eval.py compare outputs/skill_eval/<full の run_id> outputs/skill_eval/<arm の run_id>
```

`outputs/skill_eval/compare-<A>__<B>/` に `compare.html` と `compare.md` ができます。一覧には図の枚数・判定表の有無・
時間と費用が並び、各カードでは生成図と最終応答を左右で見比べられます。カードの下に、そのケースの references が
定める「必ず出す図」「必ず出す値」をチェックリストとして出します。
skill を外した側でも出ている図・値は、そのモデルに対しては書かなくても出るもの（削る候補）、
外した側にだけ無いものは skill が効いているものです。

項目ごとに「出た／出ない」を数えるには `score` を使います（これも API は呼びません）。

```bash
uv run python scripts/run_skill_eval.py score outputs/skill_eval/<skill なしの run_id> outputs/skill_eval/<full の run_id>
```

[checklists.yaml](checklists.yaml) に、reference の「必ず出す図」「必ず出す値」を 1 項目ずつ、見つけ方（正規表現）つきで
書いてあります。見つけ方は、生成されたスクリプトに当てるもの（`roc_curve(` など）と、最終応答や生成された表に当てるもの
（`VIF` など）の 2 種類です。「確認していません」のような否定の文は数えず、図の項目は図のファイルが作られていることも
条件にします。結果は「出た回数 / 実行回数」の表（`scores.md`）と、1 項目 1 行の `scores.csv` に出ます。

- 採点表があるのは `glm`（二値）・`ml-evaluation`（分類）・`clustering`（k-means）の 3 本です。ほかの reference を
  比べるときは、採点表に項目を足してください
- 正規表現による採点なので、言い回しの違いで取りこぼしや誤検出がありえます。採点表を直したら、
  いくつかの実行を `compare` のレポートで目で見て確かめてください
- 実行が落ちたもの（ERROR）は採点に入れません

間引き方（arm）は [cases.yaml](cases.yaml) の `arms` に書きます。

| arm | 内容 |
|---|---|
| `full`（既定） | 間引かない |
| `no-diagnostics` | `*-diagnostics` のルーターと references、それを指す記述（CLAUDE.md の Hard Rule とルーティング表の行、analysis-reporting の診断サマリー節など）を外す。基本 skill は残す |
| `agents-md-rule` | `no-diagnostics` と同じものを外したうえで、CLAUDE.md の Hard Rules に「手法を実行したら、その診断の図と値をセットで出す」の 1 行だけを足す。この 1 行で出る図・値は、references に書かなくてもよい候補 |
| `bare` | `.claude/`・`CLAUDE.md`・`docs/agent/` を置かない（モデルの素の挙動） |

- 間引くのは sandbox の中のコピーだけです。間引いた状態を最初のコミットにするので、エージェントからは
  「最初からその skill が無いリポジトリ」に見えます
- README.md は、どの条件でも見出しだけに差し替えます（`cases.yaml` の `stub_files`）。README には診断 skill が
  何を出すかと比較の結果が書いてあり、エージェントが読むと skill の有無による差を測れなくなるためです
- `full` 以外の arm では期待する skill 自体が無いので、発火の合否は付けません（一覧の発火欄は ➖）
- 比べるときは `--model` と `--effort` でモデルと effort を固定してください。1 回ずつの比較は実行ごとの
  ばらつきと区別できないので、結論を出すなら `--repeat` で複数回実行します
- レポートが数えるのは機械的に分かる事実だけです。図と値が references の要求を満たしているかは、
  チェックリストと見比べて人が判断します（自動判定は未実装）。モデル・effort・claude のバージョンが
  揃っていない 2 つを比べると、レポートの冒頭に注意書きが出ます
- 実際に比べた結果は [docs/skill-ablation.md](../../docs/skill-ablation.md) にあります
- `arms` の指定が skill の現状に当たらなくなると（見出しの改名など）、実行前にエラーで止まります。
  `no-diagnostics` を当てた後に `*-diagnostics` を指す記述が残らないことは、テストで確かめています

## 出力

`outputs/skill_eval/<run_id>/`（gitignore 対象）に書き出します。

| パス | 内容 |
|---|---|
| `index.html` | 一覧表 + ケースごとのカード（プロンプト、読んだ順、生成図のサムネイル、references の「必ず出す図」、最終応答） |
| `summary.md` | 同じ一覧の Markdown 版 |
| `run.json` | 実行条件（claude のバージョン、モデル、git HEAD、skills の内容ハッシュ、起動コマンド、arm と間引いた内容） |
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
