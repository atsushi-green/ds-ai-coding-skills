"""`scripts/skill_eval/`（skill 発火テストのハーネス）のユニットテスト。

claude は起動しない。検証する契約:
- transcript から Skill ツール・Read・Bash の 3 経路で skill と references の読み込みを拾える
- 期待・禁止との突き合わせで PASS / FAIL / ERROR が決まる
- cases.yaml が実在の skill・references を指し、すべての references に少なくとも 1 ケースある
- references 内の分岐（手法・条件ごとの「必ず出す図」）がすべてどれかのケースで試される
- プロンプトは分析ライブラリを指定せず、参照するデータファイルは sandbox に必ず置かれる
- sandbox は正解の実装をコピーせず、生データは読み取り専用になる
- プロンプトはコマンド引数に入らない（標準入力で渡す）
"""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path

import pytest
from skill_eval.cases import (
    Case,
    EvalConfig,
    Expectation,
    expected_figures,
    figure_table_heads,
    load_suite,
    load_variants,
    reference_short_name,
    resolve_reference,
)
from skill_eval.evaluate import evaluate
from skill_eval.report import build_html, build_markdown
from skill_eval.sandbox import build_sandbox, changed_files, claude_command, snapshot
from skill_eval.transcript import Transcript, normalize_skill_name

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
CASES_YAML = REPO_ROOT / "scripts" / "skill_eval" / "cases.yaml"
# `NAME = "..."` の 1 行代入は check_no_sensitive_patterns の .env 検出に当たるのでまとめる
SKILL_INFERENCE, SKILL_PREDICTIVE = (
    "statistical-inference-diagnostics",
    "predictive-modeling-diagnostics",
)


# --------------------------------------------------------------------------------------
# stream-json のフィクスチャ
# --------------------------------------------------------------------------------------
def _tool(name: str, inp: dict, parent: str | None = None) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "parent_tool_use_id": parent,
            "message": {"content": [{"type": "tool_use", "id": "x", "name": name, "input": inp}]},
        }
    )


def _stream(*tool_lines: str, result: dict | None = None) -> list[str]:
    init = json.dumps(
        {
            "type": "system",
            "subtype": "init",
            "skills": [SKILL_INFERENCE, SKILL_PREDICTIVE, "visualization"],
            "model": "m",
        }
    )
    lines = [init, *tool_lines]
    if result is not None:
        lines.append(json.dumps({"type": "result", "subtype": "success", **result}))
    return lines


GLM_RUN = _stream(
    _tool("Skill", {"skill": SKILL_INFERENCE}),
    _tool("Read", {"file_path": f"/tmp/sb/.claude/skills/{SKILL_INFERENCE}/references/glm.md"}),
    _tool("Write", {"file_path": "/tmp/sb/scripts/glm.py", "content": "..."}),
    _tool("Bash", {"command": "uv run --with statsmodels python scripts/glm.py"}),
    result={
        "result": "| 診断項目 | 実測値 | 合格基準 | 判定 | 次アクション |",
        "is_error": False,
        "total_cost_usd": 0.5,
        "duration_ms": 60000,
        "num_turns": 5,
        "permission_denials": [],
    },
)


def _case(**kw) -> Case:
    base = {
        "id": "c",
        "kind": "explicit",
        "prompt": "p",
        "expect": Expectation(
            skills=(SKILL_INFERENCE,), references=(f"{SKILL_INFERENCE}/references/glm.md",)
        ),
        "forbid": Expectation(),
    }
    base.update(kw)
    return Case(**base)


# --------------------------------------------------------------------------------------
# transcript
# --------------------------------------------------------------------------------------
def test_normalize_skill_name() -> None:
    assert normalize_skill_name("/glm") == "glm"
    assert normalize_skill_name("anthropic-skills:zenn-article") == "zenn-article"
    assert normalize_skill_name("apps/web:deploy") == "deploy"


