"""*-diagnostics skill の発火テストを実行し、一覧レポートを作る。

各ケースのプロンプトを、リポジトリ外に作った sandbox で headless の Claude Code（`claude -p`）に
そのまま渡す。stream-json の transcript から読まれた skill・references を取り出し、
sandbox で新しく作られた図を回収して `outputs/skill_eval/<run_id>/` に一覧を書き出す。

使い方（リポジトリ直下で）::

    uv run python scripts/run_skill_eval.py list
    uv run python scripts/run_skill_eval.py run --dry-run
    uv run python scripts/run_skill_eval.py run --core          # 基本セット（core タグ）だけ
    uv run python scripts/run_skill_eval.py run --only glm-explicit,cluster-kmeans --jobs 2
    uv run python scripts/run_skill_eval.py run --kind negative --repeat 3
    uv run python scripts/run_skill_eval.py report outputs/skill_eval/<run_id>
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from skill_eval.cases import Case, EvalConfig, load_suite
from skill_eval.datasets import GENERATORS
from skill_eval.evaluate import evaluate, read_reports
from skill_eval.report import write_report
from skill_eval.sandbox import (
    build_sandbox,
    changed_files,
    claude_command,
    collect,
    run_claude,
    snapshot,
    text_diff,
)
from skill_eval.transcript import Transcript

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
DEFAULT_CASES = Path(__file__).resolve().parent / "skill_eval" / "cases.yaml"
OUTPUT_ROOT = REPO_ROOT / "outputs" / "skill_eval"


def _git_head() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", ".claude/skills"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    # skill が未コミットのまま試すことが多いので、その旨を残す
    return out.stdout.strip() + ("+dirty-skills" if dirty.stdout.strip() else "")


def _skills_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(SKILLS_DIR.rglob("*")):
        if p.is_file() and p.name != ".DS_Store":
            h.update(p.relative_to(SKILLS_DIR).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def _claude_version(config: EvalConfig) -> str:
    try:
        out = subprocess.run([config.claude_bin, "--version"], capture_output=True, text=True)
    except FileNotFoundError:
        return "not found"
    return out.stdout.strip()


def select_cases(cases: list[Case], args: argparse.Namespace) -> list[Case]:
    """--core / --only / --kind / --tag / --include-slow でケースを絞る。"""
    selected = cases
    if args.core:
        selected = [c for c in selected if "core" in c.tags]
    if args.only:
        ids = [s.strip() for s in args.only.split(",") if s.strip()]
        unknown = set(ids) - {c.id for c in cases}
        if unknown:
            raise SystemExit(f"未知のケース ID: {sorted(unknown)}")
        selected = [c for c in selected if c.id in ids]
    if args.kind:
        selected = [c for c in selected if c.kind in args.kind]
    if args.tag:
        selected = [c for c in selected if set(args.tag) & set(c.tags)]
    if not args.include_slow and not args.only:
        # 明示指定が無い限り重いケース（CmdStan のビルドなど）は除く
        selected = [c for c in selected if "slow" not in c.tags]
    return selected


def dataset_path(sandbox_root: Path, name: str) -> Path:
    """題材データのキャッシュ（1 回の実行で 1 度だけ生成する）の置き場所。"""
    return sandbox_root / "_datasets" / f"{name}.csv"


def prepare_datasets(cases: list[Case], sandbox_root: Path) -> None:
    """選ばれたケースが使う題材データを生成する。

    追加パッケージ（lifelines など）は `uv run --with` で一時的に重ね、pyproject.toml は変えない。
    """
    for name in sorted({d for c in cases for d in c.datasets}):
        out = dataset_path(sandbox_root, name)
        if out.is_file():
            continue
        extra = [arg for pkg in GENERATORS[name][0] for arg in ("--with", pkg)]
        script = Path(__file__).resolve().parent / "skill_eval" / "datasets.py"
        subprocess.run(
            ["uv", "run", *extra, "python", str(script), name, str(out)],
            cwd=REPO_ROOT,
            check=True,
        )
        print(f"題材データ: {name} → {out}")


def run_one(
    case: Case,
    rep: int,
    config: EvalConfig,
    run_dir: Path,
    sandbox_root: Path,
    keep_sandbox: bool,
) -> dict:
    """1 ケース × 1 反復を実行し、result.json を書いて評価結果を返す。"""
    out_dir = run_dir / case.id / f"r{rep}"
    out_dir.mkdir(parents=True, exist_ok=True)
    sandbox = sandbox_root / f"{case.id}__r{rep}"
    extra_data = {f"data/raw/{d}.csv": dataset_path(sandbox_root, d) for d in case.datasets}
    build_sandbox(REPO_ROOT, sandbox, config, extra_data)
    pyproject_before = (sandbox / "pyproject.toml").read_text(encoding="utf-8")
    before = snapshot(sandbox)

    (out_dir / "prompt.txt").write_text(case.prompt + "\n", encoding="utf-8")
    timed_out = run_claude(
        config, case.prompt, sandbox, out_dir / "transcript.jsonl", out_dir / "stderr.log"
    )

    changed = changed_files(before, snapshot(sandbox))
    collect(sandbox, changed, out_dir / "files")
    diff = text_diff(
        pyproject_before, (sandbox / "pyproject.toml").read_text(encoding="utf-8"), "pyproject.toml"
    )
    if diff:
        (out_dir / "pyproject.diff").write_text(diff, encoding="utf-8")

    tx = Transcript.from_file(out_dir / "transcript.jsonl")
    result = evaluate(
        case,
        tx,
        changed,
        SKILLS_DIR,
        timed_out=timed_out,
        report_texts=read_reports(out_dir / "files", changed),
    )
    result["sandbox"] = str(sandbox) if keep_sandbox else None
    (out_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not keep_sandbox:
        shutil.rmtree(sandbox, ignore_errors=True)
    return result


def cmd_list(args: argparse.Namespace) -> None:
    """ケース一覧を表示する。"""
    _, cases = load_suite(args.cases, SKILLS_DIR)
    for c in cases:
        refs = ", ".join(r.rsplit("/", 1)[-1] for r in c.expect.references) or "—"
        tags = f" [{', '.join(c.tags)}]" if c.tags else ""
        data = f" data: {', '.join(c.datasets)}" if c.datasets else ""
        print(f"{c.id:28s} {c.kind:9s} 期待: {refs}{tags}{data}")
        print(f"    {' '.join(c.prompt.split())[:90]}")


def cmd_run(args: argparse.Namespace) -> None:
    """ケースを実行してレポートを書く。"""
    config, cases = load_suite(args.cases, SKILLS_DIR)
    # コマンドラインの指定で cases.yaml の設定を上書きする
    overrides = {
        "model": args.model,
        "effort": args.effort,
        "max_budget_usd": args.max_budget_usd,
        "timeout_min": args.timeout_min,
    }
    config = dataclasses.replace(config, **{k: v for k, v in overrides.items() if v is not None})
    selected = select_cases(cases, args)
    if not selected:
        raise SystemExit("実行対象のケースが無い")

    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = OUTPUT_ROOT / run_id
    sandbox_root = (args.sandbox_root or Path(tempfile.gettempdir()) / "skill-eval") / run_id
    jobs = [(c, rep) for c in selected for rep in range(1, args.repeat + 1)]

    print(f"run_id: {run_id}  ケース {len(selected)} 件 × {args.repeat} 回 = {len(jobs)} 実行")
    print(f"出力: {run_dir}")
    print(f"sandbox: {sandbox_root}")
    print("コマンド（プロンプトは標準入力で渡す）:")
    print("  " + shlex.join(claude_command(config)))
    if args.dry_run:
        for c, rep in jobs:
            print(f"  - {c.id} r{rep}: {' '.join(c.prompt.split())[:80]}")
        return

    run_dir.mkdir(parents=True, exist_ok=False)
    # 実行時点の skill とケース定義を残し、後から skill を直してもレポートを再現できるようにする
    shutil.copytree(
        SKILLS_DIR, run_dir / "skills_snapshot", ignore=shutil.ignore_patterns(".DS_Store")
    )
    shutil.copy2(args.cases, run_dir / "cases.yaml")
    meta = {
        "run_id": run_id,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "git_head": _git_head(),
        "skills_hash": _skills_hash(),
        "claude_version": _claude_version(config),
        "config": dataclasses.asdict(config),
        "command": claude_command(config),
        "jobs": [f"{c.id}/r{rep}" for c, rep in jobs],
    }
    (run_dir / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")

    prepare_datasets(selected, sandbox_root)
    snapshot_dir = run_dir / "skills_snapshot"
    lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(run_one, c, rep, config, run_dir, sandbox_root, args.keep_sandbox): (c, rep)
            for c, rep in jobs
        }
        for fut in as_completed(futures):
            c, rep = futures[fut]
            try:
                res = fut.result()
                print(f"[{res['status']}] {c.id} r{rep}  読んだ references: "
                      f"{[r.rsplit('/', 1)[-1] for r in res['read_references']]}  "
                      f"図 {len(res['images'])} 枚")  # fmt: skip
            except Exception as exc:  # noqa: BLE001 — 1 ケースの失敗で全体を止めない
                print(f"[CRASH] {c.id} r{rep}: {exc!r}", file=sys.stderr)
            with lock:
                # 途中経過も見られるよう、1 件終わるごとにレポートを更新する
                write_report(run_dir, selected, snapshot_dir)
    print(f"レポート: {run_dir / 'index.html'}")
    print(f"          {run_dir / 'summary.md'}")


def reevaluate(run_dir: Path, cases: list[Case], skills_dir: Path) -> int:
    """保存済みの transcript と生成物から result.json を判定し直す（API は呼ばない）。

    判定ロジックを直したあと、実行し直さずにレポートへ反映するために使う。
    sandbox は残っていないので、生成物の一覧は result.json に記録した changed_files を使う。

    Returns:
        判定し直した result.json の数。
    """
    case_map = {c.id: c for c in cases}
    n = 0
    for path in sorted(run_dir.glob("*/r*/result.json")):
        old = json.loads(path.read_text(encoding="utf-8"))
        case = case_map.get(old["case_id"])
        if case is None:
            continue
        out_dir = path.parent
        changed = old["changed_files"]
        new = evaluate(
            case,
            Transcript.from_file(out_dir / "transcript.jsonl"),
            changed,
            skills_dir,
            timed_out=old["timed_out"],
            report_texts=read_reports(out_dir / "files", changed),
        )
        new["sandbox"] = old.get("sandbox")
        path.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
        n += 1
    return n


def cmd_report(args: argparse.Namespace) -> None:
    """既存の実行結果を判定し直し、レポートを作り直す。"""
    run_dir: Path = args.run_dir
    snapshot_dir = run_dir / "skills_snapshot"
    skills_dir = snapshot_dir if snapshot_dir.is_dir() else SKILLS_DIR
    cases_path = run_dir / "cases.yaml" if (run_dir / "cases.yaml").is_file() else args.cases
    _, cases = load_suite(cases_path, skills_dir)
    if not args.no_reevaluate:
        print(f"判定し直した結果: {reevaluate(run_dir, cases, skills_dir)} 件")
    write_report(run_dir, cases, skills_dir)
    print(f"レポート: {run_dir / 'index.html'}")


def main(argv: list[str] | None = None) -> None:
    """コマンドラインの入口。"""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="ケース定義の YAML")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="ケース一覧を表示").set_defaults(func=cmd_list)

    p_run = sub.add_parser("run", help="ケースを実行してレポートを書く")
    p_run.add_argument(
        "--core", action="store_true", help="基本セット（core タグの付いたケース）だけを実行"
    )
    p_run.add_argument("--only", help="カンマ区切りのケース ID（slow タグも実行する）")
    p_run.add_argument("--kind", nargs="+", choices=["explicit", "implicit", "scope", "negative"])
    p_run.add_argument("--tag", nargs="+", help="いずれかのタグを持つケースだけ")
    p_run.add_argument("--include-slow", action="store_true", help="slow タグのケースも実行")
    p_run.add_argument("--repeat", type=int, default=1, help="各ケースの反復回数（発火率を見る）")
    p_run.add_argument("--jobs", type=int, default=2, help="並列数")
    p_run.add_argument("--model", help="cases.yaml の model を上書き")
    p_run.add_argument("--effort", help="cases.yaml の effort を上書き")
    p_run.add_argument("--max-budget-usd", type=float, help="1 実行あたりの費用上限")
    p_run.add_argument("--timeout-min", type=float, help="1 実行あたりのタイムアウト（分）")
    p_run.add_argument("--run-id", help="出力ディレクトリ名（既定は時刻）")
    p_run.add_argument(
        "--sandbox-root", type=Path, help="sandbox を作る場所（既定は一時ディレクトリ）"
    )
    p_run.add_argument("--keep-sandbox", action="store_true", help="終了後も sandbox を残す")
    p_run.add_argument("--dry-run", action="store_true", help="実行計画とコマンドを表示するだけ")
    p_run.set_defaults(func=cmd_run)

    p_rep = sub.add_parser("report", help="既存の実行結果を判定し直してレポートを作り直す")
    p_rep.add_argument("run_dir", type=Path)
    p_rep.add_argument(
        "--no-reevaluate", action="store_true", help="result.json を判定し直さずに表だけ作る"
    )
    p_rep.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
