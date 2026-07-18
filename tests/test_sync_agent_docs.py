"""`scripts/sync_agent_docs.py` のユニットテスト。

pyproject.toml の `pythonpath = ["src", "scripts"]` により、`scripts/` 配下の
`sync_agent_docs` を直接importできる。

方針: 「実装の写経」ではなく、このツールが守るべき契約(不変条件)を検証する。
- 同期で内容(`${input:...}` プレースホルダ・引数箇条書き・散文)を失わない。
- frontmatterは常に妥当なYAMLになり、値が往復で保存される。
- check時は書き込まない。方向は必須。保護ゾーンを検出できないときは書かずに理由を返す。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import sync_agent_docs as sync
import yaml

# --------------------------------------------------------------------------------------
# 共通フィクスチャ(実リポジトリと同じ正準形: descriptionは引用符付き)
# --------------------------------------------------------------------------------------
CLAUDE_ARG_SKILL = (
    '---\nname: demo\ndescription: "デモ。引数: <dataset_path> <topic>"\n'
    "disable-model-invocation: true\n---\n\n"
    "# Skill: Demo\n\n"
    "このスキルの説明。\n\n"
    "引数を確認する。\n\n"
    "- **データセットパス**\n"
    "- **トピック**\n\n"
    "`CLAUDE.md`、`.claude/skills/` に従う。\n\n"
    "1. 手順1\n2. 手順2\n"
)

PROMPT_ARG_SKILL = (
    '---\nagent: "agent"\ndescription: "デモ。引数: <dataset_path> <topic>"\n---\n\n'
    "# Skill: Demo\n\n"
    "このスキルの説明。\n\n"
    "Dataset:\n${input:dataset_path:Path to the input dataset}\n\n"
    "Topic:\n${input:topic:Short description}\n\n"
    "`AGENTS.md`、`.github/skills/` に従う。\n\n"
    "1. 手順1\n2. 手順2\n"
)


def _frontmatter_dict(text: str) -> dict:
    """テキストのfrontmatterをYAMLとして厳密にパースして辞書で返す(妥当性も兼ねる)。"""
    fm, _ = sync.split_frontmatter(text)
    loaded = yaml.safe_load("".join(fm))
    assert isinstance(loaded, dict)
    return loaded


# --------------------------------------------------------------------------------------
# 低レベルユーティリティ
# --------------------------------------------------------------------------------------
def test_normalize_crlf_and_trailing() -> None:
    assert sync.normalize("a\r\nb\r\n") == "a\nb\n"
    assert sync.normalize("a\rb") == "a\nb\n"
    assert sync.normalize("a\n\n\n") == "a\n"
    assert sync.normalize("no-trailing") == "no-trailing\n"


def test_link_conversion_round_trip() -> None:
    claude = "see [x](.claude/skills/path-and-io/SKILL.md) now"
    github = "see [x](../path-and-io/SKILL.md) now"
    assert sync.claude_to_github(claude) == github
    assert sync.github_to_claude(github) == claude


def test_split_frontmatter() -> None:
    fm, body = sync.split_frontmatter("---\nname: x\n---\nbody line\n")
    assert fm == ["name: x\n"]
    assert body == "body line\n"


def test_split_frontmatter_missing_or_unterminated() -> None:
    assert sync.split_frontmatter("no frontmatter") == ([], "no frontmatter")
    # 閉じ `---` が無い場合はfrontmatter無し扱い(本文を壊さない)
    assert sync.split_frontmatter("---\nname: x\nbody") == ([], "---\nname: x\nbody")


# --------------------------------------------------------------------------------------
# frontmatterのYAMLエンコード/デコード
# 契約: どんな値でも「妥当なYAML」になり、パースし直すと元の値に戻る(往復保存)。
# --------------------------------------------------------------------------------------
TRICKY_VALUES = [
    "普通の説明文",
    'ダブル"引用符"入り',
    "コロン: スペース入り",  # colon-space (平文では不正)
    "末尾コロン:",
    "バックスラッシュ\\入り",
    "ハッシュ #付き",
    "引数: <a> <b>",
    "- ハイフン始まり",
]


@pytest.mark.parametrize("value", TRICKY_VALUES)
def test_double_quoted_encoding_round_trips_through_yaml(value: str) -> None:
    line = f"description: {sync.emit_double_quoted(value)}"
    assert yaml.safe_load(line)["description"] == value


@pytest.mark.parametrize("value", TRICKY_VALUES)
def test_emit_description_is_valid_yaml_and_round_trips(value: str) -> None:
    # always_quote=False(Claude側)でも、平文が不正になる値は引用符が付き、必ず往復する
    line = f"description: {sync.emit_description(value, always_quote=False)}"
    assert yaml.safe_load(line)["description"] == value


def test_emit_double_quoted_exact_format() -> None:
    # in_syncはバイト一致で判定するため、エスケープの「厳密な出力形式」も契約に含まれる
    assert sync.emit_double_quoted('has "q" and \\') == '"has \\"q\\" and \\\\"'


def test_parse_scalar_is_inverse_of_emit() -> None:
    for value in TRICKY_VALUES:
        assert sync.parse_scalar(sync.emit_double_quoted(value)) == value
    # 平文/シングルクォートも解釈できる
    assert sync.parse_scalar("plain") == "plain"
    assert sync.parse_scalar("'single'") == "single"


def test_parse_frontmatter_fields_quote_agnostic() -> None:
    # 引用符あり/なしで同じ結果になること(往復の前提)
    quoted = sync.parse_frontmatter_fields(['description: "hello: world"'])
    unquoted = sync.parse_frontmatter_fields(["description: hello"])
    assert quoted["description"] == "hello: world"
    assert unquoted["description"] == "hello"


def test_extract_arg_names() -> None:
    assert sync.extract_arg_names("説明。引数: <dataset_path> <topic>") == ["dataset_path", "topic"]
    assert sync.extract_arg_names("引数なしの説明") == []


# --------------------------------------------------------------------------------------
# 保護ゾーンの抽出・挿入
# --------------------------------------------------------------------------------------
def test_strip_claude_arg_block() -> None:
    body = "\n# Skill\n\nintro paragraph.\n\n引数を確認する。\n\n- **A**\n- **B**\n\nnext.\n"
    block, remainder, idx = sync.strip_claude_arg_block(body)
    assert block is not None and idx == 2  # heading, intro, [block]
    assert "- **A**" in block and "引数を確認する。" in block
    assert "- **A**" not in remainder


def test_strip_claude_arg_block_not_found() -> None:
    # 箇条書きが無ければ検出失敗(呼び出し側はfail-safeに倒す)
    block, remainder, idx = sync.strip_claude_arg_block("# S\n\nprose only\n")
    assert block is None and idx is None and remainder == "# S\n\nprose only\n"


def test_strip_prompt_input_block_with_and_without_desc() -> None:
    body = "intro\n\nDataset:\n${input:dataset_path:desc}\n\nTopic:\n${input:topic}\n\nend"
    block, remainder, idx = sync.strip_prompt_input_block(body)
    assert block is not None and idx == 1
    assert "${input:dataset_path:desc}" in block
    assert "${input:topic}" in block  # 説明なし形式 ${input:name} も検出できる
    assert "${input:" not in remainder


def test_strip_prompt_input_block_non_contiguous_returns_none() -> None:
    # 間に散文が挟まる場合は安全側に倒してNone(誤って散文を保護ゾーンに含めない)
    body = "${input:a}\n\nmiddle prose\n\n${input:b}"
    block, remainder, idx = sync.strip_prompt_input_block(body)
    assert block is None and idx is None and remainder == body


def test_insert_block_at_para_restores_position() -> None:
    remainder = "p0\n\np1\n\np2"
    assert sync.insert_block_at_para(remainder, "BLOCK", 1) == "p0\n\nBLOCK\n\np1\n\np2"
    # 範囲外はクランプ(例外を投げない)
    assert sync.insert_block_at_para(remainder, "B", 99).endswith("p2\n\nB")


# --------------------------------------------------------------------------------------
# 相互参照の書き換え
# --------------------------------------------------------------------------------------
def test_rewrite_task_references_round_trip() -> None:
    text = "see CLAUDE.md and .claude/skills/foo/SKILL.md"
    to_prompt = sync.rewrite_task_references(text, to_prompt=True, name="run-eda")
    assert to_prompt == "see AGENTS.md and .github/skills/foo/SKILL.md"
    assert sync.rewrite_task_references(to_prompt, to_prompt=False, name="run-eda") == text


def test_rewrite_task_references_exempt_preserves_bilingual_meta() -> None:
    # 両陣営を併記するメタ文書は変換しない(文意保護)
    text = "CLAUDE.md と AGENTS.md を併記、.claude/skills/ と .github/skills/"
    assert sync.rewrite_task_references(text, to_prompt=True, name="sync-agent-docs") == text


# --------------------------------------------------------------------------------------
# 変換の中心的な契約: 内容非破壊・YAML妥当・往復・編集伝播
# --------------------------------------------------------------------------------------
def test_claude_to_prompt_equals_canonical_fixture() -> None:
    # バイト一致(in_syncの実体)。substringではなく完全一致で構造・空白も担保する
    prompt, reason = sync.claude_task_skill_to_prompt(CLAUDE_ARG_SKILL, "demo", PROMPT_ARG_SKILL)
    assert reason is None and prompt is not None
    assert sync.normalize(prompt) == sync.normalize(PROMPT_ARG_SKILL)


def test_prompt_to_claude_equals_canonical_fixture() -> None:
    claude, reason = sync.prompt_to_claude_task_skill(PROMPT_ARG_SKILL, "demo", CLAUDE_ARG_SKILL)
    assert reason is None and claude is not None
    assert sync.normalize(claude) == sync.normalize(CLAUDE_ARG_SKILL)


def test_full_round_trip_is_identity() -> None:
    # claude → prompt → claude が正準原文に戻る(情報損失ゼロ)
    prompt, _ = sync.claude_task_skill_to_prompt(CLAUDE_ARG_SKILL, "demo", PROMPT_ARG_SKILL)
    assert prompt is not None
    claude2, _ = sync.prompt_to_claude_task_skill(prompt, "demo", CLAUDE_ARG_SKILL)
    assert claude2 is not None
    assert sync.normalize(claude2) == sync.normalize(CLAUDE_ARG_SKILL)


def test_claude_to_prompt_is_idempotent() -> None:
    first, _ = sync.claude_task_skill_to_prompt(CLAUDE_ARG_SKILL, "demo", PROMPT_ARG_SKILL)
    assert first is not None
    first = sync.normalize(first)
    second, _ = sync.claude_task_skill_to_prompt(CLAUDE_ARG_SKILL, "demo", first)
    assert second is not None and sync.normalize(second) == first


def test_prose_edit_propagates_but_placeholders_preserved() -> None:
    # 実際のユースケース: Claudeの散文を編集 → promptへ反映され、かつ ${input} は保持される
    edited = CLAUDE_ARG_SKILL.replace("このスキルの説明。", "このスキルの説明（改訂）。")
    prompt, reason = sync.claude_task_skill_to_prompt(edited, "demo", PROMPT_ARG_SKILL)
    assert reason is None and prompt is not None
    assert "このスキルの説明（改訂）。" in prompt
    assert "${input:dataset_path:Path to the input dataset}" in prompt
    assert "${input:topic:Short description}" in prompt
    # 元のprompt側プレースホルダ説明はそのまま(散文更新で潰されない)
    assert "**データセットパス**" not in prompt  # Claudeの箇条書きは持ち込まれない


def test_placeholder_desc_edit_on_prompt_is_preserved_when_syncing_from_claude() -> None:
    # prompt側で ${input:...:desc} の説明を変えても、claude→prompt同期で保持される
    custom_prompt = PROMPT_ARG_SKILL.replace(
        "${input:topic:Short description}", "${input:topic:カスタム説明}"
    )
    prompt, _ = sync.claude_task_skill_to_prompt(CLAUDE_ARG_SKILL, "demo", custom_prompt)
    assert prompt is not None and "${input:topic:カスタム説明}" in prompt


def test_generated_frontmatter_is_valid_yaml_both_directions() -> None:
    prompt, _ = sync.claude_task_skill_to_prompt(CLAUDE_ARG_SKILL, "demo", PROMPT_ARG_SKILL)
    claude, _ = sync.prompt_to_claude_task_skill(PROMPT_ARG_SKILL, "demo", CLAUDE_ARG_SKILL)
    assert prompt is not None and claude is not None
    assert _frontmatter_dict(prompt)["description"] == "デモ。引数: <dataset_path> <topic>"
    assert _frontmatter_dict(claude)["description"] == "デモ。引数: <dataset_path> <topic>"


def test_description_with_quotes_survives_conversion() -> None:
    # fix#2の退行防止: descriptionに " が含まれてもYAMLが壊れず値が保存される
    claude = (
        '---\nname: q\ndescription: テスト。"引用符"入り\n'
        "disable-model-invocation: true\n---\n\n# S\n\nbody\n"
    )
    prompt, reason = sync.claude_task_skill_to_prompt(claude, "q", None)
    assert reason is None and prompt is not None
    assert _frontmatter_dict(prompt)["description"] == 'テスト。"引用符"入り'


def test_no_arg_skill_body_synced_with_reference_rewrite() -> None:
    claude = (
        "---\nname: plain\ndescription: 単純なスキル\ndisable-model-invocation: true\n---\n\n"
        "# Skill\n\n`CLAUDE.md` を見る。\n"
    )
    prompt, reason = sync.claude_task_skill_to_prompt(claude, "plain", None)
    assert reason is None and prompt is not None
    assert "AGENTS.md" in prompt and "CLAUDE.md" not in prompt


# --------------------------------------------------------------------------------------
# fail-safe: 保護ゾーンを安全に扱えないときは書かず理由を返す
# --------------------------------------------------------------------------------------
def test_arg_skill_without_existing_prompt_refuses_to_fabricate() -> None:
    # 引数ありスキルに対応promptが無い → ${input}を捏造せずNone+理由
    prompt, reason = sync.claude_task_skill_to_prompt(CLAUDE_ARG_SKILL, "demo", None)
    assert prompt is None and reason is not None


def test_arg_skill_with_prompt_missing_placeholders_refuses() -> None:
    # 既存promptに ${input} が無い → 検出失敗として書かない
    bad_prompt = '---\nagent: "agent"\ndescription: "x"\n---\n\nプレースホルダ無し本文\n'
    prompt, reason = sync.claude_task_skill_to_prompt(CLAUDE_ARG_SKILL, "demo", bad_prompt)
    assert prompt is None and reason is not None


# --------------------------------------------------------------------------------------
# 通常スキルの同期(sync_pair): 方向・check・in_sync判定・書き込み
# --------------------------------------------------------------------------------------
def _write_shared_pair(tmp_path: Path, claude_body: str, github_body: str) -> sync.SkillPair:
    claude = tmp_path / "c.md"
    github = tmp_path / "g.md"
    claude.write_text(f"---\nname: x\n---\n\n{claude_body}\n", encoding="utf-8")
    github.write_text(f"---\nname: x\n---\n\n{github_body}\n", encoding="utf-8")
    return sync.SkillPair(name="x", claude_path=claude, github_path=github)


def test_sync_pair_in_sync_ignores_only_link_notation(tmp_path: Path) -> None:
    pair = _write_shared_pair(
        tmp_path,
        "see [a](.claude/skills/foo/SKILL.md)",
        "see [a](../foo/SKILL.md)",
    )
    assert sync.sync_pair(pair, check_only=True, direction=None) == "in_sync"


def test_sync_pair_check_only_does_not_write(tmp_path: Path) -> None:
    pair = _write_shared_pair(tmp_path, "content A", "different B")
    before = pair.github_path.read_text(encoding="utf-8")
    assert sync.sync_pair(pair, check_only=True, direction=None) == "drift"
    assert pair.github_path.read_text(encoding="utf-8") == before  # 書き込まれない


def test_sync_pair_writes_in_requested_direction(tmp_path: Path) -> None:
    # direction=claude: github側がclaudeの内容(リンク変換済み)で上書きされる
    pair = _write_shared_pair(tmp_path, "see [a](.claude/skills/foo/SKILL.md)", "stale")
    assert sync.sync_pair(pair, check_only=False, direction="claude") == "updated_github"
    assert "../foo/SKILL.md" in pair.github_path.read_text(encoding="utf-8")
    assert pair.claude_path.read_text(encoding="utf-8").count("stale") == 0

    # direction=github: claude側がgithubの内容(リンク逆変換済み)で上書きされる
    pair2 = _write_shared_pair(tmp_path, "stale", "see [a](../bar/SKILL.md)")
    assert sync.sync_pair(pair2, check_only=False, direction="github") == "updated_claude"
    assert ".claude/skills/bar/SKILL.md" in pair2.claude_path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------
# タスクスキルの同期(sync_task_skill_pair): 方向・check・生成・fail-safe
# --------------------------------------------------------------------------------------
def _write_task_pair(
    tmp_path: Path, claude_text: str, prompt_text: str | None
) -> sync.TaskSkillPair:
    claude = tmp_path / "SKILL.md"
    claude.write_text(claude_text, encoding="utf-8")
    prompt = tmp_path / "demo.prompt.md"
    if prompt_text is not None:
        prompt.write_text(prompt_text, encoding="utf-8")
    return sync.TaskSkillPair(name="demo", claude_path=claude, prompt_path=prompt)


def test_sync_task_pair_check_only_does_not_write(tmp_path: Path) -> None:
    edited = CLAUDE_ARG_SKILL.replace("このスキルの説明。", "編集済み。")
    pair = _write_task_pair(tmp_path, edited, PROMPT_ARG_SKILL)
    before = pair.prompt_path.read_text(encoding="utf-8")
    status, reason = sync.sync_task_skill_pair(pair, check_only=True, direction=None)
    assert status == "drift"
    assert pair.prompt_path.read_text(encoding="utf-8") == before


def test_sync_task_pair_from_claude_writes_prompt(tmp_path: Path) -> None:
    edited = CLAUDE_ARG_SKILL.replace("このスキルの説明。", "編集済み。")
    pair = _write_task_pair(tmp_path, edited, PROMPT_ARG_SKILL)
    status, reason = sync.sync_task_skill_pair(pair, check_only=False, direction="claude")
    written = pair.prompt_path.read_text(encoding="utf-8")
    assert status == "updated_prompt" and reason is None
    assert "編集済み。" in written and "${input:dataset_path:Path to the input dataset}" in written


def test_sync_task_pair_from_github_writes_claude_keeping_bullets(tmp_path: Path) -> None:
    edited_prompt = PROMPT_ARG_SKILL.replace("このスキルの説明。", "prompt編集。")
    pair = _write_task_pair(tmp_path, CLAUDE_ARG_SKILL, edited_prompt)
    status, reason = sync.sync_task_skill_pair(pair, check_only=False, direction="github")
    written = pair.claude_path.read_text(encoding="utf-8")
    assert status == "updated_claude" and reason is None
    assert "prompt編集。" in written
    assert "- **データセットパス**" in written and "${input:" not in written


def test_sync_task_pair_creates_missing_prompt_only_for_no_arg_skill(tmp_path: Path) -> None:
    no_arg = (
        "---\nname: demo\ndescription: 引数なし\ndisable-model-invocation: true\n---\n\n"
        "# S\n\n`CLAUDE.md` に従う。\n"
    )
    pair = _write_task_pair(tmp_path, no_arg, None)
    status, _ = sync.sync_task_skill_pair(pair, check_only=False, direction="claude")
    assert status == "updated_prompt" and pair.prompt_path.exists()
    assert "AGENTS.md" in pair.prompt_path.read_text(encoding="utf-8")


def test_sync_task_pair_arg_skill_missing_prompt_is_drift_not_write(tmp_path: Path) -> None:
    # 引数ありスキルは既存promptが無いと ${input} を作れない → 書かずにdrift+理由
    pair = _write_task_pair(tmp_path, CLAUDE_ARG_SKILL, None)
    status, reason = sync.sync_task_skill_pair(pair, check_only=False, direction="claude")
    assert status == "drift" and reason is not None
    assert not pair.prompt_path.exists()


# --------------------------------------------------------------------------------------
# CLI契約(main): 方向は必須、--checkは非破壊
# --------------------------------------------------------------------------------------
def test_main_requires_direction_when_writing(capsys: pytest.CaptureFixture[str]) -> None:
    # fix#1の核: 方向未指定の書き込みはエラー(mt==由来の誤同期を防ぐ)
    with pytest.raises(SystemExit) as exc:
        sync.main([])
    assert exc.value.code == 2  # argparseのエラー終了


def test_main_check_is_nondestructive_and_reports_status(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # --check は書き込まず、整合していれば0を返す(CI契約)
    rc = sync.main(["--check"])
    assert rc == 0


# --------------------------------------------------------------------------------------
# 実リポジトリに対する統合テスト(退行防止)
# フィクスチャがコードと同じ思い込みで間違っていても、実ファイルとの照合で検出する。
# --------------------------------------------------------------------------------------
def test_repository_shared_skills_in_sync() -> None:
    pairs = sync.discover_pairs()
    assert pairs, "通常スキルのペアが検出されない"
    for pair in pairs:
        claude_text = sync.normalize(pair.claude_path.read_text(encoding="utf-8"))
        github_text = sync.normalize(pair.github_path.read_text(encoding="utf-8"))
        assert sync.claude_to_github(claude_text) == github_text, f"{pair.name}: in_syncでない"


def test_repository_task_skills_in_sync_and_valid_yaml() -> None:
    pairs = sync.discover_task_skill_pairs()
    assert pairs, "タスクスキルのペアが検出されない"
    for pair in pairs:
        claude_text = sync.normalize(pair.claude_path.read_text(encoding="utf-8"))
        prompt_text = (
            sync.normalize(pair.prompt_path.read_text(encoding="utf-8"))
            if pair.prompt_path.exists()
            else None
        )
        generated, reason = sync.claude_task_skill_to_prompt(claude_text, pair.name, prompt_text)
        assert reason is None, f"{pair.name}: 変換失敗 ({reason})"
        assert generated is not None
        assert sync.normalize(generated) == prompt_text, f"{pair.name}: in_syncでない"
        # 両実ファイルのfrontmatterが妥当なYAMLであること
        _frontmatter_dict(claude_text)
        assert prompt_text is not None
        _frontmatter_dict(prompt_text)
