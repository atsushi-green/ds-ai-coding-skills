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
    uv run python scripts/run_skill_eval.py run --only glm-explicit --arm no-diagnostics
    uv run python scripts/run_skill_eval.py run --only glm-explicit --run-id abl --resume
    uv run python scripts/run_skill_eval.py quota
    uv run python scripts/run_skill_eval.py report outputs/skill_eval/<run_id>
    uv run python scripts/run_skill_eval.py compare outputs/skill_eval/<a> outputs/skill_eval/<b>
    uv run python scripts/run_skill_eval.py score outputs/skill_eval/<a> outputs/skill_eval/<b>
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
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from skill_eval.arms import FULL_ARM, Arm
from skill_eval.cases import Case, EvalConfig, load_arms, load_suite
from skill_eval.compare import write_compare
from skill_eval.datasets import GENERATORS
from skill_eval.evaluate import evaluate, read_reports
from skill_eval.isolation import outside_copies, plan_overrides, project_skill_names
from skill_eval.quota import format_quota, probe_session, stop_reason
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
from skill_eval.score import write_scores
from skill_eval.transcript import Transcript

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
DEFAULT_CASES = Path(__file__).resolve().parent / "skill_eval" / "cases.yaml"
DEFAULT_CHECKLISTS = Path(__file__).resolve().parent / "skill_eval" / "checklists.yaml"
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
    arm: Arm,
) -> dict:
    """1 ケース × 1 反復を実行し、result.json を書いて評価結果を返す。"""
    out_dir = run_dir / case.id / f"r{rep}"
    out_dir.mkdir(parents=True, exist_ok=True)
    sandbox = sandbox_root / f"{case.id}__r{rep}"
    # 準備の途中で落ちた実行（uv sync の失敗など）の sandbox が残っていると作り直せないので消す
    shutil.rmtree(sandbox, ignore_errors=True)
    extra_data = {f"data/raw/{d}.csv": dataset_path(sandbox_root, d) for d in case.datasets}
    arm_ops = build_sandbox(REPO_ROOT, sandbox, config, extra_data, arm)
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
        check_firing=arm.is_full,
    )
    result["arm"] = arm.name
    result["arm_ops"] = arm_ops
    result["sandbox"] = str(sandbox) if keep_sandbox else None
    (out_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if not keep_sandbox:
        shutil.rmtree(sandbox, ignore_errors=True)
    return result


Job = tuple[Case, int]


def execute_jobs(
    jobs: list[Job],
    run: Callable[[Case, int], dict],
    on_done: Callable[[Case, int, dict | Exception], None],
    workers: int,
    should_stop: Callable[[dict], str | None],
) -> tuple[list[Job], str | None]:
    """実行を並列に進め、続けても無駄になると分かったら残りを始めずに返す。

    Args:
        jobs: （ケース, 反復番号）の一覧。
        run: 1 件を実行して result を返す関数。
        on_done: 1 件終わるたびに呼ぶ関数。失敗したときは例外を渡す。
        workers: 並列数。
        should_stop: 終わった実行の result を見て、残りを始めない理由を返す関数（続けるなら None）。
            利用枠が上限に近い、プロジェクトの外の skill が見えていた、などに使う。

    Returns:
        始めなかった実行（jobs の順）と、止めた理由。最後まで実行したら空のリストと None。
    """
    stop = threading.Event()
    reasons: list[str] = []

    def guarded(case: Case, rep: int) -> dict | None:
        if stop.is_set():
            return None
        result = run(case, rep)
        reason = should_stop(result)
        if reason:
            # 結果を受け取る側で止めると、その前に次の 1 件が始まってしまう
            reasons.append(reason)
            stop.set()
        return result

    skipped: set[tuple[str, int]] = set()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(guarded, c, rep): (c, rep) for c, rep in jobs}
        for fut in as_completed(futures):
            c, rep = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:  # noqa: BLE001 — 1 ケースの失敗で全体を止めない
                on_done(c, rep, exc)
                continue
            if result is None:
                skipped.add((c.id, rep))
            else:
                on_done(c, rep, result)
    not_started = [(c, rep) for c, rep in jobs if (c.id, rep) in skipped]
    return not_started, (reasons[0] if reasons else None)


def pending_jobs(run_dir: Path, jobs: list[Job]) -> list[Job]:
    """まだ結果の無い実行と、ERROR で終わった実行（利用枠で打ち切られた分など）を返す。"""
    pending = []
    for case, rep in jobs:
        path = run_dir / case.id / f"r{rep}" / "result.json"
        if not path.is_file() or json.loads(path.read_text("utf-8")).get("status") == "ERROR":
            pending.append((case, rep))
    return pending


