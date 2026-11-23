"""skill-ablation skill のスクリプト（ablate.py）のテスト。claude は起動しない。"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "skill-ablation"


def _load_module():
    spec = importlib.util.spec_from_file_location("ablate", SKILL_DIR / "scripts" / "ablate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # dataclass が自分のモジュールを引けるよう、実行前に登録する
    sys.modules["ablate"] = module
    spec.loader.exec_module(module)
    return module


ablate = _load_module()


def _write_config(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


MINIMAL = """
[run]
watch = ["my-skill"]
[run.stub]
"README.md" = "# p\\n"

[[case]]
id = "c1"
prompt = "do it"

[arm.none]
remove = [".claude/skills/my-skill"]
drop_lines = [{ files = ["CLAUDE.md"], patterns = ["my-skill"] }]

[arm.one-line]
extends = "none"
append = [{ file = "CLAUDE.md", after = "# Rules", line = "- always do X" }]

[[item]]
id = "fig-roc"
kind = "figure"
label = "ROC"
code = ['roc_curve\\(']

[[item]]
id = "val-vif"
label = "VIF"
report = ['\\bVIF\\b']
"""


def test_example_config_loads() -> None:
    """同梱の見本の設定が読め、full は常にあり、one-line は none の操作を引き継ぐ。"""
    cfg = ablate.load_config(SKILL_DIR / "assets" / "ablation.example.toml")
    assert set(cfg.arms) == {"none", "one-line", "full"}
    assert cfg.arms["full"].is_full
    assert cfg.arms["one-line"].remove == cfg.arms["none"].remove
    # [run.stub] は full を含むすべての条件に入る
    assert all(("README.md", "# project\n") in arm.stub for arm in cfg.arms.values())
    assert cfg.items


def test_config_rejects_unknown_keys(tmp_path: Path) -> None:
    """綴りを間違えたキーは黙って無視せず止める。"""
    path = _write_config(tmp_path / "a.toml", MINIMAL.replace("watch =", "wacth ="))
    with pytest.raises(ValueError, match="未知のキー"):
        ablate.load_config(path)


def test_full_arm_cannot_strip(tmp_path: Path) -> None:
    """full に間引く操作を書くと止める。"""
    body = MINIMAL + '\n[arm.full]\nremove = ["x"]\n'
    with pytest.raises(ValueError, match="full"):
        ablate.load_config(_write_config(tmp_path / "a.toml", body))


def test_apply_arm(tmp_path: Path) -> None:
    """remove・drop_sections・drop_lines・stub・append を適用し、足した行は消さない。"""
    (tmp_path / ".claude/skills/my-skill").mkdir(parents=True)
    (tmp_path / ".claude/skills/my-skill/SKILL.md").write_text("x", encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text("# Rules\n- use my-skill\n- keep\n", encoding="utf-8")
    (tmp_path / "other.md").write_text(
        "# A\n## Drop me\nsecret\n```\n# not a heading\n```\n## Keep\nok\n", encoding="utf-8"
    )
    arm = ablate.Arm(
        name="t",
        remove=(".claude/skills/my-skill",),
        drop_sections=(("other.md", "## Drop me"),),
        drop_lines=((("CLAUDE.md",), ("my-skill",)),),
        stub=(("README.md", "# p\n"),),
        append=(("CLAUDE.md", "- always mention my-skill", "# Rules"),),
    )
    log = ablate.apply_arm(tmp_path, arm)
    assert not (tmp_path / ".claude/skills/my-skill").exists()
    assert (tmp_path / "CLAUDE.md").read_text() == "# Rules\n- always mention my-skill\n- keep\n"
    assert (tmp_path / "other.md").read_text() == "# A\n## Keep\nok\n"
    assert (tmp_path / "README.md").read_text() == "# p\n"
    assert any(op.startswith("remove") for op in log)


def test_apply_arm_missing_target_stops(tmp_path: Path) -> None:
    """消す対象が無いときは、外したつもりで比べないよう止める。"""
    with pytest.raises(ValueError, match="当たるパスが無い"):
        ablate.apply_arm(tmp_path, ablate.Arm(name="t", remove=("nothing",)))


def test_negated_sentence_is_not_counted() -> None:
    """「確認していません」の文は、名前が出ていても数えない。"""
    item = ablate.Item(id="v", kind="value", label="VIF", report=(r"\bVIF\b",))
    assert ablate.item_evidence(item, "", ["VIF は確認していません"], False) is None
    assert ablate.item_evidence(item, "", ["VIF was not checked"], False) is None
    assert ablate.item_evidence(item, "", ["VIF の最大は 2.1"], False)
    lenient = ablate.Item(id="v", kind="value", label="VIF", report=(r"\bVIF\b",),
                          allow_negation=True)  # fmt: skip
    assert ablate.item_evidence(lenient, "", ["VIF は確認していません"], False)


def test_figure_needs_image() -> None:
    """図の項目は、描画コードがあっても画像ファイルが無ければ数えない。"""
    item = ablate.Item(id="f", kind="figure", label="ROC", code=(r"roc_curve\(",))
    assert ablate.item_evidence(item, "roc_curve(y, p)", [], False) is None
    assert ablate.item_evidence(item, "roc_curve(y, p)", [], True)


def test_leaked_skills_matches_namespaced_names() -> None:
    """名前空間つき（アカウントや plugin の skill）でも、監視語を含めば見つける。"""
    visible = ["code-review", "anthropic-skills:my-skill", "other"]
    assert ablate.leaked_skills(visible, ["my-skill"]) == ["anthropic-skills:my-skill"]
    assert ablate.leaked_skills(visible, []) == []


def test_claude_command_passes_skill_overrides() -> None:
    """同名 skill を消す指定は --settings で渡し、プロンプトは引数に入れない。"""
    cmd = ablate.claude_command(
        {"model": "m", "skill_overrides": {"ns:my-skill": "off"}, "allowed_tools": ["Skill"]}
    )
    assert cmd[:2] == ["claude", "-p"]
    i = cmd.index("--settings")
    assert json.loads(cmd[i + 1]) == {"skillOverrides": {"ns:my-skill": "off"}}
    assert cmd[cmd.index("--model") + 1] == "m"


def _fake_run(root: Path, arm: str, rep: int, *, error: bool = False, leak: bool = False,
              text: str = "", files: dict[str, str] | None = None) -> None:  # fmt: skip
    run_dir = root / arm / "c1" / f"r{rep}"
    for rel, content in (files or {}).items():
        target = run_dir / "files" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    run_dir.mkdir(parents=True, exist_ok=True)
    record = {"case": "c1", "arm": arm, "rep": rep, "is_error": error, "final_text": text,
              "leaked_skills": ["ns:my-skill"] if leak else []}  # fmt: skip
    (run_dir / "result.json").write_text(json.dumps(record), encoding="utf-8")


def test_score_counts_and_excludes_errors(tmp_path: Path) -> None:
    """条件ごとに数え、エラーの実行は数えずに名前を出し、見えた skill も知らせる。"""
    cfg = ablate.load_config(_write_config(tmp_path / "a.toml", MINIMAL))
    out = tmp_path / "runs"
    _fake_run(out, "full", 1, text="VIF は 1.2", files={"a.py": "roc_curve(y)", "roc.png": "x"})
    _fake_run(out, "full", 2, error=True)
    _fake_run(out, "none", 1, text="VIF は確認していません", files={"a.py": "roc_curve(y)"},
              leak=True)  # fmt: skip
    table, rows = ablate.score(cfg, [out])
    assert "| 図: ROC | 1/1 | 0/1 |" in table
    assert "| 値: VIF | 1/1 | 0/1 |" in table
    assert "full/c1/r2" in table
    assert "none/c1/r1" in table and "ns:my-skill" in table
    assert len(rows) == 4


def test_build_sandbox_copies_tracked_files_only(tmp_path: Path) -> None:
    """git 管理下のファイルだけを入れ、include・exclude・copy_untracked に従う。"""
    repo = tmp_path / "repo"
    (repo / ".claude/skills/my-skill").mkdir(parents=True)
    (repo / ".claude/skills/my-skill/SKILL.md").write_text("my-skill body", encoding="utf-8")
    (repo / "CLAUDE.md").write_text("# Rules\n- use my-skill\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs/notes.md").write_text("about my-skill", encoding="utf-8")
    (repo / "data.csv").write_text("a,b\n", encoding="utf-8")
    (repo / ".env").write_text("SECRET=1", encoding="utf-8")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "init", "-q"], cwd=repo, check=True)
    subprocess.run([*git, "add", ".claude", "CLAUDE.md", "docs"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "init"], cwd=repo, check=True)
    body = MINIMAL.replace("[run]\n", '[run]\nexclude = ["docs"]\ncopy_untracked = ["data.csv"]\n')
    cfg = ablate.load_config(_write_config(tmp_path / "a.toml", body))
    dest = tmp_path / "sandbox"
    ablate.build_sandbox(repo, dest, cfg, cfg.arms["none"])
    assert (dest / "data.csv").exists()
    assert not (dest / ".env").exists()  # 未追跡のファイルは入れない
    assert not (dest / "docs/notes.md").exists()  # exclude
    assert not (dest / ".claude/skills/my-skill").exists()  # 条件で外した
    assert (dest / ".git").is_dir()
    assert ablate.find_mentions(dest, ["my-skill"]) == []
