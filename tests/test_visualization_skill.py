"""visualization skill の Example が、書いてあるとおりに動くことのテスト。

エージェントは skill のコード例をほぼそのまま写すので、例が壊れていると毎回同じ失敗をする。
検証する契約:
- 末尾の Example をそのまま実行でき、図が保存される
- 日本語のタイトル・軸ラベルが豆腐（グリフ欠け）にならない
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 画面の無い環境（CI）でも描けるようにする

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / ".claude" / "skills" / "visualization" / "SKILL.md"


def _example_code() -> str:
    """skill の「## Example」節にある Python コードブロックを取り出す。"""
    example = SKILL.read_text(encoding="utf-8").split("## Example", 1)[1]
    match = re.search(r"```python\n(.*?)```", example, flags=re.DOTALL)
    assert match, "visualization skill の Example にコードブロックが無い"
    return match.group(1)


def test_example_runs_and_renders_japanese(tmp_path: Path, monkeypatch) -> None:
    # 例は outputs/figures/ への相対パスで保存するので、作業ディレクトリを一時ディレクトリに移す
    monkeypatch.chdir(tmp_path)
    # 例が前提にしている変数
    namespace = {"categories": ["1月", "2月", "3月"], "values": [120, 150, 90]}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        exec(compile(_example_code(), str(SKILL), "exec"), namespace)  # noqa: S102

    saved = list((tmp_path / "outputs" / "figures").glob("*.png"))
    assert len(saved) == 1
    # フォントが日本語を持たないと matplotlib が「Glyph ... missing from font(s)」を出す
    missing = [str(w.message) for w in caught if "Glyph" in str(w.message)]
    assert missing == [], f"日本語が豆腐になっている: {missing[:3]}"
