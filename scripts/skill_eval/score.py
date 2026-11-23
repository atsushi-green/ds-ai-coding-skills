"""実行結果を、reference の「必ず出す図・値」1 項目ずつ「出た／出ない」で採点する。

採点表（checklists.yaml）に、項目ごとの見つけ方を正規表現で書く。当てる先は 2 つ:

- code: sandbox で作られたスクリプト（`.py`・`.ipynb`）
- report: 最終応答と、作られた `.md`・小さな `.csv`

report は文ごとに見て、「確認していません」のような否定を含む文は当たりにしない
（「安定性は確認していません」を「安定性を出した」と数えないため）。
図の項目は、図のファイルが 1 枚以上作られていることも条件にする。

正規表現による採点は、言い回しの違いで取りこぼしや誤検出がありうる。採点表を直したら、
実行結果のいくつかを目で見て確かめること。
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from skill_eval.report import load_results

CODE_SUFFIXES = {".py", ".ipynb"}
REPORT_SUFFIXES = {".md", ".csv"}
REPORT_MAX_BYTES = 20_000  # 行ごとの予測値のような大きな CSV は報告として読まない
SENTENCE_RE = re.compile(r"[。\n]")
# 「やっていない」と述べている文。report のパターンがこの文に当たっても数えない
NEGATION_RE = re.compile(
    r"(して|でき|行って|出して|試して)(は)?(い)?(ません|ない)|未(確認|実施|検証|評価)|省略し|見送"
)
ITEM_KEYS = {"id", "kind", "label", "code", "code_all", "report", "report_all", "allow_negation"}


@dataclass(frozen=True)
class Item:
    """採点する 1 項目。

    `code`・`report` は「どれか 1 つに当たれば満たす」、`code_all`・`report_all` は
    「すべてに当たれば満たす」。書いたグループのうち 1 つでも満たせば「出た」とする。

    Attributes:
        id: 項目の ID（reference 内で一意）。
        kind: `図` または `値`。
        label: 表に出す名前。
        code: スクリプトに当てる正規表現（どれか）。
        code_all: スクリプトに当てる正規表現（すべて）。
        report: 報告に当てる正規表現（どれか）。
        report_all: 報告に当てる正規表現（すべて）。
        allow_negation: 否定の文でも当たりにするか（「チューニングはしていません」と
            書くこと自体が報告になる項目に使う）。
    """

    id: str
    kind: str
    label: str
    code: tuple[str, ...] = ()
    code_all: tuple[str, ...] = ()
    report: tuple[str, ...] = ()
    report_all: tuple[str, ...] = ()
    allow_negation: bool = False


def load_checklists(path: Path) -> dict[str, list[Item]]:
    """採点表を読む。キーは reference のファイル名（拡張子なし）。

    Raises:
        ValueError: 未知のキー、ID の重複、見つけ方が 1 つも無い項目、不正な正規表現がある場合。
    """
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    checklists: dict[str, list[Item]] = {}
    for ref, spec in raw.items():
        items: list[Item] = []
        for entry in spec["items"]:
            unknown = set(entry) - ITEM_KEYS
            if unknown:
                raise ValueError(f"{ref}/{entry.get('id')}: 未知のキー {sorted(unknown)}")
            item = Item(
                id=str(entry["id"]),
                kind=str(entry["kind"]),
                label=str(entry["label"]),
                code=tuple(entry.get("code", [])),
                code_all=tuple(entry.get("code_all", [])),
                report=tuple(entry.get("report", [])),
                report_all=tuple(entry.get("report_all", [])),
                allow_negation=bool(entry.get("allow_negation", False)),
            )
            if item.kind not in ("図", "値"):
                raise ValueError(f"{ref}/{item.id}: kind は 図 か 値（{item.kind}）")
            patterns = item.code + item.code_all + item.report + item.report_all
            if not patterns:
                raise ValueError(f"{ref}/{item.id}: 見つけ方（code / report）が 1 つも無い")
            for pattern in patterns:
                re.compile(pattern)  # 不正なら re.error（ValueError の一種）で止まる
            items.append(item)
        ids = [i.id for i in items]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{ref}: 項目の ID が重複している")
        checklists[str(ref)] = items
    return checklists


def gather_texts(files_dir: Path, result: dict[str, Any]) -> tuple[str, list[str]]:
    """採点に使う本文を集める。

    Args:
        files_dir: 回収した生成物のディレクトリ（`<case>/r<n>/files`）。
        result: その実行の result.json。

    Returns:
        (スクリプトをつなげた本文, 報告を文に分けたリスト)。
    """
    code_parts: list[str] = []
    report_parts: list[str] = [str(result.get("final_text") or "")]
    for rel in result.get("changed_files", []):
        path = files_dir / rel
        suffix = path.suffix.lower()
        if not path.is_file():
            continue
        if suffix in CODE_SUFFIXES:
            code_parts.append(path.read_text(encoding="utf-8", errors="replace"))
        elif suffix in REPORT_SUFFIXES and path.stat().st_size <= REPORT_MAX_BYTES:
            report_parts.append(path.read_text(encoding="utf-8", errors="replace"))
    sentences = [s for part in report_parts for s in SENTENCE_RE.split(part) if s.strip()]
    return "\n".join(code_parts), sentences


def _in_report(pattern: str, sentences: list[str], allow_negation: bool) -> bool:
    regex = re.compile(pattern, re.IGNORECASE)
    return any(regex.search(s) and (allow_negation or not NEGATION_RE.search(s)) for s in sentences)


def item_present(item: Item, code: str, sentences: list[str], has_image: bool) -> bool:
    """項目が「出た」かどうか。

    Args:
        item: 採点する項目。
        code: スクリプトをつなげた本文。
        sentences: 報告を文に分けたリスト。
        has_image: 図のファイルが 1 枚以上作られたか。
    """
    if item.kind == "図" and not has_image:
        return False
    groups: list[bool] = []
    if item.code:
        groups.append(any(re.search(p, code, re.IGNORECASE) for p in item.code))
    if item.code_all:
        groups.append(all(re.search(p, code, re.IGNORECASE) for p in item.code_all))
    if item.report:
        groups.append(any(_in_report(p, sentences, item.allow_negation) for p in item.report))
    if item.report_all:
        groups.append(all(_in_report(p, sentences, item.allow_negation) for p in item.report_all))
    return any(groups)


def score_run(run_dir: Path, checklists: dict[str, list[Item]]) -> list[dict[str, Any]]:
    """1 つの実行ディレクトリを採点する。

    採点表のある reference を期待しているケースだけが対象。実行が落ちた（ERROR）ものは除く。
    skill を外した条件なのに、プロジェクトの外にある同名の skill が見えていた実行も除く
    （外したことにならないため）。

    Returns:
        1 項目 1 行の辞書（run / arm / case / rep / reference / item / kind / label / present）。
    """
    meta_path = run_dir / "run.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    arm = str((meta.get("arm") or {}).get("name") or "full")
    rows: list[dict[str, Any]] = []
    for res in load_results(run_dir):
        if res["status"] == "ERROR":
            continue
        if arm != "full" and res.get("outside_skill_copies"):
            continue
        code, sentences = gather_texts(run_dir / res["_dir"] / "files", res)
        for ref_path in res["expected_references"]:
            ref = Path(ref_path).stem
            for item in checklists.get(ref, []):
                rows.append(
                    {
                        "run": meta.get("run_id") or run_dir.name,
                        "arm": arm,
                        "case": res["case_id"],
                        "rep": res["_dir"].rsplit("/", 1)[-1],
                        "reference": ref,
                        "item": item.id,
                        "kind": item.kind,
                        "label": item.label,
                        "present": int(item_present(item, code, sentences, bool(res["images"]))),
                    }
                )
    return rows


def build_score_markdown(rows: list[dict[str, Any]], arms: list[str]) -> str:
    """採点結果を、ケースごとの「項目 × 条件」の表にする。

    セルは「出た回数 / 実行回数」。最後に条件ごとの合計（全項目・全実行のうち出た割合）を出す。

    Args:
        rows: `score_run` の結果をつなげたもの。
        arms: 表に出す条件の順序。
    """
    cell: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    labels: dict[tuple[str, str], str] = {}
    for r in rows:
        cell[(r["case"], r["item"], r["arm"])].append(r["present"])
        labels[(r["case"], r["item"])] = f"{r['kind']}: {r['label']}"
    lines = ["# 採点結果（出た回数 / 実行回数）", ""]
    totals: dict[str, list[int]] = defaultdict(list)
    for case in dict.fromkeys(r["case"] for r in rows):
        lines += [
            f"## {case}",
            "",
            "| 項目 | " + " | ".join(arms) + " |",
            "|---|" + "---|" * len(arms),
        ]
        case_totals: dict[str, list[int]] = defaultdict(list)
        for (c, item), label in labels.items():
            if c != case:
                continue
            cells = []
            for arm in arms:
                hits = cell.get((case, item, arm), [])
                cells.append(f"{sum(hits)}/{len(hits)}" if hits else "—")
                case_totals[arm] += hits
                totals[arm] += hits
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        lines.append(
            "| **計** | "
            + " | ".join(
                f"{sum(case_totals[a])}/{len(case_totals[a])}" if case_totals[a] else "—"
                for a in arms
            )
            + " |"
        )
        lines.append("")
    lines += ["## 全体", "", "| 条件 | 出た / 全項目 × 実行 | 割合 |", "|---|---|---|"]
    for arm in arms:
        hits = totals[arm]
        rate = f"{100 * sum(hits) / len(hits):.0f}%" if hits else "—"
        lines.append(f"| {arm} | {sum(hits)}/{len(hits)} | {rate} |")
    return "\n".join(lines) + "\n"


def write_scores(run_dirs: list[Path], checklist_path: Path, out_dir: Path) -> list[dict[str, Any]]:
    """実行ディレクトリ群を採点し、out_dir に scores.csv と scores.md を書く。

    Args:
        run_dirs: 採点する実行ディレクトリ（条件ごと）。表の列は、この順に並ぶ。
        checklist_path: 採点表の YAML。
        out_dir: 出力先。

    Returns:
        1 項目 1 行の採点結果。
    """
    checklists = load_checklists(checklist_path)
    rows = [row for run_dir in run_dirs for row in score_run(run_dir, checklists)]
    arms = list(dict.fromkeys(r["arm"] for r in rows))
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = ["run", "arm", "case", "rep", "reference", "item", "kind", "label", "present"]
    with (out_dir / "scores.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "scores.md").write_text(build_score_markdown(rows, arms), encoding="utf-8")
    return rows
