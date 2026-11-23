"""2 つの実行結果（skill あり・なしなど）を、ケースごとに横に並べたレポートを作る。

並べるのは機械的に数えられる事実だけ（図の枚数、判定表の有無、生成物、時間と費用、最終応答）。
図と値が references の要求を満たしているかは、同じページに出す「必ず出す図」「必ず出す値」の
チェックリストと見比べて人が判断する。
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

from skill_eval.cases import Case, expected_figures, expected_values
from skill_eval.evaluate import IMAGE_SUFFIXES
from skill_eval.report import CSS, STATUS_MARK, load_results

# 条件が揃っていないと比較にならない設定（run.json の config のキー → 表示名）
COMPARED_SETTINGS = {"model": "model", "effort": "effort"}
COMPARE_CSS = """
.pair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}
@media (max-width:900px){.pair{grid-template-columns:1fr}}
.arm{border:1px solid var(--line);border-radius:8px;padding:8px 12px}
.arm h3{margin:4px 0 8px;font-size:14px}
.warn{color:var(--warn)}
.checklist{columns:2;column-gap:32px}
@media (max-width:900px){.checklist{columns:1}}
"""


def _load_meta(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _arm_name(meta: dict[str, Any]) -> str:
    return str((meta.get("arm") or {}).get("name") or "full")


def setting_mismatches(meta_a: dict[str, Any], meta_b: dict[str, Any]) -> list[str]:
    """2 つの実行で揃っていない条件を、表示用の文にして返す。

    モデル・effort・Claude Code のバージョンが違うと、skill の有無による差と区別できない。
    """
    notes = []
    cfg_a, cfg_b = meta_a.get("config") or {}, meta_b.get("config") or {}
    for key, name in COMPARED_SETTINGS.items():
        if cfg_a.get(key) != cfg_b.get(key):
            notes.append(
                f"{name} が違う（{cfg_a.get(key) or '既定'} / {cfg_b.get(key) or '既定'}）"
            )
    if meta_a.get("claude_version") != meta_b.get("claude_version"):
        notes.append(
            "claude のバージョンが違う"
            f"（{meta_a.get('claude_version')} / {meta_b.get('claude_version')}）"
        )
    if meta_a.get("skills_hash") != meta_b.get("skills_hash"):
        notes.append("間引く前の skill の内容が違う（skills の内容ハッシュが一致しない）")
    return notes


def pair_results(
    results_a: list[dict[str, Any]], results_b: list[dict[str, Any]]
) -> list[tuple[str, dict[str, Any] | None, dict[str, Any] | None]]:
    """ケース ID と反復番号（`<case>/r<n>`）で 2 つの実行の結果を対にする。

    Returns:
        (`<case>/r<n>`, A の結果, B の結果) のリスト。片方にしか無いものは None で埋める。
    """
    by_a = {r["_dir"]: r for r in results_a}
    by_b = {r["_dir"]: r for r in results_b}
    return [(key, by_a.get(key), by_b.get(key)) for key in sorted(set(by_a) | set(by_b))]


def _table_cell(res: dict[str, Any] | None) -> str:
    if res is None:
        return "—"
    if not res.get("has_diagnostics_table"):
        return "×"
    where = res.get("diagnostics_table_in")
    return "○" if where in (None, "最終応答") else "○（ファイル）"


def _cost_cell(res: dict[str, Any] | None) -> str:
    if res is None:
        return "—"
    parts = []
    if res.get("duration_ms") is not None:
        parts.append(f"{res['duration_ms'] / 60000:.1f}分")
    if res.get("total_cost_usd") is not None:
        parts.append(f"${res['total_cost_usd']:.2f}")
    return " / ".join(parts) or "—"


def _n_images(res: dict[str, Any] | None) -> str:
    return "—" if res is None else str(len(res["images"]))


def _other_files(res: dict[str, Any]) -> list[str]:
    # 図と、依存の追加で必ず変わる uv.lock を除いた生成物
    return [
        p
        for p in res["changed_files"]
        if Path(p).suffix.lower() not in IMAGE_SUFFIXES and Path(p).name != "uv.lock"
    ]


def _totals(results: list[dict[str, Any] | None]) -> tuple[int, int, int, float]:
    done = [r for r in results if r is not None]
    return (
        len(done),
        sum(len(r["images"]) for r in done),
        sum(bool(r.get("has_diagnostics_table")) for r in done),
        sum(r.get("total_cost_usd") or 0.0 for r in done),
    )


def _checklist(
    res: dict[str, Any] | None, skills_dir: Path
) -> list[tuple[str, list[str], list[str]]]:
    """期待 references ごとの (短い名前, 必ず出す図, 必ず出す値)。"""
    if res is None:
        return []
    out = []
    for ref in res["expected_references"]:
        path = skills_dir / ref
        if path.is_file():
            out.append((Path(ref).stem, expected_figures(path), expected_values(path)))
    return out


def build_compare_markdown(
    meta_a: dict[str, Any],
    meta_b: dict[str, Any],
    results_a: list[dict[str, Any]],
    results_b: list[dict[str, Any]],
    cases: list[Case],
    skills_dir: Path,
    link_a: str,
    link_b: str,
) -> str:
    """比較レポートを Markdown で返す。

    Args:
        meta_a: A（基準にする側。ふつうは full）の run.json。
        meta_b: B（比べる側。ふつうは skill を間引いた arm）の run.json。
        results_a: A の result.json（`_dir` 付き）。
        results_b: B の result.json（`_dir` 付き）。
        cases: ケース定義（プロンプトの表示に使う）。
        skills_dir: 「必ず出す図・値」を読む skill のディレクトリ（間引く前のもの）。
        link_a: レポートの置き場所から A の実行ディレクトリへの相対パス。
        link_b: 同じく B への相対パス。
    """
    name_a, name_b = _arm_name(meta_a), _arm_name(meta_b)
    case_map = {c.id: c for c in cases}
    pairs = pair_results(results_a, results_b)
    cfg_a, cfg_b = meta_a.get("config") or {}, meta_b.get("config") or {}
    lines = [
        f"# 実行結果の比較: {name_a} と {name_b}",
        "",
        "| | A | B |",
        "|---|---|---|",
        f"| 実行 | {meta_a.get('run_id', '')} | {meta_b.get('run_id', '')} |",
        f"| arm | {name_a} | {name_b} |",
        f"| arm の内容 | {(meta_a.get('arm') or {}).get('description', '')} "
        f"| {(meta_b.get('arm') or {}).get('description', '')} |",
        f"| model / effort | {cfg_a.get('model') or '既定'} / {cfg_a.get('effort') or '既定'} "
        f"| {cfg_b.get('model') or '既定'} / {cfg_b.get('effort') or '既定'} |",
        f"| claude | {meta_a.get('claude_version', '')} | {meta_b.get('claude_version', '')} |",
        f"| git HEAD | {meta_a.get('git_head', '')} | {meta_b.get('git_head', '')} |",
        "",
    ]
    lines += [f"> 注意: {note}" for note in setting_mismatches(meta_a, meta_b)]
    lines += [
        "",
        "図の枚数・判定表の有無・時間と費用は機械的に数えたもの。図と値が references の要求を"
        "満たすかは、各ケースのチェックリストと生成物を見比べて人が判断する。",
        "",
        f"| ケース | 図（{name_a}） | 図（{name_b}） | 判定表（{name_a}） | 判定表（{name_b}） "
        f"| 時間 / 費用（{name_a}） | 時間 / 費用（{name_b}） |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, a, b in pairs:
        lines.append(
            f"| {key} | {_n_images(a)} | {_n_images(b)} | {_table_cell(a)} | {_table_cell(b)} "
            f"| {_cost_cell(a)} | {_cost_cell(b)} |"
        )
    n_a, img_a, tab_a, cost_a = _totals([a for _, a, _ in pairs])
    n_b, img_b, tab_b, cost_b = _totals([b for _, _, b in pairs])
    lines += [
        f"| 合計 | {img_a} | {img_b} | {tab_a}/{n_a} | {tab_b}/{n_b} "
        f"| ${cost_a:.2f} | ${cost_b:.2f} |",
        "",
    ]
    for key, a, b in pairs:
        case = case_map.get((a or b or {}).get("case_id", ""))
        lines += [f"## {key}", ""]
        if case:
            lines += ["```text", case.prompt, "```", ""]
        for ref, figs, vals in _checklist(a or b, skills_dir):
            lines += [f"references の要求（{ref}）:", ""]
            lines += [f"- 図: {f}" for f in figs]
            lines += [f"- 値: {v}" for v in vals]
            lines.append("")
        for name, res, link in ((name_a, a, link_a), (name_b, b, link_b)):
            if res is None:
                lines += [f"### {name} — 実行なし", ""]
                continue
            lines += [f"### {name} — {STATUS_MARK[res['status']]} {res['status']}", ""]
            lines.append(
                f"- 図 {len(res['images'])} 枚 / 判定表 {_table_cell(res)} / {_cost_cell(res)}"
            )
            lines += [f"  - [{p}]({link}/{res['_dir']}/files/{p})" for p in res["images"]]
            others = _other_files(res)
            if others:
                lines.append(f"- そのほかの生成物: {', '.join(f'`{p}`' for p in others)}")
            lines += ["", "<details><summary>最終応答</summary>", "", res["final_text"], ""]
            lines += ["</details>", ""]
    return "\n".join(lines)


def build_compare_html(
    meta_a: dict[str, Any],
    meta_b: dict[str, Any],
    results_a: list[dict[str, Any]],
    results_b: list[dict[str, Any]],
    cases: list[Case],
    skills_dir: Path,
    link_a: str,
    link_b: str,
) -> str:
    """図のサムネイルを左右に並べた比較ページを返す（引数は `build_compare_markdown` と同じ）。"""
    e = html.escape
    name_a, name_b = _arm_name(meta_a), _arm_name(meta_b)
    case_map = {c.id: c for c in cases}
    pairs = pair_results(results_a, results_b)

    rows = "".join(
        f"<tr><td><a href='#{e(key)}'>{e(key)}</a></td>"
        f"<td>{_n_images(a)}</td><td>{_n_images(b)}</td>"
        f"<td>{e(_table_cell(a))}</td><td>{e(_table_cell(b))}</td>"
        f"<td>{e(_cost_cell(a))}</td><td>{e(_cost_cell(b))}</td></tr>"
        for key, a, b in pairs
    )
    n_a, img_a, tab_a, cost_a = _totals([a for _, a, _ in pairs])
    n_b, img_b, tab_b, cost_b = _totals([b for _, _, b in pairs])
    rows += (
        f"<tr><th>合計</th><th>{img_a}</th><th>{img_b}</th><th>{tab_a}/{n_a}</th>"
        f"<th>{tab_b}/{n_b}</th><th>${cost_a:.2f}</th><th>${cost_b:.2f}</th></tr>"
    )

    def arm_block(name: str, res: dict[str, Any] | None, link: str) -> str:
        if res is None:
            return f"<div class=arm><h3>{e(name)} — 実行なし</h3></div>"
        base = f"{link}/{res['_dir']}/files"
        thumbs = "".join(
            f"<figure><a href='{e(base)}/{e(p)}'>"
            + (
                "PDF"
                if p.lower().endswith(".pdf")
                else f"<img loading=lazy src='{e(base)}/{e(p)}' alt=''>"
            )
            + f"</a><figcaption>{e(p)}</figcaption></figure>"
            for p in res["images"]
        )
        others = ", ".join(f"<code>{e(p)}</code>" for p in _other_files(res))
        return (
            f"<div class=arm><h3 class={res['status']}>{e(name)} — {res['status']}</h3>"
            f"<p>図 {len(res['images'])} 枚 / 判定表 {e(_table_cell(res))} / "
            f"{e(_cost_cell(res))}</p>"
            f"<div class=grid>{thumbs or '<p class=muted>図なし</p>'}</div>"
            + (f"<p class=muted>そのほかの生成物: {others}</p>" if others else "")
            + "<details><summary>最終応答</summary>"
            f"<pre>{e(res['final_text'])}</pre></details></div>"
        )

    cards = []
    for key, a, b in pairs:
        case = case_map.get((a or b or {}).get("case_id", ""))
        checklist = "".join(
            f"<p><b>{e(ref)}</b></p><ul>"
            + "".join(f"<li>図: {e(f)}</li>" for f in figs)
            + "".join(f"<li>値: {e(v)}</li>" for v in vals)
            + "</ul>"
            for ref, figs, vals in _checklist(a or b, skills_dir)
        )
        cards.append(
            f"<div class=card id='{e(key)}'><h2>{e(key)}</h2>"
            f"<pre>{e(case.prompt if case else '')}</pre>"
            f"<div class=pair>{arm_block(name_a, a, link_a)}{arm_block(name_b, b, link_b)}</div>"
            "<details><summary>references の「必ず出す図」「必ず出す値」</summary>"
            f"<div class=checklist>{checklist or '—'}</div></details></div>"
        )

    cfg_a, cfg_b = meta_a.get("config") or {}, meta_b.get("config") or {}

    def meta_line(name: str, meta: dict[str, Any], cfg: dict[str, Any]) -> str:
        return (
            f"<p class=muted><b>{e(name)}</b>: {e(str(meta.get('run_id', '')))} / "
            f"{e(str((meta.get('arm') or {}).get('description', '')))} / model "
            f"{e(str(cfg.get('model') or '既定'))} / "
            f"effort {e(str(cfg.get('effort') or '既定'))} / "
            f"claude {e(str(meta.get('claude_version', '')))} / "
            f"git {e(str(meta.get('git_head', '')))}</p>"
        )

    return (
        f"<title>skill eval compare {e(name_a)} vs {e(name_b)}</title>"
        f"<style>{CSS}{COMPARE_CSS}</style><main>"
        f"<h1>実行結果の比較: {e(name_a)} と {e(name_b)}</h1>"
        + meta_line(name_a, meta_a, cfg_a)
        + meta_line(name_b, meta_b, cfg_b)
        + "".join(f"<p class=warn>注意: {e(n)}</p>" for n in setting_mismatches(meta_a, meta_b))
        + "<p class=muted>図の枚数・判定表の有無・時間と費用は機械的に数えたもの。"
        "図と値が references の要求を満たすかは、各カードのチェックリストと生成物を見比べて"
        "人が判断する。</p>"
        f"<div class=scroll><table><thead><tr><th>ケース</th><th>図（{e(name_a)}）</th>"
        f"<th>図（{e(name_b)}）</th><th>判定表（{e(name_a)}）</th><th>判定表（{e(name_b)}）</th>"
        f"<th>時間 / 費用（{e(name_a)}）</th><th>時間 / 費用（{e(name_b)}）</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>{''.join(cards)}</main>"
    )


def write_compare(
    run_a: Path, run_b: Path, out_dir: Path, cases: list[Case], skills_dir: Path
) -> None:
    """out_dir に compare.md と compare.html を書く。

    Args:
        run_a: 基準にする実行のディレクトリ（ふつうは full）。
        run_b: 比べる実行のディレクトリ（ふつうは skill を間引いた arm）。
        out_dir: レポートの置き場所。図は run_a・run_b を相対パスで参照する。
        cases: ケース定義。
        skills_dir: 「必ず出す図・値」を読む skill のディレクトリ。

    Raises:
        FileNotFoundError: どちらかの実行に結果（result.json）が 1 件も無い場合。
    """
    results_a, results_b = load_results(run_a), load_results(run_b)
    for run_dir, results in ((run_a, results_a), (run_b, results_b)):
        if not results:
            raise FileNotFoundError(f"結果（result.json）が無い: {run_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    # レポートを開いた場所から図に届くよう、置き場所からの相対パスにする
    link_a = Path(os.path.relpath(run_a.resolve(), out_dir.resolve())).as_posix()
    link_b = Path(os.path.relpath(run_b.resolve(), out_dir.resolve())).as_posix()
    args = (_load_meta(run_a), _load_meta(run_b), results_a, results_b, cases, skills_dir)
    (out_dir / "compare.md").write_text(
        build_compare_markdown(*args, link_a, link_b), encoding="utf-8"
    )
    (out_dir / "compare.html").write_text(
        build_compare_html(*args, link_a, link_b), encoding="utf-8"
    )
