"""「必ず出す図・値」の採点（`run_skill_eval.py score`）のテスト。claude は起動しない。

検証する契約:
- 採点表は実在の reference を指し、項目の ID が重複せず、どの項目にも見つけ方がある
- スクリプトに当てる見つけ方と、報告に当てる見つけ方のどちらでも「出た」にできる
- 「確認していません」と書いてあるだけの項目は「出た」に数えない
- 図の項目は、図のファイルが作られていなければ「出た」に数えない
- 実行が落ちたものは採点に入れない
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import run_skill_eval
from skill_eval.score import (
    Item,
    build_score_markdown,
    item_present,
    load_checklists,
    score_run,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
CHECKLISTS = REPO_ROOT / "scripts" / "skill_eval" / "checklists.yaml"
GLM_REF = "statistical-inference-diagnostics/references/glm.md"


def test_checklists_point_at_real_references() -> None:
    checklists = load_checklists(CHECKLISTS)
    refs = {p.stem for p in SKILLS_DIR.glob("*-diagnostics/references/*.md")}
    assert set(checklists) <= refs, f"存在しない reference: {set(checklists) - refs}"
    for ref, items in checklists.items():
        kinds = {i.kind for i in items}
        assert kinds == {"図", "値"}, f"{ref}: 図と値の両方の項目があること"


def test_load_checklists_rejects_bad_specs(tmp_path: Path) -> None:
    bad = tmp_path / "c.yaml"
    bad.write_text("x:\n  items:\n    - {id: a, kind: 図, label: l}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="見つけ方"):
        load_checklists(bad)
    bad.write_text("x:\n  items:\n    - {id: a, kind: 表, label: l, code: [a]}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="kind"):
        load_checklists(bad)
    bad.write_text(
        "x:\n  items:\n    - {id: a, kind: 値, label: l, code: [a]}\n"
        "    - {id: a, kind: 値, label: m, code: [b]}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="重複"):
        load_checklists(bad)


def test_item_present_matches_code_or_report() -> None:
    vif = Item(id="v", kind="値", label="VIF", report=("VIF",))
    assert item_present(vif, "", ["VIF の最大値は 2.67"], has_image=False)
    assert not item_present(vif, "", ["オッズ比は 0.08"], has_image=False)

    both = Item(
        id="s", kind="値", label="安定性", code=(r"adjusted_rand_score\(",), report=("ARI",)
    )
    # どちらか 1 つのグループを満たせばよい
    assert item_present(both, "adjusted_rand_score(a, b)", [], has_image=False)
    assert item_present(both, "", ["ARI は 0.99"], has_image=False)

    pair = Item(id="p", kind="値", label="AUC・AP", report_all=("AUC", r"\bAP\b"))
    assert item_present(pair, "", ["AUC 0.85", "AP 0.82"], has_image=False)
    assert not item_present(pair, "", ["AUC 0.85"], has_image=False)


def test_negated_sentences_do_not_count() -> None:
    stability = Item(id="s", kind="値", label="安定性", report=("安定性",))
    # 「やっていない」と書いてあるだけなら、出たことにしない
    assert not item_present(stability, "", ["安定性は確認していません"], has_image=False)
    assert item_present(stability, "", ["安定性は ARI 0.99 で十分"], has_image=False)
    # 「チューニングはしていません」と書くこと自体が報告になる項目は、否定でも数える
    tuning = Item(id="t", kind="値", label="調整", report=("チューニング",), allow_negation=True)
    assert item_present(tuning, "", ["チューニングはしていません"], has_image=False)


def test_figure_items_need_an_image() -> None:
    roc = Item(id="r", kind="図", label="ROC", code=(r"roc_curve\(",))
    assert item_present(roc, "fpr, tpr, _ = roc_curve(y, p)", [], has_image=True)
    # 計算しただけで図を保存していなければ、図は出ていない
    assert not item_present(roc, "fpr, tpr, _ = roc_curve(y, p)", [], has_image=False)


def _write_run(run_dir: Path, arm: str, results: dict[str, dict]) -> Path:
    for key, res in results.items():
        out = run_dir / key
        (out / "files" / "scripts").mkdir(parents=True)
        (out / "files" / "scripts" / "a.py").write_text(res.pop("_code", ""), encoding="utf-8")
        base = {
            "case_id": key.split("/")[0],
            "kind": "explicit",
            "status": "PASS",
            "images": [],
            "changed_files": ["scripts/a.py"],
            "final_text": "",
            "expected_references": [GLM_REF],
        }
        (out / "result.json").write_text(json.dumps({**base, **res}), encoding="utf-8")
    meta = {"run_id": run_dir.name, "arm": {"name": arm}}
    (run_dir / "run.json").write_text(json.dumps(meta), encoding="utf-8")
    return run_dir


def test_score_run_and_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    full = _write_run(
        tmp_path / "full",
        "full",
        {
            "glm-explicit/r1": {
                "_code": "roc_curve(y, p)",
                "images": ["a.png"],
                "final_text": "VIF は 2.6。EPV は 58",
            },
            "glm-explicit/r2": {"_code": "roc_curve(y, p)", "images": ["a.png"]},
            # 利用上限などで落ちた実行は、出なかったことにせず採点から外す
            "glm-explicit/r3": {"status": "ERROR"},
        },
    )
    thin = _write_run(
        tmp_path / "thin",
        "no-diagnostics",
        {"glm-explicit/r1": {"final_text": "VIF は確認していません"}},
    )
    checklists = load_checklists(CHECKLISTS)
    rows = score_run(full, checklists) + score_run(thin, checklists)
    assert {r["rep"] for r in rows if r["arm"] == "full"} == {"r1", "r2"}

    table = build_score_markdown(rows, ["no-diagnostics", "full"])
    assert "| 図: ROC 曲線 | 0/1 | 2/2 |" in table
    assert "| 値: VIF の最大値 | 0/1 | 1/2 |" in table
    n_items = len(checklists["glm"])
    assert f"| no-diagnostics | 0/{n_items} | 0% |" in table

    run_skill_eval.main(["score", str(thin), str(full), "--out", str(tmp_path / "out")])
    assert (tmp_path / "out" / "scores.csv").read_text(encoding="utf-8").count(
        "\n"
    ) == 3 * n_items + 1
    assert "| 値: EPV | 0/1 | 1/2 |" in capsys.readouterr().out