def test_transcript_picks_up_skill_tool_and_reference_read() -> None:
    tx = Transcript.from_lines(GLM_RUN)
    assert tx.loaded_skills() == {SKILL_INFERENCE: "Skill"}
    assert tx.read_references() == {f"{SKILL_INFERENCE}/references/glm.md": 1}
    assert tx.first_code_run_index() == 3
    assert tx.written_files() == ["/tmp/sb/scripts/glm.py"]
    assert tx.available_skills == sorted([SKILL_INFERENCE, SKILL_PREDICTIVE, "visualization"])


def test_transcript_counts_bash_cat_and_subagent_reads() -> None:
    tx = Transcript.from_lines(
        _stream(
            _tool("Bash", {"command": f"cat .claude/skills/{SKILL_PREDICTIVE}/SKILL.md"}),
            _tool(
                "Read",
                {"file_path": f".claude/skills/{SKILL_PREDICTIVE}/references/tree-model.md"},
                parent="toolu_1",
            ),
        )
    )
    assert tx.loaded_skills() == {SKILL_PREDICTIVE: "Bash"}
    events = tx.skill_events()
    assert [e.in_subagent for e in events] == [False, True]
    assert tx.first_code_run_index() is None


def test_uv_add_is_not_a_code_run_and_broken_lines_are_counted() -> None:
    tx = Transcript.from_lines(
        _stream(_tool("Bash", {"command": "uv add statsmodels"})) + ["not json"]
    )
    assert tx.first_code_run_index() is None
    assert tx.parse_errors == 1
    assert tx.result == {}


# --------------------------------------------------------------------------------------
# evaluate
# --------------------------------------------------------------------------------------
def test_evaluate_pass_with_figure_dir_and_order() -> None:
    tx = Transcript.from_lines(GLM_RUN)
    res = evaluate(
        _case(), tx, ["outputs/diagnostics/20260101-0000_glm/glm.png", "scripts/glm.py"], SKILLS_DIR
    )
    assert res["status"] == "PASS"
    assert res["read_before_first_run"] == {f"{SKILL_INFERENCE}/references/glm.md": True}
    assert res["figure_dir_ok"] == {"glm": True}
    assert res["images"] == ["outputs/diagnostics/20260101-0000_glm/glm.png"]
    assert res["has_diagnostics_table"] is True


def test_evaluate_fail_on_missing_and_forbidden() -> None:
    tx = Transcript.from_lines(GLM_RUN)
    missing = evaluate(
        _case(
            expect=Expectation(
                skills=(SKILL_INFERENCE,), references=(f"{SKILL_INFERENCE}/references/ols.md",)
            )
        ),
        tx,
        [],
        SKILLS_DIR,
    )
    assert missing["status"] == "FAIL"
    assert missing["missing_references"] == [f"{SKILL_INFERENCE}/references/ols.md"]

    forbidden = evaluate(
        _case(
            expect=Expectation(), forbid=Expectation(skills=("*-diagnostics",), references=("*",))
        ),
        tx,
        [],
        SKILLS_DIR,
    )
    assert forbidden["status"] == "FAIL"
    assert forbidden["forbidden_hits"] == sorted(
        [SKILL_INFERENCE, f"{SKILL_INFERENCE}/references/glm.md"]
    )


def test_evaluate_finds_diagnostics_table_in_report_file() -> None:
    lines = GLM_RUN[:-1] + [
        json.dumps(
            {"type": "result", "subtype": "success", "result": "要約のみ", "is_error": False}
        )
    ]
    tx = Transcript.from_lines(lines)
    assert evaluate(_case(), tx, [], SKILLS_DIR)["has_diagnostics_table"] is False
    res = evaluate(
        _case(),
        tx,
        ["outputs/reports/r.md"],
        SKILLS_DIR,
        report_texts={"outputs/reports/r.md": "| 診断項目 | 実測値 |"},
    )
    assert res["has_diagnostics_table"] is True
    assert res["diagnostics_table_in"] == "outputs/reports/r.md"


