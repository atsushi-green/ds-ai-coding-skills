---
name: sync-agent-docs
description: Claude Code・GitHub Copilot・Codex のルーター文書とタスクスキルの差分を検出し、機械的な部分はスクリプトで、判断が必要な部分はここで同期する
disable-model-invocation: true
---

# Skill: Sync Agent Docs

Claude Code は `CLAUDE.md` を、GitHub Copilot と Codex は `AGENTS.md` を読む。一方で skill 本体は
`.claude/skills/` の1か所だけに置き、3ツールとも同じファイルを参照する（`README.md` 参照）。
そのため同期が必要なのは「ルーター文書」と「タスク実行スキル」の2種類だけで、片方を編集した後に
このスキルを実行して差分を解消する。

## 手順

1. まず機械的な同期を実行する。`--check` で差分を確認し、`--from` で方向を明示する。

   ```bash
   uv run python scripts/sync_agent_docs.py --check          # 差分検出のみ（書き込みなし）
   uv run python scripts/sync_agent_docs.py --from claude     # Claude側を正として同期
   # または
   uv run python scripts/sync_agent_docs.py --from github     # GitHub/prompt側を正として同期
   ```

   同期方向は **必ず `--from` で指定する**（未指定はエラー）。ファイルの更新日時(mtime)は
   `git clone` や一括生成で同一値になり信頼できないため、自動判定はしない。編集した側を
   `--from` に渡すこと。

   このスクリプトは2種類のペアを扱う。
   - **ルーター文書**: `CLAUDE.md` と `AGENTS.md`。`## Hard Rules` 以降の本文は完全に同一である
     べきで、冒頭の導入文と、`CLAUDE.md` にだけある `## Skills`（skill の `@` import）は各ファイル
     固有として比較・上書きの対象外になる。`--from` で指定した側の本文をもう一方へコピーする
     （元ファイルの改行コードは保持される）。このドリフトは `--check` でCIブロッキング対象
     （終了コード1）。
   - **タスク実行スキル**（frontmatterに `disable-model-invocation: true` があるスキル）:
     `.claude/skills/<name>/SKILL.md` と `.github/prompts/<name>.prompt.md`。
     frontmatterを変換（`name`/`disable-model-invocation` ⇔ `agent: "agent"`）しつつ、
     本文を同期する。**このペアのドリフトはCIをブロックしない**（報告のみ）。以下の
     2点は機械同期でも安全に扱えるよう対応済み。
     - Copilot prompt側にしかない `${input:...}` プレースホルダ構文と、Claude側の
       「引数の確認」箇条書き（frontmatter descriptionの `引数: <a> <b>` で検出）は
       「保護ゾーン」として扱われ、同期時に削除・上書きされず、既存の内容がそのまま
       もう一方に引き継がれる。周辺の説明文だけが更新される。
     - `CLAUDE.md`⇔`AGENTS.md` のような本文中の相互参照は `TASK_REFERENCE_MAP`
       （`scripts/sync_agent_docs.py`）に従って自動的に書き換わる。skill のパスは
       3ツール共通（`.claude/skills/`）なので書き換え対象ではない。両陣営を意図的に併記する
       メタ文書（このスキル自身のように「`CLAUDE.md` と `AGENTS.md`」を並べて説明するもの）は
       `REFERENCE_REWRITE_EXEMPT` に登録して変換対象から除外する。新しい種類の相互参照を
       追加した場合は `TASK_REFERENCE_MAP` に、併記メタ文書を追加した場合は
       `REFERENCE_REWRITE_EXEMPT` にそれぞれエントリを足すこと。
     - frontmatterのdescriptionは二重引用符でエスケープしてエンコードされる
       （`"` を含んでも壊れない）。Claude側は `引数: ` のような colon-space を含むときだけ
       引用符を付ける。
     - 上記に当てはまらない未知の構文・参照が失われる可能性は残るため、機械同期を適用した
       後は必ず `git diff` で内容を確認すること。ロジックを変更した場合は
       `uv run pytest tests/test_sync_agent_docs.py` で退行がないか確認する。

2. スクリプトの出力にある **WARNING（対応するタスクスキルが無い prompt）** を確認する。
   `.github/prompts/<name>.prompt.md` だけが存在する状態であり、単純コピーでは済まない。
   以下を判断して実施する。
   - 意図的な追加であれば、`.claude/skills/<name>/SKILL.md` を作成する。frontmatter は
     `name` / `description` / `disable-model-invocation: true` の3キー。
   - 一時的な作業中のファイルであれば、ユーザーに確認してから対応する。

3. スクリプトの出力にある **タスク実行スキルのDRIFT** を確認する。
   - `${input:...}` / 引数箇条書きの保護と、既知の相互参照の書き換えは機械同期で
     安全に扱える（上記1参照）ため、通常は編集した側を `--from` に渡して同期してよい。
   - DRIFTに理由が併記されている場合（保護ゾーンを検出できなかった等）は、機械同期が
     安全に行えないサインなので、機械同期せず手作業で該当箇所を保持したまま反映する。
   - 適用後は必ず `git diff` で新種の差分の欠落が無いか確認する。
   - 文言を逐語訳する必要はない。各陣営の既存の書き方（Claudeは日本語の指示文、
     Copilotは英語の `${input:...}` プレースホルダなど）に合わせる。

4. `.github/instructions/*.instructions.md`（Copilot のパス別自動適用ルール）に対応する内容が
   ルーター文書の「File-Specific Guidelines」セクションにも反映されているか確認する。Copilot は
   `applyTo` で自動適用されるが、Claude Code と Codex はルーター文書の記述しか見ないため、
   ここが揃っていないとツール間で挙動が変わる。

5. 最後に検証する。

   ```bash
   uv run python scripts/sync_agent_docs.py --check
   uv run python scripts/validate_agent_docs.py
   ```

## ルール

- 機械的にコピーできる内容（ルーター文書の本文、タスクスキルの本文）は必ずスクリプト経由で
  同期する。手作業でコピーすると改行コードや空白の差分が再発する。
- skill 本体（`.claude/skills/<name>/`）はミラーを持たない。ここに他陣営向けのコピーを作らない。
- 言語・frontmatter書式が意図的に異なるファイル同士は、内容の**意味**を合わせることを
  目的とし、逐語的な同一化はしない。
- 新規スキルの追加や構成変更は、必ずユーザーに意図を確認してから反映する。
- 最後に、変更したファイルと解消した差分を日本語で要約する。
