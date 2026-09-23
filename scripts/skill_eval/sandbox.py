"""ケースごとの隔離作業ディレクトリ（sandbox）の作成と、claude の起動・生成物の回収。

sandbox はリポジトリの外（既定は一時ディレクトリ）に作る。理由:

- リポジトリ配下に作ると、親ディレクトリの CLAUDE.md と `.claude/skills` も読まれて二重になる
- 並列実行したケース同士、および本物の `outputs/` と生成物が混ざらない
- `scripts/diagnostics_demo/` など「正解の実装」をコピーしないことで、skill の本文だけで
  図が出せるかを見られる

生データと題材データ（datasets.py）は読み取り専用（0o444）でコピーする。
sandbox 側で書き換えられても元データは無傷。
"""

from __future__ import annotations

import difflib
import os
import shutil
import stat
import subprocess
from pathlib import Path

from skill_eval.cases import EvalConfig

SNAPSHOT_SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".ruff_cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ipynb_checkpoints",
}
COLLECT_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".pdf",
    ".py", ".ipynb", ".stan", ".sql", ".md", ".csv", ".txt", ".json",
}  # fmt: skip
COLLECT_MAX_BYTES = 5 * 1024 * 1024
DATA_DIRS = ("data/raw", "data/external", "data/interim", "data/processed", "outputs")
# 入れ子の claude 起動を妨げる可能性のある環境変数（Claude Code の中から実行した場合）
STRIP_ENV = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT")

Snapshot = dict[str, tuple[int, int]]


def _copy_read_only(src: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    # sandbox 内でもデータは書き換え不可にしておく
    target.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)


def build_sandbox(
    repo_root: Path,
    dest: Path,
    config: EvalConfig,
    extra_data: dict[str, Path] | None = None,
) -> None:
    """リポジトリの必要部分だけをコピーした sandbox を作り、git と uv を初期化する。

    Args:
        repo_root: コピー元のリポジトリルート。
        dest: sandbox のディレクトリ（存在していてはいけない）。
        config: コピー対象とデータファイルの指定。
        extra_data: sandbox 内の相対パス → コピー元。ケースごとの題材データに使う。

    Raises:
        FileExistsError: dest が既に存在する場合。
        FileNotFoundError: 指定したデータファイルが存在しない場合。
    """
    dest.mkdir(parents=True, exist_ok=False)
    ignore = shutil.ignore_patterns(".DS_Store", "__pycache__")
    for rel in config.copy:
        src = repo_root / rel
        if not src.exists():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            # symlinks=False: .claude/skills がリンクでも実体をコピーする
            shutil.copytree(src, target, ignore=ignore)
        else:
            shutil.copy2(src, target)
    for d in DATA_DIRS:
        (dest / d).mkdir(parents=True, exist_ok=True)
        (dest / d / ".gitkeep").touch()
    for rel in config.data_files:
        src = repo_root / rel
        if not src.is_file():
            raise FileNotFoundError(f"データファイルが無い: {src}")
        _copy_read_only(src, dest / rel)
    for rel, src in (extra_data or {}).items():
        _copy_read_only(src, dest / rel)

    # 実運用と同じく git 管理下のリポジトリとして見せる
    git = ["git", "-c", "user.name=skill-eval", "-c", "user.email=skill-eval@localhost",
           "-c", "commit.gpgsign=false"]  # fmt: skip
    subprocess.run([*git, "init", "-q"], cwd=dest, check=True)
    subprocess.run([*git, "add", "-A"], cwd=dest, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "sandbox"], cwd=dest, check=True)
    if (dest / "pyproject.toml").is_file():
        subprocess.run(["uv", "sync", "--quiet"], cwd=dest, check=True)


def snapshot(root: Path) -> Snapshot:
    """root 以下のファイルの (mtime_ns, size) を記録する。キャッシュ類は除く。"""
    snap: Snapshot = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SNAPSHOT_SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                st = p.stat()
            except FileNotFoundError:
                continue
            snap[p.relative_to(root).as_posix()] = (st.st_mtime_ns, st.st_size)
    return snap


def changed_files(before: Snapshot, after: Snapshot) -> list[str]:
    """before から after で新規作成・更新されたファイル（削除は含めない）。"""
    return sorted(p for p, meta in after.items() if before.get(p) != meta)


def collect(sandbox: Path, files: list[str], out_dir: Path) -> list[str]:
    """生成物のうち図・コード・小さな表とテキストを out_dir にコピーする。

    Args:
        sandbox: sandbox のディレクトリ。
        files: sandbox からの相対パス。
        out_dir: コピー先（相対パス構造を保つ）。

    Returns:
        コピーしたファイルの相対パス。
    """
    copied: list[str] = []
    for rel in files:
        src = sandbox / rel
        if (
            src.suffix.lower() not in COLLECT_SUFFIXES
            or not src.is_file()
            or src.stat().st_size > COLLECT_MAX_BYTES
        ):
            continue
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(rel)
    return copied


def text_diff(before: str, after: str, name: str) -> str:
    """unified diff（pyproject.toml への uv add の記録用）。差分が無ければ空文字。"""
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{name}",
            tofile=f"b/{name}",
        )
    )


def claude_command(config: EvalConfig) -> list[str]:
    """claude の起動コマンド。プロンプトは引数ではなく標準入力で渡す。

    `--allowedTools` などは可変長引数なので、プロンプトを位置引数にすると取り込まれてしまう。
    """
    cmd = [
        config.claude_bin,
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--permission-mode",
        config.permission_mode,
    ]
    if config.model:
        cmd += ["--model", config.model]
    if config.effort:
        cmd += ["--effort", config.effort]
    if config.max_budget_usd is not None:
        cmd += ["--max-budget-usd", str(config.max_budget_usd)]
    if config.append_system_prompt.strip():
        cmd += ["--append-system-prompt", config.append_system_prompt.strip()]
    if config.allowed_tools:
        cmd += ["--allowedTools", *config.allowed_tools]
    if config.disallowed_tools:
        cmd += ["--disallowedTools", *config.disallowed_tools]
    cmd += config.extra_args
    return cmd


def run_claude(
    config: EvalConfig, prompt: str, cwd: Path, transcript_path: Path, stderr_path: Path
) -> bool:
    """claude を headless で実行し、stream-json を transcript_path に書く。

    Args:
        config: 起動条件。
        prompt: そのまま渡すプロンプト。
        cwd: sandbox のディレクトリ。
        transcript_path: stream-json の保存先（途中終了しても書けた分は残る）。
        stderr_path: 標準エラーの保存先。

    Returns:
        タイムアウトで打ち切ったら True。
    """
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENV}
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    with transcript_path.open("wb") as out, stderr_path.open("wb") as err:
        proc = subprocess.Popen(
            claude_command(config), cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=out, stderr=err
        )
        try:
            proc.communicate(input=prompt.encode("utf-8"), timeout=config.timeout_min * 60)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return True
    return False
