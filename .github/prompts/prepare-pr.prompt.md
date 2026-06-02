---
agent: "agent"
description: "Prepare a PR summary"
---
Prepare a pull request summary for the current changes.

Include:
1. **変更内容**: What changed and which files were modified.
2. **変更理由**: Why the change was made.
3. **検証コマンド**: Commands to validate the changes:
   ```bash
   uv run pytest
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy src
   ```
4. **リスク**: Potential risks or side effects.
5. **影響ファイル**: List of files touched.

Write in Japanese. Keep it concise and reviewer-friendly.
