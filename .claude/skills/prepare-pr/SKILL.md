---
name: prepare-pr
description: 現在の変更に対するプルリクエストのサマリーを作成する
disable-model-invocation: true
---

# Skill: Prepare PR

現在の変更に対するプルリクエストのサマリーを作成する。

## 含める項目

1. **変更内容**: 何が変更され、どのファイルが修正されたか。
2. **変更理由**: なぜその変更を行ったか。
3. **検証コマンド**: 変更を検証するコマンド。

   ```bash
   uv run pytest
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy src
   ```

4. **リスク**: 潜在的なリスクや副作用。
5. **影響ファイル**: 変更されたファイルの一覧。

日本語で、簡潔かつレビュアーが読みやすい形式で記述する。
