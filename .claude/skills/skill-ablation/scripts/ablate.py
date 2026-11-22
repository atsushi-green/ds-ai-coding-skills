#!/usr/bin/env python3
"""skill の要否テスト（ablation）を回す、標準ライブラリだけのスクリプト。

同じ依頼（ケース）を、skill を外した条件・ルール 1 行だけの条件・skill をそのまま置いた条件で
headless の `claude -p` に投げ、生成物を「必ず出すもの」の採点表で数える。

サブコマンド:

- plan: 条件ごとの操作と実行回数を表示し、条件ごとに sandbox を作って、外したはずの語
  （`watch_names`）が残っていないかを調べる。claude は起動しない
- run: 1 つの条件で、ケース × 回数ぶん claude を実行して結果を保存する
- score: 保存した結果を、採点表の 1 項目ずつ「出た回数 / 実行回数」で数える
- hits: 1 項目について、どの文・コードに当たったかを実行ごとに表示する（採点の目視確認用）

sandbox はリポジトリの外（一時ディレクトリ）に作る。リポジトリの中に作ると、親ディレクトリの
CLAUDE.md や skill まで読み込まれてしまうため。リポジトリのファイルには一切書き込まない。

Python 3.11 以上（tomllib を使う）。設定ファイルの書き方は `assets/ablation.example.toml` を参照。
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FULL_ARM = "full"
RUN_KEYS = {
    "claude_bin", "model", "effort", "repeat", "timeout_min", "max_budget_usd",
    "permission_mode", "allowed_tools", "disallowed_tools", "append_system_prompt",
    "extra_args", "setup", "include", "exclude", "copy_untracked", "stub", "watch",
    "skill_overrides", "out",
}  # fmt: skip
ARM_KEYS = {"description", "extends", "remove", "drop_sections", "drop_lines", "stub", "append"}
ITEM_KEYS = {
    "id", "kind", "label", "cases", "code", "code_all", "report", "report_all", "allow_negation",
}  # fmt: skip
ITEM_KINDS = {"figure", "value"}

# Claude Code の中からこのスクリプトを実行したとき、親セッションが子プロセスに渡す環境変数。
# 引き継ぐと、起動する claude が親の設定（effort・使えるツール）で動いてしまう。
# 認証や接続先の変数（ANTHROPIC_* など）は消さないよう、名前を列挙する。
STRIP_ENV = (
    "CLAUDECODE", "CLAUDE_EFFORT", "CLAUDE_PID", "CLAUDE_AGENT_SDK_VERSION",
    "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT", "CLAUDE_CODE_EXECPATH",
    "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SESSION_ATTENDED",
    "CLAUDE_CODE_MESSAGING_SOCKET", "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_CODE_ENABLE_TASKS",
    "CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING", "CLAUDE_CODE_QUESTION_PREVIEW_FORMAT",
    "CLAUDE_CODE_STARTUP_FAILURE_RESULTS", "CLAUDE_CODE_EMIT_STARTUP_TIMING",
    "MCP_CONNECTION_NONBLOCKING", "VIRTUAL_ENV",
)  # fmt: skip

SKIP_DIRS = {".git", ".venv", "__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache",
             "node_modules", ".ipynb_checkpoints"}  # fmt: skip
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".pdf"}
CODE_SUFFIXES = {".py", ".ipynb", ".r", ".sql", ".stan", ".js", ".ts", ".sh", ".jl"}
REPORT_SUFFIXES = {".md", ".csv", ".txt", ".json"}
COLLECT_MAX_BYTES = 5 * 1024 * 1024
REPORT_MAX_BYTES = 20_000  # 行ごとの予測値のような大きな表は報告として読まない

HEADING_RE = re.compile(r"^(#{1,6})\s")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
# 報告を文に分ける（日本語の句点・改行・英語の文末）
SENTENCE_RE = re.compile(r"[。\n]|(?<=[.!?])\s+")
# 「やっていない」と述べている文。report のパターンがこの文に当たっても数えない
NEGATION_RE = re.compile(
    r"(して|でき|行って|出して|試して)(は)?(い)?(ません|ない)|未(確認|実施|検証|評価)|省略し|見送"
    r"|\b(not|never)\s+(been\s+)?(checked|computed|run|done|performed|assessed|evaluated|tested)"
    r"|\bdid\s+not\b|\bdidn't\b|\bwas\s+not\b|\bskipped\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Arm:
    """比べる条件 1 つ。sandbox にコピーしたリポジトリをどう間引くか。

    Attributes:
        name: 条件の名前（出力ディレクトリ名にも使う）。
        description: 記録に載せる説明。
        remove: 消すパス（sandbox からの相対 glob）。
        drop_sections: ファイル → 消す Markdown の見出し行。次の同じ深さ以上の見出しまで消す。
        drop_lines: (ファイルの glob 群, 正規表現群)。当たる行を消す。
        stub: ファイル → 差し替える中身（ファイルは残すが中身は見せない）。
        append: (ファイル, 行, 目印の行)。行を消した後に、目印の行（空なら末尾）の直後へ足す。
    """

    name: str
    description: str = ""
    remove: tuple[str, ...] = ()
    drop_sections: tuple[tuple[str, str], ...] = ()
    drop_lines: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = ()
    stub: tuple[tuple[str, str], ...] = ()
    append: tuple[tuple[str, str, str], ...] = ()

    @property
    def is_full(self) -> bool:
        """skill を間引かない条件か。"""
        return not (self.remove or self.drop_sections or self.drop_lines or self.append)

    def describe(self) -> list[str]:
        """この条件の操作を、人が読める文字列の一覧にする。"""
        ops = [f"remove {p}" for p in self.remove]
        ops += [f"drop section {f} :: {h}" for f, h in self.drop_sections]
        ops += [f"drop lines /{'|'.join(p)}/ in {', '.join(f)}" for f, p in self.drop_lines]
        ops += [f"stub {f}" for f, _ in self.stub]
        ops += [f"append to {f} :: {line}" for f, line, _ in self.append]
        return ops


@dataclass(frozen=True)
class Item:
    """採点する 1 項目（skill が「必ず出す」と定めた出力 1 つ）。

    `code`・`report` はどれか 1 つ、`code_all`・`report_all` はすべてに当たれば満たす。
    書いたグループのうち 1 つでも満たせば「出た」。figure は画像ファイルがあることも条件にする。
    """

    id: str
    kind: str
    label: str
    cases: tuple[str, ...] = ()
    code: tuple[str, ...] = ()
    code_all: tuple[str, ...] = ()
    report: tuple[str, ...] = ()
    report_all: tuple[str, ...] = ()
    allow_negation: bool = False


@dataclass
class Config:
    """設定ファイルの中身。"""

    run: dict[str, Any]
    cases: dict[str, str]
    arms: dict[str, Arm]
    items: list[Item] = field(default_factory=list)


def _tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def parse_arms(raw: dict[str, Any], run_stub: dict[str, str]) -> dict[str, Arm]:
    """`[arm.<名前>]` を読む。`full` は書かなくても常にある。

    `extends = "<名前>"` は、先に定義した条件の操作を引き継いでから自分の操作を足す。
    `[run] stub` はすべての条件（full を含む）に適用する。

    Raises:
        ValueError: 未知のキー、未定義の extends、full に間引く操作がある場合。
    """
    arms: dict[str, Arm] = {}
    common_stub = tuple((str(k), str(v)) for k, v in run_stub.items())
    for name, spec in raw.items():
        spec = spec or {}
        unknown = set(spec) - ARM_KEYS
        if unknown:
            raise ValueError(f"arm {name}: 未知のキー {sorted(unknown)}")
        base = Arm(name=name, stub=common_stub)
        if "extends" in spec:
            parent = arms.get(str(spec["extends"]))
            if parent is None:
                raise ValueError(f"arm {name}: extends の `{spec['extends']}` が先に無い")
            base = parent
        arms[name] = Arm(
            name=name,
            description=str(spec.get("description", "")),
            remove=base.remove + _tuple(spec.get("remove")),
            drop_sections=base.drop_sections
            + tuple(
                (str(f), str(h))
                for f, heads in (spec.get("drop_sections") or {}).items()
                for h in _tuple(heads)
            ),
            drop_lines=base.drop_lines
            + tuple(
                (_tuple(rule["files"]), _tuple(rule["patterns"]))
                for rule in spec.get("drop_lines", [])
            ),
            stub=base.stub + tuple((str(k), str(v)) for k, v in (spec.get("stub") or {}).items()),
            append=base.append
            + tuple(
                (str(a["file"]), str(a["line"]), str(a.get("after", "")))
                for a in spec.get("append", [])
            ),
        )
    arms.setdefault(FULL_ARM, Arm(name=FULL_ARM, stub=common_stub))
    if not arms[FULL_ARM].is_full:
        raise ValueError("arm full は skill をそのまま置く条件なので、間引く操作を書けない")
    return arms


def parse_items(raw: list[dict[str, Any]], case_ids: set[str]) -> list[Item]:
    """`[[item]]` を読む。

    Raises:
        ValueError: 未知のキー・種類、ID の重複、見つけ方が無い項目、不正な正規表現、
            未定義のケースを指す項目がある場合。
    """
    items: list[Item] = []
    seen: set[str] = set()
    for spec in raw:
        unknown = set(spec) - ITEM_KEYS
        if unknown:
            raise ValueError(f"item {spec.get('id')}: 未知のキー {sorted(unknown)}")
        item = Item(
            id=str(spec["id"]),
            kind=str(spec.get("kind", "value")),
            label=str(spec.get("label", spec["id"])),
            cases=_tuple(spec.get("cases")),
            code=_tuple(spec.get("code")),
            code_all=_tuple(spec.get("code_all")),
            report=_tuple(spec.get("report")),
            report_all=_tuple(spec.get("report_all")),
            allow_negation=bool(spec.get("allow_negation", False)),
        )
        if item.id in seen:
            raise ValueError(f"item {item.id}: ID が重複している")
        seen.add(item.id)
        if item.kind not in ITEM_KINDS:
            raise ValueError(f"item {item.id}: kind は {sorted(ITEM_KINDS)} のどれか")
        patterns = item.code + item.code_all + item.report + item.report_all
        if not patterns:
            raise ValueError(f"item {item.id}: code / report のどれかを書く")
        for p in patterns:
            try:
                re.compile(p)
            except re.error as e:
                raise ValueError(f"item {item.id}: 正規表現が不正 {p!r}: {e}") from e
        missing = set(item.cases) - case_ids
        if missing:
            raise ValueError(f"item {item.id}: 未定義のケース {sorted(missing)}")
        items.append(item)
    return items


def load_config(path: Path) -> Config:
    """設定ファイル（TOML）を読む。

    Raises:
        ValueError: 書式が不正な場合。
    """
    with path.open("rb") as f:
        raw = tomllib.load(f)
    run = dict(raw.get("run", {}))
    unknown = set(run) - RUN_KEYS
    if unknown:
        raise ValueError(f"[run]: 未知のキー {sorted(unknown)}")
    cases: dict[str, str] = {}
    for c in raw.get("case", []):
        cid = str(c["id"])
        if cid in cases:
            raise ValueError(f"case {cid}: ID が重複している")
        cases[cid] = str(c["prompt"]).strip()
    if not cases:
        raise ValueError("[[case]] が 1 つも無い")
    arms = parse_arms(raw.get("arm", {}), run.get("stub", {}))
    items = parse_items(raw.get("item", []), set(cases))
    return Config(run=run, cases=cases, arms=arms, items=items)


# ---------------------------------------------------------------- sandbox


def drop_section(text: str, heading: str) -> tuple[str, int]:
    """Markdown から見出し `heading` の節を消す（コードブロック内の `#` は見出しにしない）。

    Returns:
        (消した後の本文, 消した節の数)。
    """
    target = heading.strip()
    m = HEADING_RE.match(target)
    if not m:
        raise ValueError(f"見出しは `#` で始める: {heading!r}")
    level = len(m.group(1))
    kept: list[str] = []
    dropped, skipping, in_fence = 0, False, False
    for line in text.splitlines(keepends=True):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        head = None if in_fence else HEADING_RE.match(line)
        if head:
            if line.strip() == target:
                skipping, dropped = True, dropped + 1
                continue
            if skipping and len(head.group(1)) <= level:
                skipping = False
        if not skipping:
            kept.append(line)
    return "".join(kept), dropped


def apply_arm(root: Path, arm: Arm) -> list[str]:
    """条件の操作を sandbox に適用し、行った操作の記録を返す。

    Raises:
        ValueError: 消す対象のパス・見出しが見つからない場合（指定と skill の現状がずれたまま
            実行すると、外したつもりの記述が残った状態で比べてしまうので止める）。
    """
    log: list[str] = []
    for rel, text in arm.stub:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        log.append(f"stub {rel}")
    for pattern in arm.remove:
        hits = sorted(root.glob(pattern))
        if not hits:
            raise ValueError(f"arm {arm.name}: remove の `{pattern}` に当たるパスが無い")
        for p in hits:
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink()
            log.append(f"remove {p.relative_to(root).as_posix()}")
    for rel, heading in arm.drop_sections:
        p = root / rel
        if not p.is_file():
            raise ValueError(f"arm {arm.name}: drop_sections の `{rel}` が無い")
        text, n = drop_section(p.read_text(encoding="utf-8"), heading)
        if n == 0:
            raise ValueError(f"arm {arm.name}: `{rel}` に見出し `{heading}` が無い")
        p.write_text(text, encoding="utf-8")
        log.append(f"drop section {rel} :: {heading.strip()}")
    for globs, patterns in arm.drop_lines:
        regexes = [re.compile(p) for p in patterns]
        for p in sorted({f for g in globs for f in root.glob(g) if f.is_file()}):
            lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
            kept = [ln for ln in lines if not any(r.search(ln) for r in regexes)]
            if len(kept) != len(lines):
                p.write_text("".join(kept), encoding="utf-8")
                log.append(f"drop {len(lines) - len(kept)} line(s) {p.relative_to(root)}")
    # 行を消した後に足す（足した行が drop_lines のパターンに当たっても残る）
    for rel, line, after in arm.append:
        p = root / rel
        if not p.is_file():
            raise ValueError(f"arm {arm.name}: append の `{rel}` が無い")
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        if after:
            hits = [i for i, ln in enumerate(lines) if ln.strip() == after.strip()]
            if len(hits) != 1:
                raise ValueError(
                    f"arm {arm.name}: `{rel}` の目印の行が {len(hits)} 件（1 件のこと）: {after}"
                )
            lines.insert(hits[0] + 1, line.rstrip("\n") + "\n")
        else:
            lines.append(line.rstrip("\n") + "\n")
        p.write_text("".join(lines), encoding="utf-8")
        log.append(f"append to {rel} :: {line}")
    return log


def repo_root() -> Path:
    """カレントディレクトリを含む git リポジトリのルート。"""
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
    )
    return Path(out.stdout.strip())


def matches_any(rel: str, patterns: list[str]) -> bool:
    """rel がパターンのどれか（glob か、ディレクトリの接頭辞か、完全一致）に当たるか。"""
    return any(
        rel == p or fnmatch.fnmatch(rel, p) or rel.startswith(p.rstrip("/") + "/") for p in patterns
    )


def build_sandbox(root: Path, dest: Path, cfg: Config, arm: Arm) -> list[str]:
    """git 管理下のファイルと `copy_untracked` を dest にコピーし、条件を適用して commit する。

    `include` を書いたら、そのパスの下にある git 管理下のファイルだけを入れる。
    `exclude` に当たるファイル（比較の記録や、skill を説明した文書など）は、どの条件でも入れない。
    未追跡のファイル（.env や手元の作業ファイル）は `copy_untracked` に書いたものだけ入る。

    Returns:
        条件で行った操作の記録。
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True
    ).stdout.decode("utf-8")
    include = [str(p) for p in cfg.run.get("include", [])]
    exclude = [str(p) for p in cfg.run.get("exclude", [])]
    rels = [
        r
        for r in listed.split("\0")
        if r and (not include or matches_any(r, include)) and not matches_any(r, exclude)
    ]
    rels += [str(r) for r in cfg.run.get("copy_untracked", [])]
    dest.mkdir(parents=True, exist_ok=False)
    for rel in rels:
        src = root / rel
        if not (src.exists() or src.is_symlink()):
            continue  # 削除済みでまだ commit していないファイル
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir() and not src.is_symlink():
            shutil.copytree(src, target, symlinks=True)
        else:
            shutil.copy2(src, target, follow_symlinks=False)
    ops = apply_arm(dest, arm)
    git = ["git", "-c", "user.name=ablation", "-c", "user.email=ablation@localhost",
           "-c", "commit.gpgsign=false"]  # fmt: skip
    subprocess.run([*git, "init", "-q"], cwd=dest, check=True)
    subprocess.run([*git, "add", "-A"], cwd=dest, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "sandbox"], cwd=dest, check=True)
    return ops