def set_aside(run_dir: Path, case_id: str, rep: int) -> Path | None:
    """やり直す実行の出力を `_interrupted/` に退避する（消さずに残す）。

    Returns:
        退避先。出力がまだ無ければ None。
    """
    out_dir = run_dir / case_id / f"r{rep}"
    if not out_dir.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # 結果の一覧は `*/r*/result.json` で集めるので、退避先の名前は r で始めない
    dest = run_dir / "_interrupted" / f"{stamp}__{case_id}__r{rep}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(out_dir), dest)
    return dest


def check_same_condition(meta: dict, arm: Arm, config: EvalConfig, skills_hash: str) -> None:
    """続きから実行するとき、前回と条件が同じかを確かめる。

    Raises:
        SystemExit: arm・モデル・effort・skill の内容のどれかが前回と違う場合。
    """
    before = {
        "arm": meta.get("arm", {}).get("name"),
        "model": meta.get("config", {}).get("model"),
        "effort": meta.get("config", {}).get("effort"),
        "skills": meta.get("skills_hash"),
    }
    now = {"arm": arm.name, "model": config.model, "effort": config.effort, "skills": skills_hash}
    diff = [f"{k}: 前回 {before[k]} / 今回 {now[k]}" for k in now if before[k] != now[k]]
    if diff:
        raise SystemExit("前回と条件が違うので続きから実行できない（" + "、".join(diff) + "）")


def preflight(config: EvalConfig, max_utilization: float) -> EvalConfig:
    """実行を始める前に、利用枠の余裕と、プロジェクトの外にある同名の skill を確かめる。

    空のディレクトリで短い問い合わせを 1 回送る。プロジェクトの外（アカウントやユーザーレベル）に
    リポジトリの skill と同じ名前のものが見えていたら、見えなくする指定を config に足し、
    見えなくなったことをもう 1 回の問い合わせで確かめる。

    Args:
        config: 起動条件。
        max_utilization: 利用枠の使用率がこの値以上なら始めない（0 以下なら使用率では止めない）。

    Returns:
        同名の skill を見えなくする指定（`skill_overrides`）を足した config。

    Raises:
        SystemExit: 利用枠が目安以上、または同名の skill を見えなくできない場合。
    """
    project = project_skill_names(SKILLS_DIR)
    with tempfile.TemporaryDirectory(prefix="skill-eval-probe-") as tmp:
        tx = probe_session(config, Path(tmp))
        print(f"利用枠: {format_quota(tx.quota())}")
        reason = stop_reason(tx.quota(), max_utilization)
        if reason:
            raise SystemExit(f"実行を始めない — {reason}")
        if not tx.init:
            print("注意: 問い合わせの記録を読めず、プロジェクトの外の skill を確かめられなかった")
            return config
        outside = outside_copies(tx.skill_names, project)
        if not outside:
            return config
        overrides, blocking = plan_overrides(outside)
        if blocking:
            raise SystemExit(
                "実行を始めない — プロジェクトの外（~/.claude/skills など）に同名の skill があり、"
                f"見えなくできない: {', '.join(blocking)}"
            )
        config = dataclasses.replace(config, skill_overrides=overrides)
        left = outside_copies(probe_session(config, Path(tmp)).skill_names, project)
        if left:
            names = ", ".join(left)
            raise SystemExit(
                f"実行を始めない — プロジェクトの外の同名 skill を見えなくできなかった: {names}"
            )
    print(f"プロジェクトの外にある同名の skill {len(overrides)} 個を、見えなくして実行する:")
    print("  " + ", ".join(sorted(overrides)))
    return config


