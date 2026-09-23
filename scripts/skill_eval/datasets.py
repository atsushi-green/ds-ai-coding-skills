"""Titanic 以外の題材データを CSV に書き出す（sandbox の data/raw/ に置く用）。

プロンプトに「lifelines 同梱の」「numpy で作って」と書くと、
分析に使うライブラリを指示したことになり、
skill がライブラリ選択まで導けるかを試せない。そこで題材データはハーネス側で CSV にしておき、
プロンプトではファイルパスだけを示す。

生成先はリポジトリ外の sandbox（とそのキャッシュ）だけで、リポジトリの data/ には書かない。

使い方（ハーネスが呼ぶ）::

    uv run --with lifelines --with statsmodels python scripts/skill_eval/datasets.py rossi out.csv
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import numpy as np
import polars as pl


def _rossi() -> pl.DataFrame:
    # Rossi ら（1980）の再犯データ。出所者 432 人の再逮捕までの週数（week）と再逮捕の有無（arrest）
    from lifelines.datasets import load_rossi

    return pl.from_pandas(load_rossi())


def _co2() -> pl.DataFrame:
    # マウナロアの週次 CO2 濃度（1958〜2001 年）。欠測を含むが、そのまま渡す
    from statsmodels.datasets import co2

    df = co2.load_pandas().data.reset_index(names="date")
    return pl.from_pandas(df).with_columns(pl.col("date").dt.date())


def _ab_test() -> pl.DataFrame:
    # ユーザー単位の A/B テスト結果。各群 5000 人、CVR は A 10% / B 11%
    rng = np.random.default_rng(42)
    n = 5000
    group = np.repeat(["A", "B"], n)
    p = np.where(group == "A", 0.10, 0.11)
    return pl.DataFrame(
        {
            "user_id": np.arange(1, 2 * n + 1),
            "group": group,
            "converted": (rng.random(2 * n) < p).astype(np.int8),
        }
    ).sample(fraction=1.0, shuffle=True, seed=42)


def _store_panel() -> pl.DataFrame:
    # 20 店舗 × 24 か月の月次売上。店舗 1〜10 に 13 か月目から施策、効果は +5
    rng = np.random.default_rng(0)
    stores, months = 20, 24
    store_effect = rng.normal(100, 10, stores)
    rows = []
    for s in range(stores):
        for m in range(1, months + 1):
            treated = s < 10
            post = m >= 13
            sales = (
                store_effect[s]
                + 0.5 * m
                + 3 * np.sin(2 * np.pi * m / 12)
                + (5.0 if treated and post else 0.0)
                + rng.normal(0, 2)
            )
            rows.append(
                {
                    "store_id": s + 1,
                    "month": m,
                    "treated_store": int(treated),
                    "policy_active": int(treated and post),
                    "sales": round(float(sales), 2),
                }
            )
    return pl.DataFrame(rows)


def _macrodata() -> pl.DataFrame:
    # 米国の四半期マクロ系列（1959〜2009 年）。VAR の題材として 3 系列だけ残す
    from statsmodels.datasets import macrodata

    df = macrodata.load_pandas().data
    return pl.from_pandas(df[["year", "quarter", "realgdp", "realcons", "realinv"]]).with_columns(
        pl.col("year").cast(pl.Int32), pl.col("quarter").cast(pl.Int32)
    )


def _nile() -> pl.DataFrame:
    # ナイル川アスワンの年間流量（1871〜1970 年）。1898 年前後に水準が変わる
    from statsmodels.datasets import nile

    return pl.from_pandas(nile.load_pandas().data).with_columns(pl.col("year").cast(pl.Int32))


def _worker_panel() -> pl.DataFrame:
    # 労働者 200 人 × 6 年の賃金パネル。施策（処置）は無く、固定効果回帰の題材
    rng = np.random.default_rng(1)
    n, years = 200, 6
    ability = rng.normal(0, 0.3, n)
    rows = []
    for i in range(n):
        exp0 = rng.integers(0, 20)
        for t in range(years):
            hours = rng.normal(40, 5) + 3 * ability[i]
            exp = exp0 + t
            log_wage = 2.5 + ability[i] + 0.03 * exp - 0.0005 * exp**2 + 0.01 * hours
            rows.append(
                {
                    "worker_id": i + 1,
                    "year": 2015 + t,
                    "experience": int(exp),
                    "hours": round(float(hours), 1),
                    "log_wage": round(float(log_wage + rng.normal(0, 0.1)), 4),
                }
            )
    return pl.DataFrame(rows)


def _paired_scores() -> pl.DataFrame:
    # 研修の前後で同じ受講者 60 人が受けたテストの点数
    rng = np.random.default_rng(2)
    n = 60
    pre = rng.normal(60, 10, n)
    post = pre + rng.normal(3, 6, n)
    return pl.DataFrame(
        {
            "student_id": np.arange(1, n + 1),
            "score_before": np.clip(pre, 0, 100).round(0).astype(int),
            "score_after": np.clip(post, 0, 100).round(0).astype(int),
        }
    )


def _competing_churn() -> pl.DataFrame:
    # 契約 800 件の追跡。event: 0 = 打ち切り、1 = 解約、2 = 他プランへの乗り換え
    rng = np.random.default_rng(3)
    n = 800
    plan = rng.choice(["basic", "premium"], n)
    age = rng.integers(20, 70, n)
    rate_cancel = np.where(plan == "basic", 1 / 24, 1 / 40) * np.exp(-0.01 * (age - 40))
    rate_switch = np.where(plan == "basic", 1 / 30, 1 / 60)
    t_cancel = rng.exponential(1 / rate_cancel)
    t_switch = rng.exponential(1 / rate_switch)
    t_censor = rng.uniform(6, 36, n)
    t = np.minimum.reduce([t_cancel, t_switch, t_censor])
    event = np.select([t == t_cancel, t == t_switch], [1, 2], 0)
    return pl.DataFrame(
        {
            "contract_id": np.arange(1, n + 1),
            "plan": plan,
            "age": age,
            "months": np.round(t, 2),
            "event": event,
        }
    )


def _ab_revenue() -> pl.DataFrame:
    # ユーザー単位の売上の A/B テスト。大半は 0 円で、購入者の売上は裾が重い
    rng = np.random.default_rng(4)
    n = 4000
    group = np.repeat(["A", "B"], n)
    buy = rng.random(2 * n) < np.where(group == "A", 0.08, 0.085)
    amount = rng.lognormal(np.where(group == "A", 8.0, 8.05), 1.0)
    return pl.DataFrame(
        {
            "user_id": np.arange(1, 2 * n + 1),
            "group": group,
            "revenue": np.where(buy, amount.round(0), 0.0),
        }
    ).sample(fraction=1.0, shuffle=True, seed=4)


def _ab_multi() -> pl.DataFrame:
    # 3 群（A / B / C）の A/B/n テスト。CVR は A 10% / B 10.5% / C 11.5%
    rng = np.random.default_rng(5)
    n = 4000
    group = np.repeat(["A", "B", "C"], n)
    p = np.select([group == "A", group == "B"], [0.10, 0.105], 0.115)
    return pl.DataFrame(
        {
            "user_id": np.arange(1, 3 * n + 1),
            "group": group,
            "converted": (rng.random(3 * n) < p).astype(np.int8),
        }
    ).sample(fraction=1.0, shuffle=True, seed=5)


def _iv_schooling() -> pl.DataFrame:
    # 教育年数と賃金。能力（観測されない）が両方に効く。大学までの距離が操作変数の候補
    rng = np.random.default_rng(6)
    n = 3000
    ability = rng.normal(0, 1, n)
    distance = rng.exponential(20, n)
    urban = rng.integers(0, 2, n)
    school = 12 + 1.5 * ability - 0.05 * distance + 0.5 * urban + rng.normal(0, 1.5, n)
    log_wage = 1.5 + 0.08 * school + 0.3 * ability + 0.1 * urban + rng.normal(0, 0.3, n)
    return pl.DataFrame(
        {
            "person_id": np.arange(1, n + 1),
            "schooling_years": school.round(1),
            "distance_to_college_km": distance.round(1),
            "urban": urban,
            "log_wage": log_wage.round(4),
        }
    )


def _synth_panel() -> pl.DataFrame:
    # 地域 20 × 30 年の 1 人当たり消費量。地域 1 だけが 21 年目に規制を導入（効果 -8）
    rng = np.random.default_rng(7)
    regions, years = 20, 30
    loading = rng.normal(1, 0.2, regions)
    offset = rng.normal(0, 5, regions)
    common = np.cumsum(rng.normal(-0.3, 1, years)) + 100
    rows = []
    for r in range(regions):
        for t in range(years):
            y = offset[r] + loading[r] * common[t] + rng.normal(0, 1)
            if r == 0 and t >= 20:
                y -= 8
            rows.append({"region_id": r + 1, "year": 1990 + t, "consumption": round(float(y), 2)})
    return pl.DataFrame(rows)


def _survey_items() -> pl.DataFrame:
    # 500 人が答えた 8 問（5 件法）。q1〜q4 と q5〜q8 がそれぞれ 1 つの潜在因子を測る想定
    rng = np.random.default_rng(8)
    n = 500
    f = rng.multivariate_normal([0, 0], [[1, 0.4], [0.4, 1]], n)
    data: dict[str, np.ndarray] = {"respondent_id": np.arange(1, n + 1)}
    for j in range(8):
        latent = f[:, 0] if j < 4 else f[:, 1]
        x = 0.8 * latent + rng.normal(0, 0.6, n)
        data[f"q{j + 1}"] = np.clip(np.round(3 + x), 1, 5).astype(int)
    return pl.DataFrame(data)


def _cities() -> pl.DataFrame:
    # 巡回路を求める 40 地点の座標（km）
    rng = np.random.default_rng(9)
    n = 40
    return pl.DataFrame(
        {
            "city_id": np.arange(1, n + 1),
            "x_km": rng.uniform(0, 100, n).round(2),
            "y_km": rng.uniform(0, 100, n).round(2),
        }
    )


# 名前 → (生成に要る追加パッケージ, 生成関数)
GENERATORS: dict[str, tuple[list[str], Callable[[], pl.DataFrame]]] = {
    "rossi": (["lifelines"], _rossi),
    "co2": (["statsmodels"], _co2),
    "ab_test": ([], _ab_test),
    "store_panel": ([], _store_panel),
    "macrodata": (["statsmodels"], _macrodata),
    "nile": (["statsmodels"], _nile),
    "worker_panel": ([], _worker_panel),
    "paired_scores": ([], _paired_scores),
    "competing_churn": ([], _competing_churn),
    "ab_revenue": ([], _ab_revenue),
    "ab_multi": ([], _ab_multi),
    "iv_schooling": ([], _iv_schooling),
    "synth_panel": ([], _synth_panel),
    "survey_items": ([], _survey_items),
    "cities": ([], _cities),
}


def main(argv: list[str]) -> None:
    """`<name> <出力 CSV パス>` を受け取り、データを書き出す。"""
    name, out = argv
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    GENERATORS[name][1]().write_csv(path)


if __name__ == "__main__":
    main(sys.argv[1:])
