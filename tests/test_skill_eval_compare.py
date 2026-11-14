"""2 つの実行結果を並べる比較レポート（`run_skill_eval.py compare`）のテスト。claude は起動しない。

検証する契約:
- 2 つの実行の結果が、ケース ID と反復番号で対になる（片方にしか無いものも落とさない）
- 図の枚数・判定表の有無・費用の合計が、result.json の値どおりに出る
- モデルや effort が揃っていない比較には注意書きが出る
- レポートから図へのリンクが、レポートの置き場所からの相対パスになっている
- すべての references から「必ず出す値」の項目名が取れる（チェックリストが空にならない）
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import run_skill_eval
from skill_eval.cases import expected_values
from skill_eval.compare import pair_results, setting_mismatches, write_compare

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
GLM_REF = "statistical-inference-diagnostics/references/glm.md"


def _result(case_id: str, **overrides: object) -> dict:
    base = {
        "case_id": case_id,
        "kind": "explicit",
        "status": "PASS",
        "images": [],
        "changed_files": [],
        "has_diagnostics_table": False,
        "diagnostics_table_in": None,
        "duration_ms": 60000,
        "total_cost_usd": 0.5,
        "final_text": "",
        "expected_references": [GLM_REF],
    }
    return {**base, **overrides}


def _write_run(run_dir: Path, arm: str, results: list[dict], **config: object) -> Path:
    """result.json と run.json だけを持つ実行ディレクトリを作る。"""
    for res in results:
        out = run_dir / res["case_id"] / "r1"
        out.mkdir(parents=True)
        (out / "result.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    meta = {
        "run_id": run_dir.name,
        "claude_version": "2.1.310",
        "skills_hash": "abc",
        "config": {"model": "claude-opus-5-5", "effort": "medium", **config},
        "arm": {"name": arm, "description": f"{arm} の説明", "operations": []},
    }
    (run_dir / "run.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return run_dir


@pytest.fixture
def two_runs(tmp_path: Path) -> tuple[Path, Path]:
    full = _write_run(
        tmp_path / "runs" / "a-full",
        "full",
        [
            _result(
                "glm-explicit",
                images=["outputs/diagnostics/x_glm/fig.png"],
                changed_files=["outputs/diagnostics/x_glm/fig.png", "scripts/logit.py", "uv.lock"],
                has_diagnostics_table=True,
                diagnostics_table_in="最終応答",
                total_cost_usd=0.65,
                final_text="| 診断項目 | 実測値 |",
            ),
            _result("cluster-kmeans", total_cost_usd=0.9),
        ],
    )
    thinned = _write_run(
        tmp_path / "runs" / "b-no-diagnostics",
        "no-diagnostics",
        [
            _result(
                "glm-explicit",
                status="DONE",
                changed_files=["scripts/logit.py"],
                total_cost_usd=0.36,
                final_text="当てはまりは確認していません",
            )
        ],
    )
    return full, thinned


def test_pair_results_keeps_cases_that_only_one_run_has() -> None:
    a = [{"_dir": "x/r1", "v": 1}, {"_dir": "y/r1", "v": 2}]
    b = [{"_dir": "y/r1", "v": 3}, {"_dir": "z/r1", "v": 4}]
    pairs = pair_results(a, b)
    assert [key for key, _, _ in pairs] == ["x/r1", "y/r1", "z/r1"]
    assert pairs[0][2] is None and pairs[2][1] is None
    assert (pairs[1][1], pairs[1][2]) == (a[1], b[0])


def test_setting_mismatches_reports_what_differs() -> None:
    base = {"config": {"model": "m", "effort": "medium"}, "claude_version": "1", "skills_hash": "h"}
    assert setting_mismatches(base, base) == []
    other = {"config": {"model": "m", "effort": "max"}, "claude_version": "2", "skills_hash": "h"}
    notes = setting_mismatches(base, other)
    # effort が違うと、skill の有無による差と区別できない
    assert len(notes) == 2
    assert "effort" in notes[0] and "medium / max" in notes[0]
    assert "バージョン" in notes[1]


def test_write_compare_counts_and_links(two_runs: tuple[Path, Path], tmp_path: Path) -> None:
    full, thinned = two_runs
    out = tmp_path / "report" / "cmp"
    write_compare(full, thinned, out, [], SKILLS_DIR)

    md = (out / "compare.md").read_text(encoding="utf-8")
    assert "| glm-explicit/r1 | 1 | 0 | ○ | × | 1.0分 / $0.65 | 1.0分 / $0.36 |" in md
    # 片方にしか無いケースも行として残り、合計は実行できた件数を分母にする
    assert "| cluster-kmeans/r1 | 0 | — | × | — | 1.0分 / $0.90 | — |" in md
    assert "| 合計 | 1 | 0 | 1/2 | 0/1 | $1.55 | $0.36 |" in md
    assert "### no-diagnostics — 実行なし" in md
    # 図以外の生成物（uv.lock は除く）と、references の要求がチェックリストとして出る
    assert "そのほかの生成物: `scripts/logit.py`" in md
    assert "- 値: 共通: VIF (max)" in md
    assert "当てはまりは確認していません" in md
    assert "注意:" not in md

    page = (out / "compare.html").read_text(encoding="utf-8")
    # レポートを置いた場所から図に届く相対パス
    assert "../../runs/a-full/glm-explicit/r1/files/outputs/diagnostics/x_glm/fig.png" in page
    assert "図なし" in page


def test_write_compare_warns_when_settings_differ(tmp_path: Path) -> None:
    a = _write_run(tmp_path / "a", "full", [_result("glm-explicit")])
    b = _write_run(tmp_path / "b", "no-diagnostics", [_result("glm-explicit")], effort="max")
    write_compare(a, b, tmp_path / "out", [], SKILLS_DIR)
    assert "注意: effort が違う（medium / max）" in (tmp_path / "out/compare.md").read_text("utf-8")
    assert "class=warn" in (tmp_path / "out/compare.html").read_text("utf-8")


def test_write_compare_stops_on_a_run_without_results(tmp_path: Path) -> None:
    a = _write_run(tmp_path / "a", "full", [_result("glm-explicit")])
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError, match="result.json"):
        write_compare(a, tmp_path / "empty", tmp_path / "out", [], SKILLS_DIR)


def test_compare_command_writes_next_to_the_first_run(
    two_runs: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    full, thinned = two_runs
    run_skill_eval.main(["compare", str(full), str(thinned)])
    out = full.parent / "compare-a-full__b-no-diagnostics"
    assert (out / "compare.html").is_file()
    # 実行ディレクトリに cases.yaml が無ければ、リポジトリのケース定義からプロンプトを出す
    assert "ロジスティック回帰" in (out / "compare.md").read_text(encoding="utf-8")
    assert "compare.html" in capsys.readouterr().out


def test_expected_values_reads_the_item_column(tmp_path: Path) -> None:
    ref = tmp_path / "x.md"
    ref.write_text(
        "## 必ず出す図\n\n| 条件 | 出す図 |\n|---|---|\n| a | 図 1 |\n\n"
        "## 必ず出す値\n\n| 区分 | 項目 | 合格基準 |\n|---|---|---|\n"
        "| 共通 | `VIF` (max) | < 10 |\n| 二値 | \\|係数\\| | < 10 |\n\n"
        "## 落とし穴\n\n| 項目 | x |\n",
        encoding="utf-8",
    )
    # 「区分」があれば前に付け、他の節の表は拾わない
    assert expected_values(ref) == ["共通: VIF (max)", "二値: |係数|"]


def test_every_reference_lists_required_values() -> None:
    refs = sorted(SKILLS_DIR.glob("*-diagnostics/references/*.md"))
    assert refs, "references が見つからない"
    empty = [p.name for p in refs if not expected_values(p)]
    assert empty == [], f"「必ず出す値」の項目が取れない references: {empty}"
