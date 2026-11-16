"""利用枠（5 時間枠・7 日枠）を見て、上限に当たる前に実行を止める。

headless の Claude Code は、stream-json に `rate_limit_event` を流す。そこに枠ごとの使用率と
リセット時刻が入っている（`Transcript.quota()`）。上限に達すると、実行の途中でも
「You've hit your session limit」で打ち切られ、そこまでの分が無駄になる。そこで、

- 実行を始める前に、短い問い合わせを 1 回送って使用率を読む（`probe_session`）
- 1 件終わるたびに使用率を見て、目安を超えていたら残りを始めない（`stop_reason`）

の 2 か所で止める。始めなかった分は `run --resume` で続きから実行できる。
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from skill_eval.cases import EvalConfig
from skill_eval.sandbox import sandbox_env
from skill_eval.transcript import Transcript

WINDOW_LABELS = {"five_hour": "5 時間枠", "seven_day": "7 日枠"}
# 使用率を読むだけなので、いちばん安いモデルに短く答えさせる
PROBE_MODEL = "haiku"
PROBE_PROMPT = "OK とだけ答えて。"
PROBE_TIMEOUT_SEC = 120


def _window_text(name: str, window: dict[str, Any]) -> str:
    """「5 時間枠 57%（リセット 11/16 14:20）」の形にする。"""
    label = WINDOW_LABELS.get(name, name)
    text = f"{label} {window['utilization']:.0%}"
    if window.get("resets_at"):
        reset = datetime.fromtimestamp(window["resets_at"]).strftime("%m/%d %H:%M")
        text += f"（リセット {reset}）"
    return text


def format_quota(quota: dict[str, Any] | None) -> str:
    """利用枠の状況を 1 行にする。読めなかったときはその旨を返す。"""
    if not quota:
        return "使用率を読めなかった"
    parts = [_window_text(name, w) for name, w in sorted(quota["windows"].items())]
    if quota.get("rejected"):
        parts.append("上限に達している")
    return " / ".join(parts)


def stop_reason(quota: dict[str, Any] | None, max_utilization: float) -> str | None:
    """これ以上実行を始めないほうがよい理由を返す。続けてよければ None。

    Args:
        quota: `Transcript.quota()` の戻り値。読めなかったときは None（止めない）。
        max_utilization: 使用率がこの値以上の枠があれば止める（0〜1）。0 以下なら
            使用率では止めず、上限に達して断られたときだけ止める。

    Returns:
        止める理由。止めなくてよければ None。
    """
    if not quota:
        return None
    if quota.get("rejected"):
        return f"上限に達して実行を断られた（{format_quota(quota)}）"
    if max_utilization <= 0:
        return None
    over = [
        _window_text(name, w)
        for name, w in sorted(quota["windows"].items())
        if w["utilization"] >= max_utilization
    ]
    if over:
        return f"使用率が目安の {max_utilization:.0%} 以上になった: {' / '.join(over)}"
    return None


def probe_session(config: EvalConfig, cwd: Path) -> Transcript:
    """短い問い合わせを 1 回だけ送り、そのセッションの記録を返す。

    利用枠の使用率（`Transcript.quota()`）と、プロジェクトの外から見えている skill
    （`Transcript.skill_names`）を、本番の実行を始める前に知るために使う。

    Args:
        config: 起動条件。claude のパスと、`skill_overrides`（指定があれば同じように渡す）を使う。
        cwd: 作業ディレクトリ。プロジェクトの設定や skill を読み込ませないよう、
            空のディレクトリを渡す。

    Returns:
        問い合わせの記録。claude を起動できない・時間切れのときは、中身が空の記録。
    """
    cmd = [
        config.claude_bin,
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        "--model",
        PROBE_MODEL,
    ]
    if config.skill_overrides:
        cmd += ["--settings", json.dumps({"skillOverrides": config.skill_overrides})]
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=sandbox_env(os.environ, cwd),
            input=PROBE_PROMPT.encode("utf-8"),
            capture_output=True,
            timeout=PROBE_TIMEOUT_SEC,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return Transcript.from_lines([])
    return Transcript.from_lines(proc.stdout.decode("utf-8", errors="replace").splitlines())
