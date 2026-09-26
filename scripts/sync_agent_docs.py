"""エージェント向けルーター文書とタスクスキルを同期するスクリプト。

このリポジトリの設計(README.md参照)では、以下の2種類の対応関係がある。

1. ルーター文書: `CLAUDE.md`(Claude Code)と `AGENTS.md`(GitHub Copilot / Codex)は、
   `## Hard Rules` 以降の本文が完全に同一であるべき。冒頭の導入文と、Claude 固有の
   `## Skills`(skill の @import)ブロックだけが各ファイル固有。
2. タスク実行スキル: `.claude/skills/<name>/SKILL.md` の frontmatter に
   `disable-model-invocation: true` があるスキルは、モデルからの自動起動ができない
   スラッシュコマンド専用スキルであり、`.github/prompts/<name>.prompt.md` に対応する。
   frontmatterの書式(`name`/`disable-model-invocation` ⇔ `agent: "agent"`)を変換しつつ
   本文を同期する。本文中の以下は自動で扱う:
   - Copilotの `${input:...}` プレースホルダとClaudeの「引数の確認」箇条書きは
     「保護ゾーン」として、削除・上書きせず相手側の既存内容を保持する。
   - `CLAUDE.md`⇔`AGENTS.md` の相互参照を変換する(両陣営を意図的に併記するメタ文書は
     `REFERENCE_REWRITE_EXEMPT` で除外)。

skill 本体(`.claude/skills/<name>/`)はミラーを持たない。Claude Code・Copilot・Codex の
いずれも `.claude/skills/` を直接参照する(Codex 向けに `.agents/skills` がシンボリック
リンクを張っている)ため、同期対象は上記2種類だけである。

同期方向は **必ず `--from claude` / `--from github` で明示する**。ファイルの更新日時
(mtime)は `git clone` や一括生成で同一値になり信頼できないため、方向の自動判定は行わない。

CIブロッキング:
- ルーター文書のドリフトのみ終了コード1でCIを止める。
- タスクスキル⇔prompt間のドリフトは検出・報告のみ(終了コードに影響しない)。保護ゾーンの
  検出に失敗した場合などは理由付きで報告され、書き込みを見送る(安全側に倒す)。

対象外(このスクリプトでは同期しない):
- タスクスキルの新規ポーティング。内容の取捨選択が必要なため警告のみ行う。差分の解消には
  `sync-agent-docs` スキル(エージェント)を使うこと。

Usage:
    uv run python scripts/sync_agent_docs.py --check           # 書き込みせず差分検出(CI向け)
    uv run python scripts/sync_agent_docs.py --from claude      # Claude側を正として同期
    uv run python scripts/sync_agent_docs.py --from github      # GitHub側を正として同期
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
GITHUB_PROMPTS_DIR = REPO_ROOT / ".github" / "prompts"

# ルーター文書。Claude Code は CLAUDE.md を、Copilot / Codex は AGENTS.md を読む。
CLAUDE_ROUTER_PATH = REPO_ROOT / "CLAUDE.md"
AGENTS_ROUTER_PATH = REPO_ROOT / "AGENTS.md"
# 両者で一致していなければならない本文の開始見出し
ROUTER_BODY_START = "## Hard Rules (Always Apply)"
# CLAUDE.md にだけ存在する末尾セクション(skill の @import)
CLAUDE_ONLY_SECTION = "## Skills"

FRONTMATTER_DELIM = "---"

# frontmatterのdescriptionにある `引数: <a> <b>` 形式から引数名リストを取り出す
ARG_LIST_PATTERN = re.compile(r"引数:\s*((?:<[\w-]+>\s*)+)")
ARG_NAME_PATTERN = re.compile(r"<([\w-]+)>")

# Copilot prompt本文の `${input:name}` または `${input:name:desc}` プレースホルダ
INPUT_PLACEHOLDER_PATTERN = re.compile(r"\$\{input:[\w-]+(?::[^}]*)?\}")

# タスクスキル本文中の相互参照(単なるファイル名・ディレクトリ名の言及)の対応表。
# (Claude側の語, GitHub側の語)。
TASK_REFERENCE_MAP = [
    ("CLAUDE.md", "AGENTS.md"),
]

# 相互参照の書き換えを行わないタスクスキル。両陣営を意図的に併記するメタ文書
# (このスキル自身のように「CLAUDE.md と AGENTS.md」を並べて説明するもの)を登録する。
REFERENCE_REWRITE_EXEMPT = {"sync-agent-docs"}


# --------------------------------------------------------------------------------------
# 低レベルユーティリティ
# --------------------------------------------------------------------------------------
def normalize(text: str) -> str:
    """改行コード(CRLF/CR)と末尾改行を統一し、内容比較・書き込み用に正規化する。"""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"


def split_frontmatter(text: str) -> tuple[list[str], str]:
    """先頭の frontmatter ブロック(`---`〜`---`)を行のリストとして取り出し、本文と分離する。

    Args:
        text: SKILL.md / prompt.md 全体のテキスト。

    Returns:
        (frontmatter内側の行のリスト, frontmatterに続く本文全体)。
        frontmatterが見つからない場合は `([], text)`。
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        return [], text
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIM:
            return lines[1:i], "".join(lines[i + 1 :])
    return [], text


