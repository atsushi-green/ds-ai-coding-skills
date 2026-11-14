"""skill 要否テストの条件（arm）のテスト。claude は起動しない。

検証する契約:
- arm は sandbox のコピーだけを間引き、指定した節・行・パスだけが消える
- cases.yaml の指定が skill の現状とずれていたら、黙って進まずに止まる
- `no-diagnostics` を実際のリポジトリに当てると、*-diagnostics を指す記述が残らず、基本 skill は残る
- 間引きは sandbox の最初のコミットに含まれる（エージェントには未コミットの差分として見えない）
- skill を間引いた実行には、発火の合否を付けない
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from skill_eval.arms import FULL_ARM, Arm, LineRule, apply_arm, drop_lines, drop_section, parse_arms
from skill_eval.cases import Case, EvalConfig, Expectation, load_arms, load_suite
from skill_eval.evaluate import evaluate
from skill_eval.report import build_html, build_markdown
from skill_eval.sandbox import build_sandbox
from skill_eval.transcript import Transcript

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
CASES_YAML = REPO_ROOT / "scripts" / "skill_eval" / "cases.yaml"
# *-diagnostics の機能を指す記述。間引いた後に残っていたら、外したつもりの知識が漏れている
TRACE_RE = re.compile(r"-diagnostics|診断サマリー|診断項目|必ず出す")
# skill 名を含まなくても、診断 skill の中身（何を出すか、判定の語彙）が読めてしまう記述
LEAK_RE = re.compile(r"diagnos|診断|判定表|判定バッジ|要対処", re.IGNORECASE)

DOC = """\
# Title

intro

## Keep A

a

## Drop Me

body

### Child

child body

```python
## not a heading
```

## Keep B

