---
name: update-agent-docs
description: リポジトリの規約が変更されたときにCLAUDE.md・スキル・docs/agentを更新する
disable-model-invocation: true
---

# Skill: Update Agent Docs

リポジトリの規約が変更された際に、関連するエージェント文書を更新する。

変更内容が渡されていない場合は、まずユーザーにどの規約・ルールが変更されたかを確認する。

## 手順

1. `CLAUDE.md` のルーティングテーブルやルールに更新が必要か確認する。
2. `.claude/skills/*/SKILL.md` に更新が必要なものがないか確認する。
3. `docs/agent/*.md` に更新が必要なものがないか確認する。

## ルール

- `CLAUDE.md` は薄く保つ — 詳細ガイドではなくルーターである。
- 詳細なルールを複数ファイルに重複させない。
- 内容をコピーするのではなく、スキルファイルへのリンクを優先する。
- 変更後は `uv run python scripts/validate_agent_docs.py` を実行する。