def parse_scalar(raw: str) -> str:
    """frontmatterの値をYAMLの単純スカラーとして解釈する(引用符の除去とアンエスケープ)。

    Args:
        raw: `key: value` の value 部分(前後空白を含みうる)。

    Returns:
        引用符を外しエスケープを解いた文字列。
    """
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        inner = value[1:-1]
        if value[0] == '"':
            # 二重引用符スカラーのエスケープを解く
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return value


def parse_frontmatter_fields(fm_lines: list[str]) -> dict[str, str]:
    """frontmatterの行から `key: value` の単純な組を辞書として取り出す。

    値は `parse_scalar` を通し、引用符の有無に関わらず同じ結果になるようにする。
    """
    fields: dict[str, str] = {}
    for line in fm_lines:
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        fields[key.strip()] = parse_scalar(value)
    return fields


def emit_double_quoted(value: str) -> str:
    """文字列をYAMLの二重引用符スカラーとして安全にエンコードする。"""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def needs_quoting(value: str) -> bool:
    """YAMLの平文スカラーとして安全でない(引用符が必要な)値か判定する。

    主に `引数: ` のような colon-space を含む場合を検出する。
    """
    if value != value.strip():
        return True
    if ": " in value or value.endswith(":"):
        return True
    if " #" in value:
        return True
    # 平文スカラーとして特別扱いされる先頭文字
    return bool(value) and value[0] in "!&*?|>%@`\"'#,[]{}-:"


def emit_description(value: str, *, always_quote: bool) -> str:
    """descriptionフィールドの値を、必要なら引用符付きでエンコードする。

    Args:
        value: description の生の値(引用符なし)。
        always_quote: Trueなら常に二重引用符で囲む(prompt側の慣習)。
            Falseなら平文で安全なときだけ引用符を省く(Claude側の慣習)。

    Returns:
        frontmatterに書ける形にエンコードした文字列。
    """
    if always_quote or needs_quoting(value):
        return emit_double_quoted(value)
    return value


def is_task_skill(claude_skill_path: Path) -> bool:
    """Claudeスキルが `disable-model-invocation: true` を持つタスクスキルか判定する。"""
    fm_lines, _ = split_frontmatter(claude_skill_path.read_text(encoding="utf-8"))
    return parse_frontmatter_fields(fm_lines).get("disable-model-invocation", "").lower() == "true"


def extract_arg_names(description: str) -> list[str]:
    """frontmatterのdescriptionから `引数: <a> <b>` 形式の引数名リストを取り出す。"""
    match = ARG_LIST_PATTERN.search(description)
    if match is None:
        return []
    return ARG_NAME_PATTERN.findall(match.group(1))


