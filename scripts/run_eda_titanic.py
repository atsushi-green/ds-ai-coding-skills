"""Titanic EDA スクリプト：生存に効く変数を探索する。

使い方:
    uv run python scripts/run_eda_titanic.py
"""

from __future__ import annotations

from analysis_project.eda_titanic import (
    basic_summary,
    load_titanic,
    plot_age_distribution,
    plot_correlation_heatmap,
    plot_fare_vs_survival,
    plot_survival_rate_bar,
    survival_rate_age_bins,
    survival_rate_by,
    survival_rate_fare_bins,
)
from analysis_project.paths import data_dir, ensure_parent_dir, outputs_dir


def main() -> None:
    """EDA メイン処理。"""
    # ------------------------------------------------------------------
    # パス設定
    # ------------------------------------------------------------------
    csv_path = data_dir() / "raw" / "titanic" / "train.csv"
    tables_dir = outputs_dir() / "tables"
    figures_dir = outputs_dir() / "figures"

    # ------------------------------------------------------------------
    # データ読み込み（生データは読み取り専用）
    # ------------------------------------------------------------------
    print(f"[INFO] データ読み込み: {csv_path}")
    df = load_titanic(csv_path)
    print(f"[INFO] 行数={df.height}, 列数={df.width}")

    # ------------------------------------------------------------------
    # 1. 基本サマリー
    # ------------------------------------------------------------------
    summary = basic_summary(df)
    print("\n--- 基本サマリー ---")
    print(summary)
    summary_path = ensure_parent_dir(tables_dir / "titanic_basic_summary.csv")
    summary.write_csv(summary_path)
    print(f"[SAVE] {summary_path}")

    # ------------------------------------------------------------------
    # 2. カテゴリ別生存率
    # ------------------------------------------------------------------
    # 客室クラス
    rate_pclass = survival_rate_by(df, "Pclass")
    print("\n--- 客室クラス別生存率 ---")
    print(rate_pclass)
    rate_pclass_path = ensure_parent_dir(tables_dir / "survival_rate_by_pclass.csv")
    rate_pclass.write_csv(rate_pclass_path)
    print(f"[SAVE] {rate_pclass_path}")

    # 性別
    rate_sex = survival_rate_by(df, "Sex")
    print("\n--- 性別生存率 ---")
    print(rate_sex)
    rate_sex_path = ensure_parent_dir(tables_dir / "survival_rate_by_sex.csv")
    rate_sex.write_csv(rate_sex_path)
    print(f"[SAVE] {rate_sex_path}")

    # 乗船港
    rate_embarked = survival_rate_by(df, "Embarked")
    print("\n--- 乗船港別生存率 ---")
    print(rate_embarked)
    rate_embarked_path = ensure_parent_dir(tables_dir / "survival_rate_by_embarked.csv")
    rate_embarked.write_csv(rate_embarked_path)
    print(f"[SAVE] {rate_embarked_path}")

    # 年齢ビン
    rate_age = survival_rate_age_bins(df)
    print("\n--- 年齢ビン別生存率 ---")
    print(rate_age)
    rate_age_path = ensure_parent_dir(tables_dir / "survival_rate_by_age_bin.csv")
    rate_age.write_csv(rate_age_path)
    print(f"[SAVE] {rate_age_path}")

    # 運賃分位ビン
    rate_fare = survival_rate_fare_bins(df)
    print("\n--- 運賃分位ビン別生存率 ---")
    print(rate_fare)
    rate_fare_path = ensure_parent_dir(tables_dir / "survival_rate_by_fare_bin.csv")
    rate_fare.write_csv(rate_fare_path)
    print(f"[SAVE] {rate_fare_path}")

    # ------------------------------------------------------------------
    # 3. 可視化
    # ------------------------------------------------------------------
    print("\n[INFO] 図を生成中...")

    # 客室クラス別生存率
    plot_survival_rate_bar(
        rate_pclass,
        "Pclass",
        title="客室クラス別 生存率",
        xlabel="客室クラス (1=上, 3=下)",
        output_path=figures_dir / "survival_rate_by_pclass.png",
    )
    print(f"[SAVE] {figures_dir / 'survival_rate_by_pclass.png'}")

    # 性別生存率
    plot_survival_rate_bar(
        rate_sex,
        "Sex",
        title="性別 生存率",
        xlabel="性別",
        output_path=figures_dir / "survival_rate_by_sex.png",
    )
    print(f"[SAVE] {figures_dir / 'survival_rate_by_sex.png'}")

    # 乗船港別生存率
    plot_survival_rate_bar(
        rate_embarked.drop_nulls("Embarked"),
        "Embarked",
        title="乗船港別 生存率",
        xlabel="乗船港 (C=Cherbourg, Q=Queenstown, S=Southampton)",
        output_path=figures_dir / "survival_rate_by_embarked.png",
    )
    print(f"[SAVE] {figures_dir / 'survival_rate_by_embarked.png'}")

    # 年齢分布
    plot_age_distribution(df, output_path=figures_dir / "age_distribution_by_survival.png")
    print(f"[SAVE] {figures_dir / 'age_distribution_by_survival.png'}")

    # 運賃箱ひげ図
    plot_fare_vs_survival(df, output_path=figures_dir / "fare_boxplot_by_survival.png")
    print(f"[SAVE] {figures_dir / 'fare_boxplot_by_survival.png'}")

    # 相関ヒートマップ
    plot_correlation_heatmap(df, output_path=figures_dir / "correlation_heatmap.png")
    print(f"[SAVE] {figures_dir / 'correlation_heatmap.png'}")

    print("\n[DONE] EDA 完了")


if __name__ == "__main__":
    main()
