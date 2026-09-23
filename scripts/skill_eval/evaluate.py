"""1 ケース分の transcript と生成物を、期待値（cases.yaml）と突き合わせる。

判定するのは「発火」だけ（期待した skill・references が読まれ、禁止したものが読まれていないか）。
図の中身が references の要求を満たすかは、レポートの一覧を見て人が判断する。
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

from skill_eval.cases import Case, reference_short_name
from skill_eval.transcript import Transcript

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".pdf"}
DIAG_TABLE_RE = re.compile(r"\|\s*診断項目\s*\|")


def _matches_any(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def read_reports(files_dir: Path, changed_files: list[str]) -> dict[str, str]:
    """回収済みの生成物のうち Markdown の本文を読む（判定表の検出用）。"""
    texts: dict[str, str] = {}
    for rel in changed_files:
        p = files_dir / rel
        if p.suffix.lower() == ".md" and p.is_file():
            texts[rel] = p.read_text(encoding="utf-8", errors="replace")
    return texts


def evaluate(
    case: Case,
    tx: Transcript,
    changed_files: list[str],
    skills_dir: Path,
    *,
    timed_out: bool = False,
    report_texts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """発火の判定と、レポートに載せる事実をまとめる。

    Args:
        case: テストケース。
        tx: 解析済みの transcript。
        changed_files: sandbox 内で新規作成・更新されたファイル（sandbox からの相対パス）。
        skills_dir: `.claude/skills` ディレクトリ（短縮名の取得に使う）。
        timed_out: タイムアウトで打ち切ったか。
        report_texts: 生成された Markdown（sandbox からの相対パス → 本文）。判定表を
            報告ファイル（outputs/reports/*.md など）に書き、最終応答には要約だけを載せる
            ことがあるので、最終応答と合わせて探す。

    Returns:
        JSON にそのまま保存できる辞書。`status` は PASS / FAIL / ERROR。
    """
    loaded = tx.loaded_skills()
    refs = tx.read_references()
    first_run = tx.first_code_run_index()

    missing_skills = [s for s in case.expect.skills if s not in loaded]
    missing_refs = [r for r in case.expect.references if r not in refs]
    forbidden = sorted(
        [s for s in loaded if _matches_any(s, case.forbid.skills)]
        + [r for r in refs if _matches_any(r, case.forbid.references)]
    )
    # 「references を読んでから実行する」を守ったか（実行が無ければ判定しない）
    read_before_run = {
        r: (None if first_run is None or r not in refs else refs[r] < first_run)
        for r in case.expect.references
    }

    images = sorted(p for p in changed_files if Path(p).suffix.lower() in IMAGE_SUFFIXES)
    # references が指定する保存先 outputs/diagnostics/<ts>_<短縮名>/ に図があるか
    dir_ok: dict[str, bool] = {}
    for r in case.expect.references:
        short = reference_short_name(skills_dir / r)
        if short:
            pat = f"outputs/diagnostics/*_{short}/*"
            dir_ok[short] = any(fnmatch.fnmatchcase(p, pat) for p in images)

    # 判定表の在りか。最終応答を優先し、無ければ生成された Markdown から探す
    table_in = None
    if DIAG_TABLE_RE.search(tx.final_text):
        table_in = "最終応答"
    else:
        for path, text in sorted((report_texts or {}).items()):
            if DIAG_TABLE_RE.search(text):
                table_in = path
                break

    denials = tx.result.get("permission_denials") or []
    if timed_out or not tx.result or tx.result.get("is_error"):
        status = "ERROR"
    elif missing_skills or missing_refs or forbidden:
        status = "FAIL"
    else:
        status = "PASS"

    return {
        "case_id": case.id,
        "kind": case.kind,
        "status": status,
        "timed_out": timed_out,
        "result_subtype": tx.result.get("subtype"),
        "available_skills": tx.available_skills,
        "expected_skills": list(case.expect.skills),
        "expected_references": list(case.expect.references),
        "loaded_skills": loaded,
        "read_references": list(refs),
        "missing_skills": missing_skills,
        "missing_references": missing_refs,
        "forbidden_hits": forbidden,
        "read_before_first_run": read_before_run,
        "figure_dir_ok": dir_ok,
        "images": images,
        "changed_files": sorted(changed_files),
        "has_diagnostics_table": table_in is not None,
        "diagnostics_table_in": table_in,
        "skill_events": [
            {"index": e.index, "path": e.path, "via": e.via, "in_subagent": e.in_subagent}
            for e in tx.skill_events()
        ],
        "first_code_run_index": first_run,
        "num_tool_calls": len(tx.tool_calls),
        "num_turns": tx.result.get("num_turns"),
        "duration_ms": tx.result.get("duration_ms"),
        "total_cost_usd": tx.result.get("total_cost_usd"),
        "permission_denials": denials,
        "final_text": tx.final_text,
        "parse_errors": tx.parse_errors,
    }
