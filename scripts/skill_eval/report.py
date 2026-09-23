"""実行結果（各ケースの result.json）から一覧レポート（summary.md / index.html）を作る。"""

from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from skill_eval.cases import Case, expected_figures

STATUS_MARK = {"PASS": "✅", "FAIL": "❌", "ERROR": "⚠️"}


def load_results(run_dir: Path) -> list[dict[str, Any]]:
    """run_dir/<case>/<rep>/result.json をすべて読む（ケース ID・反復番号順）。"""
    results = []
    for p in sorted(run_dir.glob("*/r*/result.json")):
        with p.open(encoding="utf-8") as f:
            res = json.load(f)
        res["_dir"] = p.parent.relative_to(run_dir).as_posix()
        results.append(res)
    return results


def _short_ref(path: str) -> str:
    # `<skill>/references/glm.md` → `glm`
    return path.rsplit("/", 1)[-1].removesuffix(".md")


def _short_skill(name: str) -> str:
    return name.removesuffix("-diagnostics")


def _fmt_refs(paths: list[str]) -> str:
    return ", ".join(_short_ref(p) for p in paths) or "—"


def _fmt_before_run(flags: dict[str, bool | None]) -> str:
    if not flags:
        return "—"
    marks = {True: "○", False: "×", None: "−"}
    return " ".join(f"{_short_ref(r)}:{marks[v]}" for r, v in flags.items())


def _one_line(text: str, n: int) -> str:
    t = " ".join(text.split())
    return t if len(t) <= n else t[: n - 1] + "…"


def _cost(res: dict[str, Any]) -> str:
    c = res.get("total_cost_usd")
    d = res.get("duration_ms")
    parts = []
    if d is not None:
        parts.append(f"{d / 60000:.1f}分")
    if c is not None:
        parts.append(f"${c:.2f}")
    return " / ".join(parts) or "—"


def _table_mark(res: dict[str, Any]) -> str:
    # 判定表が最終応答にあれば ○、報告ファイルにだけあれば ○（ファイル）
    where = res.get("diagnostics_table_in")
    if not res.get("has_diagnostics_table"):
        return "×"
    return "○" if where in (None, "最終応答") else "○（ファイル）"


