"""利用枠を見て実行を止める・続きから実行する仕組みのテスト。claude は起動しない。

検証する契約:
- transcript の `rate_limit_event` から、枠ごとの最後の使用率とリセット時刻を読める
- 使用率が目安以上になったら、次の実行を始めない（始めた実行は最後まで終える）
- 上限に達して断られた実行は、目安を無効にしていても止める理由になる
- 続きからの実行では、結果の無い実行と ERROR の実行だけが対象になる
- やり直す実行の出力は消さずに退避し、退避先は結果の一覧に混ざらない
- 前回と条件（arm・モデル・effort・skill の内容）が違えば、続きから実行しない
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import run_skill_eval
from skill_eval.arms import Arm
from skill_eval.cases import EvalConfig
from skill_eval.quota import format_quota, stop_reason
from skill_eval.transcript import Transcript


def _event(five_hour: float, seven_day: float, status: str = "allowed") -> str:
    return json.dumps(
        {
            "type": "rate_limit_event",
            "rate_limit_info": {
                "status": status,
                "rateLimitType": "five_hour",
                "unifiedWindows": {
                    "five_hour": {"utilization": five_hour, "resetsAt": 1794714000},
                    "seven_day": {"utilization": seven_day, "resetsAt": 1795021200},
                },
            },
        }
    )


def _quota(five_hour: float, seven_day: float = 0.1, rejected: bool = False) -> dict:
    return {
        "windows": {
            "five_hour": {"utilization": five_hour, "resets_at": 1794714000},
            "seven_day": {"utilization": seven_day, "resets_at": 1795021200},
        },
        "rejected": rejected,
    }


def test_quota_keeps_last_utilization_of_each_window() -> None:
    tx = Transcript.from_lines([_event(0.51, 0.24), _event(0.57, 0.25)])
    quota = tx.quota()
    assert quota is not None
    assert quota["windows"]["five_hour"] == {"utilization": 0.57, "resets_at": 1794714000}
    assert quota["windows"]["seven_day"]["utilization"] == 0.25
    assert quota["rejected"] is False


def test_quota_is_none_without_events() -> None:
    assert Transcript.from_lines([json.dumps({"type": "result", "result": "ok"})]).quota() is None


def test_quota_is_rejected_when_the_limit_was_hit() -> None:
    result = json.dumps(
        {
            "type": "result",
            "is_error": True,
            "api_error_status": 429,
            "result": "You've hit your session limit",
        }
    )
    quota = Transcript.from_lines([_event(1, 0.77, status="rejected"), result]).quota()
    assert quota is not None and quota["rejected"] is True
    # 使用率の目安を無効にしていても、断られたら止める
    assert stop_reason(quota, 0) is not None


def test_stop_reason_compares_every_window_with_the_threshold() -> None:
    assert stop_reason(None, 0.85) is None
    assert stop_reason(_quota(0.84), 0.85) is None
    assert "5 時間枠" in (stop_reason(_quota(0.85), 0.85) or "")
    # 5 時間枠に余裕があっても、7 日枠が目安以上なら止める
    assert "7 日枠" in (stop_reason(_quota(0.2, seven_day=0.9), 0.85) or "")
    assert stop_reason(_quota(0.99), 0) is None
    assert "57%" in format_quota(_quota(0.57))


def test_execute_jobs_does_not_start_the_next_run_over_the_threshold() -> None:
    jobs = [(SimpleNamespace(id="a"), rep) for rep in (1, 2, 3, 4)]
    utilization = {1: 0.5, 2: 0.86, 3: 0.9, 4: 0.95}
    started: list[int] = []
    done: list[int] = []

    def run(case: SimpleNamespace, rep: int) -> dict:
        started.append(rep)
        return {"quota": _quota(utilization[rep])}

    not_started, reason = run_skill_eval.execute_jobs(
        jobs,  # type: ignore[arg-type]
        run,  # type: ignore[arg-type]
        lambda c, rep, res: done.append(rep),
        workers=1,
        should_stop=lambda res: stop_reason(res["quota"], 0.85),
    )
    assert started == [1, 2] and done == [1, 2]
    assert [rep for _, rep in not_started] == [3, 4]
    assert reason is not None and "86%" in reason


def test_execute_jobs_runs_everything_under_the_threshold() -> None:
    jobs = [(SimpleNamespace(id="a"), rep) for rep in (1, 2)]
    not_started, reason = run_skill_eval.execute_jobs(
        jobs,  # type: ignore[arg-type]
        lambda c, rep: {"quota": _quota(0.3)},
        lambda c, rep, res: None,
        workers=2,
        should_stop=lambda res: stop_reason(res["quota"], 0.85),
    )
    assert not_started == [] and reason is None


def _write_result(run_dir: Path, case_id: str, rep: int, status: str) -> None:
    out = run_dir / case_id / f"r{rep}"
    out.mkdir(parents=True)
    (out / "result.json").write_text(json.dumps({"status": status}), encoding="utf-8")


def test_pending_jobs_are_missing_or_error_runs(tmp_path: Path) -> None:
    _write_result(tmp_path, "a", 1, "PASS")
    _write_result(tmp_path, "a", 2, "ERROR")
    _write_result(tmp_path, "b", 1, "DONE")
    jobs = [(SimpleNamespace(id=c), rep) for c in ("a", "b") for rep in (1, 2, 3)]
    pending = run_skill_eval.pending_jobs(tmp_path, jobs)  # type: ignore[arg-type]
    assert [(c.id, rep) for c, rep in pending] == [("a", 2), ("a", 3), ("b", 2), ("b", 3)]


def test_set_aside_keeps_the_interrupted_run_out_of_the_results(tmp_path: Path) -> None:
    # ケース名が r で始まっても、退避先が結果の一覧（*/r*/result.json）に混ざらない
    _write_result(tmp_path, "rdd-age13", 1, "ERROR")
    moved = run_skill_eval.set_aside(tmp_path, "rdd-age13", 1)
    assert moved is not None and (moved / "result.json").is_file()
    assert not (tmp_path / "rdd-age13" / "r1").exists()
    assert list(tmp_path.glob("*/r*/result.json")) == []
    assert run_skill_eval.set_aside(tmp_path, "rdd-age13", 2) is None


def test_resume_refuses_a_different_condition() -> None:
    config = EvalConfig(model="m", effort="medium")
    arm = Arm(name="full", description="")
    meta = {
        "arm": {"name": "full"},
        "config": {"model": "m", "effort": "medium"},
        "skills_hash": "abc",
    }
    run_skill_eval.check_same_condition(meta, arm, config, "abc")
    with pytest.raises(SystemExit, match="skills"):
        run_skill_eval.check_same_condition(meta, arm, config, "changed")
    with pytest.raises(SystemExit, match="arm"):
        run_skill_eval.check_same_condition(meta, Arm(name="bare", description=""), config, "abc")
