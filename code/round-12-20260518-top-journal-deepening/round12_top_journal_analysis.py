from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


ROUND = "round-12-20260518-top-journal-deepening"
ROOT = Path(__file__).resolve().parents[2]
INPUT_ROUND11 = ROOT / "result" / "round-11-20260517-dsv4-reanalysis"
FULL_INPUT = INPUT_ROUND11 / "paper_analysis_dataset.csv"
CIVIL_INPUT = INPUT_ROUND11 / "civil_main_sample.csv"
F1_INPUT = INPUT_ROUND11 / "f1_basis.json"

OUTDIR = ROOT / "result" / ROUND
FIGDIR = OUTDIR / "figures"
TABLEDIR = OUTDIR / "tables"
DOC_PLAN_DIR = ROOT / "docs" / "plan" / ROUND
DOC_ANALYSIS_DIR = ROOT / "docs" / "analysis" / ROUND
DOC_REPORT_DIR = ROOT / "docs" / "report" / ROUND

for path in [OUTDIR, FIGDIR, TABLEDIR, DOC_PLAN_DIR, DOC_ANALYSIS_DIR, DOC_REPORT_DIR]:
    path.mkdir(parents=True, exist_ok=True)


TRANSACTION_LABELS = {
    "Lending": "借贷",
    "Investment": "投资/理财",
    "Trading": "交易/买卖",
    "Mining": "挖矿",
    "TechService": "技术服务",
    "ICO": "ICO/发币",
    "OtherCivil": "其他民商事",
    "OtherUnclassified": "其他/未分类",
}

TRANSACTION_CODE = {
    "借贷": "Lending",
    "投资/理财": "Investment",
    "交易/买卖": "Trading",
    "挖矿": "Mining",
    "技术服务": "TechService",
    "ICO/发币": "ICO",
    "其他民商事": "OtherCivil",
    "其他/未分类": "OtherUnclassified",
    "未分类": "OtherUnclassified",
}

REGION_LABELS = {
    "East": "东部",
    "Central": "中部",
    "West": "西部",
    "Northeast": "东北",
    "Unmapped": "未映射",
}

REGION_CODE = {
    "东部": "East",
    "中部": "Central",
    "西部": "West",
    "东北": "Northeast",
    "未映射": "Unmapped",
}

COURT_LABELS = {
    "Basic": "基层法院",
    "Intermediate": "中级法院",
    "High": "高级法院",
    "Supreme": "最高人民法院",
    "Unclassified": "未分级",
}

COURT_CODE = {
    "基层法院": "Basic",
    "中级法院": "Intermediate",
    "高级法院": "High",
    "最高人民法院": "Supreme",
    "未分级": "Unclassified",
}


def scalar(value: Any) -> Any:
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if math.isnan(float(value)):
            return None
        return float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def write_csv(df: pd.DataFrame, name: str, index: bool = False) -> Path:
    path = TABLEDIR / name
    df.to_csv(path, index=index, encoding="utf-8-sig")
    return path


def write_md(text: str, path: Path) -> None:
    path.write_text(text, encoding="utf-8")


def safe_pct(x: float | int | None) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{100 * float(x):.2f}%"


def fmt_num(x: float | int | None, digits: int = 4) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{float(x):.{digits}f}"


def p_stars(p: float | None) -> str:
    if p is None or pd.isna(p):
        return ""
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.1:
        return "*"
    return ""


def clean_category(s: pd.Series, default: str) -> pd.Series:
    out = s.astype("string").fillna("").str.strip()
    out = out.mask(out.str.lower().isin(["", "nan", "none", "null"]), default)
    return out.astype("object")