def test_evaluate_error_when_no_result_or_timeout() -> None:
    no_result = Transcript.from_lines(GLM_RUN[:-1])
    assert evaluate(_case(), no_result, [], SKILLS_DIR)["status"] == "ERROR"
    tx = Transcript.from_lines(GLM_RUN)
    assert evaluate(_case(), tx, [], SKILLS_DIR, timed_out=True)["status"] == "ERROR"


# --------------------------------------------------------------------------------------
# cases.yaml と references
# --------------------------------------------------------------------------------------
def test_resolve_reference() -> None:
    assert resolve_reference("glm", SKILLS_DIR) == f"{SKILL_INFERENCE}/references/glm.md"
    with pytest.raises(ValueError):
        resolve_reference("no-such-reference", SKILLS_DIR)


def test_cases_yaml_is_valid_and_covers_every_reference() -> None:
    config, cases = load_suite(CASES_YAML, SKILLS_DIR)
    assert cases
    covered = {r for c in cases for r in c.expect.references}
    all_refs = {
        p.relative_to(SKILLS_DIR).as_posix()
        for p in SKILLS_DIR.glob("*-diagnostics/references/*.md")
    }
    # references を足したらケースも足す
    assert all_refs - covered == set()
    assert any(c.kind == "negative" for c in cases)
    for c in cases:
        # プロンプトに skill 名を書くと発火のテストにならない
        assert "diagnostics" not in c.prompt, c.id
        assert "references" not in c.prompt, c.id
    # 無人実行の追記も skill に触れない
    assert "skill" not in config.append_system_prompt.lower()
    assert "診断" not in config.append_system_prompt


REFERENCES = sorted(SKILLS_DIR.glob("*-diagnostics/references/*.md"))


def test_core_suite_covers_every_reference() -> None:
    # --core（基本セット）だけでも、すべての references と否定ケースを 1 回は試す
    _, cases = load_suite(CASES_YAML, SKILLS_DIR)
    core = [c for c in cases if "core" in c.tags]
    covered = {r for c in core for r in c.expect.references}
    assert {r.relative_to(SKILLS_DIR).as_posix() for r in REFERENCES} <= covered
    assert any(c.kind == "negative" for c in core)


def test_every_variant_is_covered_by_a_case() -> None:
    _, cases = load_suite(CASES_YAML, SKILLS_DIR)
    variants = load_variants(CASES_YAML)
    # すべての references に分岐の宣言がある（分岐の無い手法も 1 つ書く）
    assert set(variants) == {r.stem for r in REFERENCES}
    covered = {c for case in cases for c in case.covers}
    uncovered = [f"{stem}:{v}" for stem, vs in variants.items() for v in vs]
    uncovered = [v for v in uncovered if v not in covered]
    assert uncovered == [], f"どのケースも試していない分岐: {uncovered}"


@pytest.mark.parametrize("ref", REFERENCES, ids=lambda p: p.stem)
def test_table_rows_are_declared_as_variants(ref: Path) -> None:
    # 「必ず出す図」の表に行を足したら、cases.yaml の variants とケースも足す
    declared = set(load_variants(CASES_YAML).get(ref.stem, ()))
    missing = [h for h in figure_table_heads(ref) if h not in declared]
    assert missing == [], f"{ref.stem} の表の行が variants に無い: {missing}"


# 実装ライブラリを指定すると、skill がライブラリ選択まで導けるかを試せない。
# 手法名（t 検定・k-means・SHAP 値など）は書いてよいので、ここには実装ライブラリだけを並べる
LIBRARY_NAMES = (
    "cmdstanpy", "pystan", "pymc", "numpyro", "arviz", "statsmodels", "sklearn", "scikit-learn",
    "scipy", "numpy", "pandas", "polars", "lightgbm", "xgboost", "catboost", "lifelines",
    "pingouin", "missingno", "dowhy", "econml", "causalml", "doubleml", "rdrobust", "linearmodels",
    "simpy", "salib", "pulp", "ortools", "pyomo", "cvxpy", "prophet", "ruptures", "umap-learn",
    "pyod", "factor_analyzer", "isolationforest", "kmeans(",
)  # fmt: skip


