"""rawデータディレクトリ配下のファイルがコミットされていないかチェックするスクリプト。

data/raw/ および data/external/ 配下に .gitkeep や README 以外のファイルがある場合、
エラーとして報告する。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# 許可するファイル名パターン
ALLOWED_NAMES = {".gitkeep", "README.md", "README"}

# チェック対象ディレクトリ
PROTECTED_DIRS = ["data/raw", "data/external"]


def get_tracked_files() -> list[str]:
    """Gitで追跡されているファイル一覧を取得する。

    Returns:
        追跡中のファイルパスのリスト。
    """
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip().splitlines()


def check_violations(tracked_files: list[str]) -> list[str]:
    """保護ディレクトリ内の不正ファイルを検出する。

    Args:
        tracked_files: Gitで追跡されているファイルパスのリスト。

    Returns:
        違反ファイルパスのリスト。
    """
    violations = []
    for filepath in tracked_files:
        for protected_dir in PROTECTED_DIRS:
            if filepath.startswith(f"{protected_dir}/"):
                name = Path(filepath).name
                if name not in ALLOWED_NAMES:
                    violations.append(filepath)
    return violations


def main() -> None:
    """メイン処理。"""
    try:
        tracked_files = get_tracked_files()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Gitリポジトリ外や git が見つからない場合はスキップ
        print("WARNING: Could not list git-tracked files. Skipping raw data check.")
        return

    violations = check_violations(tracked_files)
    if violations:
        print(
            "ERROR: The following files under protected data directories should not be committed:"
        )
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    else:
        print("OK: No raw/external data files committed.")


if __name__ == "__main__":
    main()