def cmd_quota(args: argparse.Namespace) -> None:
    """利用枠（5 時間枠・7 日枠）の使用率を表示する。短い問い合わせを 1 回送る。"""
    config, _ = load_suite(args.cases, SKILLS_DIR)
    with tempfile.TemporaryDirectory(prefix="skill-eval-quota-") as tmp:
        print(format_quota(probe_session(config, Path(tmp)).quota()))


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
    arms = load_arms(args.cases)
    if args.arm not in arms:
        raise SystemExit(f"未知の arm: {args.arm}（cases.yaml にあるのは {sorted(arms)}）")
    arm = arms[args.arm]

    if args.resume and not args.run_id:
        raise SystemExit("--resume には --run-id が必要（続きを実行する出力ディレクトリ名）")
    # skill を間引いた実行は、同じ時刻の full の実行と取り違えないよう名前に arm を付ける
    suffix = "" if arm.is_full else f"-{arm.name}"
    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M%S") + suffix
    run_dir = OUTPUT_ROOT / run_id
    sandbox_root = (args.sandbox_root or Path(tempfile.gettempdir()) / "skill-eval") / run_id
    jobs = [(c, rep) for c in selected for rep in range(1, args.repeat + 1)]
    # --resume を付けても、出力がまだ無ければ新しい実行として始める（同じコマンドを繰り返せる）
    resuming = args.resume and run_dir.is_dir()
    meta: dict = {}
    if resuming:
        meta = json.loads((run_dir / "run.json").read_text("utf-8"))
        check_same_condition(meta, arm, config, _skills_hash())
        total = len(jobs)
        jobs = pending_jobs(run_dir, jobs)
        print(f"run_id: {run_id}  続きから実行: 残り {len(jobs)} / {total} 実行")
    else:
        print(f"run_id: {run_id}  ケース {len(selected)} 件 × {args.repeat} 回 = {len(jobs)} 実行")
    print(f"出力: {run_dir}")
    print(f"sandbox: {sandbox_root}")
    print("コマンド（プロンプトは標準入力で渡す）:")
    print("  " + shlex.join(claude_command(config)))
    if not arm.is_full:
        print(f"arm: {arm.name} — {arm.description}（発火の合否は付けない）")
        for line in arm.describe():
            print(f"  - {line}")
    if args.dry_run:
        for c, rep in jobs:
            print(f"  - {c.id} r{rep}: {' '.join(c.prompt.split())[:80]}")
        return

    if not jobs:
        print("残っている実行は無い")
        return

    # 上限の近くで始めると途中で打ち切られ、外の skill が見えたままだと比較にならない。
    # どちらも実行が無駄になるので、始める前に確かめる
    config = preflight(config, args.max_utilization)

    job_names = [f"{c.id}/r{rep}" for c, rep in jobs]
    if resuming:
        for c, rep in jobs:
            # 打ち切られた実行の出力は退避し、sandbox が残っていれば消してからやり直す
            moved = set_aside(run_dir, c.id, rep)
            if moved:
                print(f"やり直す実行の出力を退避: {moved}")
            shutil.rmtree(sandbox_root / f"{c.id}__r{rep}", ignore_errors=True)
        meta.setdefault("resumes", []).append(
            {
                "at": datetime.now().isoformat(timespec="seconds"),
                "jobs": job_names,
                "skill_overrides": sorted(config.skill_overrides),
            }
        )
    else:
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
            "arm": {"name": arm.name, "description": arm.description, "operations": arm.describe()},
            "jobs": job_names,
        }
    (run_dir / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), "utf-8")

    prepare_datasets(selected, sandbox_root)
    snapshot_dir = run_dir / "skills_snapshot"

    def run(c: Case, rep: int) -> dict:
        return run_one(c, rep, config, run_dir, sandbox_root, args.keep_sandbox, arm)

    def on_done(c: Case, rep: int, res: dict | Exception) -> None:
        if isinstance(res, Exception):
            print(f"[CRASH] {c.id} r{rep}: {res!r}", file=sys.stderr)
        else:
            refs = [r.rsplit("/", 1)[-1] for r in res["read_references"]]
            print(
                f"[{res['status']}] {c.id} r{rep}  読んだ references: {refs}  "
                f"図 {len(res['images'])} 枚  利用枠: {format_quota(res.get('quota'))}"
            )
        # 途中経過も見られるよう、1 件終わるごとにレポートを更新する
        write_report(run_dir, selected, snapshot_dir)

    def should_stop(res: dict) -> str | None:
        if res.get("outside_skill_copies"):
            names = ", ".join(res["outside_skill_copies"])
            return f"プロジェクトの外にある同名の skill が見えていた（比較にならない）: {names}"
        return stop_reason(res.get("quota"), args.max_utilization)

    not_started, reason = execute_jobs(jobs, run, on_done, args.jobs, should_stop)
    print(f"レポート: {run_dir / 'index.html'}")
    print(f"          {run_dir / 'summary.md'}")
    if not_started:
        print(f"{len(not_started)} 件を始めなかった — {reason}")
        for c, rep in not_started:
            print(f"  - {c.id} r{rep}")
        print(f"続きは、同じコマンドに --run-id {run_id} --resume を付けて実行する")


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
            # skill を間引いた arm の実行には、判定し直しても発火の合否を付けない
            check_firing=old.get("arm", FULL_ARM) == FULL_ARM,
        )
        for key in ("arm", "arm_ops", "sandbox"):
            if key in old:
                new[key] = old[key]
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


