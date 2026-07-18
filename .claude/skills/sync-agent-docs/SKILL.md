---
name: sync-agent-docs
description: Claude CodeとGitHub Copilotのスキル・指示ファイルの差分を検出し、機械的な部分はスクリプトで、判断が必要な部分はここで同期する
disable-model-invocation: true
---

# Skill: Sync Agent Docs

Claude Code (`.claude/`) と GitHub Copilot (`.github/`, `AGENTS.md`) は、共通スキルについて
「内部リンクの表記以外は同一内容」という設計になっている（`README.md` 参照）。
片方を編集した後にこのスキルを実行し、もう一方との差分を解消する。

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
   - **通常スキル**: `.claude/skills/<name>/SKILL.md` と `.github/skills/<name>/SKILL.md`。
     内部リンクの相対パス表記だけを変換し、`--from` で指定した側の内容をもう一方へコピーする。
     このドリフトは `--check` でCIブロッキング対象（終了コード1）。
   - **タスク実行スキル**（frontmatterに `disable-model-invocation: true` があるスキル）:
     `.claude/skills/<name>/SKILL.md` と `.github/prompts/<name>.prompt.md`。
     frontmatterを変換（`name`/`disable-model-invocation` ⇔ `agent: "agent"`）しつつ、
     本文を同期する。**このペアのドリフトはCIをブロックしない**（報告のみ）。以下の
     2点は機械同期でも安全に扱えるよう対応済み。
     - Copilot prompt側にしかない `${input:...}` プレースホルダ構文と、Claude側の
       「引数の確認」箇条書き（frontmatter descriptionの `引数: <a> <b>` で検出）は
       「保護ゾーン」として扱われ、同期時に削除・上書きされず、既存の内容がそのまま
       もう一方に引き継がれる。周辺の説明文だけが更新される。
     - `CLAUDE.md`⇔`AGENTS.md`、`.claude/skills/`⇔`.github/skills/` のような
       本文中の相互参照は `TASK_REFERENCE_MAP`（`scripts/sync_agent_docs.py`）に従って
       自動的に書き換わる。両陣営を意図的に併記するメタ文書（このスキル自身のように
       「`CLAUDE.md` と `AGENTS.md`」を並べて説明するもの）は `REFERENCE_REWRITE_EXEMPT`
       に登録して変換対象から除外する。新しい種類の相互参照を追加した場合は
       `TASK_REFERENCE_MAP` に、併記メタ文書を追加した場合は `REFERENCE_REWRITE_EXEMPT` に
       それぞれエントリを足すこと。
     - frontmatterのdescriptionは二重引用符でエスケープしてエンコードされる
       （`"` を含んでも壊れない）。Claude側は `引数: ` のような colon-space を含むときだけ
       引用符を付ける。
     - 上記に当てはまらない未知の構文・参照が失われる可能性は残るため、機械同期を適用した
       後は必ず `git diff` で内容を確認すること。ロジックを変更した場合は
       `uv run pytest tests/test_sync_agent_docs.py` で退行がないか確認する。

2. スクリプトの出力にある **WARNING（片側にのみ存在するスキル）** を確認する。
   これは新規スキルディレクトリの追加であり、単純コピーでは済まない（frontmatter形式や
   ディレクトリ構成が異なる場合がある）。以下を判断して実施する。
   - 意図的な追加であれば、もう一方の陣営にも同内容のスキルを作成する（内部リンクの表記は
     対象陣営の規約に合わせて書き換える）。
   - `.claude/skills/` に作る場合: frontmatter は `name` / `description` の2キー。
   - `.github/skills/` に作る場合: 同じ frontmatter 形式でよいが、内部リンクは
     `../<name>/SKILL.md` 形式にする。
   - 一時的な作業中のファイルであれば、ユーザーに確認してから対応する。

3. スクリプトの出力にある **タスク実行スキルのDRIFT** を確認する。
   - `${input:...}` / 引数箇条書きの保護と、既知の相互参照の書き換えは機械同期で
     安全に扱える（上記1参照）ため、通常は編集した側を `--from` に渡して同期してよい。
   - DRIFTに理由が併記されている場合（保護ゾーンを検出できなかった等）は、機械同期が
     安全に行えないサインなので、機械同期せず手作業で該当箇所を保持したまま反映する。
   - 適用後は必ず `git diff` で新種の差分の欠落が無いか確認する。
   - 文言を逐語訳する必要はない。各陣営の既存の書き方（Claudeは日本語の指示文、
     Copilotは英語の `${input:...}` プレースホルダなど）に合わせる。

4. `CLAUDE.md` と `AGENTS.md` / `.github/copilot-instructions.md` のハードルール・
   ルーティングテーブルに差分がないか確認する。これらも意図的に構成が異なる
   （`CLAUDE.md` はハードルール+ルーターを1ファイルに統合、Copilot側は
   `AGENTS.md` とcopilot-instructions.mdに分割）ため、内容の一致（ルールの意味）を見るのであって
   バイト単位の一致を求めない。

5. `.github/instructions/*.instructions.md`（パス別自動適用ルール）に対応する内容が
   `CLAUDE.md` の「File-Specific Guidelines」セクションにも反映されているか確認する。

6. 最後に検証する。

   ```bash
   uv run python scripts/sync_agent_docs.py --check
   uv run python scripts/validate_agent_docs.py
   ```

## ルール

- 機械的にコピーできる内容（10個の共通スキル）は必ずスクリプト経由で同期する。
  手作業でコピーすると改行コードやリンク表記の差分が再発する。
- 言語・frontmatter書式が意図的に異なるファイル同士は、内容の**意味**を合わせることを
  目的とし、逐語的な同一化はしない。
- 新規スキルの追加や構成変更は、必ずユーザーに意図を確認してから両陣営に反映する。
- 最後に、変更したファイルと解消した差分を日本語で要約する。
