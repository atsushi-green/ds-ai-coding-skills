---
name: review-sql
description: SQLクエリの正確性と安全性をレビューする
disable-model-invocation: true
---

# Skill: Review SQL

[sql-analysis](.claude/skills/sql-analysis/SKILL.md) のチェックリストを使って、提示されたSQLクエリをレビューする。

レビュー対象のクエリが渡されていない場合は、ユーザーにレビューしたいSQLクエリを貼り付けるよう依頼する。

## チェック項目

- `SELECT *` の使用（明示的なカラム指定にすべきか）
- 大規模テーブルへの日付フィルタの欠如
- JOINカーディナリティの問題（1:1, 1:N, M:N）
- JOIN前後の行数検証
- 破壊的な文（DROP, TRUNCATE, DELETE, UPDATE）
- 指標定義の曖昧さ
- NULLの扱い
- 重複のリスク
- 暗黙的なクロスジョイン

具体的な行参照と修正案を添えて、日本語でフィードバックする。
