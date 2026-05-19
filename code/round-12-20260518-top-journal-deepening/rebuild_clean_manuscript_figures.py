from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib import font_manager


ROOT = Path.cwd()
ROUND_DIR = ROOT / "newstudy" / "result" / "round-12-20260518-top-journal-deepening"
TABLE_DIR = ROUND_DIR / "tables"
ROUND_FIG_DIR = ROUND_DIR / "figures"
MANUSCRIPT_FIG_DIR = ROOT / "稿件" / "assets" / "figures"


def configure_matplotlib() -> None:
    preferred = [
        "Microsoft YaHei",
        "SimHei",
        "SimSun",
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "Arial Unicode MS",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 140
    plt.rcParams["savefig.dpi"] = 240
    plt.rcParams["axes.edgecolor"] = "#333333"
    plt.rcParams["axes.linewidth"] = 0.8


def savefig(name: str) -> None:
    for out_dir in (MANUSCRIPT_FIG_DIR, ROUND_FIG_DIR):
        out_dir.mkdir(parents=True, exist_ok=True)
        plt.savefig(out_dir / name, bbox_inches="tight", facecolor="white")
    plt.close()


def clean_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#d9d9d9", linewidth=0.7, alpha=0.7)


def pct_axis(ax) -> None:
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=0))


def fig01_year_trend() -> None:
    df = pd.read_csv(TABLE_DIR / "descriptive_by_year.csv")
    x = df["year_int"].astype(int).to_numpy()
    y = df["invalid_rate"].astype(float).to_numpy()
    weights = df["n"].astype(float).to_numpy()
    coef = np.polyfit(x, y, deg=1, w=np.sqrt(weights))
    yhat = np.polyval(coef, x)

    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    ax.plot(x, y, color="#2B6CB0", marker="o", linewidth=2.1, label="年度否定性认定率")
    ax.plot(x, yhat, color="#D97706", linestyle="--", linewidth=2.0, label="样本期线性趋势")
    ax.axvline(2021, color="#8B1E3F", linestyle=":", linewidth=1.8)
    ax.text(2021.08, min(0.54, max(y) + 0.02), "2021政策节点", color="#8B1E3F", fontsize=10)
    ax.set_title("合同效力否定性认定的年度变化：持续上升趋势", fontsize=13, pad=12)
    ax.set_xlabel("裁判年份")
    ax.set_ylabel("无效或非完全有效率")
    ax.set_xticks(x)
    pct_axis(ax)
    clean_axes(ax)
    ax.legend(frameon=False, loc="upper left")
    savefig("fig01_invalid_rate_by_year.png")


def fig02_transaction_rates() -> None:
    df = pd.read_csv(TABLE_DIR / "descriptive_by_transaction.csv")
    excluded = {"OtherCivil", "OtherUnclassified"}
    df = df[~df["transaction_code"].isin(excluded)].copy()
    df = df.sort_values("invalid_rate", ascending=True)

    fig, ax = plt.subplots(figsize=(8.2, 4.9))
    colors = ["#4C78A8" if n >= 100 else "#9E6A03" for n in df["n"]]
    ax.barh(df["transaction_label"], df["invalid_rate"], color=colors, alpha=0.92)
    for i, row in enumerate(df.itertuples()):
        ax.text(row.invalid_rate + 0.012, i, f"{row.invalid_rate:.1%}  n={int(row.n)}", va="center", fontsize=9)
    ax.set_title("不同交易类型的无效或非完全有效率", fontsize=13, pad=12)
    ax.set_xlabel("无效或非完全有效率")
    ax.set_xlim(0, min(0.88, max(df["invalid_rate"]) + 0.14))
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=0))
    clean_axes(ax)
    savefig("fig02_invalid_rate_by_transaction.png")


def fig03_event_study() -> None:
    df = pd.read_csv(TABLE_DIR / "event_study_2020_base.csv")
    rows = []
    for row in df.itertuples():
        term = str(row.term)
        if term.startswith("year_"):
            year = int(term.split("_")[1])
        elif term == "base_2020":
            year = 2020
        else:
            continue
        rows.append(
            {
                "year": year,
                "coef": float(row.coef),
                "ci_low": float(row.ci_low),
                "ci_high": float(row.ci_high),
            }
        )
    plot = pd.DataFrame(rows).sort_values("year")
    post = plot[plot["year"] >= 2021].copy()
    post_coef = np.polyfit(post["year"], post["coef"], deg=1)
    post_yhat = np.polyval(post_coef, post["year"])

    fig, ax = plt.subplots(figsize=(8.3, 5.0))
    yerr = np.vstack([plot["coef"] - plot["ci_low"], plot["ci_high"] - plot["coef"]])
    ax.errorbar(
        plot["year"],
        plot["coef"],
        yerr=yerr,
        fmt="o",
        color="#2B6CB0",
        ecolor="#8DB3D9",
        elinewidth=1.6,
        capsize=3,
        label="相对2020年的动态系数",
    )
    ax.plot(post["year"], post_yhat, color="#D97706", linestyle="--", linewidth=2.0, label="2021后趋势引导线")
    ax.axhline(0, color="#333333", linewidth=0.9)
    ax.axvline(2021, color="#8B1E3F", linestyle=":", linewidth=1.6)
    ax.set_title("事件研究：2021后逐步抬升而非单点跳跃", fontsize=13, pad=12)
    ax.set_xlabel("裁判年份")
    ax.set_ylabel("相对2020年的概率差")
    ax.set_xticks(plot["year"])
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=0))
    clean_axes(ax)
    ax.legend(frameon=False, loc="upper left")
    savefig("fig03_event_study_2020_base.png")