b
"""


# --------------------------------------------------------------------------------------
# 定義の読み込み
# --------------------------------------------------------------------------------------
def test_parse_arms_always_has_full_and_rejects_bad_specs() -> None:
    arms = parse_arms({"x": {"remove": ["a"], "description": "d"}})
    assert set(arms) == {"x", FULL_ARM}
    assert arms[FULL_ARM].is_full and not arms["x"].is_full
    assert arms["x"].describe() == ["remove a"]
    # full は「間引かない」条件なので、操作を書けない
    with pytest.raises(ValueError, match="full"):
        parse_arms({FULL_ARM: {"remove": ["a"]}})
    with pytest.raises(ValueError, match="未知のキー"):
        parse_arms({"x": {"delete": ["a"]}})


def test_cases_yaml_defines_the_arms_used_in_the_readme() -> None:
    arms = load_arms(CASES_YAML)
    assert {FULL_ARM, "no-diagnostics", "bare"} <= set(arms)
    assert arms[FULL_ARM].is_full
    assert all(a.description for name, a in arms.items() if name != FULL_ARM)


# --------------------------------------------------------------------------------------
# 節・行の削除
# --------------------------------------------------------------------------------------
def test_drop_section_removes_the_section_with_its_children_only() -> None:
    text, n = drop_section(DOC, "## Drop Me")
    assert n == 1
    assert "## Keep A" in text and "## Keep B" in text and "intro" in text
    # 子の見出しと、コードブロック内の `##` もまとめて消える
    for gone in ("Drop Me", "Child", "child body", "not a heading"):
        assert gone not in text
    assert text.endswith("## Keep B\n\nb\n")


def test_drop_section_reports_missing_heading_and_ignores_fenced_hashes() -> None:
    assert drop_section(DOC, "## No Such Section") == (DOC, 0)
    # コードブロックの中の行は見出しとして扱わないので、節としては見つからない
    assert drop_section(DOC, "## not a heading")[1] == 0
    with pytest.raises(ValueError):
        drop_section(DOC, "Drop Me")


def test_drop_lines_removes_matching_lines() -> None:
    text, n = drop_lines(
        "keep\nuse the x-diagnostics skill\n| 診断項目 | 値 |\nkeep2\n", ("-diagnostics", "診断")
    )
    assert (text, n) == ("keep\nkeep2\n", 2)


# --------------------------------------------------------------------------------------
# sandbox への適用
# --------------------------------------------------------------------------------------
def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_apply_arm_removes_paths_sections_and_lines(tmp_path: Path) -> None:
    _write(tmp_path / "skills/a-diagnostics/SKILL.md", "x")
    _write(tmp_path / "skills/a-diagnostics/references/m.md", "x")
    _write(tmp_path / "skills/base/SKILL.md", DOC)
    _write(tmp_path / "ROUTER.md", "rule 1\nalways apply the a-diagnostics skill\nrule 2\n")
    arm = Arm(
        name="t",
        remove=("skills/*-diagnostics",),
        drop_sections={"skills/base/SKILL.md": ("## Drop Me",)},
        drop_lines=(LineRule(files=("ROUTER.md", "skills/**/*.md"), patterns=("-diagnostics",)),),
    )
    log = apply_arm(tmp_path, arm)

    assert not (tmp_path / "skills/a-diagnostics").exists()
    assert "Drop Me" not in (tmp_path / "skills/base/SKILL.md").read_text(encoding="utf-8")
    assert (tmp_path / "ROUTER.md").read_text(encoding="utf-8") == "rule 1\nrule 2\n"
    assert log == [
        "remove skills/a-diagnostics",
        "drop section skills/base/SKILL.md :: ## Drop Me",
        "drop 1 line(s) ROUTER.md",
    ]


def test_apply_arm_stops_when_the_spec_no_longer_matches(tmp_path: Path) -> None:
    _write(tmp_path / "a.md", "## Other\n")
    # skill の構成が変わって指定が当たらなくなったら、間引けていない状態で比べないよう止める
    with pytest.raises(ValueError, match="当たるパスが無い"):
        apply_arm(tmp_path, Arm(name="t", remove=("missing/*",)))
    with pytest.raises(ValueError, match="見出し"):
        apply_arm(tmp_path, Arm(name="t", drop_sections={"a.md": ("## Gone",)}))
    with pytest.raises(ValueError, match="が無い"):
        apply_arm(tmp_path, Arm(name="t", drop_sections={"b.md": ("## Gone",)}))


def _copy_repo_parts(dest: Path) -> None:
    """発火テストが sandbox に置くもの（cases.yaml の copy）を dest にコピーする。"""
    config, _ = load_suite(CASES_YAML, SKILLS_DIR)
    ignore = shutil.ignore_patterns(".DS_Store", "__pycache__")
    for rel in config.copy:
        src = REPO_ROOT / rel
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target, ignore=ignore)
        elif src.is_file():
            shutil.copy2(src, target)


def _markdown_under(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.md") if p.is_file())


def _text_lines_under(root: Path) -> list[tuple[Path, str]]:
    """root 以下のテキストファイルの (パス, 行)。uv.lock は依存の一覧なので見ない。"""
    lines: list[tuple[Path, str]] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name == "uv.lock":
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines += [(p, line) for line in text.splitlines()]
    return lines


def test_no_diagnostics_arm_leaves_no_trace_and_keeps_base_skills(tmp_path: Path) -> None:
    _copy_repo_parts(tmp_path)
    # 前提: 間引く前は、*-diagnostics を指す記述がある
    assert TRACE_RE.search((tmp_path / "CLAUDE.md").read_text(encoding="utf-8"))

    apply_arm(tmp_path, load_arms(CASES_YAML)["no-diagnostics"])

    assert list((tmp_path / ".claude/skills").glob("*-diagnostics")) == []
    # README は診断 skill の説明書きなので置かない（段落の残りから中身が読めてしまう）
    assert not (tmp_path / "README.md").exists()
    # Markdown だけでなく .gitignore（outputs/diagnostics/）なども見る
    leaks = [
        f"{p.relative_to(tmp_path)}: {line.strip()[:60]}"
        for p, line in _text_lines_under(tmp_path)
        if TRACE_RE.search(line) or LEAK_RE.search(line)
    ]
    assert leaks == [], "間引いた後も診断 skill の内容が読める記述が残っている"

    # 基本 skill とルーター文書の骨格は残る（外すのは診断の機能だけ）
    claude_md = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "## Hard Rules (Always Apply)" in claude_md
    assert "@.claude/skills/visualization/SKILL.md" in claude_md
    for skill in ("visualization", "dataframe-polars", "python-style", "analysis-reporting"):
        assert (tmp_path / ".claude/skills" / skill / "SKILL.md").is_file()
    reporting = (tmp_path / ".claude/skills/analysis-reporting/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "## Structure" in reporting and "## Required Context" in reporting


def test_bare_and_full_arms_on_the_real_repo(tmp_path: Path) -> None:
    arms = load_arms(CASES_YAML)
    bare = tmp_path / "bare"
    bare.mkdir()
    _copy_repo_parts(bare)
    apply_arm(bare, arms["bare"])
    assert _markdown_under(bare) == []

    full = tmp_path / "full"
    full.mkdir()
    _copy_repo_parts(full)
    before = {p: p.read_bytes() for p in _markdown_under(full)}
    assert apply_arm(full, arms[FULL_ARM]) == []
    assert {p: p.read_bytes() for p in _markdown_under(full)} == before


def test_build_sandbox_commits_the_ablated_tree(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _write(repo / ".claude/skills/a-diagnostics/SKILL.md", "x")
    _write(repo / ".claude/skills/base/SKILL.md", "base")
    _write(repo / "CLAUDE.md", "rule\nuse a-diagnostics\n")
    dest = tmp_path / "sb"
    arm = Arm(
        name="t",
        remove=(".claude/skills/*-diagnostics",),
        drop_lines=(LineRule(files=("CLAUDE.md",), patterns=("-diagnostics",)),),
    )
    ops = build_sandbox(repo, dest, EvalConfig(copy=[".claude", "CLAUDE.md"]), arm=arm)

    assert ops == ["remove .claude/skills/a-diagnostics", "drop 1 line(s) CLAUDE.md"]
    assert not (dest / ".claude/skills/a-diagnostics").exists()
    assert (dest / "CLAUDE.md").read_text(encoding="utf-8") == "rule\n"
    # 間引いた状態が最初のコミットなので、作業ツリーに差分が無い
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=dest, capture_output=True, text=True, check=True
    )
    assert status.stdout == ""
    # 元のリポジトリは変わらない
    assert (repo / ".claude/skills/a-diagnostics/SKILL.md").is_file()


# --------------------------------------------------------------------------------------
# 判定とレポート
# --------------------------------------------------------------------------------------
def _transcript(is_error: bool = False) -> Transcript:
    return Transcript.from_lines(
        [
            json.dumps({"type": "system", "subtype": "init", "skills": ["visualization"]}),
            json.dumps(
                {"type": "result", "subtype": "success", "result": "x", "is_error": is_error}
            ),
        ]
    )


def _case() -> Case:
    skill = "statistical-inference-diagnostics"
    return Case(
        id="c",
        kind="explicit",
        prompt="p",
        expect=Expectation(skills=(skill,), references=(f"{skill}/references/glm.md",)),
        forbid=Expectation(),
    )


def test_ablated_run_is_done_not_fail() -> None:
    # 同じ transcript でも、full なら「期待した skill を読んでいない」ので FAIL
    assert evaluate(_case(), _transcript(), [], SKILLS_DIR)["status"] == "FAIL"
    res = evaluate(_case(), _transcript(), [], SKILLS_DIR, check_firing=False)
    assert res["status"] == "DONE"
    assert res["missing_skills"] == [] and res["missing_references"] == []
    # 実行そのものが落ちたら、間引いた arm でも ERROR
    assert evaluate(_case(), _transcript(True), [], SKILLS_DIR, check_firing=False)["status"] == (
        "ERROR"
    )


def test_report_states_what_the_arm_removed() -> None:
    res = evaluate(_case(), _transcript(), [], SKILLS_DIR, check_firing=False)
    res["_dir"] = "c/r1"
    meta = {
        "run_id": "t",
        "arm": {"name": "no-x", "description": "x を外す", "operations": ["remove a", "remove b"]},
    }
    md = build_markdown(meta, [_case()], [res])
    assert "arm: no-x（x を外す）" in md and "remove a / remove b" in md
    assert "| c | explicit | ➖ 0/1 |" in md
    assert "remove a / remove b" in build_html(meta, [_case()], [res], SKILLS_DIR)
    # full の実行には arm の行を足さない
    assert "arm:" not in build_markdown({"run_id": "t"}, [_case()], [res])
