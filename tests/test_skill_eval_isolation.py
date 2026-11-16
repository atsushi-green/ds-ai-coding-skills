"""プロジェクトの外にある同名の skill を見えなくする仕組みのテスト。claude は起動しない。

検証する契約:
- プロジェクトの外から見えている skill のうち、リポジトリの skill と同じ名前のものを拾う
- 名前空間つき（アカウントに登録した skill など）は `off` にする
- 名前空間の無いものは `off` にできないので、実行を止める対象にする
- `off` の指定は settings の `skillOverrides` として claude に渡る（指定が無ければ渡さない）
- 実行ごとの結果に、見えていた同名の skill が残る
"""

from __future__ import annotations

import json
from pathlib import Path

from skill_eval.cases import Case, EvalConfig, Expectation
from skill_eval.evaluate import evaluate
from skill_eval.isolation import (
    namespaced_copies,
    outside_copies,
    plan_overrides,
    project_skill_names,
)
from skill_eval.sandbox import claude_command
from skill_eval.transcript import Transcript

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
ACCOUNT_COPY = "anthropic-skills:statistical-inference-diagnostics"
PROJECT = {"statistical-inference-diagnostics", "visualization"}


def test_project_skill_names_are_the_skill_directories() -> None:
    names = project_skill_names(SKILLS_DIR)
    assert {"statistical-inference-diagnostics", "visualization", "python-style"} <= names


def test_outside_copies_match_by_name_with_or_without_namespace() -> None:
    visible = [ACCOUNT_COPY, "anthropic-skills:pdf", "visualization", "dataviz"]
    assert outside_copies(visible, PROJECT) == [ACCOUNT_COPY, "visualization"]
    assert outside_copies(["anthropic-skills:pdf", "dataviz"], PROJECT) == []


def test_plan_overrides_hides_namespaced_copies_and_blocks_the_rest() -> None:
    overrides, blocking = plan_overrides([ACCOUNT_COPY, "visualization"])
    assert overrides == {ACCOUNT_COPY: "off"}
    # 名前空間が無い同名の skill を off にすると、プロジェクトの skill まで消えてしまう
    assert blocking == ["visualization"]


def test_namespaced_copies_ignore_the_project_own_skills() -> None:
    # sandbox の中では、プロジェクトの skill が名前空間なしで見えている
    visible = ["statistical-inference-diagnostics", "visualization", ACCOUNT_COPY]
    assert namespaced_copies(visible, PROJECT) == [ACCOUNT_COPY]


def test_claude_command_passes_overrides_as_settings() -> None:
    assert "--settings" not in claude_command(EvalConfig())
    cmd = claude_command(EvalConfig(skill_overrides={ACCOUNT_COPY: "off"}, allowed_tools=["Skill"]))
    settings = json.loads(cmd[cmd.index("--settings") + 1])
    assert settings == {"skillOverrides": {ACCOUNT_COPY: "off"}}
    # 可変長の --allowedTools に取り込まれない位置にあること
    assert cmd.index("--settings") < cmd.index("--allowedTools")


def test_evaluate_records_outside_copies_seen_by_the_run() -> None:
    init = {
        "type": "system",
        "subtype": "init",
        "skills": ["statistical-inference-diagnostics", ACCOUNT_COPY, "anthropic-skills:pdf"],
    }
    result = {"type": "result", "subtype": "success", "result": "ok", "is_error": False}
    tx = Transcript.from_lines([json.dumps(init), json.dumps(result)])
    case = Case(id="c", kind="explicit", prompt="p", expect=Expectation(), forbid=Expectation())
    res = evaluate(case, tx, [], SKILLS_DIR)
    assert res["outside_skill_copies"] == [ACCOUNT_COPY]
