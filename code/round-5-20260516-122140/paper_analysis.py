from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


ROUND = "round-5-20260516-122140"
ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "data" / "processed" / "master" / "master_dataset.csv"
ROUND4_DERIVED = ROOT / "result" / "round-4-20260516-071827" / "analysis_dataset_derived.csv"
OUTDIR = ROOT / "result" / ROUND
FIGDIR = OUTDIR / "figures"
OUTDIR.mkdir(parents=True, exist_ok=True)
FIGDIR.mkdir(parents=True, exist_ok=True)


def clean_str(value: Any) -> str:
    if pd.isna(value):
        return ""
    s = str(value).strip()
    if s.lower() in {"nan", "none", "null"}:
        return ""
    return s


def to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def safe_float(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)) or math.isinf(float(value)):
            return None
        return float(value)
    return value


def classify_transaction_type(activity: Any, cause: Any) -> str:
    text = f"{clean_str(activity)} {clean_str(cause)}"
    if not text.strip() or any(x in text for x in ["未分类", "未知", "不适用"]):
        if not any(x in text for x in ["借贷", "合同", "交易", "买卖", "理财", "投资", "挖矿", "发币", "ICO", "技术"]):
            return "未分类"
    if any(x in text for x in ["发币", "ICO", "首次代币", "代币发行", "非法金融"]):
        return "ICO/发币"
    if any(x in text for x in ["委托理财", "代投", "投资", "炒币", "理财"]):
        return "投资/理财"
    if any(x in text for x in ["场外交易", "OTC", "虚拟货币交易", "虚拟货币买卖", "虚拟货币兑换", "买卖合同", "买卖", "交易"]):
        return "交易/买卖"
    if any(x in text for x in ["借贷", "借款", "民间借贷"]):
        return "借贷"
    if "挖矿" in text:
        return "挖矿"
    if any(x in text for x in ["技术服务", "网络服务", "服务合同", "信息网络传播权"]):
        return "技术服务"
    if any(x in text for x in ["赌博", "赌场", "诈骗", "传销", "掩饰", "隐瞒", "洗钱", "非法吸收", "帮助信息网络犯罪"]):
        return "其他/未分类"
    if any(x in text for x in ["合同", "不当得利"]):
        return "其他民商事"
    return "其他/未分类"


def civil_main_sample(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        (df["case_domain"] == "民商事")
        & df["contract_invalid"].notna()
        & df["year"].notna()
        & (df["year"] >= 2014)
        & (df["year"] <= 2024)
    ].copy()
    return out


def set_plot_style() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 120


