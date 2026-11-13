"""`src/analysis_project/paths.py`（パスユーティリティ）のテスト。

検証する契約:
- リポジトリルートを `pyproject.toml` の位置から見つけ、`data/`・`outputs/` をその直下に解決する
- 環境変数 `DATA_DIR` / `OUTPUT_DIR`（`.env` に書いた値も含む）で差し替えられ、環境変数が優先される
- `ensure_parent_dir` は親ディレクトリを作り、不変ディレクトリ（raw・external）への書き込みを止める
- path-and-io skill が「ある」と書いている関数が実在する
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from analysis_project import paths

REPO_ROOT = Path(__file__).resolve().parents[1]
PATH_SKILL = REPO_ROOT / ".claude" / "skills" / "path-and-io" / "SKILL.md"


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`get_repo_root()` が tmp_path を返すようにし、環境変数の差し替えを外す。"""
    monkeypatch.setattr(paths, "get_repo_root", lambda: tmp_path)
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    return tmp_path


def test_repo_root_is_the_directory_with_pyproject() -> None:
    assert paths.get_repo_root() == REPO_ROOT
    assert (paths.get_repo_root() / "pyproject.toml").is_file()


def test_find_root_walks_up_and_gives_up_without_marker(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert paths._find_root(nested) == tmp_path
    # 目印が無い場所から探しても、実在しないルートを返さない
    assert paths._find_root(Path(tmp_path.anchor)) is None


def test_default_dirs_are_under_repo_root(fake_repo: Path) -> None:
    assert paths.data_dir() == fake_repo / "data"
    assert paths.outputs_dir() == fake_repo / "outputs"


def test_env_var_overrides_relative_and_absolute(
    fake_repo: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 相対パスはリポジトリルートからの位置になる
    monkeypatch.setenv("DATA_DIR", "storage/data")
    assert paths.data_dir() == fake_repo / "storage" / "data"
    # 絶対パスはそのまま使う
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    monkeypatch.setenv("OUTPUT_DIR", str(elsewhere))
    assert paths.outputs_dir() == elsewhere


def test_dotenv_file_is_used_and_env_var_wins(
    fake_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (fake_repo / ".env").write_text("DATA_DIR=from_dotenv\n", encoding="utf-8")
    assert paths.data_dir() == fake_repo / "from_dotenv"
    monkeypatch.setenv("DATA_DIR", "from_environ")
    assert paths.data_dir() == fake_repo / "from_environ"


def test_ensure_parent_dir_creates_parents_and_returns_path(fake_repo: Path) -> None:
    target = paths.outputs_dir() / "tables" / "nested" / "summary.csv"
    assert not target.parent.exists()
    assert paths.ensure_parent_dir(target) == target
    assert target.parent.is_dir()
    # 作るのは親ディレクトリだけで、ファイル自体は作らない
    assert not target.exists()
    # 文字列で渡しても Path で返る
    assert paths.ensure_parent_dir(str(target)) == target


@pytest.mark.parametrize("sub", ["raw", "external"])
def test_ensure_parent_dir_refuses_immutable_dirs(fake_repo: Path, sub: str) -> None:
    target = paths.data_dir() / sub / "titanic" / "train.csv"
    with pytest.raises(ValueError, match="不変ディレクトリ"):
        paths.ensure_parent_dir(target)
    assert not target.parent.exists()
    # interim・processed は書き込める
    assert paths.ensure_parent_dir(paths.data_dir() / "processed" / "x.parquet").parent.is_dir()


def test_functions_named_in_the_skill_exist() -> None:
    # skill が案内している関数が無いと、エージェントは毎回 paths.py を自作することになる
    text = PATH_SKILL.read_text(encoding="utf-8")
    section = text.split("## Available Utilities", 1)[1].split("\n## ", 1)[0]
    names = re.findall(r"^- `(\w+)\(", section, flags=re.MULTILINE)
    assert names, "skill の Available Utilities から関数名を読み取れない"
    missing = [n for n in names if not callable(getattr(paths, n, None))]
    assert missing == [], f"skill に書いてあるのに paths.py に無い: {missing}"
