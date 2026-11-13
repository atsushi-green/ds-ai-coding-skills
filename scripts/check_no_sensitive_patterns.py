"""テキストファイル中に秘密情報のパターンが含まれていないかチェックするスクリプト。

APIキー、トークン、秘密鍵などの一般的なパターンを検索する。

走査するのは git が扱うファイル（追跡中のファイルと、未追跡で .gitignore に当たらないファイル）
だけ。.gitignore で除外したファイル（outputs/ の生成物など）はコミットされないので見ない。
ここを見ると、手元では生成物の中の無関係な文字列に反応して必ず失敗し、CI とも結果が食い違う。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# 検出パターン（パターン名, 正規表現）
_API_KEY_RE = r"""(?:api[_-]?key|apikey)\s*[:=]\s*["']?[A-Za-z0-9_\-]{20,}"""
_SECRET_RE = r"""(?:secret|password|passwd|pwd)\s*[:=]\s*["']?[A-Za-z0-9_\-]{8,}"""
_TOKEN_RE = r"""(?:token|bearer)\s*[:=]\s*["']?[A-Za-z0-9_\-\.]{20,}"""
_ENV_RE = r"""^[A-Z_]+\s*=\s*["']?[A-Za-z0-9_\-]{16,}["']?\s*$"""

SENSITIVE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE)),
    ("Generic API Key", re.compile(_API_KEY_RE, re.IGNORECASE)),
    ("Generic Secret", re.compile(_SECRET_RE, re.IGNORECASE)),
    ("Generic Token", re.compile(_TOKEN_RE, re.IGNORECASE)),
    ("Private Key Header", re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\sKEY-----")),
    (".env file content", re.compile(_ENV_RE, re.MULTILINE)),
]

# スキャン対象の拡張子
TEXT_EXTENSIONS = {
    ".py",
    ".sql",
    ".md",
    ".txt",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
    ".cfg",
    ".ini",
    ".sh",
    ".bash",
    ".env",
}

# スキャン除外パターン
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".mypy_cache", ".ruff_cache"}
SKIP_FILES = {".env.example", "check_no_sensitive_patterns.py"}


def is_text_file(path: Path) -> bool:
    """テキストファイルかどうか判定する。

    Args:
        path: チェック対象のファイルパス。

    Returns:
        テキストファイルならTrue。
    """
    return path.suffix.lower() in TEXT_EXTENSIONS


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    """ファイルを走査して秘密情報パターンを検出する。

    Args:
        path: スキャン対象のファイルパス。

    Returns:
        (パターン名, 行番号, 行内容) のリスト。
    """
    findings: list[tuple[str, int, str]] = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return findings

    for line_num, line in enumerate(content.splitlines(), start=1):
        for pattern_name, pattern in SENSITIVE_PATTERNS:
            if pattern.search(line):
                findings.append((pattern_name, line_num, line.strip()[:100]))
    return findings


def list_candidate_files(repo_root: Path) -> list[Path]:
    """走査対象の候補（コミットされうるファイル）を返す。

    git が使えるときは、追跡中のファイルと、未追跡で .gitignore に当たらないファイルだけを返す。
    Git リポジトリの外や git が無い環境では、ディレクトリ全体を歩く。

    Args:
        repo_root: 走査を始めるディレクトリ。

    Returns:
        ファイルパスのリスト（repo_root からの相対位置でソート済み）。
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=repo_root,
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return sorted(p for p in repo_root.rglob("*") if p.is_file())
    # -z の出力は NUL 区切りで、日本語のファイル名もエスケープされない
    names = result.stdout.decode("utf-8", errors="replace").split("\0")
    return sorted(repo_root / name for name in names if name)


def find_sensitive(repo_root: Path) -> list[tuple[str, str, int, str]]:
    """repo_root 以下の走査対象から秘密情報パターンを探す。

    Args:
        repo_root: 走査を始めるディレクトリ。

    Returns:
        (repo_root からの相対パス, パターン名, 行番号, 行内容) のリスト。
    """
    all_findings: list[tuple[str, str, int, str]] = []
    for path in list_candidate_files(repo_root):
        rel = path.relative_to(repo_root)
        # ディレクトリのスキップ判定
        if any(skip in rel.parts for skip in SKIP_DIRS):
            continue
        # 追跡中でも作業ツリーから消えているファイルや、ディレクトリへのリンクは読まない
        if not path.is_file():
            continue
        if path.name in SKIP_FILES:
            continue
        if not is_text_file(path):
            continue

        for pattern_name, line_num, line_content in scan_file(path):
            all_findings.append((rel.as_posix(), pattern_name, line_num, line_content))
    return all_findings


def main() -> None:
    """メイン処理。"""
    all_findings = find_sensitive(Path("."))

    if all_findings:
        print("ERROR: Potential sensitive patterns detected:")
        for filepath, pattern_name, line_num, line_content in all_findings:
            print(f"  {filepath}:{line_num} [{pattern_name}] {line_content}")
        sys.exit(1)
    else:
        print("OK: No sensitive patterns detected.")


if __name__ == "__main__":
    main()
