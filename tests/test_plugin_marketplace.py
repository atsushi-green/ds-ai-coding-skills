"""`.claude-plugin/marketplace.json`（診断 skill を plugin として配る定義）のテスト。

検証する契約:
- plugin が配るのは、実在する `*-diagnostics` のルーターすべてで、それ以外を含まない
  （ルーターを足したのに plugin に入れ忘れる、消した skill を指したままにする、を防ぐ）
- plugin の中身はリポジトリ直下を指し、skill のパスはそこからの相対パスになっている
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


def test_marketplace_has_the_required_fields() -> None:
    data = _load()
    assert ID_RE.match(data["name"])
    assert data["owner"]["name"]
    assert data["description"]
    names = [p["name"] for p in data["plugins"]]
    assert names == ["ds-diagnostics"]
    assert all(ID_RE.match(n) for n in names)


def test_plugin_ships_exactly_the_diagnostics_routers() -> None:
    plugin = _load()["plugins"][0]
    # リポジトリ直下を plugin の中身にして、skills で配るディレクトリを絞っている
    assert plugin["source"] == "./"
    shipped = plugin["skills"]
    assert all(s.startswith("./.claude/skills/") for s in shipped)
    assert len(shipped) == len(set(shipped))
    for rel in shipped:
        skill_dir = REPO_ROOT / rel
        assert (skill_dir / "SKILL.md").is_file(), f"{rel} に SKILL.md が無い"
        assert any((skill_dir / "references").glob("*.md")), f"{rel} に references が無い"
    routers = sorted(p.name for p in SKILLS_DIR.glob("*-diagnostics") if p.is_dir())
    assert sorted(Path(s).name for s in shipped) == routers


def test_shipped_skills_do_not_point_outside_their_own_directory() -> None:
    # plugin では skill だけがプロジェクトの外に置かれる。リポジトリのファイルを指していると、
    # 入れた先で存在しないパスを読みに行く
    outside = re.compile(r"\.claude/skills/|src/analysis_project|docs/agent|scripts/")
    hits = [
        f"{p.relative_to(REPO_ROOT)}: {line.strip()[:60]}"
        for rel in _load()["plugins"][0]["skills"]
        for p in sorted((REPO_ROOT / rel).rglob("*.md"))
        for line in p.read_text(encoding="utf-8").splitlines()
        if outside.search(line)
    ]
    assert hits == []
