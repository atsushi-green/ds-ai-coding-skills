"""テストケース定義（cases.yaml）の読み込みと、references からの期待値の取り出し。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from skill_eval.datasets import GENERATORS

KINDS = ("explicit", "implicit", "scope", "negative")
SHORT_NAME_RE = re.compile(r"短縮名: `([^`]+)`")
NUMBERED_RE = re.compile(r"^\d+\. (.+)")
TABLE_SEP_RE = re.compile(r"^\|[\s|:-]+\|?\s*$")


@dataclass(frozen=True)
class Expectation:
    """読まれるべき（または読まれてはいけない）skill と references。

    Attributes:
        skills: skill 名。forbid 側では fnmatch のパターン（`*-diagnostics` など）も書ける。
        references: `<skill>/references/<file>.md` 形式。forbid 側ではパターンも書ける。
    """

    skills: tuple[str, ...] = ()
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class Case:
    """1 本のテストケース。

    Attributes:
        id: ケース ID（出力ディレクトリ名にも使う）。
        kind: explicit（手法を名指し） / implicit（手法を言わない） / scope（部品の手法で
            別の references を読まないか） / negative（診断 skill が発火しないはず）。
        prompt: セッションにそのまま渡すプロンプト。
        expect: 読まれるべき skill と references。references の skill は自動で skills に足す。
        forbid: 読まれてはいけない skill と references。
        tags: 絞り込み用のタグ（`slow` は既定で除外）。
        note: 期待値の根拠や曖昧さのメモ。
        datasets: sandbox の `data/raw/<name>.csv` に置く題材データ（datasets.py の名前）。
        covers: このケースが試す references 内の分岐（`<references の stem>:<分岐名>`）。
    """

    id: str
    kind: str
    prompt: str
    expect: Expectation
    forbid: Expectation
    tags: tuple[str, ...] = ()
    note: str = ""
    datasets: tuple[str, ...] = ()
    covers: tuple[str, ...] = ()


@dataclass
class EvalConfig:
    """claude の起動条件と sandbox の作り方。

    Attributes:
        claude_bin: claude 実行ファイル。
        model: `--model` に渡す値。None なら claude の既定。
        effort: `--effort` に渡す値。None なら既定。
        max_budget_usd: 1 ケースあたりの上限（`--max-budget-usd`）。None なら上限なし。
        timeout_min: 1 ケースのタイムアウト（分）。
        permission_mode: `--permission-mode` に渡す値。
        allowed_tools: `--allowedTools` に渡す許可リスト。
        disallowed_tools: `--disallowedTools` に渡す拒否リスト。
        append_system_prompt: 無人実行のための追記。skill 名や手法には触れない。
        extra_args: そのほか claude に渡す引数。
        copy: sandbox にコピーするリポジトリ内のパス。
        data_files: sandbox に読み取り専用でコピーするデータファイル。
    """

    claude_bin: str = "claude"
    model: str | None = None
    effort: str | None = None
    max_budget_usd: float | None = None
    timeout_min: float = 40.0
    permission_mode: str = "acceptEdits"
    allowed_tools: list[str] = field(default_factory=list)
    disallowed_tools: list[str] = field(default_factory=list)
    append_system_prompt: str = ""
    extra_args: list[str] = field(default_factory=list)
    copy: list[str] = field(default_factory=list)
    data_files: list[str] = field(default_factory=list)


def _is_pattern(name: str) -> bool:
    return any(ch in name for ch in "*?[")


def resolve_reference(name: str, skills_dir: Path) -> str:
    """references の短い名前を `<skill>/references/<file>.md` に解決する。

    Args:
        name: `glm` のような拡張子なしのファイル名、または `<skill>/references/<file>.md`。
        skills_dir: `.claude/skills` ディレクトリ。

    Returns:
        `<skill>/references/<file>.md` 形式の相対パス。

    Raises:
        ValueError: 該当ファイルが無い、または複数の skill にまたがって見つかった場合。
    """
    if name.endswith(".md"):
        if not (skills_dir / name).is_file():
            raise ValueError(f"references が見つからない: {name}")
        return name
    hits = sorted(skills_dir.glob(f"*/references/{name}.md"))
    if len(hits) != 1:
        raise ValueError(f"references `{name}` の候補が {len(hits)} 件: {hits}")
    return hits[0].relative_to(skills_dir).as_posix()


def _parse_expectation(
    raw: dict[str, Any] | None, skills_dir: Path, *, allow_patterns: bool
) -> Expectation:
    raw = raw or {}
    skills = [str(s) for s in raw.get("skills", [])]
    refs: list[str] = []
    for r in raw.get("references", []):
        r = str(r)
        # forbid 側のパターンは解決せずそのまま照合に使う
        refs.append(r if allow_patterns and _is_pattern(r) else resolve_reference(r, skills_dir))
    if not allow_patterns:
        # references を読むにはルーターを通るはずなので、その skill も期待に足す
        for r in refs:
            owner = r.split("/", 1)[0]
            if owner not in skills:
                skills.append(owner)
        for s in skills:
            if not (skills_dir / s / "SKILL.md").is_file():
                raise ValueError(f"skill が見つからない: {s}")
    return Expectation(skills=tuple(skills), references=tuple(refs))


def _parse_variants(raw: dict[str, Any] | None) -> dict[str, tuple[str, ...]]:
    return {str(k): tuple(str(v) for v in vs) for k, vs in (raw or {}).items()}


def _parse_covers(
    cid: str,
    raw: dict[str, Any] | None,
    expect: Expectation,
    variants: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    expected_stems = {r.rsplit("/", 1)[-1].removesuffix(".md") for r in expect.references}
    covers: list[str] = []
    for stem, labels in (raw or {}).items():
        stem = str(stem)
        # 期待していない references の分岐を「試した」とは言えない
        if stem not in expected_stems:
            raise ValueError(f"{cid}: covers の {stem} が expect.references に無い")
        for label in labels:
            if str(label) not in variants.get(stem, ()):
                raise ValueError(f"{cid}: 未定義の分岐 {stem}:{label}")
            covers.append(f"{stem}:{label}")
    return tuple(covers)


def load_variants(path: Path) -> dict[str, tuple[str, ...]]:
    """cases.yaml の variants（references の stem → 分岐名の一覧）を返す。"""
    with path.open(encoding="utf-8") as f:
        return _parse_variants(yaml.safe_load(f).get("variants"))


def figure_table_heads(ref_path: Path) -> list[str]:
    """「必ず出す図」節の表の 1 列目（手法・条件ごとの分岐）を重複なしで返す。

    表で分岐を書いている references は、行を足したら cases.yaml の variants にも
    足す必要がある。その照合に使う。
    """
    heads: list[str] = []
    for item in expected_figures(ref_path, tables_only=True):
        head = item.split(": ", 1)[0]
        if head not in heads:
            heads.append(head)
    return heads


def load_suite(path: Path, skills_dir: Path) -> tuple[EvalConfig, list[Case]]:
    """cases.yaml を読み込み、設定とケース一覧を返す。

    Args:
        path: cases.yaml のパス。
        skills_dir: `.claude/skills` ディレクトリ（references の解決に使う）。

    Returns:
        (設定, ケースのリスト)。

    Raises:
        ValueError: ID の重複、未知の kind・datasets・分岐、
            存在しない skill・references がある場合。
    """
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    config = EvalConfig(**(raw.get("config") or {}))
    variants = _parse_variants(raw.get("variants"))
    cases: list[Case] = []
    seen: set[str] = set()
    for item in raw["cases"]:
        cid = str(item["id"])
        if cid in seen:
            raise ValueError(f"ケース ID が重複している: {cid}")
        seen.add(cid)
        kind = str(item["kind"])
        if kind not in KINDS:
            raise ValueError(f"{cid}: kind は {KINDS} のいずれか（{kind}）")
        datasets = tuple(str(d) for d in item.get("datasets", []))
        unknown = set(datasets) - set(GENERATORS)
        if unknown:
            raise ValueError(f"{cid}: 未知の datasets {sorted(unknown)}")
        expect = _parse_expectation(item.get("expect"), skills_dir, allow_patterns=False)
        covers = _parse_covers(cid, item.get("covers"), expect, variants)
        cases.append(
            Case(
                id=cid,
                kind=kind,
                prompt=str(item["prompt"]).strip(),
                expect=expect,
                forbid=_parse_expectation(item.get("forbid"), skills_dir, allow_patterns=True),
                tags=tuple(str(t) for t in item.get("tags", [])),
                note=str(item.get("note", "")).strip(),
                datasets=datasets,
                covers=covers,
            )
        )
    return config, cases


def reference_short_name(ref_path: Path) -> str | None:
    """references 冒頭の「短縮名」（図の保存先ディレクトリの接尾辞）を返す。"""
    m = SHORT_NAME_RE.search(ref_path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def expected_figures(ref_path: Path, *, tables_only: bool = False) -> list[str]:
    """references の「必ず出す図」節から、図の項目を取り出す。

    節内の書き方は 3 通りある。トップレベルの箇条書き（`- `）と番号付き（`1. `）は
    「 — 」より前（何の図か）を、表は「条件: 出す図」（先頭 2 列）を返す。
    合格基準は references 本体を見る。

    Args:
        ref_path: references の Markdown ファイル。
        tables_only: True なら表の行だけを返す。

    Returns:
        図の説明のリスト。節が無ければ空。
    """
    items: list[str] = []
    in_section = False
    for line in ref_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_section = line.startswith("## 必ず出す図")
            continue
        if not in_section:
            continue
        head: str | None = None
        if line.startswith("- ") and not tables_only:
            head = line[2:].split(" — ", 1)[0]
        elif not tables_only and (m := NUMBERED_RE.match(line)):
            head = m.group(1).split(" — ", 1)[0]
        elif line.startswith("|") and not TABLE_SEP_RE.match(line):
            # エスケープされた \| はセル区切りではない
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
            # ヘッダ行（「出す図」の列見出し）は項目ではない
            if len(cells) >= 2 and "出す図" not in line:
                head = f"{cells[0]}: {cells[1]}"
        if head is not None:
            # Markdown の強調とコード記法を落として一覧で読みやすくする
            items.append(re.sub(r"[`*]", "", head).strip())
    return items
