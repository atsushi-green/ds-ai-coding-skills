# セキュリティ・プライバシー

## Raw Data

- `data/raw/` と `data/external/` は `.gitignore` でコミット対象外にしている。
- これらのディレクトリのデータは不変として扱う。

## Credentials・Secrets

- `.env` ファイルは `.gitignore` でコミット対象外。
- `.env.example` にキー名のみ記載し、実際の値は含めない。
- APIキー、トークン、パスワードをコード中にハードコードしない。
- `python-dotenv` を使って環境変数から読み込む。

## PII・顧客データ

- 個人を特定できる情報（PII）をコミットしない。
- 顧客レベルのレコードをコミットしない。
- 集計・匿名化したデータのみ `data/processed/` や `outputs/` に保存可能。
- 分析結果にも個人が特定されないよう注意する。

## 検証スクリプト

- `scripts/check_no_raw_data_commit.py` — rawデータのコミットを検知する。
- `scripts/check_no_sensitive_patterns.py` — 秘密情報のパターンを検知する。

## CIでの保護

- GitHub Actions CI で上記スクリプトを自動実行し、違反を検知する。
