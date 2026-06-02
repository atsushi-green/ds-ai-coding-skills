---
name: dataframe-polars
description: Use this when performing DataFrame operations — including loading, filtering, joining, aggregating, transforming, or reshaping tabular data with polars or pandas.
---

# Skill: DataFrame Operations with Polars

Use this skill for DataFrame operations.

## Default: Polars

- Prefer **polars** for all DataFrame work.
- Prefer **LazyFrame** for loading, filtering, joins, aggregations, and transformations.
- Use eager execution when simpler and data is small.

## Pandas: Only When Required

- Use pandas **only** when required by an existing dependency, external library, or legacy code.
- If pandas is needed, keep its usage minimal and convert back to polars as soon as practical.

## Transformations

- Transformations should be reproducible and scriptable.
- Avoid manual, spreadsheet-like edits.
- Document data transformations with comments (in Japanese).

## Examples

### Lazy Scan and Filter

```python
import polars as pl

# Parquetファイルを遅延読み込み
lf = pl.scan_parquet("data/raw/events.parquet")

# 日付フィルタと列選択
result = (
    lf.filter(pl.col("event_date") >= "2024-01-01")
    .select(["user_id", "event_type", "event_date"])
    .collect()
)
```

### Group By and Aggregation

```python
# ユーザーごとのイベント数を集計
summary = (
    lf.group_by("user_id")
    .agg(
        pl.col("event_type").count().alias("event_count"),
        pl.col("event_date").max().alias("last_event"),
    )
    .collect()
)
```

### Safe Join with Row Count Check

```python
left = pl.scan_parquet("data/processed/users.parquet")
right = pl.scan_parquet("data/processed/orders.parquet")

# 結合前の行数を確認
left_count = left.select(pl.len()).collect().item()
right_count = right.select(pl.len()).collect().item()

joined = left.join(right, on="user_id", how="left").collect()

# 結合後の行数を確認（ファンアウトの検出）
assert joined.height >= left_count, "LEFT JOINで行が減少：joinキーを確認"
print(f"left={left_count}, right={right_count}, joined={joined.height}")
```