# --------------------------------------------------------------------------------------
# 保護ゾーン(引数プレースホルダ)の抽出・挿入
# --------------------------------------------------------------------------------------
def _is_heading(paragraph: str) -> bool:
    """段落がMarkdown見出し(`#` 始まり)か判定する。"""
    return paragraph.lstrip().startswith("#")


def _is_bullet_list(paragraph: str) -> bool:
    """段落が箇条書き(全ての非空行が `- ` 始まり)か判定する。"""
    lines = [line for line in paragraph.split("\n") if line.strip()]
    return bool(lines) and all(line.lstrip().startswith("- ") for line in lines)


def strip_claude_arg_block(body: str) -> tuple[str | None, str, int | None]:
    """Claude本文から「引数の確認」保護ゾーンを抽出し、本文から取り除く。

    保護ゾーンは「本文中で最初に現れる箇条書き段落」と、その直前の導入段落(見出しを除く)
    からなる。番号付きリスト(`1.`)や末尾のまとめ箇条書きより前に引数の箇条書きが来る、
    という規約を前提とする。

    Args:
        body: frontmatterを除いた本文。

    Returns:
        (抽出したブロック または None, ブロックを除いた本文, ブロックの段落インデックス)。
        箇条書きが見つからない場合は (None, body, None)。
    """
    paragraphs = body.split("\n\n")
    bullet_idx = next(
        (i for i, para in enumerate(paragraphs) if _is_bullet_list(para)),
        None,
    )
    if bullet_idx is None:
        return None, body, None

    start = bullet_idx
    intro_idx = bullet_idx - 1
    if intro_idx >= 0 and paragraphs[intro_idx].strip() and not _is_heading(paragraphs[intro_idx]):
        start = intro_idx

    block = "\n\n".join(paragraphs[start : bullet_idx + 1])
    remainder = "\n\n".join(paragraphs[:start] + paragraphs[bullet_idx + 1 :])
    return block, remainder, start


def strip_prompt_input_block(body: str) -> tuple[str | None, str, int | None]:
    """Copilot prompt本文から `${input:...}` 保護ゾーンを抽出し、本文から取り除く。

    `${input:...}` を含む段落が連続している(間に別の段落が挟まらない)場合にのみ、
    それらをまとめて1つの保護ゾーンとして扱う。連続していない場合は安全側に倒して
    None を返す。

    Args:
        body: frontmatterを除いた本文。

    Returns:
        (抽出したブロック または None, ブロックを除いた本文, ブロックの段落インデックス)。
    """
    paragraphs = body.split("\n\n")
    input_idxs = [i for i, para in enumerate(paragraphs) if INPUT_PLACEHOLDER_PATTERN.search(para)]
    if not input_idxs:
        return None, body, None

    start, end = input_idxs[0], input_idxs[-1]
    if input_idxs != list(range(start, end + 1)):
        return None, body, None

    block = "\n\n".join(paragraphs[start : end + 1])
    remainder = "\n\n".join(paragraphs[:start] + paragraphs[end + 1 :])
    return block, remainder, start


def insert_block_at_para(remainder: str, block: str, index: int) -> str:
    """remainderを段落単位で分割し、指定インデックス位置に block を挿入する。

    Args:
        remainder: 保護ゾーンを取り除いた本文。
        block: 挿入する保護ゾーンの内容。
        index: 挿入する段落インデックス(範囲外はクランプする)。

    Returns:
        blockを挿入した本文。
    """
    paragraphs = remainder.split("\n\n")
    index = max(0, min(index, len(paragraphs)))
    return "\n\n".join(paragraphs[:index] + [block] + paragraphs[index:])