def cmd_compare(args: argparse.Namespace) -> None:
    """2 つの実行結果を、ケースごとに横に並べたレポートにする（API は呼ばない）。"""
    run_a: Path = args.run_a
    run_b: Path = args.run_b
    # ケース定義と「必ず出す図・値」は、基準にする側（A）の実行時点のものを使う
    snapshot_dir = run_a / "skills_snapshot"
    skills_dir = snapshot_dir if snapshot_dir.is_dir() else SKILLS_DIR
    cases_path = run_a / "cases.yaml" if (run_a / "cases.yaml").is_file() else args.cases
    _, cases = load_suite(cases_path, skills_dir)
    out_dir = args.out or run_a.parent / f"compare-{run_a.name}__{run_b.name}"
    write_compare(run_a, run_b, out_dir, cases, skills_dir)
    print(f"比較レポート: {out_dir / 'compare.html'}")
    print(f"              {out_dir / 'compare.md'}")


def cmd_score(args: argparse.Namespace) -> None:
    """実行結果を「必ず出す図・値」1 項目ずつ、出たか出ないかで採点する（API は呼ばない）。"""
    run_dirs: list[Path] = args.run_dirs
    out_dir = args.out or run_dirs[0].parent / ("score-" + "__".join(d.name for d in run_dirs))
    rows = write_scores(run_dirs, args.checklists, out_dir)
    if not rows:
        raise SystemExit("採点できる実行が無い（採点表のある reference を期待するケースが無い）")
    print((out_dir / "scores.md").read_text(encoding="utf-8"))
    print(f"採点結果: {out_dir / 'scores.md'}")
    print(f"          {out_dir / 'scores.csv'}")


def main(argv: list[str] | None = None) -> None:
    """コマンドラインの入口。"""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES, help="ケース定義の YAML")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="ケース一覧を表示").set_defaults(func=cmd_list)
    sub.add_parser(
        "quota", help="利用枠（5 時間枠・7 日枠）の使用率を表示（短い問い合わせを 1 回送る）"
    ).set_defaults(func=cmd_quota)

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
    p_run.add_argument(
        "--arm",
        default=FULL_ARM,
        help="skill をどう間引いて実行するか（cases.yaml の arms。既定の full は間引かない）",
    )
    p_run.add_argument("--model", help="cases.yaml の model を上書き")
    p_run.add_argument("--effort", help="cases.yaml の effort を上書き")
    p_run.add_argument("--max-budget-usd", type=float, help="1 実行あたりの費用上限")
    p_run.add_argument("--timeout-min", type=float, help="1 実行あたりのタイムアウト（分）")
    p_run.add_argument("--run-id", help="出力ディレクトリ名（既定は時刻）")
    p_run.add_argument(
        "--resume",
        action="store_true",
        help="--run-id の出力があれば、終わっていない実行（ERROR を含む）だけを続きから実行",
    )
    p_run.add_argument(
        "--max-utilization",
        type=float,
        default=0.85,
        help="利用枠の使用率がこの値以上なら次の実行を始めない（0〜1。既定 0.85、0 で無効）",
    )
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

    p_cmp = sub.add_parser(
        "compare", help="2 つの実行結果（skill あり・なしなど）を横に並べたレポートを作る"
    )
    p_cmp.add_argument("run_a", type=Path, help="基準にする実行（ふつうは full）")
    p_cmp.add_argument("run_b", type=Path, help="比べる実行（ふつうは skill を間引いた arm）")
    p_cmp.add_argument("--out", type=Path, help="レポートの置き場所（既定は run_a の隣）")
    p_cmp.set_defaults(func=cmd_compare)

    p_score = sub.add_parser(
        "score", help="実行結果を「必ず出す図・値」1 項目ずつ、出たか出ないかで採点する"
    )
    p_score.add_argument("run_dirs", type=Path, nargs="+", help="採点する実行（条件ごとに並べる）")
    p_score.add_argument(
        "--checklists", type=Path, default=DEFAULT_CHECKLISTS, help="採点表の YAML"
    )
    p_score.add_argument("--out", type=Path, help="出力先（既定は最初の実行の隣）")
    p_score.set_defaults(func=cmd_score)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
