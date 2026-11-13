"""CI で走らせる検査スクリプト（`scripts/check_no_*.py`）のテスト。

検証する契約:
- 秘密情報の検査は、コミットされうるファイルだけを見る（追跡中のファイルと、未追跡で
  .gitignore に当たらないファイル）。除外した生成物は見ないので、手元と CI で結果が食い違わない
- Git リポジトリの外では、ディレクトリ全体を見る
- raw データの検査は、保護ディレクトリの .gitkeep と README 以外を違反にする
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import check_no_raw_data_commit as raw_check
import check_no_sensitive_patterns as sensitive


def _fake_secret_line() -> str:
    # この文字列をソースにそのまま書くと、検査スクリプトがこのテストファイル自体に反応する
    return "api" + "_key = '" + "a1B2c3D4" * 3 + "'\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@localhost", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_scan_file_flags_secret_and_ignores_plain_text(tmp_path: Path) -> None:
    leaked = tmp_path / "leaked.py"
    leaked.write_text("x = 1\n" + _fake_secret_line(), encoding="utf-8")
    assert [(name, line) for name, line, _ in sensitive.scan_file(leaked)] == [
        ("Generic API Key", 2)
    ]
    clean = tmp_path / "clean.md"
    clean.write_text("APIキーは環境変数から読み込む。\n", encoding="utf-8")
    assert sensitive.scan_file(clean) == []


def test_only_files_git_can_commit_are_scanned(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("outputs/\n", encoding="utf-8")
    leak = _fake_secret_line()
    # 追跡中のファイル
    (tmp_path / "tracked.py").write_text(leak, encoding="utf-8")
    _git(tmp_path, "add", ".gitignore", "tracked.py")
    # 未追跡だが .gitignore に当たらない（git add すればコミットされる）ファイル
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "untracked.md").write_text(leak, encoding="utf-8")
    # .gitignore で除外した生成物
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs" / "ignored.md").write_text(leak, encoding="utf-8")
    # 対象外の拡張子
    (tmp_path / "image.png").write_text(leak, encoding="utf-8")

    found = {path for path, *_ in sensitive.find_sensitive(tmp_path)}
    assert found == {"tracked.py", "docs/untracked.md"}


def test_tracked_file_missing_from_worktree_is_skipped(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    (tmp_path / "gone.py").write_text(_fake_secret_line(), encoding="utf-8")
    _git(tmp_path, "add", "gone.py")
    (tmp_path / "gone.py").unlink()
    assert sensitive.find_sensitive(tmp_path) == []


def test_outside_git_repo_walks_the_whole_tree(tmp_path: Path, monkeypatch) -> None:
    def no_git(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(sensitive.subprocess, "run", no_git)
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "config.yaml").write_text(_fake_secret_line(), encoding="utf-8")
    # git が無くても、キャッシュ類のディレクトリは見ない
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "lib.py").write_text(_fake_secret_line(), encoding="utf-8")
    assert [path for path, *_ in sensitive.find_sensitive(tmp_path)] == ["a/config.yaml"]


def test_raw_data_check_allows_only_gitkeep_and_readme() -> None:
    tracked = [
        "data/raw/.gitkeep",
        "data/raw/README.md",
        "data/raw/train.csv",
        "data/external/zip/codes.parquet",
        "data/processed/features.parquet",
        "src/analysis_project/paths.py",
    ]
    assert raw_check.check_violations(tracked) == [
        "data/raw/train.csv",
        "data/external/zip/codes.parquet",
    ]