def rewrite_task_references(text: str, *, to_prompt: bool, name: str) -> str:
    """タスクスキル本文中の `CLAUDE.md`⇔`AGENTS.md` のような相互参照を変換する。

    `REFERENCE_REWRITE_EXEMPT` に登録されたスキル(両陣営を意図的に併記するメタ文書)は
    変換しない。それ以外は `TASK_REFERENCE_MAP` に従って単純置換する。

    Args:
        text: 変換対象のテキスト(本文またはdescription)。
        to_prompt: TrueならClaude→Copilot方向、Falseなら逆方向。
        name: タスクスキル名(除外判定に使う)。

    Returns:
        変換後のテキスト。
    """
    if name in REFERENCE_REWRITE_EXEMPT:
        return text
    for claude_term, github_term in TASK_REFERENCE_MAP:
        src, dst = (claude_term, github_term) if to_prompt else (github_term, claude_term)
        text = text.replace(src, dst)
    return text


# --------------------------------------------------------------------------------------
# タスクスキル ⇔ prompt の相互変換
# --------------------------------------------------------------------------------------
def claude_task_skill_to_prompt(
    text: str, name: str, existing_prompt_text: str | None
) -> tuple[str | None, str | None]:
    """Claudeタスクスキルの内容をCopilot prompt形式に変換する。

    Args:
        text: Claudeタスクスキルの全体テキスト。
        name: タスクスキル名。
        existing_prompt_text: 対応するprompt側の現在の内容。まだ存在しない場合は None。

    Returns:
        (変換後テキスト, 理由)。変換できた場合は理由がNone、
        安全に変換できない場合はテキストがNoneで理由が入る。
    """
    fm_lines, body = split_frontmatter(text)
    description = parse_frontmatter_fields(fm_lines).get("description", "")
    arg_names = extract_arg_names(description)

    prompt_description = rewrite_task_references(description, to_prompt=True, name=name)
    frontmatter = (
        f'---\nagent: "agent"\ndescription: {emit_double_quoted(prompt_description)}\n---\n'
    )

    body = rewrite_task_references(body, to_prompt=True, name=name)
    if not arg_names:
        return frontmatter + body, None

    _, remainder, para_index = strip_claude_arg_block(body)
    if para_index is None:
        return None, "Claude側で「引数の確認」箇条書きブロックを検出できなかった"
    if existing_prompt_text is None:
        return None, "引数を持つタスクスキルの新規prompt作成は非対応(手動で作成すること)"

    _, existing_prompt_body = split_frontmatter(existing_prompt_text)
    preserved_block, _, _ = strip_prompt_input_block(existing_prompt_body)
    if preserved_block is None:
        return None, "既存prompt側で `${input:...}` ブロックを検出できなかった"

    return frontmatter + insert_block_at_para(remainder, preserved_block, para_index), None