def find_mentions(root: Path, words: list[str]) -> list[str]:
    """sandbox に残った `words` の出現箇所（`path:line: 本文`）。"""
    if not words:
        return []
    rx = re.compile("|".join(re.escape(w) for w in words), re.IGNORECASE)
    hits: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{p.relative_to(root)}:{i}: {line.strip()[:120]}")
    return hits


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """root 以下のファイルの (mtime_ns, size)。キャッシュ類は除く。"""
    snap: dict[str, tuple[int, int]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                st = p.stat()
            except OSError:
                continue
            snap[p.relative_to(root).as_posix()] = (st.st_mtime_ns, st.st_size)
    return snap


def claude_command(run: dict[str, Any]) -> list[str]:
    """claude の起動コマンド。プロンプトは標準入力で渡す（可変長オプションに取り込まれるため）。"""
    cmd = [str(run.get("claude_bin", "claude")), "-p", "--output-format", "stream-json",
           "--verbose", "--no-session-persistence",
           "--permission-mode", str(run.get("permission_mode", "acceptEdits"))]  # fmt: skip
    if run.get("model"):
        cmd += ["--model", str(run["model"])]
    if run.get("effort"):
        cmd += ["--effort", str(run["effort"])]
    if run.get("max_budget_usd"):
        cmd += ["--max-budget-usd", str(run["max_budget_usd"])]
    if str(run.get("append_system_prompt", "")).strip():
        cmd += ["--append-system-prompt", str(run["append_system_prompt"]).strip()]
    if run.get("skill_overrides"):
        # プロジェクトの外にある同名の skill（名前空間つき）を見えなくする
        cmd += ["--settings", json.dumps({"skillOverrides": dict(run["skill_overrides"])})]
    if run.get("allowed_tools"):
        cmd += ["--allowedTools", *map(str, run["allowed_tools"])]
    if run.get("disallowed_tools"):
        cmd += ["--disallowedTools", *map(str, run["disallowed_tools"])]
    return cmd + [str(a) for a in run.get("extra_args", [])]


def child_env() -> dict[str, str]:
    """子の claude に渡す環境変数（親セッションの変数を除く）。"""
    return {k: v for k, v in os.environ.items() if k not in STRIP_ENV}


def parse_transcript(path: Path) -> dict[str, Any]:
    """stream-json から、見えていた skill と最後の result を取り出す。"""
    skills: list[str] = []
    result: dict[str, Any] = {}
    if not path.exists():
        return {"skills": skills, "result": result}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("type") == "system" and msg.get("subtype") == "init" and not skills:
            skills = [s.get("name", "") if isinstance(s, dict) else str(s)
                      for s in msg.get("skills") or []]  # fmt: skip
        if msg.get("type") == "result":
            result = msg
    return {"skills": skills, "result": result}


def leaked_skills(visible: list[str], watch: list[str]) -> list[str]:
    """見えていた skill のうち、名前に `watch` の語を含むもの（大文字小文字を区別しない）。"""
    words = [w.lower() for w in watch if w]
    return sorted(s for s in visible if any(w in s.lower() for w in words))


def run_one(root: Path, cfg: Config, arm: Arm, case_id: str, rep: int, out: Path) -> dict:
    """1 回の実行。sandbox を作り、claude を起動し、結果と生成物を out に保存する。"""
    work = Path(tempfile.mkdtemp(prefix=f"ablation-{arm.name}-{case_id}-r{rep}-")) / "repo"
    try:
        return _run_in_sandbox(root, cfg, arm, case_id, rep, out, work)
    finally:
        shutil.rmtree(work.parent, ignore_errors=True)


def _run_in_sandbox(
    root: Path, cfg: Config, arm: Arm, case_id: str, rep: int, out: Path, work: Path
) -> dict:
    run = cfg.run
    ops = build_sandbox(root, work, cfg, arm)
    env = child_env()
    for command in run.get("setup", []):
        subprocess.run(command, shell=True, cwd=work, env=env, check=True)
    before = snapshot(work)
    out.mkdir(parents=True, exist_ok=True)
    transcript, stderr = out / "transcript.jsonl", out / "stderr.txt"
    timed_out = False
    with transcript.open("wb") as fo, stderr.open("wb") as fe:
        proc = subprocess.Popen(
            claude_command(run), cwd=work, env=env, stdin=subprocess.PIPE, stdout=fo, stderr=fe
        )
        try:
            proc.communicate(cfg.cases[case_id].encode("utf-8"),
                             timeout=float(run.get("timeout_min", 30)) * 60)  # fmt: skip
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            timed_out = True
    after = snapshot(work)
    files: list[str] = []
    for rel, meta in sorted(after.items()):
        src = work / rel
        if before.get(rel) == meta or src.stat().st_size > COLLECT_MAX_BYTES:
            continue
        target = out / "files" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        files.append(rel)
    parsed = parse_transcript(transcript)
    res = parsed["result"]
    watch = [] if arm.is_full else [str(w) for w in run.get("watch", [])]
    record = {
        "case": case_id, "arm": arm.name, "rep": rep, "ops": ops, "files": files,
        "timed_out": timed_out, "is_error": bool(res.get("is_error", True)) or timed_out,
        "subtype": res.get("subtype"), "cost_usd": res.get("total_cost_usd"),
        "duration_min": round((res.get("duration_ms") or 0) / 60000, 1),
        "num_turns": res.get("num_turns"),
        "permission_denials": len(res.get("permission_denials") or []),
        "visible_skills": parsed["skills"],
        "leaked_skills": leaked_skills(parsed["skills"], watch),
        "final_text": res.get("result") or "",
    }  # fmt: skip
    (out / "result.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), "utf-8")
    return record


# ---------------------------------------------------------------- 採点


def gather_texts(run_dir: Path, record: dict[str, Any]) -> tuple[str, list[str], bool]:
    """採点に使うコード・報告の文・画像の有無を集める。"""
    code_parts: list[str] = []
    report_parts: list[str] = [record.get("final_text", "")]
    has_image = False
    files_dir = run_dir / "files"
    for p in sorted(files_dir.rglob("*")) if files_dir.exists() else []:
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            has_image = True
        elif suffix in CODE_SUFFIXES:
            code_parts.append(p.read_text(encoding="utf-8", errors="replace"))
        elif suffix in REPORT_SUFFIXES and p.stat().st_size <= REPORT_MAX_BYTES:
            report_parts.append(p.read_text(encoding="utf-8", errors="replace"))
    sentences = [s for part in report_parts for s in SENTENCE_RE.split(part) if s.strip()]
    return "\n".join(code_parts), sentences, has_image


def _report_hit(pattern: str, sentences: list[str], allow_negation: bool) -> str | None:
    rx = re.compile(pattern, re.IGNORECASE)
    for s in sentences:
        if rx.search(s) and (allow_negation or not NEGATION_RE.search(s)):
            return s.strip()
    return None


def item_evidence(item: Item, code: str, sentences: list[str], has_image: bool) -> str | None:
    """項目が出ていれば、当たった根拠（短い抜粋）を返す。出ていなければ None。"""
    if item.kind == "figure" and not has_image:
        return None
    for p in item.code:
        m = re.search(p, code, re.IGNORECASE)
        if m:
            return f"[code] {code[max(0, m.start() - 40) : m.end() + 40]!r}"
    if item.code_all and all(re.search(p, code, re.IGNORECASE) for p in item.code_all):
        return f"[code_all] {', '.join(item.code_all)}"
    for p in item.report:
        hit = _report_hit(p, sentences, item.allow_negation)
        if hit:
            return f"[report] {hit[:160]}"
    if item.report_all:
        hits = [_report_hit(p, sentences, item.allow_negation) for p in item.report_all]
        if all(hits):
            return f"[report_all] {' / '.join(h[:60] for h in hits if h)}"
    return None


def load_runs(dirs: list[Path]) -> list[tuple[Path, dict[str, Any]]]:
    """dirs 以下の result.json をすべて読む。"""
    runs = []
    for d in dirs:
        for p in sorted(d.rglob("result.json")):
            runs.append((p.parent, json.loads(p.read_text(encoding="utf-8"))))
    return runs


def score(cfg: Config, dirs: list[Path]) -> tuple[str, list[dict[str, Any]]]:
    """項目 × 条件で「出た回数 / 実行回数」の Markdown 表と、1 行 1 判定の記録を返す。

    エラー・タイムアウトで終わった実行は「何も出なかった」ように見えるので、数えずに件数だけ出す。
    """
    runs = load_runs(dirs)
    arms = list(dict.fromkeys(r["arm"] for _, r in runs))
    rows: list[dict[str, Any]] = []
    excluded: list[str] = []
    for run_dir, rec in runs:
        if rec.get("is_error"):
            excluded.append(f"{rec['arm']}/{rec['case']}/r{rec['rep']}")
            continue
        code, sentences, has_image = gather_texts(run_dir, rec)
        for item in cfg.items:
            if item.cases and rec["case"] not in item.cases:
                continue
            ev = item_evidence(item, code, sentences, has_image)
            rows.append(
                {"arm": rec["arm"], "case": rec["case"], "rep": rec["rep"], "item": item.id,
                 "present": ev is not None, "evidence": ev or ""}
            )  # fmt: skip
    lines = ["| 項目 | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
    totals = {a: [0, 0] for a in arms}
    for item in cfg.items:
        cells = []
        for a in arms:
            hits = [r["present"] for r in rows if r["arm"] == a and r["item"] == item.id]
            totals[a][0] += sum(hits)
            totals[a][1] += len(hits)
            cells.append(f"{sum(hits)}/{len(hits)}" if hits else "—")
        kind = "図" if item.kind == "figure" else "値"
        lines.append(f"| {kind}: {item.label} | " + " | ".join(cells) + " |")
    lines.append("| **計** | " + " | ".join(f"{h}/{n}" for h, n in totals.values()) + " |")
    leaks = [f"{r['arm']}/{r['case']}/r{r['rep']}: {r['leaked_skills']}"
             for _, r in runs if r.get("leaked_skills")]  # fmt: skip
    if excluded:
        lines += ["", f"エラー・タイムアウトで数えなかった実行: {', '.join(excluded)}"]
    if leaks:
        lines += ["", "外したはずの skill が見えていた実行（比較にならない）: " + "; ".join(leaks)]
    return "\n".join(lines), rows


# ---------------------------------------------------------------- CLI


def cmd_plan(cfg: Config, args: argparse.Namespace) -> int:
    root = repo_root()
    repeat = int(cfg.run.get("repeat", 3))
    arms = [cfg.arms[a] for a in (args.arm or cfg.arms)]
    print(f"ケース {len(cfg.cases)} 件 × 回数 {repeat} = 条件あたり {len(cfg.cases) * repeat} 実行")
    status = 0
    for arm in arms:
        print(f"\n## {arm.name}  {arm.description}")
        work = Path(tempfile.mkdtemp(prefix=f"ablation-plan-{arm.name}-")) / "repo"
        try:
            for op in build_sandbox(root, work, cfg, arm):
                print(f"  - {op}")
            if not arm.is_full:
                left = find_mentions(work, [str(w) for w in cfg.run.get("watch", [])])
                print(f"  外したはずの語の残り: {len(left)} 件")
                for hit in left[:40]:
                    print(f"    {hit}")
                status = status or (1 if left else 0)
        finally:
            shutil.rmtree(work.parent, ignore_errors=True)
    print(f"\n起動コマンド: {' '.join(claude_command(cfg.run))}")
    return status


def _failed(result_path: Path) -> bool:
    return bool(json.loads(result_path.read_text(encoding="utf-8")).get("is_error", True))


def cmd_run(cfg: Config, args: argparse.Namespace) -> int:
    root = repo_root()
    arm = cfg.arms[args.arm]
    out_root = Path(args.out or cfg.run.get("out", "outputs/ablation")) / args.label / arm.name
    cases = args.case or list(cfg.cases)
    repeat = args.repeat or int(cfg.run.get("repeat", 3))
    for case_id in cases:
        for rep in range(1, repeat + 1):
            out = out_root / case_id / f"r{rep}"
            done = out / "result.json"
            if args.resume and done.exists() and not _failed(done):
                continue
            shutil.rmtree(out, ignore_errors=True)
            rec = run_one(root, cfg, arm, case_id, rep, out)
            flag = "ERROR" if rec["is_error"] else "done"
            print(f"[{flag}] {arm.name}/{case_id}/r{rep}  ${rec['cost_usd']}  "
                  f"{rec['duration_min']} 分  拒否 {rec['permission_denials']} 回  "
                  f"生成 {len(rec['files'])} ファイル"
                  + (f"  外したはずの skill が見えた: {rec['leaked_skills']}"
                     if rec["leaked_skills"] else ""), flush=True)  # fmt: skip
    return 0


def cmd_score(cfg: Config, args: argparse.Namespace) -> int:
    table, rows = score(cfg, [Path(d) for d in args.dirs])
    print(table)
    if args.csv:
        path = Path(args.csv)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["arm", "case", "rep", "item", "present",
                                                   "evidence"])  # fmt: skip
            writer.writeheader()
            writer.writerows(rows)
    return 0


def cmd_hits(cfg: Config, args: argparse.Namespace) -> int:
    items = {i.id: i for i in cfg.items}
    if args.item not in items:
        print(f"項目 {args.item} が採点表に無い", file=sys.stderr)
        return 2
    item = items[args.item]
    for run_dir, rec in load_runs([Path(d) for d in args.dirs]):
        if item.cases and rec["case"] not in item.cases:
            continue
        code, sentences, has_image = gather_texts(run_dir, rec)
        ev = item_evidence(item, code, sentences, has_image)
        mark = "○" if ev else "×"
        print(f"{mark} {rec['arm']}/{rec['case']}/r{rec['rep']}: {ev or ''}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """エントリポイント。"""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default="ablation.toml", help="設定ファイル（TOML）")
    sub = parser.add_subparsers(dest="command", required=True)
    p_plan = sub.add_parser("plan", help="操作と残った語を確かめる（claude は起動しない）")
    p_plan.add_argument("--arm", action="append", help="確かめる条件（複数可。省略で全部）")
    p_run = sub.add_parser("run", help="1 つの条件を、ケース × 回数ぶん実行する")
    p_run.add_argument("--arm", required=True)
    p_run.add_argument("--label", required=True, help="実行の名前（出力ディレクトリ名）")
    p_run.add_argument("--case", action="append", help="実行するケース（複数可。省略で全部）")
    p_run.add_argument("--repeat", type=int, help="回数（省略で [run] repeat）")
    p_run.add_argument("--out", help="出力先（省略で [run] out か outputs/ablation）")
    p_run.add_argument("--resume", action="store_true", help="成功済みの実行を飛ばす")
    p_score = sub.add_parser("score", help="結果を採点表で数える（API は呼ばない）")
    p_score.add_argument("dirs", nargs="+", help="run の出力ディレクトリ（複数可）")
    p_score.add_argument("--csv", help="1 行 1 判定の CSV の保存先")
    p_hits = sub.add_parser("hits", help="1 項目の根拠を実行ごとに表示する")
    p_hits.add_argument("item")
    p_hits.add_argument("dirs", nargs="+")
    args = parser.parse_args(argv)
    try:
        cfg = load_config(Path(args.config))
    except (OSError, ValueError, KeyError, tomllib.TOMLDecodeError) as e:
        print(f"設定ファイルを読めない: {e}", file=sys.stderr)
        return 2
    wanted = getattr(args, "arm", None) or []
    for name in [wanted] if isinstance(wanted, str) else wanted:
        if name not in cfg.arms:
            print(f"条件 {name} が無い（{', '.join(cfg.arms)}）", file=sys.stderr)
            return 2
    handlers = {"plan": cmd_plan, "run": cmd_run, "score": cmd_score, "hits": cmd_hits}
    return handlers[args.command](cfg, args)


if __name__ == "__main__":
    sys.exit(main())
