"""skill 要否テストで比べる条件（arm）の定義と、sandbox への適用。

arm は「sandbox にコピーした skill をどう間引くか」の指定。`full` は何もしない（発火テストと同じ）。
それ以外の arm は、指定したパスを消し、指定した節・行を落として、skill の一部が無い状態を作る。
同じプロンプトを arm ごとに実行して成果物を比べれば、その skill が無くても出るものが分かる。

間引くのは sandbox の中のコピーだけで、リポジトリの skill には触れない。
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FULL_ARM = "full"
HEADING_RE = re.compile(r"^(#{1,6})\s")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class LineRule:
    """ファイル群から、正規表現に当たる行を落とす指定。

    Attributes:
        files: sandbox からの相対 glob。
        patterns: 行に対して `re.search` する正規表現。
    """

    files: tuple[str, ...]
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class Arm:
    """比べる条件 1 つ。

    Attributes:
        name: arm の名前（出力ディレクトリ名にも使う）。
        description: レポートに載せる説明。
        remove: sandbox から消すパス（sandbox からの相対 glob）。
        drop_sections: ファイル（相対パス）→ 消す節の見出し行。見出しから、同じ深さ以上の
            次の見出しの手前までを消す。
        drop_lines: 行を落とす指定。
    """

    name: str
    description: str = ""
    remove: tuple[str, ...] = ()
    drop_sections: dict[str, tuple[str, ...]] = field(default_factory=dict)
    drop_lines: tuple[LineRule, ...] = ()

    @property
    def is_full(self) -> bool:
        """skill を間引かない arm か（発火の合否を付けるのはこの arm だけ）。"""
        return not (self.remove or self.drop_sections or self.drop_lines)

    def describe(self) -> list[str]:
        """この arm が行う操作を、実行計画やレポートに載せる文字列の一覧にする。"""
        lines = [f"remove {p}" for p in self.remove]
        lines += [
            f"drop section {path} :: {h}"
            for path, heads in self.drop_sections.items()
            for h in heads
        ]
        lines += [
            f"drop lines matching {' | '.join(rule.patterns)} in {', '.join(rule.files)}"
            for rule in self.drop_lines
        ]
        return lines


def parse_arms(raw: dict[str, Any] | None) -> dict[str, Arm]:
    """cases.yaml の `arms` を読む。`full` は書かれていなくても常にある。

    Raises:
        ValueError: `full` に操作が書かれている場合、または未知のキーがある場合。
    """
    arms: dict[str, Arm] = {}
    for name, spec in (raw or {}).items():
        spec = spec or {}
        unknown = set(spec) - {"description", "remove", "drop_sections", "drop_lines"}
        if unknown:
            raise ValueError(f"arm {name}: 未知のキー {sorted(unknown)}")
        arms[str(name)] = Arm(
            name=str(name),
            description=str(spec.get("description", "")).strip(),
            remove=tuple(str(p) for p in spec.get("remove", [])),
            drop_sections={
                str(path): tuple(str(h) for h in heads)
                for path, heads in (spec.get("drop_sections") or {}).items()
            },
            drop_lines=tuple(
                LineRule(
                    files=tuple(str(f) for f in rule["files"]),
                    patterns=tuple(str(p) for p in rule["patterns"]),
                )
                for rule in spec.get("drop_lines", [])
            ),
        )
    arms.setdefault(FULL_ARM, Arm(name=FULL_ARM))
    if not arms[FULL_ARM].is_full:
        raise ValueError(f"arm {FULL_ARM} は skill をそのまま使う条件なので、操作を書けない")
    return arms


def drop_section(text: str, heading: str) -> tuple[str, int]:
    """Markdown から、見出し `heading` の節を消す。

    見出し行から、同じ深さ以上（`#` の数が同じか少ない）の次の見出しの手前までを消す。
    コードブロックの中の `#` は見出しとして数えない。

    Args:
        text: Markdown の本文。
        heading: 消す節の見出し行（`## 節の名前` の形。前後の空白は無視する）。

    Returns:
        (消した後の本文, 消した節の数)。
    """
    target = heading.strip()
    target_match = HEADING_RE.match(target)
    if not target_match:
        raise ValueError(f"見出しは `#` で始める: {heading!r}")
    level = len(target_match.group(1))

    kept: list[str] = []
    dropped = 0
    skipping = False
    in_fence = False
    for line in text.splitlines(keepends=True):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        head = None if in_fence else HEADING_RE.match(line)
        if head:
            if line.strip() == target:
                skipping = True
                dropped += 1
                continue
            if skipping and len(head.group(1)) <= level:
                skipping = False
        if not skipping:
            kept.append(line)
    return "".join(kept), dropped


def drop_lines(text: str, patterns: tuple[str, ...]) -> tuple[str, int]:
    """正規表現のどれかに当たる行を落とす。

    Returns:
        (落とした後の本文, 落とした行数)。
    """
    regexes = [re.compile(p) for p in patterns]
    kept: list[str] = []
    dropped = 0
    for line in text.splitlines(keepends=True):
        if any(r.search(line) for r in regexes):
            dropped += 1
        else:
            kept.append(line)
    return "".join(kept), dropped


def apply_arm(root: Path, arm: Arm) -> list[str]:
    """arm の操作を root（リポジトリをコピーした直後の sandbox）に適用する。

    Args:
        root: sandbox のディレクトリ。
        arm: 適用する条件。

    Returns:
        行った操作の記録（レポートと result.json に残す）。

    Raises:
        ValueError: 消す対象のパスや見出しが見つからない場合。cases.yaml の指定が skill の現状と
            ずれたまま実行すると、間引いたつもりの記述が残った状態で比べてしまうので止める。
    """
    log: list[str] = []
    for pattern in arm.remove:
        hits = sorted(root.glob(pattern))
        if not hits:
            raise ValueError(f"arm {arm.name}: remove の `{pattern}` に当たるパスが無い")
        for path in hits:
            rel = path.relative_to(root).as_posix()
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
            log.append(f"remove {rel}")

    for rel, headings in arm.drop_sections.items():
        path = root / rel
        if not path.is_file():
            raise ValueError(f"arm {arm.name}: drop_sections の `{rel}` が無い")
        text = path.read_text(encoding="utf-8")
        for heading in headings:
            text, n = drop_section(text, heading)
            if n == 0:
                raise ValueError(f"arm {arm.name}: `{rel}` に見出し `{heading}` が無い")
            log.append(f"drop section {rel} :: {heading.strip()}")
        path.write_text(text, encoding="utf-8")

    for rule in arm.drop_lines:
        files = sorted({p for g in rule.files for p in root.glob(g) if p.is_file()})
        for path in files:
            text, n = drop_lines(path.read_text(encoding="utf-8"), rule.patterns)
            if n:
                path.write_text(text, encoding="utf-8")
                log.append(f"drop {n} line(s) {path.relative_to(root).as_posix()}")
    return log