def prompt_to_claude_task_skill(
    text: str, name: str, existing_claude_text: str | None
) -> tuple[str | None, str | None]:
    """Copilot promptの内容をClaudeタスクスキル形式に変換する。

    Args:
        text: Copilot promptの全体テキスト。
        name: タスクスキル名(Claude側のディレクトリ名)。
        existing_claude_text: 対応するClaude側の現在の内容。まだ存在しない場合は None。

    Returns:
        (変換後テキスト, 理由)。変換できた場合は理由がNone、
        安全に変換できない場合はテキストがNoneで理由が入る。
    """
    fm_lines, body = split_frontmatter(text)
    description = parse_frontmatter_fields(fm_lines).get("description", "")

    # 「引数: <a> <b>」マーカーはClaude側のdescriptionにしか無い規約のため、
    # 既存Claude側のdescriptionを優先して引数名を判定する。
    existing_claude_description = ""
    if existing_claude_text is not None:
        existing_fm_lines, _ = split_frontmatter(existing_claude_text)
        existing_claude_description = parse_frontmatter_fields(existing_fm_lines).get(
            "description", ""
        )
    arg_names = extract_arg_names(existing_claude_description) or extract_arg_names(description)

    claude_description = rewrite_task_references(description, to_prompt=False, name=name)
    if arg_names and "引数:" not in claude_description:
        # promptのdescriptionには引数マーカーが無いため、既存Claude側の表記を引き継ぐ
        arg_marker = " ".join(f"<{n}>" for n in arg_names)
        claude_description = f"{claude_description}。引数: {arg_marker}"

    frontmatter = (
        f"---\nname: {name}\n"
        f"description: {emit_description(claude_description, always_quote=False)}\n"
        f"disable-model-invocation: true\n---\n"
    )

    body = rewrite_task_references(body, to_prompt=False, name=name)
    if not arg_names:
        return frontmatter + body, None

    _, remainder, para_index = strip_prompt_input_block(body)
    if para_index is None:
        return None, "prompt側で `${input:...}` ブロックを検出できなかった"
    if existing_claude_text is None:
        return None, "引数を持つタスクスキルの新規SKILL.md作成は非対応(手動で作成すること)"

    _, existing_claude_body = split_frontmatter(existing_claude_text)
    preserved_block, _, _ = strip_claude_arg_block(existing_claude_body)
    if preserved_block is None:
        return None, "既存Claude側で「引数の確認」箇条書きブロックを検出できなかった"

    return frontmatter + insert_block_at_para(remainder, preserved_block, para_index), None


# --------------------------------------------------------------------------------------
# ペアの探索
# --------------------------------------------------------------------------------------
@dataclass
class TaskSkillPair:
    """Claudeタスクスキルと、対応するCopilot promptのペア。"""

    name: str
    claude_path: Path
    prompt_path: Path


def task_skill_names() -> set[str]:
    """`.claude/skills/` 配下のタスクスキル名の集合を返す。"""
    return {p.parent.name for p in CLAUDE_SKILLS_DIR.glob("*/SKILL.md") if is_task_skill(p)}


def discover_task_skill_pairs() -> list[TaskSkillPair]:
    """タスクスキルを検出し、対応する `.github/prompts/<name>.prompt.md` とペア化する。"""
    return [
        TaskSkillPair(
            name=name,
            claude_path=CLAUDE_SKILLS_DIR / name / "SKILL.md",
            prompt_path=GITHUB_PROMPTS_DIR / f"{name}.prompt.md",
        )
        for name in sorted(task_skill_names())
    ]


def find_orphan_prompts() -> list[str]:
    """タスクスキルに対応しない `.github/prompts/*.prompt.md` を検出する。"""
    tasks = task_skill_names()
    prompt_names = {p.stem.removesuffix(".prompt") for p in GITHUB_PROMPTS_DIR.glob("*.prompt.md")}
    return sorted(prompt_names - tasks)


# --------------------------------------------------------------------------------------
# 同期処理
# --------------------------------------------------------------------------------------
def split_router_doc(text: str) -> tuple[str, str, str]:
    """ルーター文書を (冒頭, 共通本文, 末尾) の3つに分ける。

    共通本文は `ROUTER_BODY_START` 以降で、CLAUDE.md だけが持つ `CLAUDE_ONLY_SECTION`
    の手前まで。冒頭(導入文)と末尾は各ファイル固有なので比較・同期の対象外。

    Args:
        text: CLAUDE.md または AGENTS.md の全体テキスト。

    Returns:
        (冒頭, 共通本文, 末尾)。末尾は直前の空行を含み、CLAUDE.md 以外では空文字列。
        3つを連結すると元のテキスト(改行コード正規化後)に戻る。

    Raises:
        ValueError: `ROUTER_BODY_START` の見出しが見つからない場合。
    """
    normalized = normalize(text)
    start = normalized.find(ROUTER_BODY_START)
    if start < 0:
        raise ValueError(f"見出し `{ROUTER_BODY_START}` が見つからない")
    end = normalized.find(f"\n{CLAUDE_ONLY_SECTION}", start)
    if end < 0:
        return normalized[:start], normalized[start:].rstrip("\n") + "\n", ""
    return normalized[:start], normalized[start:end].rstrip("\n") + "\n", normalized[end:]