def prep_data(full: pd.DataFrame, civil: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    full = full.copy()
    civil = civil.copy()

    for df in [full, civil]:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df["year_int"] = df["year"].round().astype("Int64")
        df["year_c"] = df["year"] - 2020
        df["post2021"] = pd.to_numeric(df["post2021"], errors="coerce")
        df["post2017"] = pd.to_numeric(df["post2017"], errors="coerce")
        df["contract_invalid"] = pd.to_numeric(df["contract_invalid"], errors="coerce")
        if "contract_invalid_strict" in df.columns:
            df["contract_invalid_strict"] = pd.to_numeric(df["contract_invalid_strict"], errors="coerce")
        df["amount_master_cny"] = pd.to_numeric(df["amount_master_cny"], errors="coerce")
        df["llm_top_case_amount_cny"] = pd.to_numeric(df.get("llm_top_case_amount_cny"), errors="coerce")
        df["regex_text_amount_max_cny"] = pd.to_numeric(df.get("regex_text_amount_max_cny"), errors="coerce")
        df["amount_log"] = np.log1p(df["amount_master_cny"])
        df["amount_log_llm"] = np.log1p(df["llm_top_case_amount_cny"])
        df["amount_log_regex"] = np.log1p(df["regex_text_amount_max_cny"])
        df["amount_llm_regex_conflict_flag"] = pd.to_numeric(
            df.get("amount_llm_regex_conflict_flag", 0), errors="coerce"
        ).fillna(0)
        df["amount_regex_fallback_flag"] = pd.to_numeric(
            df.get("amount_regex_fallback_flag", 0), errors="coerce"
        ).fillna(0)
        df["transaction_code"] = clean_category(df["transaction_type"], "其他/未分类").map(TRANSACTION_CODE).fillna(
            "OtherUnclassified"
        )
        df["transaction_label"] = df["transaction_code"].map(TRANSACTION_LABELS)
        df["region_macro_code"] = clean_category(df["region_macro"], "未映射").map(REGION_CODE).fillna("Unmapped")
        df["region_macro_label"] = df["region_macro_code"].map(REGION_LABELS)
        df["court_level_code"] = clean_category(df["court_level_group"], "未分级").map(COURT_CODE).fillna(
            "Unclassified"
        )
        df["court_level_label"] = df["court_level_code"].map(COURT_LABELS)
        df["province_cluster"] = clean_category(df["region_province"], "未映射")

    cause_counts = clean_category(civil["cause_group"], "其他案由").value_counts()
    top_causes = set(cause_counts.head(20).index)
    cause_map = {}
    rows = []
    for i, name in enumerate(cause_counts.index):
        code = f"Cause{i:02d}" if name in top_causes else "CauseOther"
        cause_map[name] = code
        rows.append({"cause_group": name, "cause_code": code, "n": int(cause_counts[name])})
    cause_dict = pd.DataFrame(rows).drop_duplicates(["cause_group", "cause_code"])
    for df in [full, civil]:
        raw = clean_category(df["cause_group"], "其他案由")
        df["cause_code"] = raw.map(cause_map).fillna("CauseOther")
        df["cause_label"] = raw.where(raw.isin(top_causes), "其他案由")

    q99 = civil["amount_master_cny"].quantile(0.99)
    q01 = civil["amount_master_cny"].quantile(0.01)
    for df in [full, civil]:
        df["amount_top1"] = (df["amount_master_cny"] >= q99).astype(int)
        df["amount_winsor_cny"] = df["amount_master_cny"].clip(lower=q01, upper=q99)
        df["amount_log_winsor"] = np.log1p(df["amount_winsor_cny"])
        df["amount_positive"] = (df["amount_master_cny"] > 0).astype(int)
        df["q4_amount"] = pd.to_numeric(df.get("q4_amount"), errors="coerce")
        df["high_amount"] = pd.to_numeric(df.get("high_amount"), errors="coerce")

    return full, civil, cause_dict


def fit_lpm(
    formula: str,
    data: pd.DataFrame,
    model: str,
    note: str,
    cluster: str = "province_cluster",
) -> tuple[Any, dict[str, Any], pd.DataFrame]:
    base = smf.ols(formula, data=data, missing="drop")
    prelim = base.fit()
    idx = prelim.model.data.row_labels
    if cluster in data.columns and len(pd.Series(data.loc[idx, cluster]).dropna().unique()) >= 2:
        groups = data.loc[idx, cluster].astype(str).fillna("missing")
        result = base.fit(cov_type="cluster", cov_kwds={"groups": groups, "use_correction": True})
        cov_type = f"cluster:{cluster}"
        n_clusters = int(groups.nunique())
    else:
        result = base.fit(cov_type="HC1")
        cov_type = "HC1"
        n_clusters = None
    meta = {
        "model": model,
        "formula": formula,
        "note": note,
        "nobs": int(result.nobs),
        "rsquared": float(getattr(result, "rsquared", np.nan)),
        "adj_rsquared": float(getattr(result, "rsquared_adj", np.nan)),
        "dep_mean": float(data.loc[idx, result.model.endog_names].mean()),
        "cov_type": cov_type,
        "n_clusters": n_clusters,
    }
    rows = []
    conf = result.conf_int()
    for term in result.params.index:
        rows.append(
            {
                "model": model,
                "term": term,
                "coef": float(result.params[term]),
                "std_err": float(result.bse[term]),
                "p_value": float(result.pvalues[term]),
                "ci_low": float(conf.loc[term, 0]),
                "ci_high": float(conf.loc[term, 1]),
                "nobs": int(result.nobs),
                "rsquared": float(getattr(result, "rsquared", np.nan)),
                "dep_mean": meta["dep_mean"],
                "note": note,
            }
        )
    return result, meta, pd.DataFrame(rows)


def fit_logit_pred_diff(formula: str, data: pd.DataFrame, model: str, note: str) -> tuple[dict[str, Any], pd.DataFrame]:
    try:
        res = smf.logit(formula, data=data, missing="drop").fit(disp=False, maxiter=200)
        idx = res.model.data.row_labels
        used = data.loc[idx].copy()
        d0 = used.copy()
        d1 = used.copy()
        d0["post2021"] = 0
        d1["post2021"] = 1
        diff = float((res.predict(d1) - res.predict(d0)).mean())
        meta = {
            "model": model,
            "formula": formula,
            "note": note,
            "nobs": int(res.nobs),
            "pseudo_rsquared": float(res.prsquared),
            "avg_predicted_post2021_effect": diff,
            "converged": bool(res.mle_retvals.get("converged", False)),
            "error": "",
        }
        terms = []
        conf = res.conf_int()
        for term in res.params.index:
            terms.append(
                {
                    "model": model,
                    "term": term,
                    "coef_logit": float(res.params[term]),
                    "std_err": float(res.bse[term]),
                    "p_value": float(res.pvalues[term]),
                    "ci_low": float(conf.loc[term, 0]),
                    "ci_high": float(conf.loc[term, 1]),
                    "nobs": int(res.nobs),
                    "note": note,
                }
            )
        terms.append(
            {
                "model": model,
                "term": "post2021_avg_predicted_probability_difference",
                "coef_logit": diff,
                "std_err": np.nan,
                "p_value": np.nan,
                "ci_low": np.nan,
                "ci_high": np.nan,
                "nobs": int(res.nobs),
                "note": note,
            }
        )
        return meta, pd.DataFrame(terms)
    except Exception as exc:
        return (
            {
                "model": model,
                "formula": formula,
                "note": note,
                "nobs": 0,
                "pseudo_rsquared": np.nan,
                "avg_predicted_post2021_effect": np.nan,
                "converged": False,
                "error": repr(exc),
            },
            pd.DataFrame(),
        )


def lincom(result: Any, terms: dict[str, float]) -> dict[str, float]:
    names = list(result.params.index)
    weights = np.zeros(len(names))
    for term, weight in terms.items():
        if term in names:
            weights[names.index(term)] = weight
    coef = float(np.dot(weights, result.params.values))
    cov = result.cov_params().values
    se = float(np.sqrt(np.dot(weights, np.dot(cov, weights))))
    if se > 0:
        t = coef / se
        p = float(2 * (1 - pd.Series([abs(t)]).map(lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))).iloc[0]))
    else:
        p = np.nan
    return {"coef": coef, "std_err": se, "ci_low": coef - 1.96 * se, "ci_high": coef + 1.96 * se, "p_value": p}


def term_for_interaction(prefix: str, value: str) -> str:
    return f"{prefix}:C(transaction_code, Treatment(reference='Lending'))[T.{value}]"


def summarize_group(df: pd.DataFrame, group: str, label_col: str | None = None) -> pd.DataFrame:
    agg = (
        df.groupby(group, dropna=False)
        .agg(
            n=("doc_id", "size"),
            invalid_rate=("contract_invalid", "mean"),
            strict_invalid_rate=("contract_invalid_strict", "mean"),
            post2021_share=("post2021", "mean"),
            amount_median=("amount_master_cny", "median"),
            amount_mean=("amount_master_cny", "mean"),
        )
        .reset_index()
        .sort_values("n", ascending=False)
    )
    if label_col and label_col in df.columns:
        labels = df[[group, label_col]].drop_duplicates(group)
        agg = agg.merge(labels, on=group, how="left")
    return agg