def fig04_forest() -> None:
    df = pd.read_csv(TABLE_DIR / "model_key_terms.csv")
    df = df[df["term"].eq("post2021")].copy()
    keep = [
        ("m01_policy_baseline", "基准模型"),
        ("m02_add_transaction", "加入交易类型"),
        ("m03_add_region", "加入地区"),
        ("m04_linear_time_trend", "加入线性趋势"),
        ("m09_strict_dv", "严格因变量"),
        ("m12_winsor_amount", "金额缩尾"),
        ("m13_exclude_top1_amount", "剔除金额Top1%"),
    ]
    order = {m: i for i, (m, _) in enumerate(keep)}
    labels = {m: label for m, label in keep}
    df = df[df["model"].isin(order)].copy()
    df["order"] = df["model"].map(order)
    df["label"] = df["model"].map(labels)
    df = df.sort_values("order", ascending=False)
    y = np.arange(len(df))
    colors = ["#B91C1C" if m == "m04_linear_time_trend" else "#2B6CB0" for m in df["model"]]

    fig, ax = plt.subplots(figsize=(8.0, 4.9))
    ax.errorbar(
        df["coef"],
        y,
        xerr=np.vstack([df["coef"] - df["ci_low"], df["ci_high"] - df["coef"]]),
        fmt="none",
        ecolor="#7A7A7A",
        elinewidth=1.5,
        capsize=3,
    )
    ax.scatter(df["coef"], y, s=46, color=colors, zorder=3)
    ax.axvline(0, color="#333333", linewidth=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(df["label"])
    ax.set_xlabel("post2021系数及95%置信区间")
    ax.set_title("控制线性趋势后，独立2021水平跃升证据消失", fontsize=13, pad=12)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=0))
    clean_axes(ax)
    savefig("fig04_post2021_forest.png")


def fig05_amount_quartiles() -> None:
    df = pd.read_csv(TABLE_DIR / "descriptive_by_amount_quartile.csv")
    df = df[df["amount_quartile"].isin(["Q1", "Q2", "Q3", "Q4"])].copy()
    df["label"] = df["amount_quartile"].map(
        {
            "Q1": "Q1\n最低金额",
            "Q2": "Q2",
            "Q3": "Q3",
            "Q4": "Q4\n最高金额",
        }
    )

    fig, ax = plt.subplots(figsize=(7.2, 4.7))
    ax.bar(df["label"], df["invalid_rate"], color=["#4C78A8", "#72B7B2", "#F58518", "#B279A2"], alpha=0.93)
    for i, row in enumerate(df.itertuples()):
        ax.text(i, row.invalid_rate + 0.012, f"{row.invalid_rate:.1%}\nn={int(row.n)}", ha="center", fontsize=9)
    ax.set_title("金额四分位与合同效力否定性认定", fontsize=13, pad=12)
    ax.set_ylabel("无效或非完全有效率")
    ax.set_ylim(0, max(df["invalid_rate"]) + 0.11)
    pct_axis(ax)
    clean_axes(ax)
    savefig("fig05_amount_quartile_rates.png")


def fig06_region_rates() -> None:
    df = pd.read_csv(TABLE_DIR / "descriptive_by_region_macro.csv")
    df = df[df["region_macro_code"].ne("Unmapped")].copy()
    df = df.sort_values("invalid_rate", ascending=True)

    fig, ax = plt.subplots(figsize=(7.4, 4.7))
    ax.barh(df["region_macro_label"], df["invalid_rate"], color="#4C78A8", alpha=0.92)
    for i, row in enumerate(df.itertuples()):
        ax.text(row.invalid_rate + 0.012, i, f"{row.invalid_rate:.1%}  n={int(row.n)}", va="center", fontsize=9)
    ax.set_title("宏观地区与合同效力否定性认定", fontsize=13, pad=12)
    ax.set_xlabel("无效或非完全有效率")
    ax.set_xlim(0, max(df["invalid_rate"]) + 0.12)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=0))
    clean_axes(ax)
    savefig("fig06_region_rates.png")


def fig07_transaction_heterogeneity() -> None:
    df = pd.read_csv(TABLE_DIR / "heterogeneity_policy_effect_by_transaction.csv")
    df = df[~df["group"].isin({"OtherCivil", "OtherUnclassified"})].copy()
    df = df.sort_values("coef", ascending=True)
    y = np.arange(len(df))
    sig = df["p_value"] < 0.05
    colors = np.where(sig, "#2B6CB0", "#9CA3AF")

    fig, ax = plt.subplots(figsize=(8.1, 4.9))
    ax.errorbar(
        df["coef"],
        y,
        xerr=np.vstack([df["coef"] - df["ci_low"], df["ci_high"] - df["coef"]]),
        fmt="none",
        ecolor="#7A7A7A",
        elinewidth=1.5,
        capsize=3,
    )
    ax.scatter(df["coef"], y, color=colors, s=48, zorder=3)
    ax.axvline(0, color="#333333", linewidth=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(df["label"])
    ax.set_xlabel("2021后边际效应及95%置信区间")
    ax.set_title("政策节点效应的交易类型异质性", fontsize=13, pad=12)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=0))
    clean_axes(ax)
    savefig("fig07_policy_effect_by_transaction.png")


def main() -> None:
    configure_matplotlib()
    fig01_year_trend()
    fig02_transaction_rates()
    fig03_event_study()
    fig04_forest()
    fig05_amount_quartiles()
    fig06_region_rates()
    fig07_transaction_heterogeneity()


if __name__ == "__main__":
    main()
