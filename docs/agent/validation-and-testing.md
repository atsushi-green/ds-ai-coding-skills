# テスト・検証方針

## pytest

- テストは `tests/` ディレクトリに配置する
- `uv run pytest` で実行する
- テストは高速に保つ（外部依存を最小限に）

## ruff

- `uv run ruff check .` でリントする
- `uv run ruff format .` でフォーマットする
- 設定は `pyproject.toml` の `[tool.ruff]` セクション

## mypy

- `uv run mypy src` で型チェックする
- 設定は `pyproject.toml` の `[tool.mypy]` セクション

## Notebook検証

- Notebookがクリーンなカーネルから再実行できることを確認する
- 秘密情報がセル出力に含まれていないことを確認する

## データ検証

- `uv run python scripts/check_no_raw_data_commit.py` — rawデータのコミット防止
- `uv run python scripts/check_no_sensitive_patterns.py` — 秘密情報パターンの検出

## エージェント文書検証

- `uv run python scripts/validate_agent_docs.py` — 必須ファイルの存在確認

## 一括実行

```bash
bash scripts/run_quality_checks.sh
```
