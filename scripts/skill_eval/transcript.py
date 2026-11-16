"""`claude -p --output-format stream-json --verbose` の出力から skill の発火と実行の経過を取り出す。

skill が「読まれた」とみなす経路は 3 つ:

- `Skill` ツールの呼び出し（skill 本文が注入される正規の発火）
- `Read` ツールで `.claude/skills/<skill>/SKILL.md` や `references/*.md` を開いた
- `Bash` のコマンド文字列にそれらのパスが現れた（`cat` / `sed -n` など）

サブエージェント（Agent ツール）内の呼び出しも `parent_tool_use_id` 付きで流れてくるので含める。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# `.claude/skills/<skill>/SKILL.md` と `.claude/skills/<skill>/references/<file>.md` を拾う
SKILL_FILE_RE = re.compile(r"\.claude/skills/([^/\s'\"]+)/(SKILL\.md|references/[^/\s'\"]+\.md)")
# Python の実行（`python x.py` / `uv run python ...` / `uv run --with a python ...`）
CODE_RUN_RE = re.compile(r"(^|[\s;&|(])python3?(\s|$)")


@dataclass(frozen=True)
class ToolCall:
    """transcript に現れたツール呼び出し 1 件。"""

    index: int
    name: str
    input: dict[str, Any]
    in_subagent: bool


@dataclass(frozen=True)
class SkillEvent:
    """skill ファイルが読まれた（または Skill ツールで発火した）記録。

    Attributes:
        index: ツール呼び出しの通し番号（読んだ順序の比較に使う）。
        skill: skill 名。
        file: `SKILL.md` または `references/<file>.md`。
        via: `Skill` / `Read` / `Bash`。
        in_subagent: サブエージェント内の呼び出しか。
    """

    index: int
    skill: str
    file: str
    via: str
    in_subagent: bool

    @property
    def path(self) -> str:
        """`<skill>/<file>` 形式のパス。"""
        return f"{self.skill}/{self.file}"


def normalize_skill_name(name: str) -> str:
    """`plugin:skill` や `dir/scope:skill`、`/skill` を skill 名だけにそろえる。"""
    return name.strip().lstrip("/").rsplit(":", 1)[-1].rsplit("/", 1)[-1]


@dataclass
class Transcript:
    """stream-json を解析した結果。

    Attributes:
        init: `system/init` メッセージ（利用可能な skill・モデルなど）。
        tool_calls: ツール呼び出しを出現順に並べたもの。
        result: 最後の `result` メッセージ。無ければ空（途中終了・タイムアウト）。
        parse_errors: JSON として読めなかった行の数。
        rate_limits: `rate_limit_event` の `rate_limit_info` を届いた順に並べたもの。
    """

    init: dict[str, Any]
    tool_calls: list[ToolCall]
    result: dict[str, Any]
    parse_errors: int = 0
    rate_limits: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_lines(cls, lines: list[str]) -> Transcript:
        """stream-json の各行から Transcript を作る。"""
        init: dict[str, Any] = {}
        result: dict[str, Any] = {}
        calls: list[ToolCall] = []
        limits: list[dict[str, Any]] = []
        errors = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                errors += 1
                continue
            mtype = msg.get("type")
            if mtype == "system" and msg.get("subtype") == "init" and not init:
                init = msg
            elif mtype == "result":
                result = msg
            elif mtype == "rate_limit_event":
                limits.append(msg.get("rate_limit_info") or {})
            elif mtype == "assistant":
                content = (msg.get("message") or {}).get("content") or []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        calls.append(
                            ToolCall(
                                index=len(calls),
                                name=str(block.get("name", "")),
                                input=block.get("input") or {},
                                in_subagent=msg.get("parent_tool_use_id") is not None,
                            )
                        )
        return cls(
            init=init, tool_calls=calls, result=result, parse_errors=errors, rate_limits=limits
        )

    @classmethod
    def from_file(cls, path: Path) -> Transcript:
        """stream-json のファイルから Transcript を作る。"""
        return cls.from_lines(path.read_text(encoding="utf-8").splitlines())

    @property
    def skill_names(self) -> list[str]:
        """セッション開始時に一覧に載っていた skill の名前（`plugin:skill` の形のまま）。"""
        skills = self.init.get("skills") or []
        names = [s.get("name", "") if isinstance(s, dict) else str(s) for s in skills]
        return [n for n in names if n]

    @property
    def available_skills(self) -> list[str] | None:
        """セッション開始時に一覧に載っていた skill 名。init に情報が無ければ None。"""
        if self.init.get("skills") is None:
            return None
        return sorted({normalize_skill_name(n) for n in self.skill_names})

    def skill_events(self) -> list[SkillEvent]:
        """skill の発火と skill ファイルの読み込みを出現順に返す。"""
        events: list[SkillEvent] = []
        for call in self.tool_calls:
            if call.name == "Skill":
                name = normalize_skill_name(str(call.input.get("skill", "")))
                if name:
                    events.append(
                        SkillEvent(call.index, name, "SKILL.md", "Skill", call.in_subagent)
                    )
                continue
            if call.name == "Read":
                text = str(call.input.get("file_path", ""))
            elif call.name == "Bash":
                text = str(call.input.get("command", ""))
            else:
                continue
            for skill, file in SKILL_FILE_RE.findall(text):
                events.append(SkillEvent(call.index, skill, file, call.name, call.in_subagent))
        return events

    def loaded_skills(self) -> dict[str, str]:
        """発火した skill 名 → 最初の経路（`Skill` / `Read` / `Bash`）。"""
        loaded: dict[str, str] = {}
        for ev in self.skill_events():
            if ev.file == "SKILL.md":
                loaded.setdefault(ev.skill, ev.via)
        return loaded

    def read_references(self) -> dict[str, int]:
        """読まれた references（`<skill>/references/<file>.md`）→ 最初に読まれた index。"""
        refs: dict[str, int] = {}
        for ev in self.skill_events():
            if ev.file.startswith("references/"):
                refs.setdefault(ev.path, ev.index)
        return refs

    def first_code_run_index(self) -> int | None:
        """最初に Python を実行したツール呼び出しの index。実行が無ければ None。"""
        for call in self.tool_calls:
            if call.name == "Bash" and CODE_RUN_RE.search(str(call.input.get("command", ""))):
                return call.index
            if call.name == "NotebookEdit":
                return call.index
        return None

    def written_files(self) -> list[str]:
        """Write / Edit / NotebookEdit で書かれたファイルパス（重複除去、出現順）。"""
        seen: dict[str, None] = {}
        for call in self.tool_calls:
            if call.name in ("Write", "Edit", "NotebookEdit"):
                p = call.input.get("file_path") or call.input.get("notebook_path")
                if p:
                    seen.setdefault(str(p), None)
        return list(seen)

    @property
    def final_text(self) -> str:
        """最終応答の本文。"""
        return str(self.result.get("result") or "")

    def quota(self) -> dict[str, Any] | None:
        """利用枠（5 時間枠・7 日枠）の使用率を、最後に届いた通知から取り出す。

        Returns:
            `windows` は枠の名前（`five_hour` / `seven_day`）→ 使用率 `utilization`（0〜1）と
            リセット時刻 `resets_at`（epoch 秒）。`rejected` は上限に達して実行を断られたか。
            通知が 1 つも無く、断られてもいなければ None。
        """
        windows: dict[str, dict[str, Any]] = {}
        rejected = self.result.get("api_error_status") == 429
        for info in self.rate_limits:
            rejected = rejected or info.get("status") == "rejected"
            for name, window in (info.get("unifiedWindows") or {}).items():
                if isinstance(window, dict) and "utilization" in window:
                    # 後から届いた通知で上書きし、実行の終わりの時点の値を残す
                    windows[name] = {
                        "utilization": window["utilization"],
                        "resets_at": window.get("resetsAt"),
                    }
        if not windows and not rejected:
            return None
        return {"windows": windows, "rejected": rejected}