def write_preserving_eol(path: Path, text: str) -> None:
    """既存ファイルの改行コード(LF/CRLF)を保ったままテキストを書き込む。"""
    # CRLF のファイルを LF で書き戻すと差分が全行に広がるため、元の形式に合わせる
    was_crlf = b"\r\n" in path.read_bytes() if path.exists() else False
    body = text.replace("\r\n", "\n")
    path.write_bytes((body.replace("\n", "\r\n") if was_crlf else body).encode("utf-8"))


def sync_router_docs(*, check_only: bool, direction: str | None) -> str:
    """CLAUDE.md と AGENTS.md の共通本文を比較し、必要なら方向に従って書き込む。

    Args:
        check_only: Trueなら書き込まず差分の有無のみ判定する。
        direction: "claude" なら CLAUDE.md を、"github" なら AGENTS.md を正とする。
            check_only=False のときは必須。

    Returns:
        "in_sync" | "updated_claude" | "updated_github" | "drift"。
    """
    claude_head, claude_body, claude_tail = split_router_doc(
        CLAUDE_ROUTER_PATH.read_text(encoding="utf-8")
    )
    agents_head, agents_body, agents_tail = split_router_doc(
        AGENTS_ROUTER_PATH.read_text(encoding="utf-8")
    )

    if claude_body == agents_body:
        return "in_sync"
    if check_only:
        return "drift"

    if direction == "claude":
        write_preserving_eol(AGENTS_ROUTER_PATH, agents_head + claude_body + agents_tail)
        return "updated_github"
    write_preserving_eol(CLAUDE_ROUTER_PATH, claude_head + agents_body + claude_tail)
    return "updated_claude"


def sync_task_skill_pair(
    pair: TaskSkillPair, *, check_only: bool, direction: str | None
) -> tuple[str, str | None]:
    """タスクスキル1ペアを比較し、必要なら方向に従ってもう一方へ書き込む。

    Args:
        pair: 同期対象のタスクスキルペア。
        check_only: Trueなら書き込まず差分の有無のみ判定する。
        direction: "claude" ならClaude側を、"github"(prompt側)を正とする。
            check_only=False のときは必須。

    Returns:
        (状態, 理由)。状態は "in_sync" | "updated_claude" | "updated_prompt" | "drift"。
        安全に変換できず見送った場合のみ理由が入る。
    """
    claude_text = normalize(pair.claude_path.read_text(encoding="utf-8"))
    prompt_text = (
        normalize(pair.prompt_path.read_text(encoding="utf-8"))
        if pair.prompt_path.exists()
        else None
    )

    claude_as_prompt, reason = claude_task_skill_to_prompt(claude_text, pair.name, prompt_text)
    if claude_as_prompt is not None:
        claude_as_prompt = normalize(claude_as_prompt)

    # prompt未作成: Claude側を正とするときだけ生成する
    if prompt_text is None:
        if not check_only and direction == "claude" and claude_as_prompt is not None:
            pair.prompt_path.parent.mkdir(parents=True, exist_ok=True)
            pair.prompt_path.write_text(claude_as_prompt, encoding="utf-8")
            return "updated_prompt", None
        return "drift", reason or "対応するpromptが存在しない"

    if claude_as_prompt is not None and claude_as_prompt == prompt_text:
        return "in_sync", None
    if check_only:
        # Claude側を正にできない理由があれば伝える
        return "drift", reason

    if direction == "claude":
        if claude_as_prompt is None:
            return "drift", reason
        pair.prompt_path.write_text(claude_as_prompt, encoding="utf-8")
        return "updated_prompt", None

    prompt_as_claude, reason = prompt_to_claude_task_skill(prompt_text, pair.name, claude_text)
    if prompt_as_claude is None:
        return "drift", reason
    pair.claude_path.write_text(normalize(prompt_as_claude), encoding="utf-8")
    return "updated_claude", None


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def _run_router_docs(*, check_only: bool, direction: str | None) -> str:
    """ルーター文書を同期し、結果を表示して状態を返す。"""
    print("--- Router docs (CLAUDE.md <-> AGENTS.md) ---")
    status = sync_router_docs(check_only=check_only, direction=direction)
    message = {
        "in_sync": "OK     (in sync):            CLAUDE.md / AGENTS.md",
        "updated_claude": "SYNCED (AGENTS.md -> CLAUDE.md)",
        "updated_github": "SYNCED (CLAUDE.md -> AGENTS.md)",
        "drift": (
            "DRIFT  (CI-blocking — run --from claude/github to sync): "
            f"CLAUDE.md / AGENTS.md の `{ROUTER_BODY_START}` 以降が一致しない"
        ),
    }[status]
    print(message)
    return status