def test_prompts_do_not_name_libraries() -> None:
    _, cases = load_suite(CASES_YAML, SKILLS_DIR)
    for c in cases:
        prompt = c.prompt.lower()
        hits = [lib for lib in LIBRARY_NAMES if lib in prompt]
        assert not hits, f"{c.id}: {hits}"


def test_prompt_data_files_are_placed_in_sandbox() -> None:
    config, cases = load_suite(CASES_YAML, SKILLS_DIR)
    for c in cases:
        placed = set(config.data_files) | {f"data/raw/{d}.csv" for d in c.datasets}
        mentioned = set(re.findall(r"data/raw/[\w.-]+\.csv", c.prompt))
        assert mentioned <= placed, f"{c.id}: sandbox に無い {sorted(mentioned - placed)}"
        # datasets に書いたのにプロンプトで触れていないデータは置いても使われない
        assert {f"data/raw/{d}.csv" for d in c.datasets} <= mentioned, c.id


@pytest.mark.parametrize("ref", REFERENCES, ids=lambda p: p.stem)
def test_every_reference_has_short_name_and_figures(ref: Path) -> None:
    assert reference_short_name(ref)
    assert expected_figures(ref)


# --------------------------------------------------------------------------------------
# sandbox と起動コマンド
# --------------------------------------------------------------------------------------
def test_build_sandbox_isolated_and_raw_read_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".claude/skills/demo").mkdir(parents=True)
    (repo / ".claude/skills/demo/SKILL.md").write_text("x", encoding="utf-8")
    (repo / "scripts/diagnostics_demo").mkdir(parents=True)
    (repo / "scripts/diagnostics_demo/answer.py").write_text("x", encoding="utf-8")
    (repo / "data/raw").mkdir(parents=True)
    (repo / "data/raw/train.csv").write_text("a\n1\n", encoding="utf-8")
    (repo / "CLAUDE.md").write_text("x", encoding="utf-8")

    extra = tmp_path / "rossi.csv"
    extra.write_text("week\n1\n", encoding="utf-8")

    dest = tmp_path / "sb"
    config = EvalConfig(copy=[".claude", "CLAUDE.md"], data_files=["data/raw/train.csv"])
    build_sandbox(repo, dest, config, {"data/raw/rossi.csv": extra})

    assert (dest / ".claude/skills/demo/SKILL.md").is_file()
    assert not (dest / "scripts").exists()
    assert (dest / ".git").is_dir()
    assert (dest / "outputs").is_dir()
    for rel in ("data/raw/train.csv", "data/raw/rossi.csv"):
        mode = (dest / rel).stat().st_mode
        assert not mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH), rel

    before = snapshot(dest)
    (dest / "outputs/fig.png").write_bytes(b"png")
    assert changed_files(before, snapshot(dest)) == ["outputs/fig.png"]


def test_claude_command_keeps_prompt_out_of_argv() -> None:
    cmd = claude_command(
        EvalConfig(
            model="sonnet",
            max_budget_usd=2,
            allowed_tools=["Bash(uv *)"],
            append_system_prompt="無人実行",
        )
    )
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[cmd.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in cmd
    assert cmd[cmd.index("--model") + 1] == "sonnet"
    assert cmd[cmd.index("--allowedTools") + 1] == "Bash(uv *)"


# --------------------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------------------
def test_report_renders_one_row_per_run() -> None:
    tx = Transcript.from_lines(GLM_RUN)
    res = evaluate(_case(), tx, ["outputs/diagnostics/x_glm/a.png"], SKILLS_DIR)
    res["_dir"] = "c/r1"
    md = build_markdown({"run_id": "t"}, [_case()], [res])
    assert "| c | explicit | ✅ 1/1 |" in md
    page = build_html({"run_id": "t"}, [_case()], [res], SKILLS_DIR)
    assert "c/r1/files/outputs/diagnostics/x_glm/a.png" in page