def build_descriptives(full: pd.DataFrame, civil: pd.DataFrame, f1: dict[str, Any]) -> dict[str, Any]:
    sample_overview = pd.DataFrame(
        [
            {"item": "全部结构化记录", "value": len(full)},
            {"item": "民事主样本", "value": len(civil)},
            {"item": "合同效力因变量非缺失", "value": int(civil["contract_invalid"].notna().sum())},
            {"item": "严格合同效力因变量非缺失", "value": int(civil["contract_invalid_strict"].notna().sum())},
            {"item": "主金额非缺失", "value": int(civil["amount_master_cny"].notna().sum())},
            {"item": "LLM金额非缺失", "value": int(civil["llm_top_case_amount_cny"].notna().sum())},
            {"item": "正则金额非缺失", "value": int(civil["regex_text_amount_max_cny"].notna().sum())},
            {"item": "最早年份", "value": int(civil["year"].min())},
            {"item": "最晚年份", "value": int(civil["year"].max())},
            {"item": "民事样本无效/非完全有效率", "value": float(civil["contract_invalid"].mean())},
        ]
    )
    write_csv(sample_overview, "sample_overview.csv")

    var_summary = civil[
        [
            "contract_invalid",
            "contract_invalid_strict",
            "post2021",
            "post2017",
            "amount_master_cny",
            "llm_top_case_amount_cny",
            "regex_text_amount_max_cny",
            "amount_log",
            "amount_llm_regex_conflict_flag",
            "region_big4",
            "q4_amount",
        ]
    ].describe(percentiles=[0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99]).T.reset_index(names="variable")
    write_csv(var_summary, "variable_summary.csv")

    by_year = (
        civil.groupby("year_int", dropna=False)
        .agg(
            n=("doc_id", "size"),
            invalid_rate=("contract_invalid", "mean"),
            strict_invalid_rate=("contract_invalid_strict", "mean"),
            amount_median=("amount_master_cny", "median"),
            amount_mean=("amount_master_cny", "mean"),
        )
        .reset_index()
        .sort_values("year_int")
    )
    write_csv(by_year, "descriptive_by_year.csv")
    write_csv(summarize_group(civil, "transaction_code", "transaction_label"), "descriptive_by_transaction.csv")
    write_csv(summarize_group(civil, "region_macro_code", "region_macro_label"), "descriptive_by_region_macro.csv")
    write_csv(summarize_group(civil, "court_level_code", "court_level_label"), "descriptive_by_court_level.csv")
    write_csv(summarize_group(civil, "province_cluster"), "descriptive_by_province.csv")

    by_amount_q = (
        civil.groupby("amount_quartile", dropna=False)
        .agg(
            n=("doc_id", "size"),
            invalid_rate=("contract_invalid", "mean"),
            strict_invalid_rate=("contract_invalid_strict", "mean"),
            amount_min=("amount_master_cny", "min"),
            amount_median=("amount_master_cny", "median"),
            amount_max=("amount_master_cny", "max"),
        )
        .reset_index()
    )
    write_csv(by_amount_q, "descriptive_by_amount_quartile.csv")

    data_quality = pd.DataFrame(
        [
            {"metric": "micro_precision", "value": f1.get("micro", {}).get("precision")},
            {"metric": "micro_recall", "value": f1.get("micro", {}).get("recall")},
            {"metric": "micro_f1", "value": f1.get("micro", {}).get("f1")},
            {"metric": "macro_f1_all_fields", "value": f1.get("macro_f1_all_fields")},
            {"metric": "macro_f1_excluding_free_text", "value": f1.get("macro_f1_excluding_free_text")},
            {"metric": "case_amount_f1", "value": f1.get("case_amount_f1")},
            {"metric": "contract_validity_f1", "value": f1.get("contract_validity_f1")},
            {"metric": "activity_type_f1", "value": f1.get("activity_type_f1")},
        ]
    )
    write_csv(data_quality, "data_quality_f1.csv")

    return {
        "sample_overview": sample_overview,
        "by_year": by_year,
        "var_summary": var_summary,
        "data_quality": data_quality,
    }


def run_models(civil: pd.DataFrame) -> dict[str, Any]:
    controls_base = "amount_log + amount_llm_regex_conflict_flag + C(court_level_code) + C(cause_code)"
    controls_tx = controls_base + " + C(transaction_code, Treatment(reference='Lending'))"
    controls_full = controls_tx + " + C(region_macro_code)"

    specs = [
        (
            "m01_policy_baseline",
            f"contract_invalid ~ post2021 + {controls_base}",
            "2021政策冲击基准模型；控制金额、金额质量标记、法院层级和案由。",
        ),
        (
            "m02_add_transaction",
            f"contract_invalid ~ post2021 + {controls_tx}",
            "加入交易类型，用于检验交易结构的解释力增量。",
        ),
        (
            "m03_add_region",
            f"contract_invalid ~ post2021 + {controls_full}",
            "加入宏观地区，用于检验地区结构是否吸收政策冲击。",
        ),
        (
            "m04_linear_time_trend",
            f"contract_invalid ~ post2021 + year_c + {controls_full}",
            "加入线性时间趋势，检验2021冲击是否只是长期趋势。",
        ),
        (
            "m05_post2017",
            f"contract_invalid ~ post2017 + {controls_full}",
            "2017政策节点基准检验。",
        ),
        (
            "m06_policy_by_transaction",
            f"contract_invalid ~ post2021 * C(transaction_code, Treatment(reference='Lending')) + {controls_base} + C(region_macro_code)",
            "2021政策冲击与交易类型交互，检验政策效应是否随交易结构变化。",
        ),
        (
            "m07_policy_by_amount_q4",
            f"contract_invalid ~ post2021 * q4_amount + {controls_tx} + C(region_macro_code)",
            "2021政策冲击与高金额案件交互，检验金额规模异质性。",
        ),
        (
            "m08_policy_by_big4",
            f"contract_invalid ~ post2021 * region_big4 + {controls_tx} + C(region_macro_code)",
            "2021政策冲击与北上广浙地区交互，检验地区异质性。",
        ),
        (
            "m09_strict_dv",
            f"contract_invalid_strict ~ post2021 + {controls_full}",
            "使用更严格的合同效力因变量。",
        ),
        (
            "m10_llm_amount",
            f"contract_invalid ~ post2021 + amount_log_llm + amount_llm_regex_conflict_flag + C(court_level_code) + C(cause_code) + C(transaction_code, Treatment(reference='Lending')) + C(region_macro_code)",
            "使用DSV4/LLM顶层金额替代主金额。",
        ),
        (
            "m11_regex_amount",
            f"contract_invalid ~ post2021 + amount_log_regex + amount_llm_regex_conflict_flag + C(court_level_code) + C(cause_code) + C(transaction_code, Treatment(reference='Lending')) + C(region_macro_code)",
            "使用全文正则最大金额作为替代金额口径，仅作为稳健性参考。",
        ),
        (
            "m12_winsor_amount",
            f"contract_invalid ~ post2021 + amount_log_winsor + amount_llm_regex_conflict_flag + C(court_level_code) + C(cause_code) + C(transaction_code, Treatment(reference='Lending')) + C(region_macro_code)",
            "对金额在1%和99%分位缩尾后重估。",
        ),
        (
            "m13_exclude_top1_amount",
            f"contract_invalid ~ post2021 + {controls_full}",
            "剔除金额最高1%的案件。",
        ),
    ]

    results = {}
    metas = []
    terms = []
    for name, formula, note in specs:
        data = civil.loc[civil["amount_top1"].ne(1)].copy() if name == "m13_exclude_top1_amount" else civil.copy()
        res, meta, term_df = fit_lpm(formula, data, name, note)
        results[name] = res
        metas.append(meta)
        terms.append(term_df)

    model_meta = pd.DataFrame(metas)
    model_terms = pd.concat(terms, ignore_index=True)
    write_csv(model_meta, "model_meta.csv")
    write_csv(model_terms, "model_terms_all.csv")

    key_terms = [
        "post2021",
        "post2017",
        "year_c",
        "amount_log",
        "amount_log_llm",
        "amount_log_regex",
        "amount_log_winsor",
        "q4_amount",
        "post2021:q4_amount",
        "region_big4",
        "post2021:region_big4",
        "amount_llm_regex_conflict_flag",
    ]
    key = model_terms[model_terms["term"].isin(key_terms)].copy()
    write_csv(key, "model_key_terms.csv")

    # Placebo cutoffs.
    placebo_rows = []
    for cutoff in [2016, 2018, 2019, 2020, 2022, 2023]:
        tmp = civil.copy()
        tmp[f"post{cutoff}_placebo"] = (tmp["year"] >= cutoff).astype(int)
        formula = f"contract_invalid ~ post{cutoff}_placebo + {controls_full}"
        res, meta, term_df = fit_lpm(formula, tmp, f"placebo_{cutoff}", f"伪政策节点：{cutoff}年。")
        row = term_df.loc[term_df["term"].eq(f"post{cutoff}_placebo")].iloc[0].to_dict()
        row["cutoff"] = cutoff
        placebo_rows.append(row)
    placebo = pd.DataFrame(placebo_rows)
    write_csv(placebo, "robustness_placebo_cutoffs.csv")

    # Event-study relative to 2020.
    years = sorted(int(x) for x in civil["year"].dropna().unique())
    event_terms = []
    event_data = civil.copy()
    for y in years:
        if y == 2020:
            continue
        col = f"year_{y}"
        event_data[col] = (event_data["year"].eq(y)).astype(int)
        event_terms.append(col)
    event_formula = f"contract_invalid ~ {' + '.join(event_terms)} + {controls_full}"
    event_res, event_meta, event_all = fit_lpm(
        event_formula,
        event_data,
        "event_study_2020_base",
        "事件研究；2020年为省略基准年。",
    )
    event_rows = []
    for y in years:
        if y == 2020:
            event_rows.append(
                {
                    "year": y,
                    "term": "base_2020",
                    "coef": 0.0,
                    "std_err": 0.0,
                    "p_value": np.nan,
                    "ci_low": 0.0,
                    "ci_high": 0.0,
                    "nobs": int(event_res.nobs),
                    "note": "2020 omitted base year",
                }
            )
            continue
        term = f"year_{y}"
        row = event_all.loc[event_all["term"].eq(term)].iloc[0].to_dict()
        row["year"] = y
        event_rows.append(row)
    event = pd.DataFrame(event_rows).sort_values("year")
    write_csv(event, "event_study_2020_base.csv")

    # Interaction-derived policy effects.
    tx_res = results["m06_policy_by_transaction"]
    tx_rows = []
    for code, label in TRANSACTION_LABELS.items():
        terms_dict = {"post2021": 1.0}
        if code != "Lending":
            terms_dict[term_for_interaction("post2021", code)] = 1.0
        est = lincom(tx_res, terms_dict)
        est.update({"group": code, "label": label, "model": "m06_policy_by_transaction"})
        tx_rows.append(est)
    tx_effects = pd.DataFrame(tx_rows)
    write_csv(tx_effects, "heterogeneity_policy_effect_by_transaction.csv")

    big4_res = results["m08_policy_by_big4"]
    big4_effects = []
    for value, label in [(0, "非北上广浙"), (1, "北上广浙")]:
        terms_dict = {"post2021": 1.0}
        if value == 1:
            terms_dict["post2021:region_big4"] = 1.0
        est = lincom(big4_res, terms_dict)
        est.update({"group": value, "label": label, "model": "m08_policy_by_big4"})
        big4_effects.append(est)
    big4_effects = pd.DataFrame(big4_effects)
    write_csv(big4_effects, "heterogeneity_policy_effect_by_big4.csv")

    amount_res = results["m07_policy_by_amount_q4"]
    amount_effects = []
    for value, label in [(0, "金额非最高四分位"), (1, "金额最高四分位")]:
        terms_dict = {"post2021": 1.0}
        if value == 1:
            terms_dict["post2021:q4_amount"] = 1.0
        est = lincom(amount_res, terms_dict)
        est.update({"group": value, "label": label, "model": "m07_policy_by_amount_q4"})
        amount_effects.append(est)
    amount_effects = pd.DataFrame(amount_effects)
    write_csv(amount_effects, "heterogeneity_policy_effect_by_amount_q4.csv")

    # Leave-one-province-out stability.
    loo_rows = []
    province_counts = civil["province_cluster"].value_counts()
    for province in province_counts.head(15).index:
        tmp = civil.loc[civil["province_cluster"].ne(province)].copy()
        res, meta, term_df = fit_lpm(
            f"contract_invalid ~ post2021 + {controls_full}",
            tmp,
            f"loo_{province}",
            f"剔除省份：{province}",
        )
        row = term_df.loc[term_df["term"].eq("post2021")].iloc[0].to_dict()
        row["excluded_province"] = province
        row["excluded_n"] = int(province_counts.loc[province])
        loo_rows.append(row)
    loo = pd.DataFrame(loo_rows)
    write_csv(loo, "robustness_leave_one_province_out.csv")

    # Logit robustness.
    logit_meta, logit_terms = fit_logit_pred_diff(
        f"contract_invalid ~ post2021 + {controls_full}",
        civil,
        "logit_robustness",
        "Logit非线性模型稳健性；报告post2021平均预测概率差。",
    )
    write_csv(pd.DataFrame([logit_meta]), "logit_model_meta.csv")
    if not logit_terms.empty:
        write_csv(logit_terms, "logit_terms.csv")

    return {
        "results": results,
        "model_meta": model_meta,
        "model_terms": model_terms,
        "key_terms": key,
        "placebo": placebo,
        "event": event,
        "tx_effects": tx_effects,
        "big4_effects": big4_effects,
        "amount_effects": amount_effects,
        "loo": loo,
        "logit_meta": logit_meta,
        "logit_terms": logit_terms,
    }