def _group(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        grouped[r["case_id"]].append(r)
    return grouped


def build_markdown(
    run_meta: dict[str, Any], cases: list[Case], results: list[dict[str, Any]]
) -> str:
    """一覧表とケースごとの詳細を Markdown で返す。"""
    by_case = _group(results)
    case_map = {c.id: c for c in cases}
    lines = [
        f"# skill 発火テスト {run_meta.get('run_id', '')}",
        "",
        f"- 実行開始: {run_meta.get('started_at', '')}",
        f"- claude: {run_meta.get('claude_version', '')} / model: "
        f"{run_meta.get('config', {}).get('model') or '既定'}",
        f"- git HEAD: {run_meta.get('git_head', '')}（skills の内容ハッシュ: "
        f"{run_meta.get('skills_hash', '')[:12]}）",
        "",
        "判定は「期待した skill・references が読まれ、禁止したものが読まれていないか」だけ。"
        "図の中身は index.html のサムネイルと references の「必ず出す図」を見比べて判断する。",
        "",
        "| ケース | 種別 | 発火 | プロンプト | 期待 references | 発火した skill "
        "| 読んだ references | 禁止ヒット | 図 | 読了→実行 | 判定表 | 時間 / 費用 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for cid, runs in by_case.items():
        case = case_map.get(cid)
        prompt = _one_line(case.prompt, 40) if case else ""
        n_pass = sum(r["status"] == "PASS" for r in runs)
        for i, r in enumerate(runs):
            head = (
                f"| {cid} | {r['kind']} | {STATUS_MARK[r['status']]} {n_pass}/{len(runs)} "
                f"| {prompt} "
                if i == 0
                else f"| ↳ {r['_dir']} | | {STATUS_MARK[r['status']]} | "
            )
            skills = ", ".join(f"{_short_skill(s)}({v})" for s, v in r["loaded_skills"].items())
            lines.append(
                head + f"| {_fmt_refs(r['expected_references'])} | {skills or '—'} "
                f"| {_fmt_refs(r['read_references'])} | {_fmt_refs(r['forbidden_hits'])} "
                f"| {len(r['images'])} | {_fmt_before_run(r['read_before_first_run'])} "
                f"| {_table_mark(r)} | {_cost(r)} |"
            )
    lines += [
        "",
        "列の読み方: 発火した skill の括弧内は経路（Skill ツール / Read / Bash）。"
        "読了→実行は「references を読んでから最初の Python 実行をしたか」"
        "（○ 守った / × 実行が先 / − 未読か未実行）。"
        "判定表は最終応答にあれば ○、"
        "報告ファイル（outputs/reports/*.md など）にだけあれば ○（ファイル）。",
        "",
    ]
    for cid, runs in by_case.items():
        case = case_map.get(cid)
        lines += [f"## {cid}", ""]
        if case:
            lines += ["```text", case.prompt, "```", ""]
            if case.note:
                lines += [f"メモ: {case.note}", ""]
        for r in runs:
            lines.append(f"### {r['_dir']} — {r['status']}")
            if r["missing_skills"] or r["missing_references"]:
                lines.append(
                    f"- 読まれなかった: {', '.join(r['missing_skills'] + r['missing_references'])}"
                )
            if r["forbidden_hits"]:
                lines.append(f"- 読まれてはいけないのに読まれた: {', '.join(r['forbidden_hits'])}")
            if r["timed_out"]:
                lines.append("- タイムアウトで打ち切り")
            if r["permission_denials"]:
                denied = {d.get("tool_name", "?") for d in r["permission_denials"]}
                lines.append(f"- 権限で拒否されたツール: {', '.join(sorted(denied))}")
            timeline = " → ".join(
                f"{e['path'].replace('-diagnostics', '')}[{e['via']}]" for e in r["skill_events"]
            )
            lines.append(f"- 読んだ順: {timeline or '—'}")
            if r.get("diagnostics_table_in"):
                lines.append(f"- 判定表の在りか: {r['diagnostics_table_in']}")
            if r["images"]:
                lines.append("- 図:")
                lines += [f"  - [{p}]({r['_dir']}/files/{p})" for p in r["images"]]
            lines.append("")
    return "\n".join(lines)


CSS = """
:root{--bg:#fbfbf9;--fg:#1d1d1b;--muted:#6b6b66;--line:#deded8;--card:#fff;
--ok:#1f7a3f;--ng:#b3261e;--warn:#9a6700}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ececea;--muted:#a3a39c;
--line:#34342f;--card:#1f1f1d;--ok:#6fcf8f;--ng:#ff8a80;--warn:#e3b341}}
body{background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,"Hiragino Sans",sans-serif;
margin:0;padding:24px 16px}
main{max-width:1400px;margin:0 auto}
h1{font-size:22px}h2{font-size:17px;margin-top:40px}
.muted{color:var(--muted)}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{position:sticky;top:0;background:var(--bg)}
.PASS{color:var(--ok)}.FAIL{color:var(--ng)}.ERROR{color:var(--warn)}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:12px 16px;margin:12px 0}
pre{white-space:pre-wrap;background:var(--bg);border:1px solid var(--line);
padding:8px;border-radius:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.grid figure{margin:0}
.grid img{width:100%;border:1px solid var(--line);border-radius:4px;background:#fff}
figcaption{font-size:12px;color:var(--muted);word-break:break-all}
.cols{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:16px}
@media (max-width:800px){.cols{grid-template-columns:1fr}}
code{font-size:12px}
"""


def build_html(
    run_meta: dict[str, Any], cases: list[Case], results: list[dict[str, Any]], skills_dir: Path
) -> str:
    """サムネイル付きの一覧ページを返す（run_dir に置いて相対パスで図を参照する）。"""
    e = html.escape
    by_case = _group(results)
    case_map = {c.id: c for c in cases}
    rows = []
    for cid, runs in by_case.items():
        case = case_map.get(cid)
        for r in runs:
            skills = "<br>".join(
                f"{e(_short_skill(s))} <span class=muted>({e(v)})</span>"
                for s, v in r["loaded_skills"].items()
            )
            rows.append(
                f"<tr><td><a href='#{e(r['_dir'])}'>{e(r['_dir'])}</a></td><td>{e(r['kind'])}</td>"
                f"<td class={r['status']}>{r['status']}</td>"
                f"<td>{e(_one_line(case.prompt, 60) if case else '')}</td>"
                f"<td>{e(_fmt_refs(r['expected_references']))}</td><td>{skills or '—'}</td>"
                f"<td>{e(_fmt_refs(r['read_references']))}</td>"
                f"<td class={'FAIL' if r['forbidden_hits'] else ''}>"
                f"{e(_fmt_refs(r['forbidden_hits']))}</td>"
                f"<td>{len(r['images'])}</td><td>{e(_fmt_before_run(r['read_before_first_run']))}</td>"
                f"<td>{e(_table_mark(r))}</td><td>{e(_cost(r))}</td></tr>"
            )
    cards = []
    for cid, runs in by_case.items():
        case = case_map.get(cid)
        for r in runs:
            # 期待 references の「必ず出す図」を、生成された図の横にチェックリストとして並べる
            expected = []
            for ref in r["expected_references"]:
                figs = expected_figures(skills_dir / ref)
                items = "".join(f"<li>{e(f)}</li>" for f in figs) or "<li>—</li>"
                expected.append(f"<p><b>{e(_short_ref(ref))}</b></p><ul>{items}</ul>")
            thumbs = "".join(
                f"<figure><a href='{e(r['_dir'])}/files/{e(p)}'>"
                + (
                    f"<img loading=lazy src='{e(r['_dir'])}/files/{e(p)}' alt=''>"
                    if not p.lower().endswith(".pdf")
                    else "PDF"
                )
                + f"</a><figcaption>{e(p)}</figcaption></figure>"
                for p in r["images"]
            )
            timeline = " → ".join(
                f"{e(ev['path'].replace('-diagnostics', ''))}[{e(ev['via'])}]"
                for ev in r["skill_events"]
            )
            notes = []
            if r["missing_skills"] or r["missing_references"]:
                notes.append(
                    "読まれなかった: " + e(", ".join(r["missing_skills"] + r["missing_references"]))
                )
            if r["forbidden_hits"]:
                notes.append("禁止ヒット: " + e(", ".join(r["forbidden_hits"])))
            if r["timed_out"]:
                notes.append("タイムアウト")
            if r["permission_denials"]:
                denied = sorted({d.get("tool_name", "?") for d in r["permission_denials"]})
                notes.append("権限で拒否: " + e(", ".join(denied)))
            cards.append(
                f"<div class=card id='{e(r['_dir'])}'><h2 class={r['status']}>"
                f"{e(r['_dir'])} — {r['status']}</h2>"
                f"<pre>{e(case.prompt if case else '')}</pre>"
                + (f"<p class=muted>メモ: {e(case.note)}</p>" if case and case.note else "")
                + "".join(f"<p class=FAIL>{n}</p>" for n in notes)
                + f"<p>読んだ順: {timeline or '—'}</p>"
                + (
                    f"<p class=muted>判定表の在りか: {e(r['diagnostics_table_in'])}</p>"
                    if r.get("diagnostics_table_in")
                    else ""
                )
                + f"<div class=cols><div><div class=grid>{thumbs or '<p>図なし</p>'}</div></div>"
                "<div><p class=muted>references の「必ず出す図」</p>"
                f"{''.join(expected) or '—'}</div></div>"
                f"<details><summary>最終応答</summary><pre>{e(r['final_text'])}</pre></details>"
                "</div>"
            )
    cfg = run_meta.get("config", {})
    return (
        f"<title>skill eval {e(run_meta.get('run_id', ''))}</title><style>{CSS}</style><main>"
        f"<h1>skill 発火テスト {e(run_meta.get('run_id', ''))}</h1>"
        f"<p class=muted>claude {e(str(run_meta.get('claude_version', '')))} / model "
        f"{e(str(cfg.get('model') or '既定'))} / git {e(str(run_meta.get('git_head', '')))} / "
        f"skills hash {e(str(run_meta.get('skills_hash', ''))[:12])}</p>"
        "<p class=muted>判定は発火（期待した skill・references を読んだか、"
        "禁止したものを読んでいないか）だけ。図の中身は各カードで「必ず出す図」と見比べる。</p>"
        "<div class=scroll><table><thead><tr><th>ケース</th><th>種別</th><th>発火</th>"
        "<th>プロンプト</th><th>期待 references</th><th>発火した skill</th>"
        "<th>読んだ references</th>"
        "<th>禁止ヒット</th><th>図</th><th>読了→実行</th><th>判定表</th><th>時間 / 費用</th></tr>"
        f"</thead><tbody>{''.join(rows)}</tbody></table></div>{''.join(cards)}</main>"
    )


def write_report(run_dir: Path, cases: list[Case], skills_dir: Path) -> None:
    """run_dir に summary.md と index.html を書く。

    skills_dir は実行時点の skill のスナップショット（run_dir/skills_snapshot）を渡すと、
    後で skill を編集しても当時の「必ず出す図」で見比べられる。
    """
    meta_path = run_dir / "run.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    results = load_results(run_dir)
    (run_dir / "summary.md").write_text(build_markdown(meta, cases, results), encoding="utf-8")
    (run_dir / "index.html").write_text(
        build_html(meta, cases, results, skills_dir), encoding="utf-8"
    )
