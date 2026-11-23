"""`.claude-plugin/marketplace.json`（skill を Claude Code の plugin として配る定義）のテスト。

検証する契約:
- 配る plugin は `ds-diagnostics`（診断 skill）と `skill-ablation`（skill の要否を確かめる実験）
  の 2 つ
- `ds-diagnostics` が配るのは、実在する `*-diagnostics` のルーターすべてで、それ以外を含まない
  （ルーターを足したのに plugin に入れ忘れる、消した skill を指したままにする、を防ぐ）
- plugin の中身はリポジトリ直下を指し、skill のパスはそこからの相対パスになっている
- plugin の skill は、リポジトリ内のパスで自分のファイルを指さない（入れた先には無い）
- README の導入コマンドが、定義の plugin 名と同じ名前を使っている
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
# plugin 名と marketplace 名に使える文字（英数字で始まり、英数字・`.`・`_`・`-`）
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _load() -> dict:
    return json.loads(MARKETPLACE.read_text(encoding="utf-8"))


def _plugin(name: str) -> dict:
    return next(p for p in _load()["plugins"] if p["name"] == name)


def test_marketplace_has_the_required_fields() -> None:
    data = _load()
    assert ID_RE.match(data["name"])
    assert data["owner"]["name"]
    assert data["description"]
    names = [p["name"] for p in data["plugins"]]
    assert names == ["ds-diagnostics", "skill-ablation"]
    assert all(ID_RE.match(n) for n in names)
    for plugin in data["plugins"]:
        # リポジトリ直下を plugin の中身にして、skills で配るディレクトリを絞っている
        assert plugin["source"] == "./"
        assert plugin["description"]
        shipped = plugin["skills"]
        assert all(s.startswith("./.claude/skills/") for s in shipped)
        assert len(shipped) == len(set(shipped))
        for rel in shipped:
            assert (REPO_ROOT / rel / "SKILL.md").is_file(), f"{rel} に SKILL.md が無い"


def test_plugin_ships_exactly_the_diagnostics_routers() -> None:
    shipped = _plugin("ds-diagnostics")["skills"]
    for rel in shipped:
        assert any((REPO_ROOT / rel / "references").glob("*.md")), f"{rel} に references が無い"
    routers = sorted(p.name for p in SKILLS_DIR.glob("*-diagnostics") if p.is_dir())
    assert sorted(Path(s).name for s in shipped) == routers


def test_shipped_skills_do_not_point_outside_their_own_directory() -> None:
    # plugin では skill だけがプロジェクトの外に置かれる。リポジトリのファイルを指していると、
    # 入れた先で存在しないパスを読みに行く
    outside = re.compile(r"\.claude/skills/|src/analysis_project|docs/agent|scripts/")
    hits = [
        f"{p.relative_to(REPO_ROOT)}: {line.strip()[:60]}"
        for rel in _plugin("ds-diagnostics")["skills"]
        for p in sorted((REPO_ROOT / rel).rglob("*.md"))
        for line in p.read_text(encoding="utf-8").splitlines()
        if outside.search(line)
    ]
    assert hits == []


def test_skill_ablation_runs_its_scripts_from_its_own_directory() -> None:
    # plugin で入れると skill はプロジェクトの外に置かれるので、同梱のスクリプトと見本は
    # `${CLAUDE_SKILL_DIR}` から指す（リポジトリ内のパスで書くと、入れた先に無い）
    assert _plugin("skill-ablation")["skills"] == ["./.claude/skills/skill-ablation"]
    text = (SKILLS_DIR / "skill-ablation" / "SKILL.md").read_text(encoding="utf-8")
    assert ".claude/skills/skill-ablation/" not in text
    for rel in ("scripts/ablate.py", "assets/ablation.example.toml"):
        assert f"${{CLAUDE_SKILL_DIR}}/{rel}" in text
        assert (SKILLS_DIR / "skill-ablation" / rel).is_file()


def test_readme_install_commands_match_the_manifest() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for plugin in _load()["plugins"]:
        assert f"claude plugin install {plugin['name']} --marketplace " in readme
    # skills CLI で名前を指定する例は、plugin と同じ 5 つを挙げている
    block = readme[readme.index("npx skills add") :]
    named = set(re.findall(r"--skill ([a-z-]+)", block))
    assert named == {Path(s).name for s in _plugin("ds-diagnostics")["skills"]}