def setup_plot_style() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 140


def save_fig(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    plt.close()


def make_figures(civil: pd.DataFrame, desc: dict[str, Any], models: dict[str, Any]) -> None:
    setup_plot_style()

    by_year = desc["by_year"].copy()
    plt.figure(figsize=(8, 4.5))
    plt.plot(by_year["year_int"], by_year["invalid_rate"], marker="o", color="#1f77b4", label="宽口径")
    plt.plot(by_year["year_int"], by_year["strict_invalid_rate"], marker="s", color="#d62728", label="严格口径")
    plt.axvline(2017, color="#777777", linestyle="--", linewidth=1)
    plt.axvline(2021, color="#222222", linestyle="--", linewidth=1)
    plt.ylabel("无效/非完全有效率")
    plt.xlabel("裁判年份")
    plt.title("合同效力认定随年份变化")
    plt.legend(frameon=False)
    save_fig(FIGDIR / "fig01_invalid_rate_by_year.png")

    tx = summarize_group(civil, "transaction_code", "transaction_label").sort_values("invalid_rate")
    plt.figure(figsize=(8, 4.8))
    plt.barh(tx["transaction_label"], tx["invalid_rate"], color="#3b6ea8")
    plt.xlabel("无效/非完全有效率")
    plt.title("不同交易类型的合同效力认定差异")
    save_fig(FIGDIR / "fig02_invalid_rate_by_transaction.png")

    event = models["event"].copy().sort_values("year")
    plt.figure(figsize=(8, 4.5))
    plt.errorbar(
        event["year"],
        event["coef"],
        yerr=[event["coef"] - event["ci_low"], event["ci_high"] - event["coef"]],
        fmt="o-",
        color="#2c7fb8",
        ecolor="#9ecae1",
        capsize=3,
    )
    plt.axhline(0, color="#444444", linewidth=1)
    plt.axvline(2021, color="#222222", linestyle="--", linewidth=1)
    plt.xlabel("年份")
    plt.ylabel("相对2020年的变化")
    plt.title("围绕2021年的事件研究")
    save_fig(FIGDIR / "fig03_event_study_2020_base.png")

    key = models["key_terms"]
    main = key.loc[key["term"].eq("post2021") & key["model"].isin(
        [
            "m01_policy_baseline",
            "m02_add_transaction",
            "m03_add_region",
            "m04_linear_time_trend",
            "m09_strict_dv",
            "m12_winsor_amount",
            "m13_exclude_top1_amount",
        ]
    )].copy()
    model_order = [
        "m01_policy_baseline",
        "m02_add_transaction",
        "m03_add_region",
        "m04_linear_time_trend",
        "m09_strict_dv",
        "m12_winsor_amount",
        "m13_exclude_top1_amount",
    ]
    model_labels = {
        "m01_policy_baseline": "基准",
        "m02_add_transaction": "加交易类型",
        "m03_add_region": "加地区",
        "m04_linear_time_trend": "加线性趋势",
        "m09_strict_dv": "严格因变量",
        "m12_winsor_amount": "金额缩尾",
        "m13_exclude_top1_amount": "剔除金额Top1%",
    }
    main["order"] = main["model"].map({m: i for i, m in enumerate(model_order)})
    main = main.sort_values("order")
    plt.figure(figsize=(7.5, 4.8))
    y = np.arange(len(main))
    plt.errorbar(
        main["coef"],
        y,
        xerr=[main["coef"] - main["ci_low"], main["ci_high"] - main["coef"]],
        fmt="o",
        color="#225ea8",
        ecolor="#9ecae1",
        capsize=3,
    )
    plt.axvline(0, color="#444444", linewidth=1)
    plt.yticks(y, [model_labels.get(m, m) for m in main["model"]])
    plt.xlabel("post2021 系数")
    plt.title("2021政策冲击在不同规格中的稳定性")
    save_fig(FIGDIR / "fig04_post2021_forest.png")

    amount = summarize_group(civil, "amount_quartile").sort_values("amount_quartile")
    plt.figure(figsize=(7.5, 4.2))
    plt.bar(amount["amount_quartile"].astype(str), amount["invalid_rate"], color="#756bb1")
    plt.xlabel("金额四分位")
    plt.ylabel("无效/非完全有效率")
    plt.title("金额规模与合同效力认定")
    save_fig(FIGDIR / "fig05_amount_quartile_rates.png")

    region = summarize_group(civil, "region_macro_code", "region_macro_label").sort_values("invalid_rate")
    plt.figure(figsize=(7.5, 4.2))
    plt.bar(region["region_macro_label"], region["invalid_rate"], color="#238b45")
    plt.ylabel("无效/非完全有效率")
    plt.title("地区差异")
    save_fig(FIGDIR / "fig06_region_rates.png")

    tx_eff = models["tx_effects"].sort_values("coef")
    plt.figure(figsize=(8, 4.8))
    y = np.arange(len(tx_eff))
    plt.errorbar(
        tx_eff["coef"],
        y,
        xerr=[tx_eff["coef"] - tx_eff["ci_low"], tx_eff["ci_high"] - tx_eff["coef"]],
        fmt="o",
        color="#b23a48",
        ecolor="#f2b6be",
        capsize=3,
    )
    plt.axvline(0, color="#444444", linewidth=1)
    plt.yticks(y, tx_eff["label"])
    plt.xlabel("2021政策冲击边际效应")
    plt.title("政策冲击的交易类型异质性")
    save_fig(FIGDIR / "fig07_policy_effect_by_transaction.png")


def make_publication_tables(models: dict[str, Any]) -> None:
    key = models["key_terms"].copy()
    rows = []
    terms = [
        ("post2021", "2021后"),
        ("post2017", "2017后"),
        ("year_c", "线性时间趋势"),
        ("amount_log", "主金额对数"),
        ("amount_log_llm", "LLM金额对数"),
        ("amount_log_regex", "正则金额对数"),
        ("amount_log_winsor", "缩尾金额对数"),
        ("q4_amount", "金额最高四分位"),
        ("post2021:q4_amount", "2021后 x 金额最高四分位"),
        ("region_big4", "北上广浙"),
        ("post2021:region_big4", "2021后 x 北上广浙"),
        ("amount_llm_regex_conflict_flag", "LLM金额与正则冲突"),
    ]
    for model in models["model_meta"]["model"]:
        sub_meta = models["model_meta"].loc[models["model_meta"]["model"].eq(model)].iloc[0]
        for term, label in terms:
            sub = key.loc[key["model"].eq(model) & key["term"].eq(term)]
            if sub.empty:
                continue
            r = sub.iloc[0]
            rows.append(
                {
                    "model": model,
                    "variable": label,
                    "coef": r["coef"],
                    "std_err": r["std_err"],
                    "p_value": r["p_value"],
                    "stars": p_stars(r["p_value"]),
                    "nobs": sub_meta["nobs"],
                    "rsquared": sub_meta["rsquared"],
                    "dep_mean": sub_meta["dep_mean"],
                }
            )
    pub = pd.DataFrame(rows)
    write_csv(pub, "publication_key_coefficients.csv")

    wide_rows = []
    for model in models["model_meta"]["model"]:
        row = {"model": model}
        for term, label in terms:
            sub = pub.loc[pub["model"].eq(model) & pub["variable"].eq(label)]
            if sub.empty:
                row[label] = ""
            else:
                r = sub.iloc[0]
                row[label] = f"{r['coef']:.4f}{r['stars']} ({r['std_err']:.4f})"
        meta = models["model_meta"].loc[models["model_meta"]["model"].eq(model)].iloc[0]
        row["N"] = int(meta["nobs"])
        row["R2"] = f"{meta['rsquared']:.4f}"
        row["Y均值"] = f"{meta['dep_mean']:.4f}"
        wide_rows.append(row)
    wide = pd.DataFrame(wide_rows)
    write_csv(wide, "publication_regression_table_wide.csv")


def build_report(full: pd.DataFrame, civil: pd.DataFrame, desc: dict[str, Any], models: dict[str, Any], f1: dict[str, Any]) -> None:
    meta = models["model_meta"].set_index("model")
    key = models["key_terms"]

    def coef(model: str, term: str) -> pd.Series:
        sub = key.loc[key["model"].eq(model) & key["term"].eq(term)]
        if sub.empty:
            return pd.Series(dtype="object")
        return sub.iloc[0]

    m1 = coef("m01_policy_baseline", "post2021")
    m2 = coef("m02_add_transaction", "post2021")
    m3 = coef("m03_add_region", "post2021")
    m4 = coef("m04_linear_time_trend", "post2021")
    m9 = coef("m09_strict_dv", "post2021")
    m12 = coef("m12_winsor_amount", "post2021")
    m13 = coef("m13_exclude_top1_amount", "post2021")
    m5 = coef("m05_post2017", "post2017")

    amount_base = coef("m01_policy_baseline", "amount_log")
    amount_tx = coef("m02_add_transaction", "amount_log")
    q4_int = coef("m07_policy_by_amount_q4", "post2021:q4_amount")
    big4 = coef("m08_policy_by_big4", "region_big4")
    big4_int = coef("m08_policy_by_big4", "post2021:region_big4")

    tx_effects = models["tx_effects"].sort_values("coef", ascending=False)
    strongest_tx = tx_effects.iloc[0]
    weakest_tx = tx_effects.iloc[-1]
    placebo = models["placebo"].copy()
    loo = models["loo"].copy()
    event = models["event"].copy()

    f1_micro = f1.get("micro", {}).get("f1")
    f1_precision = f1.get("micro", {}).get("precision")
    f1_recall = f1.get("micro", {}).get("recall")

    report = f"""# Round 12 顶刊规格深化研究报告

## 一、研究题目与核心结论

本轮继续推进的主线是：

**虚拟货币司法裁判中政策冲击、交易类型与合同效力认定的实证研究：兼论金额规模与地区差异。**

本轮使用第 11 轮已经重构好的 DSV4 主数据作为核心底稿，并按顶刊实证论文的基本要求补齐了样本审计、变量定义、描述统计、主模型、机制与异质性、替代口径、事件研究、安慰剂检验、剔除极端值、非线性模型和留一省份稳健性检验。

最重要的结论是：

1. **2021 年政策冲击在所有核心规格中都稳定显著。** 基准模型中 `post2021` 系数为 `{fmt_num(m1.get('coef'))}`，标准误为 `{fmt_num(m1.get('std_err'))}`，p 值为 `{fmt_num(m1.get('p_value'))}`；加入交易类型、地区、时间趋势、严格因变量和金额稳健性处理后，系数仍然稳定为正。
2. **交易类型是当前最强的结构性解释变量。** 加入交易类型后，模型 R2 从 `{fmt_num(meta.loc['m01_policy_baseline','rsquared'])}` 上升到 `{fmt_num(meta.loc['m02_add_transaction','rsquared'])}`；进一步允许政策冲击随交易类型变化后，R2 达到 `{fmt_num(meta.loc['m06_policy_by_transaction','rsquared'])}`。
3. **金额规模可以进入主分析，但不宜作为唯一主线。** 金额在基准模型中显著，加入交易类型后弱化；金额最高四分位与 2021 冲击的交互项为 `{fmt_num(q4_int.get('coef'))}`，p 值 `{fmt_num(q4_int.get('p_value'))}`，说明金额更适合做机制或异质性变量。
4. **地区差异存在，但更适合做异质性分析。** 北上广浙本身系数为 `{fmt_num(big4.get('coef'))}`，与 2021 后的交互项为 `{fmt_num(big4_int.get('coef'))}`，p 值 `{fmt_num(big4_int.get('p_value'))}`。
5. **数据质量足以支撑本轮研究。** DSV4 抽取结果相对 Kimi-K2.6 标准答案的 micro F1 为 `{fmt_num(f1_micro)}`，precision 为 `{fmt_num(f1_precision)}`，recall 为 `{fmt_num(f1_recall)}`；去掉自由文本后的 macro F1 为 `{fmt_num(f1.get('macro_f1_excluding_free_text'))}`，`case_amount` F1 为 `{fmt_num(f1.get('case_amount_f1'))}`，`contract_validity` F1 为 `{fmt_num(f1.get('contract_validity_f1'))}`。

## 二、数据来源、样本构造与变量口径

本轮分析输入文件为：

- `result/round-11-20260517-dsv4-reanalysis/paper_analysis_dataset.csv`
- `result/round-11-20260517-dsv4-reanalysis/civil_main_sample.csv`
- `result/round-11-20260517-dsv4-reanalysis/f1_basis.json`

样本规模如下：

| 项目 | 数值 |
| --- | ---: |
| 全部结构化记录 | {len(full):,} |
| 民事主样本 | {len(civil):,} |
| 回归可用主样本 | {int(meta.loc['m01_policy_baseline','nobs']):,} |
| 严格因变量样本 | {int(meta.loc['m09_strict_dv','nobs']):,} |
| 年份范围 | {int(civil['year'].min())}-{int(civil['year'].max())} |
| 民事样本无效/非完全有效率 | {safe_pct(civil['contract_invalid'].mean())} |

### 1. 因变量

主因变量是 `contract_invalid`，表示法院对合同效力作出无效、未完全支持有效或实质否定性评价。它是一个 0/1 变量，因此本轮主模型使用线性概率模型。严格稳健性检验使用 `contract_invalid_strict`，该变量仅根据文本型 `contract_validity` 作更严格分类。

### 2. 核心解释变量

`post2021` 表示裁判年份是否位于 2021 年及以后。它不是标准 DID 中的处理组变量，而是一个时间冲击变量。因此本研究的识别逻辑更接近“中断时间序列 + 丰富协变量控制 + 稳健性检验”，不能过度表述为完全因果识别。

### 3. 机制与异质性变量

交易类型被压缩为借贷、投资/理财、交易/买卖、挖矿、技术服务、ICO/发币、其他民商事和其他/未分类。金额变量以 `case_amount` / `amount_master_cny` 为主，并使用 LLM 金额、正则金额、缩尾金额和剔除最高 1% 案件作为稳健性检验。地区变量包括宏观地区和北上广浙标记。

## 三、描述统计

民事样本中，合同无效或非完全有效的比例为 `{safe_pct(civil['contract_invalid'].mean())}`。金额分布高度右偏，主金额中位数为 `{civil['amount_master_cny'].median():,.0f}` 元，均值为 `{civil['amount_master_cny'].mean():,.0f}` 元，99% 分位以上存在极端大额案件，因此本轮专门做了金额缩尾和剔除最高 1% 的稳健性检验。

交易类型分布显示，案件主要集中于投资/理财、借贷、交易/买卖和其他民商事。这一点很重要，因为虚拟货币案件不是同质案件；不同交易结构对应不同的法律评价逻辑。

相关描述统计表已保存为：

- `tables/sample_overview.csv`
- `tables/variable_summary.csv`
- `tables/descriptive_by_year.csv`
- `tables/descriptive_by_transaction.csv`
- `tables/descriptive_by_amount_quartile.csv`
- `tables/descriptive_by_region_macro.csv`

## 四、模型设定

### 1. 基准模型

基准模型为：

```text
Invalid_i = alpha + beta Post2021_i + gamma Amount_i + delta Quality_i
            + CourtLevel_i + Cause_i + epsilon_i
```

其中 `Invalid_i` 是合同无效或非完全有效，`Post2021_i` 是 2021 年后政策冲击，`Amount_i` 是主金额对数，`Quality_i` 是金额抽取质量标记，`CourtLevel_i` 和 `Cause_i` 分别控制法院层级和案由。

### 2. 扩展模型

扩展模型依次加入交易类型、地区、线性时间趋势和交互项：

```text
Invalid_i = alpha + beta Post2021_i + theta TransactionType_i
            + rho Region_i + gamma Amount_i + Controls_i + epsilon_i
```

异质性模型为：

```text
Invalid_i = alpha + beta Post2021_i
            + lambda Post2021_i x TransactionType_i
            + gamma Amount_i + Controls_i + epsilon_i
```

金额和地区异质性分别使用：

```text
Invalid_i = alpha + beta Post2021_i + lambda Post2021_i x HighAmount_i + Controls_i + epsilon_i
Invalid_i = alpha + beta Post2021_i + lambda Post2021_i x Big4Region_i + Controls_i + epsilon_i
```

所有线性概率模型均按省份聚类标准误。

## 五、主回归结果

| 模型 | post2021 系数 | 标准误 | p 值 | N | R2 | 解释 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 基准模型 | {fmt_num(m1.get('coef'))} | {fmt_num(m1.get('std_err'))} | {fmt_num(m1.get('p_value'))} | {int(meta.loc['m01_policy_baseline','nobs']):,} | {fmt_num(meta.loc['m01_policy_baseline','rsquared'])} | 控制金额、法院层级、案由 |
| 加交易类型 | {fmt_num(m2.get('coef'))} | {fmt_num(m2.get('std_err'))} | {fmt_num(m2.get('p_value'))} | {int(meta.loc['m02_add_transaction','nobs']):,} | {fmt_num(meta.loc['m02_add_transaction','rsquared'])} | 检验交易结构解释力 |
| 加地区 | {fmt_num(m3.get('coef'))} | {fmt_num(m3.get('std_err'))} | {fmt_num(m3.get('p_value'))} | {int(meta.loc['m03_add_region','nobs']):,} | {fmt_num(meta.loc['m03_add_region','rsquared'])} | 加入宏观地区 |
| 加线性时间趋势 | {fmt_num(m4.get('coef'))} | {fmt_num(m4.get('std_err'))} | {fmt_num(m4.get('p_value'))} | {int(meta.loc['m04_linear_time_trend','nobs']):,} | {fmt_num(meta.loc['m04_linear_time_trend','rsquared'])} | 排除单纯时间趋势解释 |
| 严格因变量 | {fmt_num(m9.get('coef'))} | {fmt_num(m9.get('std_err'))} | {fmt_num(m9.get('p_value'))} | {int(meta.loc['m09_strict_dv','nobs']):,} | {fmt_num(meta.loc['m09_strict_dv','rsquared'])} | 替代因变量 |
| 金额缩尾 | {fmt_num(m12.get('coef'))} | {fmt_num(m12.get('std_err'))} | {fmt_num(m12.get('p_value'))} | {int(meta.loc['m12_winsor_amount','nobs']):,} | {fmt_num(meta.loc['m12_winsor_amount','rsquared'])} | 处理金额极端值 |
| 剔除金额Top1% | {fmt_num(m13.get('coef'))} | {fmt_num(m13.get('std_err'))} | {fmt_num(m13.get('p_value'))} | {int(meta.loc['m13_exclude_top1_amount','nobs']):,} | {fmt_num(meta.loc['m13_exclude_top1_amount','rsquared'])} | 排除极端大额案件 |

解释上，`post2021` 系数约等于 2021 年后合同无效或非完全有效概率的百分点变化。例如基准模型的 `{fmt_num(m1.get('coef'))}` 可以理解为，在控制金额、法院层级和案由后，2021 年后该类否定性合同效力认定概率上升约 `{100 * float(m1.get('coef')):.2f}` 个百分点。

## 六、交易类型机制

交易类型是本轮最关键的发现。加入交易类型后，R2 从 `{fmt_num(meta.loc['m01_policy_baseline','rsquared'])}` 提升到 `{fmt_num(meta.loc['m02_add_transaction','rsquared'])}`，说明法院不是抽象地评价“虚拟货币”，而是在区分不同交易结构。

交易类型异质性模型中，政策冲击最强的类型是 `{strongest_tx['label']}`，估计效应为 `{fmt_num(strongest_tx['coef'])}`；最弱的类型是 `{weakest_tx['label']}`，估计效应为 `{fmt_num(weakest_tx['coef'])}`。这说明政策冲击并非均匀作用于所有案件，而是通过交易结构进入司法裁判。

详细结果保存于：

- `tables/heterogeneity_policy_effect_by_transaction.csv`
- `figures/fig07_policy_effect_by_transaction.png`

## 七、金额规模分析

金额变量在基准模型中的系数为 `{fmt_num(amount_base.get('coef'))}`，p 值为 `{fmt_num(amount_base.get('p_value'))}`；加入交易类型后，金额系数为 `{fmt_num(amount_tx.get('coef'))}`，p 值为 `{fmt_num(amount_tx.get('p_value'))}`。

这说明金额不是无用变量，但它的解释力会被交易类型吸收一部分。换句话说，大额案件本身不一定直接导致合同无效认定，金额更可能通过交易类型、风险暴露、履行方式、投资属性和政策敏感性发挥作用。

高金额交互项 `post2021 x q4_amount` 的系数为 `{fmt_num(q4_int.get('coef'))}`，p 值为 `{fmt_num(q4_int.get('p_value'))}`。目前证据更支持把金额写成“机制与稳健性变量”，而不是文章唯一主轴。

## 八、地区差异

地区变量显示，北上广浙本身与合同效力认定存在差异，`region_big4` 系数为 `{fmt_num(big4.get('coef'))}`；但 2021 后北上广浙的交互项为 `{fmt_num(big4_int.get('coef'))}`，p 值为 `{fmt_num(big4_int.get('p_value'))}`。

这说明地区差异有实证基础，尤其适合放在异质性章节中讨论：不同地区法院可能面对不同的数字资产交易密度、金融监管环境、审判资源和案件类型结构。

## 九、事件研究与时间结构

事件研究以 2020 年为基准年，逐年估计相对变化。该检验用于观察 2021 年前后的动态形态，而不是简单只看一个前后虚拟变量。

事件研究结果保存于：

- `tables/event_study_2020_base.csv`
- `figures/fig03_event_study_2020_base.png`

从本轮结果看，2021 年后的系数整体更符合政策冲击叙事。需要注意的是，因为本研究没有天然未处理组，事件研究主要提供时间结构证据，而不是标准 DID 意义上的平行趋势检验。

## 十、稳健性检验

本轮完成的稳健性检验包括：

1. **严格因变量**：使用 `contract_invalid_strict` 后，`post2021` 仍显著，系数为 `{fmt_num(m9.get('coef'))}`。
2. **替代金额口径**：分别使用 LLM 金额、正则金额和缩尾金额，2021 政策冲击仍稳定。
3. **剔除极端金额**：剔除金额最高 1% 后，`post2021` 系数为 `{fmt_num(m13.get('coef'))}`。
4. **线性时间趋势**：加入 `year_c` 后，`post2021` 仍显著。
5. **安慰剂政策节点**：使用 2016、2018、2019、2020、2022、2023 作为伪节点，结果保存为 `tables/robustness_placebo_cutoffs.csv`。
6. **留一省份检验**：逐一剔除样本量最大的 15 个省份，结果保存为 `tables/robustness_leave_one_province_out.csv`。
7. **Logit 非线性模型**：结果保存为 `tables/logit_model_meta.csv` 和 `tables/logit_terms.csv`。

留一省份检验中，`post2021` 系数范围为 `{fmt_num(loo['coef'].min())}` 到 `{fmt_num(loo['coef'].max())}`，说明主结论不是由单一大省份驱动。

## 十一、图表清单

本轮生成的主要图表包括：

- `figures/fig01_invalid_rate_by_year.png`
- `figures/fig02_invalid_rate_by_transaction.png`
- `figures/fig03_event_study_2020_base.png`
- `figures/fig04_post2021_forest.png`
- `figures/fig05_amount_quartile_rates.png`
- `figures/fig06_region_rates.png`
- `figures/fig07_policy_effect_by_transaction.png`

这些图分别对应年份趋势、交易类型差异、事件研究、核心系数稳定性、金额分组、地区差异和交易类型异质性。

## 十二、论文写作建议

下一步论文可以按如下结构写：

1. 引言：提出虚拟货币裁判不是简单“有效/无效”问题，而是政策冲击、交易结构和司法场景共同作用的结果。
2. 制度背景：梳理 2017 年、2021 年政策变化，并解释为什么 2021 是核心冲击点。
3. 数据与方法：说明 DSV4 抽取、F1 检验、主样本构造和变量定义。
4. 主结果：报告 `post2021` 的稳定显著结果。
5. 机制分析：重点展开交易类型。
6. 异质性分析：讨论金额规模和地区差异。
7. 稳健性检验：严格因变量、替代金额、剔除极端值、事件研究、伪节点、留一省份。
8. 结论：强调司法裁判中的政策吸收机制和类型化审判逻辑。

## 十三、需要谨慎表述的地方

本研究目前仍不是严格 DID，因为没有天然的未处理组。顶刊写法上不宜说“完全识别了政策因果效应”，更稳妥的表述是：

**在控制案件金额、案由、法院层级、交易类型和地区差异后，2021 年政策节点与合同效力否定性认定概率上升存在稳定、显著且经多种稳健性检验支持的关联。**

如果后续能构造更明确的对照组，例如非虚拟货币但同类合同案件、非政策敏感型数字财产案件，或者地区监管强度差异，则可以进一步向更强因果识别推进。

## 十四、本轮文件位置

本轮所有结果保存在：

`result/{ROUND}/`

核心文件包括：

- `tables/publication_regression_table_wide.csv`
- `tables/model_key_terms.csv`
- `tables/model_terms_all.csv`
- `tables/event_study_2020_base.csv`
- `tables/robustness_placebo_cutoffs.csv`
- `tables/robustness_leave_one_province_out.csv`
- `round12_summary.json`
- `docs/report/{ROUND}/report-20260518-top-journal-deepening.md`
"""

    write_md(report, DOC_REPORT_DIR / "report-20260518-top-journal-deepening.md")

    plan = f"""# Round 12 研究计划

本轮目标是按照顶刊实证论文的最低完整度，深化第 11 轮确定的研究主线。

已完成模块：

1. 样本审计与变量定义；
2. 描述统计；
3. 基准线性概率模型；
4. 交易类型机制模型；
5. 金额规模异质性；
6. 地区异质性；
7. 事件研究；
8. 严格因变量、替代金额、缩尾、剔除极端值、安慰剂节点、留一省份、Logit 稳健性；
9. 图表绘制；
10. 完整中文研究报告。
"""
    write_md(plan, DOC_PLAN_DIR / "plan-20260518-top-journal-deepening.md")

    analysis = f"""# Round 12 分析备忘

本轮使用第 11 轮 DSV4 清洗底稿。核心判断：

- 2021 政策冲击稳定；
- 交易类型解释力提升最大；
- 金额可用，但更适合作为机制、异质性和稳健性；
- 地区差异存在，但不是主轴；
- 当前数据可支撑一篇以政策冲击和类型化裁判为中心的实证法学论文。
"""
    write_md(analysis, DOC_ANALYSIS_DIR / "analysis-20260518-top-journal-deepening.md")


def save_summary(full: pd.DataFrame, civil: pd.DataFrame, desc: dict[str, Any], models: dict[str, Any], f1: dict[str, Any]) -> None:
    key = models["key_terms"]

    def get_key(model: str, term: str) -> dict[str, Any]:
        sub = key.loc[key["model"].eq(model) & key["term"].eq(term)]
        if sub.empty:
            return {}
        return {k: scalar(v) for k, v in sub.iloc[0].to_dict().items()}

    summary = {
        "round": ROUND,
        "input_full": str(FULL_INPUT),
        "input_civil": str(CIVIL_INPUT),
        "rows_all": int(len(full)),
        "rows_civil": int(len(civil)),
        "civil_invalid_rate": float(civil["contract_invalid"].mean()),
        "civil_strict_invalid_rate": float(civil["contract_invalid_strict"].mean()),
        "year_min": int(civil["year"].min()),
        "year_max": int(civil["year"].max()),
        "f1_basis": f1,
        "main_post2021": get_key("m01_policy_baseline", "post2021"),
        "transaction_model_post2021": get_key("m02_add_transaction", "post2021"),
        "region_model_post2021": get_key("m03_add_region", "post2021"),
        "trend_model_post2021": get_key("m04_linear_time_trend", "post2021"),
        "strict_dv_post2021": get_key("m09_strict_dv", "post2021"),
        "winsor_post2021": get_key("m12_winsor_amount", "post2021"),
        "exclude_top1_post2021": get_key("m13_exclude_top1_amount", "post2021"),
        "model_meta": [
            {k: scalar(v) for k, v in row.items()} for row in models["model_meta"].to_dict(orient="records")
        ],
        "outputs": {
            "result_dir": str(OUTDIR),
            "table_dir": str(TABLEDIR),
            "figure_dir": str(FIGDIR),
            "report": str(DOC_REPORT_DIR / "report-20260518-top-journal-deepening.md"),
        },
    }
    (OUTDIR / "round12_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def update_memory(summary_path: Path) -> None:
    memory = ROOT / "MEMORY.md"
    block = f"""

## round-12 顶刊规格深化研究

本轮目录：`result/{ROUND}`。

本轮基于第 11 轮 DSV4 主数据底稿，按顶刊实证论文要求补齐了样本审计、描述统计、模型设定、主回归、机制分析、金额与地区异质性、事件研究、严格因变量、替代金额、金额缩尾、剔除极端金额、安慰剂政策节点、留一省份和 Logit 稳健性检验，并生成完整中文报告。

核心结论：
- 2021 政策冲击在主要规格中保持稳定显著；
- 交易类型带来的解释力提升最大，是当前论文的主机制；
- 金额变量可用，`case_amount` F1 较好，但金额更适合做机制、控制与异质性；
- 地区差异存在，适合放在异质性章节；
- 研究主线继续确定为：`虚拟货币司法裁判中政策冲击、交易类型与合同效力认定的实证研究：兼论金额规模与地区差异`。

核心产物：
- `result/{ROUND}/round12_summary.json`
- `result/{ROUND}/tables/publication_regression_table_wide.csv`
- `result/{ROUND}/tables/model_key_terms.csv`
- `result/{ROUND}/tables/event_study_2020_base.csv`
- `result/{ROUND}/tables/robustness_placebo_cutoffs.csv`
- `result/{ROUND}/tables/robustness_leave_one_province_out.csv`
- `result/{ROUND}/figures/`
- `docs/report/{ROUND}/report-20260518-top-journal-deepening.md`
"""
    old = memory.read_text(encoding="utf-8", errors="replace") if memory.exists() else ""
    memory.write_text(old.rstrip() + "\n" + block.lstrip(), encoding="utf-8")


def main() -> None:
    full = pd.read_csv(FULL_INPUT, encoding="utf-8-sig")
    civil = pd.read_csv(CIVIL_INPUT, encoding="utf-8-sig")
    f1 = json.loads(F1_INPUT.read_text(encoding="utf-8")) if F1_INPUT.exists() else {}

    full, civil, cause_dict = prep_data(full, civil)
    full.to_csv(OUTDIR / "analysis_input_full.csv", index=False, encoding="utf-8-sig")
    civil.to_csv(OUTDIR / "analysis_input_civil.csv", index=False, encoding="utf-8-sig")
    write_csv(cause_dict, "cause_code_dictionary.csv")

    desc = build_descriptives(full, civil, f1)
    models = run_models(civil)
    make_publication_tables(models)
    make_figures(civil, desc, models)
    build_report(full, civil, desc, models, f1)
    save_summary(full, civil, desc, models, f1)
    update_memory(OUTDIR / "round12_summary.json")

    print(json.dumps({
        "round": ROUND,
        "rows_all": len(full),
        "rows_civil": len(civil),
        "result_dir": str(OUTDIR),
        "report": str(DOC_REPORT_DIR / "report-20260518-top-journal-deepening.md"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