def fit_lpm(formula: str, data: pd.DataFrame, model: str, note: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        res = smf.ols(formula=formula, data=data).fit(cov_type="HC1")
        conf = res.conf_int()
        rows = []
        for term, coef in res.params.items():
            rows.append(
                {
                    "model": model,
                    "term": term,
                    "coef": float(coef),
                    "std_err": float(res.bse[term]),
                    "p_value": float(res.pvalues[term]),
                    "ci_low": float(conf.loc[term, 0]),
                    "ci_high": float(conf.loc[term, 1]),
                    "nobs": int(res.nobs),
                    "rsquared": float(res.rsquared),
                    "dep_mean": float(np.mean(res.model.endog)),
                    "note": note,
                    "error": "",
                }
            )
        meta = {
            "model": model,
            "nobs": int(res.nobs),
            "rsquared": float(res.rsquared),
            "dep_mean": float(np.mean(res.model.endog)),
            "note": note,
            "error": "",
        }
        return pd.DataFrame(rows), meta
    except Exception as exc:
        return (
            pd.DataFrame(
                [
                    {
                        "model": model,
                        "term": "",
                        "coef": np.nan,
                        "std_err": np.nan,
                        "p_value": np.nan,
                        "ci_low": np.nan,
                        "ci_high": np.nan,
                        "nobs": 0,
                        "rsquared": np.nan,
                        "dep_mean": np.nan,
                        "note": note,
                        "error": str(exc),
                    }
                ]
            ),
            {"model": model, "note": note, "error": str(exc)},
        )


def grouped_rate(df: pd.DataFrame, by: str) -> pd.DataFrame:
    return (
        df.groupby(by, dropna=False)
        .agg(
            rows=("doc_id", "size"),
            validity_n=("contract_invalid", "count"),
            invalid_n=("contract_invalid", "sum"),
            invalid_rate=("contract_invalid", "mean"),
            amount_n=("amount_master_cny", "count"),
            amount_median=("amount_master_cny", "median"),
            llm_amount_n=("llm_top_case_amount_cny", "count"),
            regex_amount_n=("regex_text_amount_max_cny", "count"),
        )
        .reset_index()
        .sort_values(["validity_n", "rows"], ascending=False)
    )


def add_event_dummies(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["rel_year_2021"] = out["year"].astype(int) - 2021
    for k in range(-6, 4):
        if k == -1:
            continue
        name = f"event_{'m' + str(abs(k)) if k < 0 else 'p' + str(k)}"
        out[name] = (out["rel_year_2021"] == k).astype(int)
    return out


def event_terms() -> list[tuple[int, str]]:
    terms = []
    for k in range(-6, 4):
        if k == -1:
            continue
        name = f"event_{'m' + str(abs(k)) if k < 0 else 'p' + str(k)}"
        terms.append((k, name))
    return terms


def extract_terms(reg: pd.DataFrame, model: str, terms: list[str]) -> pd.DataFrame:
    return reg[(reg["model"] == model) & reg["term"].isin(terms)].copy()


def write_csv(df: pd.DataFrame, name: str) -> None:
    df.to_csv(OUTDIR / name, index=False, encoding="utf-8-sig")


def main() -> None:
    derived = pd.read_csv(ROUND4_DERIVED, encoding="utf-8-sig")
    master_cols = [
        "doc_id",
        "activity_type",
        "index_case_cause",
        "case_number",
        "index_case_number",
        "case_type_primary",
        "doc_type",
    ]
    master = pd.read_csv(MASTER, encoding="utf-8-sig", usecols=master_cols)
    df = derived.merge(master, on="doc_id", how="left", validate="one_to_one")

    numeric_cols = [
        "year",
        "post2017",
        "post2021",
        "contract_invalid",
        "contract_invalid_strict",
        "amount_master_cny",
        "llm_top_case_amount_cny",
        "regex_text_amount_max_cny",
        "amount_regex_fallback_flag",
        "amount_llm_regex_conflict_flag",
        "log_amount_master",
        "log_llm_case_amount",
        "log_regex_text_max",
        "high_amount",
        "region_big4",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = to_num(df[col])

    df["transaction_type"] = [
        classify_transaction_type(activity, cause)
        for activity, cause in zip(df["activity_type"], df["index_case_cause"])
    ]
    order = ["借贷", "投资/理财", "交易/买卖", "ICO/发币", "挖矿", "技术服务", "其他民商事", "其他/未分类", "未分类"]
    df["transaction_type"] = pd.Categorical(df["transaction_type"], categories=order, ordered=False)
    df["year_group"] = df["year"].astype("Int64").astype("string")
    df["post2021"] = np.where(df["year"].notna(), (df["year"] >= 2021).astype(int), np.nan)
    df["post2017"] = np.where(df["year"].notna(), (df["year"] >= 2017).astype(int), np.nan)
    df["q4_amount"] = (df["amount_quartile"] == "Q4最高").astype(int)

    civil = civil_main_sample(df)
    civil_event = add_event_dummies(civil[(civil["year"] >= 2015) & (civil["year"] <= 2024)].copy())

    tables: dict[str, pd.DataFrame] = {}
    tables["sample_overview"] = pd.DataFrame(
        [
            {"sample": "all_rows", "rows": len(df), "validity_n": int(df["contract_invalid"].notna().sum()), "invalid_rate": float(df["contract_invalid"].mean(skipna=True))},
            {"sample": "civil_main_2014_2024", "rows": len(civil), "validity_n": int(civil["contract_invalid"].notna().sum()), "invalid_rate": float(civil["contract_invalid"].mean(skipna=True))},
            {"sample": "criminal_reference", "rows": int((df["case_domain"] == "刑事").sum()), "validity_n": int(df.loc[df["case_domain"] == "刑事", "contract_invalid"].notna().sum()), "invalid_rate": float(df.loc[df["case_domain"] == "刑事", "contract_invalid"].mean(skipna=True))},
        ]
    )
    tables["civil_by_year"] = grouped_rate(civil, "year")
    tables["civil_by_transaction"] = grouped_rate(civil, "transaction_type")
    tables["civil_by_amount_quartile"] = grouped_rate(civil, "amount_quartile")
    tables["civil_by_region_macro"] = grouped_rate(civil, "region_macro")
    tables["civil_by_province"] = grouped_rate(civil, "region_province")
    tables["civil_by_big4"] = grouped_rate(civil, "region_big4")
    tables["civil_by_court_level"] = grouped_rate(civil, "court_level_group")
    tables["civil_by_cause"] = grouped_rate(civil, "index_case_cause").head(50)

    # Difference-in-means style policy contrasts by subgroup.
    contrasts = []
    for by in ["transaction_type", "amount_quartile", "region_macro", "region_big4"]:
        grouped = civil.groupby([by, "post2021"], dropna=False)["contract_invalid"].agg(["count", "mean"]).reset_index()
        wide = grouped.pivot(index=by, columns="post2021", values=["count", "mean"])
        for idx in wide.index:
            pre_n = safe_float(wide.loc[idx, ("count", 0)]) if ("count", 0) in wide.columns else None
            post_n = safe_float(wide.loc[idx, ("count", 1)]) if ("count", 1) in wide.columns else None
            pre_mean = safe_float(wide.loc[idx, ("mean", 0)]) if ("mean", 0) in wide.columns else None
            post_mean = safe_float(wide.loc[idx, ("mean", 1)]) if ("mean", 1) in wide.columns else None
            diff = None if pre_mean is None or post_mean is None else post_mean - pre_mean
            contrasts.append(
                {
                    "group_variable": by,
                    "group": idx,
                    "pre2021_n": pre_n,
                    "post2021_n": post_n,
                    "pre2021_invalid_rate": pre_mean,
                    "post2021_invalid_rate": post_mean,
                    "diff_post_minus_pre": diff,
                }
            )
    tables["policy_contrasts"] = pd.DataFrame(contrasts)

    common_controls = (
        "amount_llm_regex_conflict_flag + amount_regex_fallback_flag + "
        "C(court_level_group) + C(index_case_cause)"
    )
    trans = "C(transaction_type, Treatment(reference='借贷'))"

    specs = [
        (
            "m1_policy_baseline",
            f"contract_invalid ~ post2021 + log_amount_master + {common_controls}",
            civil,
            "Civil main sample; 2021 post indicator, master amount, amount-quality flags, court level and cause controls.",
        ),
        (
            "m2_transaction_types",
            f"contract_invalid ~ post2021 + {trans} + log_amount_master + {common_controls}",
            civil,
            "Adds compressed transaction types.",
        ),
        (
            "m3_policy_by_transaction",
            f"contract_invalid ~ post2021 * {trans} + log_amount_master + {common_controls}",
            civil,
            "Policy effect heterogeneity by transaction type.",
        ),
        (
            "m4_amount_quartiles",
            f"contract_invalid ~ post2021 + C(amount_quartile, Treatment(reference='Q1最低')) + {trans} + {common_controls}",
            civil[civil["amount_quartile"].ne("missing")].copy(),
            "Uses amount quartiles instead of linear log amount.",
        ),
        (
            "m5_policy_by_q4_amount",
            f"contract_invalid ~ post2021 * q4_amount + {trans} + log_amount_master + {common_controls}",
            civil,
            "Policy effect heterogeneity for top amount quartile.",
        ),
        (
            "m6_llm_amount",
            f"contract_invalid ~ post2021 + {trans} + log_llm_case_amount + amount_llm_regex_conflict_flag + C(court_level_group) + C(index_case_cause)",
            civil,
            "Uses LLM top-level case amount.",
        ),
        (
            "m7_regex_amount",
            f"contract_invalid ~ post2021 + {trans} + log_regex_text_max + amount_llm_regex_conflict_flag + C(court_level_group) + C(index_case_cause)",
            civil,
            "Uses full-text regex maximum amount.",
        ),
        (
            "m8_region_big4",
            f"contract_invalid ~ post2021 + region_big4 + {trans} + log_amount_master + {common_controls}",
            civil[civil["region_province"].astype(str).ne("")].copy(),
            "Adds Big4 region indicator.",
        ),
        (
            "m9_policy_by_big4",
            f"contract_invalid ~ post2021 * region_big4 + {trans} + log_amount_master + {common_controls}",
            civil[civil["region_province"].astype(str).ne("")].copy(),
            "Policy effect heterogeneity by Big4 region.",
        ),
        (
            "m10_region_macro",
            f"contract_invalid ~ post2021 + C(region_macro) + {trans} + log_amount_master + {common_controls}",
            civil[civil["region_macro"].astype(str).ne("未映射")].copy(),
            "Adds macro-region categories.",
        ),
        (
            "m11_strict_dv",
            f"contract_invalid_strict ~ post2021 + {trans} + log_amount_master + {common_controls}",
            civil[civil["contract_invalid_strict"].notna()].copy(),
            "Strict DV robustness.",
        ),
    ]

    event_formula = (
        "contract_invalid ~ "
        + " + ".join(name for _, name in event_terms())
        + f" + {trans} + log_amount_master + {common_controls}"
    )
    specs.append(
        (
            "m12_event_study",
            event_formula,
            civil_event,
            "Event study around 2021; 2020 is omitted reference year.",
        )
    )

    reg_frames = []
    reg_meta = []
    for name, formula, data, note in specs:
        rows, meta = fit_lpm(formula, data, name, note)
        reg_frames.append(rows)
        reg_meta.append(meta)
    regressions = pd.concat(reg_frames, ignore_index=True)
    regression_meta = pd.DataFrame(reg_meta)

    key_terms = [
        "post2021",
        "log_amount_master",
        "log_llm_case_amount",
        "log_regex_text_max",
        "q4_amount",
        "post2021:q4_amount",
        "region_big4",
        "post2021:region_big4",
        "amount_llm_regex_conflict_flag",
        "amount_regex_fallback_flag",
    ]
    key_regressions = regressions[regressions["term"].isin(key_terms)].copy()

    event_rows = []
    for rel, term in event_terms():
        match = regressions[(regressions["model"] == "m12_event_study") & (regressions["term"] == term)]
        if match.empty:
            continue
        row = match.iloc[0].to_dict()
        row["relative_year"] = rel
        row["calendar_year"] = 2021 + rel
        event_rows.append(row)
    event_df = pd.DataFrame(event_rows).sort_values("relative_year")

    derived_effects = []
    m3 = regressions[regressions["model"] == "m3_policy_by_transaction"].copy()
    if not m3.empty:
        base = float(m3.loc[m3["term"] == "post2021", "coef"].iloc[0])
        trans_rows = m3[m3["term"].str.startswith("post2021:C(transaction_type", na=False)].copy()
        for _, row in trans_rows.iterrows():
            term = str(row["term"])
            group = term.split("[T.")[-1].rstrip("]")
            derived_effects.append(
                {
                    "dimension": "transaction_type",
                    "group": group,
                    "baseline_group": "借贷",
                    "post2021_effect": base + float(row["coef"]),
                    "baseline_post2021": base,
                    "interaction_coef": float(row["coef"]),
                    "interaction_term": term,
                }
            )
        derived_effects.append(
            {
                "dimension": "transaction_type",
                "group": "借贷",
                "baseline_group": "借贷",
                "post2021_effect": base,
                "baseline_post2021": base,
                "interaction_coef": 0.0,
                "interaction_term": "",
            }
        )

    m5 = regressions[regressions["model"] == "m5_policy_by_q4_amount"].copy()
    if not m5.empty:
        base = float(m5.loc[m5["term"] == "post2021", "coef"].iloc[0])
        inter = m5[m5["term"] == "post2021:q4_amount"]
        q4_inter = float(inter["coef"].iloc[0]) if not inter.empty else 0.0
        derived_effects.append(
            {
                "dimension": "amount_q4",
                "group": "Q4最高",
                "baseline_group": "Q1-Q3",
                "post2021_effect": base + q4_inter,
                "baseline_post2021": base,
                "interaction_coef": q4_inter,
                "interaction_term": "post2021:q4_amount",
            }
        )
        derived_effects.append(
            {
                "dimension": "amount_q4",
                "group": "Q1-Q3",
                "baseline_group": "Q1-Q3",
                "post2021_effect": base,
                "baseline_post2021": base,
                "interaction_coef": 0.0,
                "interaction_term": "",
            }
        )

    m9 = regressions[regressions["model"] == "m9_policy_by_big4"].copy()
    if not m9.empty:
        base = float(m9.loc[m9["term"] == "post2021", "coef"].iloc[0])
        inter = m9[m9["term"] == "post2021:region_big4"]
        big4_inter = float(inter["coef"].iloc[0]) if not inter.empty else 0.0
        derived_effects.append(
            {
                "dimension": "region_big4",
                "group": "Big4",
                "baseline_group": "non-Big4",
                "post2021_effect": base + big4_inter,
                "baseline_post2021": base,
                "interaction_coef": big4_inter,
                "interaction_term": "post2021:region_big4",
            }
        )
        derived_effects.append(
            {
                "dimension": "region_big4",
                "group": "non-Big4",
                "baseline_group": "non-Big4",
                "post2021_effect": base,
                "baseline_post2021": base,
                "interaction_coef": 0.0,
                "interaction_term": "",
            }
        )

    derived_effects_df = pd.DataFrame(derived_effects)

    set_plot_style()
    year_tab = tables["civil_by_year"].sort_values("year")
    fig, ax1 = plt.subplots(figsize=(8, 4.6))
    ax1.bar(year_tab["year"].astype(int), year_tab["rows"], color="#7aa6c2", alpha=0.75)
    ax1.set_ylabel("案件数")
    ax1.set_xlabel("裁判年份")
    ax2 = ax1.twinx()
    ax2.plot(year_tab["year"].astype(int), year_tab["invalid_rate"], color="#b6463a", marker="o")
    ax2.axvline(2021, color="#333333", linestyle="--", linewidth=1)
    ax2.set_ylabel("非完全有效率")
    ax2.set_ylim(0, min(1, max(0.75, float(year_tab["invalid_rate"].max()) + 0.1)))
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig_civil_year_trend.png")
    plt.close(fig)

    tx_tab = tables["civil_by_transaction"].copy()
    tx_tab = tx_tab[tx_tab["validity_n"] >= 20].sort_values("invalid_rate", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(tx_tab["transaction_type"].astype(str), tx_tab["invalid_rate"], color="#6d8f71")
    ax.set_xlabel("非完全有效率")
    ax.set_ylabel("交易类型")
    ax.set_xlim(0, 1)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig_invalid_rate_by_transaction.png")
    plt.close(fig)

    if not event_df.empty:
        fig, ax = plt.subplots(figsize=(8, 4.6))
        ax.errorbar(
            event_df["calendar_year"],
            event_df["coef"],
            yerr=[event_df["coef"] - event_df["ci_low"], event_df["ci_high"] - event_df["coef"]],
            fmt="o-",
            color="#4f6f9f",
            ecolor="#9da9bd",
            capsize=3,
        )
        ax.axhline(0, color="#333333", linewidth=1)
        ax.axvline(2021, color="#b6463a", linestyle="--", linewidth=1)
        ax.set_xlabel("年份")
        ax.set_ylabel("相对 2020 年的系数")
        ax.set_title("2021 政策节点事件研究")
        fig.tight_layout()
        fig.savefig(FIGDIR / "fig_event_study_2021.png")
        plt.close(fig)

    macro_tab = tables["civil_by_region_macro"].sort_values("invalid_rate")
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.barh(macro_tab["region_macro"].astype(str), macro_tab["invalid_rate"], color="#8f7a5b")
    ax.set_xlabel("非完全有效率")
    ax.set_ylabel("宏观区域")
    ax.set_xlim(0, 1)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig_invalid_rate_by_macro_region.png")
    plt.close(fig)

    paper_cols = [
        "doc_id",
        "year",
        "post2021",
        "case_domain",
        "contract_validity",
        "contract_invalid",
        "contract_invalid_strict",
        "activity_type",
        "transaction_type",
        "index_case_cause",
        "amount_master_cny",
        "llm_top_case_amount_cny",
        "regex_text_amount_max_cny",
        "log_amount_master",
        "log_llm_case_amount",
        "log_regex_text_max",
        "amount_quartile",
        "q4_amount",
        "amount_master_source",
        "amount_regex_fallback_flag",
        "amount_llm_regex_conflict_flag",
        "region_province",
        "region_city",
        "region_macro",
        "region_big4",
        "court_level_group",
        "cause_group",
    ]
    paper_df = df[paper_cols].copy()

    for name, table in tables.items():
        write_csv(table, f"{name}.csv")
    write_csv(paper_df, "paper_analysis_dataset.csv")
    write_csv(civil, "civil_main_sample.csv")
    write_csv(regressions, "regression_all_terms.csv")
    write_csv(key_regressions, "regression_main.csv")
    write_csv(regression_meta, "regression_model_meta.csv")
    write_csv(event_df, "event_study.csv")
    write_csv(derived_effects_df, "policy_effects_derived.csv")

    with pd.ExcelWriter(OUTDIR / "descriptive_tables.xlsx", engine="openpyxl") as writer:
        for name, table in tables.items():
            table.to_excel(writer, sheet_name=name[:31], index=False)
        key_regressions.to_excel(writer, sheet_name="regression_main", index=False)
        regression_meta.to_excel(writer, sheet_name="regression_meta", index=False)
        event_df.to_excel(writer, sheet_name="event_study", index=False)
        derived_effects_df.to_excel(writer, sheet_name="policy_effects", index=False)

    summary = {
        "round": ROUND,
        "input_round4_derived": str(ROUND4_DERIVED),
        "input_master": str(MASTER),
        "rows_all": int(len(df)),
        "rows_civil_main": int(len(civil)),
        "civil_invalid_rate": safe_float(civil["contract_invalid"].mean(skipna=True)),
        "civil_year_min": safe_float(civil["year"].min()),
        "civil_year_max": safe_float(civil["year"].max()),
        "transaction_counts_civil": {str(k): int(v) for k, v in civil["transaction_type"].value_counts(dropna=False).items()},
        "key_regression_terms": key_regressions.to_dict(orient="records"),
        "regression_meta": regression_meta.to_dict(orient="records"),
        "derived_policy_effects": derived_effects_df.to_dict(orient="records"),
    }
    (OUTDIR / "paper_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=safe_float), encoding="utf-8")

    readme = [
        "# Round 5 Paper Analysis",
        "",
        f"Civil main sample: {len(civil):,}; invalid/non-fully-valid rate: {civil['contract_invalid'].mean(skipna=True):.3f}.",
        "",
        "Main outputs:",
        "- `paper_analysis_dataset.csv`",
        "- `civil_main_sample.csv`",
        "- `descriptive_tables.xlsx`",
        "- `regression_main.csv`",
        "- `regression_all_terms.csv`",
        "- `event_study.csv`",
        "- `policy_effects_derived.csv`",
        "- `figures/`",
    ]
    (OUTDIR / "README.md").write_text("\n".join(readme), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=safe_float))


if __name__ == "__main__":
    main()
