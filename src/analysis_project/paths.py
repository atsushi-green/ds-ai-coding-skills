"""リポジトリ内の標準ディレクトリを解決するパスユーティリティ。

絶対パスをコードに埋め込まずに済むよう、リポジトリルートからの相対位置でパスを組み立てる。
`data/` と `outputs/` の場所は、環境変数 `DATA_DIR` / `OUTPUT_DIR`（リポジトリ直下の `.env` に
書いてもよい）で差し替えられる。

Examples:
    >>> from analysis_project.paths import data_dir, ensure_parent_dir, outputs_dir
    >>> input_path = data_dir() / "raw" / "titanic" / "train.csv"
    >>> output_path = ensure_parent_dir(outputs_dir() / "tables" / "summary.csv")
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

# リポジトリルートの目印にするファイル
_ROOT_MARKER = "pyproject.toml"
# 書き込みを禁止する不変ディレクトリ（data_dir() からの相対位置）
_IMMUTABLE_SUBDIRS = ("raw", "external")


def _find_root(start: Path) -> Path | None:
    """start から親をたどり、目印のファイルがある最初のディレクトリを返す。"""
    for candidate in (start, *start.parents):
        if (candidate / _ROOT_MARKER).is_file():
            return candidate
    return None


def get_repo_root() -> Path:
    """リポジトリルート（`pyproject.toml` があるディレクトリ）を返す。

    まずこのファイルの場所から親をたどる（`uv sync` による editable インストールならここで
    見つかる）。見つからなければ、作業ディレクトリから親をたどる。

    Returns:
        リポジトリルートの絶対パス。

    Raises:
        FileNotFoundError: どちらからたどっても `pyproject.toml` が見つからない場合。
    """
    for start in (Path(__file__).resolve().parent, Path.cwd().resolve()):
        root = _find_root(start)
        if root is not None:
            return root
    raise FileNotFoundError(
        f"{_ROOT_MARKER} が見つからない。リポジトリの中で実行しているか確認すること。"
    )


def _configured_dir(env_name: str, default: str) -> Path:
    """環境変数 → `.env` → 既定値の順でディレクトリを決める。"""
    root = get_repo_root()
    # .env は値を読むだけで、os.environ には書き込まない
    value = os.environ.get(env_name) or dotenv_values(root / ".env").get(env_name) or default
    path = Path(value).expanduser()
    # 相対パスはリポジトリルートからの位置として扱う
    return path if path.is_absolute() else root / path


def data_dir() -> Path:
    """`data/` ディレクトリのパスを返す。

    Returns:
        `data/` の絶対パス。環境変数 `DATA_DIR` があればそちらを使う。
    """
    return _configured_dir("DATA_DIR", "data")


def outputs_dir() -> Path:
    """`outputs/` ディレクトリのパスを返す。

    Returns:
        `outputs/` の絶対パス。環境変数 `OUTPUT_DIR` があればそちらを使う。
    """
    return _configured_dir("OUTPUT_DIR", "outputs")


def ensure_parent_dir(path: str | Path) -> Path:
    """書き込み先の親ディレクトリを作成し、渡されたパスを返す。

    Args:
        path: これから書き込むファイルのパス。

    Returns:
        渡されたパス（`Path` にしたもの）。

    Raises:
        ValueError: 書き込み先が不変ディレクトリ（`data/raw/`・`data/external/`）の配下にある場合。
    """
    path = Path(path)
    resolved = path.resolve()
    # 生データ・外部データは不変なので、出力先に選ばれた時点で止める
    for sub in _IMMUTABLE_SUBDIRS:
        immutable = (data_dir() / sub).resolve()
        if resolved.is_relative_to(immutable):
            raise ValueError(f"不変ディレクトリ {immutable} の配下には書き込まない: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