def _run_task_skills(*, check_only: bool, direction: str | None) -> dict[str, list[str]]:
    """タスクスキルを同期し、結果を表示して集計を返す。"""
    print("\n--- Task skills (.claude/skills <-> .github/prompts) ---")
    results: dict[str, list[str]] = {
        "in_sync": [],
        "updated_claude": [],
        "updated_prompt": [],
        "drift": [],
    }
    reasons: dict[str, str] = {}
    for pair in discover_task_skill_pairs():
        status, reason = sync_task_skill_pair(pair, check_only=check_only, direction=direction)
        results[status].append(pair.name)
        if reason is not None:
            reasons[pair.name] = reason

    for name in results["in_sync"]:
        print(f"OK     (in sync):            {name}")
    for name in results["updated_claude"]:
        print(f"SYNCED (prompt -> claude):   {name}")
    for name in results["updated_prompt"]:
        print(f"SYNCED (claude -> prompt):   {name}")
    for name in results["drift"]:
        suffix = f" ({reasons[name]})" if name in reasons else ""
        print(f"DRIFT  (not CI-blocking): {name}{suffix}")

    orphan_prompts = find_orphan_prompts()
    if orphan_prompts:
        print("\nWARNING: the following prompts have no matching Claude task skill:")
        for name in orphan_prompts:
            print(f"  - .github/prompts/{name}.prompt.md")
    return results


def main(argv: list[str] | None = None) -> int:
    """メイン処理。終了コードを返す。"""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="書き込みを行わず、ルーター文書に差分があれば終了コード1で報告する(CI向け)",
    )
    parser.add_argument(
        "--from",
        dest="direction",
        choices=["claude", "github"],
        default=None,
        help="同期方向。書き込み時は必須。'claude'はClaude側を、'github'はGitHub/prompt側を正とする",
    )
    args = parser.parse_args(argv)

    if not args.check and args.direction is None:
        parser.error("書き込みには --from claude / --from github の指定が必要です(または --check)")

    router_status = _run_router_docs(check_only=args.check, direction=args.direction)
    tasks = _run_task_skills(check_only=args.check, direction=args.direction)

    router_updated = router_status in ("updated_claude", "updated_github")
    updated = int(router_updated) + sum(len(tasks[k]) for k in ("updated_claude", "updated_prompt"))
    router_drift = router_status == "drift"
    task_drift = len(tasks["drift"])
    total = 1 + len(discover_task_skill_pairs())
    print(
        f"\n{total} pair(s) checked, {updated} updated, "
        f"{int(router_drift)} router drift, {task_drift} task drift."
    )
    if task_drift:
        print(
            "\nNOTE: task-skill drift is not CI-blocking. 保護ゾーンの検出に失敗した等の理由が"
            "ある場合は上に表示される。`sync-agent-docs` スキルで内容を確認すること。"
        )

    # ルーター文書のドリフトのみCIブロッキング対象
    return 1 if router_drift else 0


if __name__ == "__main__":
    sys.exit(main())
