"""プロジェクトの外にある同名の skill を、テスト用のセッションから見えなくする。

Claude Code は、プロジェクトの `.claude/skills` のほかに、次の 2 つの skill も読み込む。

- ユーザーレベルの skill（`~/.claude/skills`）
- アカウントに登録した skill（claude.ai にアップロードしたもの。`anthropic-skills:<名前>` で見える）

そこにこのリポジトリの skill と同じ名前のものがあると、比較が成り立たなくなる。

- skill を外した条件でも、外したはずの skill がエージェントから見える
- フルの条件でも、同じ名前の skill が 2 つ見え、どちらが読まれるか分からない

そこで、実行を始める前に空のディレクトリで短い問い合わせを送り、プロジェクトの外から見えている
skill を調べる。同名のものは settings の `skillOverrides` で `off` にし、どの条件でも見えなくする。
名前空間（`anthropic-skills:` など）が付いていない同名の skill は、`off` にするとプロジェクトの
skill まで消えてしまうので、実行を始めずに知らせる。
"""

from __future__ import annotations

from pathlib import Path

from skill_eval.transcript import normalize_skill_name


def project_skill_names(skills_dir: Path) -> set[str]:
    """リポジトリの skill の名前（`SKILL.md` を持つディレクトリ名）。"""
    return {p.parent.name for p in skills_dir.glob("*/SKILL.md")}


def outside_copies(visible: list[str], project: set[str]) -> list[str]:
    """プロジェクトの外から見えている skill のうち、リポジトリの skill と同じ名前のもの。

    Args:
        visible: プロジェクトの無い場所（空のディレクトリ）で起動したセッションに
            見えている skill 名。
        project: リポジトリの skill の名前。

    Returns:
        同名の skill の名前（見えているままの形。名前空間つきのものを含む）。
    """
    return sorted({n for n in visible if normalize_skill_name(n) in project})


def namespaced_copies(visible: list[str], project: set[str]) -> list[str]:
    """sandbox の中のセッションに見えている skill のうち、名前空間つきの同名 skill。

    sandbox の中ではプロジェクトの skill も同じ名前で見えるので、名前空間（`plugin:skill` の
    `plugin:`）が付いているものだけを、プロジェクトの外のものと判断する。
    """
    return sorted({n for n in visible if ":" in n and normalize_skill_name(n) in project})


def plan_overrides(outside: list[str]) -> tuple[dict[str, str], list[str]]:
    """同名の skill を見えなくする指定と、見えなくできないものを返す。

    Args:
        outside: `outside_copies` の戻り値。

    Returns:
        `skillOverrides` に渡す辞書（名前空間つきの名前 → `off`）と、名前空間が無いので
        `off` にできない名前（プロジェクトの skill まで消えてしまう）。
    """
    overrides = {n: "off" for n in outside if ":" in n}
    blocking = [n for n in outside if ":" not in n]
    return overrides, blocking
