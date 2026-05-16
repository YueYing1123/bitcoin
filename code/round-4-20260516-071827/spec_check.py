from __future__ import annotations

import json
import math
import re
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


ROUND = "round-4-20260516-071827"
ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "data" / "processed" / "master" / "master_dataset.csv"
OUTDIR = ROOT / "result" / ROUND
OUTDIR.mkdir(parents=True, exist_ok=True)


PROVINCE_BY_CASE_CODE = {
    "京": "北京",
    "津": "天津",
    "沪": "上海",
    "渝": "重庆",
    "冀": "河北",
    "豫": "河南",
    "云": "云南",
    "辽": "辽宁",
    "黑": "黑龙江",
    "湘": "湖南",
    "皖": "安徽",
    "鲁": "山东",
    "苏": "江苏",
    "浙": "浙江",
    "赣": "江西",
    "鄂": "湖北",
    "甘": "甘肃",
    "晋": "山西",
    "蒙": "内蒙古",
    "陕": "陕西",
    "吉": "吉林",
    "闽": "福建",
    "贵": "贵州",
    "粤": "广东",
    "青": "青海",
    "藏": "西藏",
    "川": "四川",
    "宁": "宁夏",
    "新": "新疆",
    "桂": "广西",
    "琼": "海南",
}

PROVINCES = [
    "北京",
    "天津",
    "上海",
    "重庆",
    "广东",
    "浙江",
    "江苏",
    "山东",
    "福建",
    "四川",
    "河南",
    "湖北",
    "湖南",
    "安徽",
    "河北",
    "山西",
    "陕西",
    "辽宁",
    "吉林",
    "黑龙江",
    "甘肃",
    "青海",
    "云南",
    "贵州",
    "海南",
    "江西",
    "广西",
    "新疆",
    "西藏",
    "内蒙古",
    "宁夏",
]

REGION_MACRO = {
    "北京": "东部",
    "天津": "东部",
    "河北": "东部",
    "上海": "东部",
    "江苏": "东部",
    "浙江": "东部",
    "福建": "东部",
    "山东": "东部",
    "广东": "东部",
    "海南": "东部",
    "山西": "中部",
    "安徽": "中部",
    "江西": "中部",
    "河南": "中部",
    "湖北": "中部",
    "湖南": "中部",
    "内蒙古": "西部",
    "广西": "西部",
    "重庆": "西部",
    "四川": "西部",
    "贵州": "西部",
    "云南": "西部",
    "西藏": "西部",
    "陕西": "西部",
    "甘肃": "西部",
    "青海": "西部",
    "宁夏": "西部",
    "新疆": "西部",
    "辽宁": "东北",
    "吉林": "东北",
    "黑龙江": "东北",
}


def scalar(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if math.isnan(float(value)):
            return None
        return float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def safe_log1p(series: pd.Series) -> pd.Series:
    x = to_num(series)
    return np.log1p(x.where(x >= 0))


def clean_text(series: pd.Series) -> pd.Series:
    s = series.astype("string").fillna("").str.strip()
    return s.mask(s.str.lower().isin(["nan", "none", "null"]), "")


def first_nonblank(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    out = pd.Series([""] * len(df), index=df.index, dtype="object")
    for col in columns:
        if col not in df.columns:
            continue
        s = clean_text(df[col])
        out = out.mask(out.eq("") & s.ne(""), s)
    return out


def top_group(series: pd.Series, n: int, missing: str = "未分类", other: str = "其他") -> pd.Series:
    s = clean_text(series).replace("", missing)
    counts = s.value_counts(dropna=False)
    keep = set(counts.head(n).index)
    return s.where(s.isin(keep), other).astype("category")


def normalize_province(value: Any) -> str:
    s = "" if pd.isna(value) else str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return ""
    replacements = [
        ("维吾尔自治区", ""),
        ("壮族自治区", ""),
        ("回族自治区", ""),
        ("自治区", ""),
        ("省", ""),
        ("市", ""),
        ("特别行政区", ""),
    ]
    for old, new in replacements:
        s = s.replace(old, new)
    return s


def map_case_number_province(case_number: str) -> str:
    match = re.search(r"[（(]\d{4}[）)]([京津沪渝冀豫云辽黑湘皖鲁苏浙赣鄂甘晋蒙陕吉闽贵粤青藏川宁新桂琼])", case_number)
    if not match:
        return ""
    return PROVINCE_BY_CASE_CODE.get(match.group(1), "")


def map_name_province(court_name: str) -> str:
    for province in PROVINCES:
        if province in court_name:
            return province
    return ""


def map_regions(df: pd.DataFrame) -> pd.DataFrame:
    raw_court = first_nonblank(df, ["court_name", "index_court_name"])
    raw_case_number = first_nonblank(df, ["case_number", "index_case_number", "first_instance_case_number"])

    cpca_province = pd.Series([""] * len(df), index=df.index, dtype="object")
    cpca_city = pd.Series([""] * len(df), index=df.index, dtype="object")
    cpca_district = pd.Series([""] * len(df), index=df.index, dtype="object")
    cpca_adcode = pd.Series([""] * len(df), index=df.index, dtype="object")
    cpca_ok = False

    try:
        import cpca

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            loc = cpca.transform(raw_court.tolist())
        if "省" in loc.columns:
            cpca_province = loc["省"].map(normalize_province).fillna("")
            cpca_city = loc.get("市", pd.Series([""] * len(df))).fillna("").astype(str)
            cpca_district = loc.get("区", pd.Series([""] * len(df))).fillna("").astype(str)
            cpca_adcode = loc.get("adcode", pd.Series([""] * len(df))).fillna("").astype(str)
            cpca_ok = True
    except Exception:
        cpca_ok = False

    case_province = raw_case_number.map(map_case_number_province)
    name_province = raw_court.map(map_name_province)

    province = cpca_province.copy()
    source = pd.Series(np.where(province.ne(""), "cpca_court", ""), index=df.index, dtype="object")

    use_case = province.eq("") & case_province.ne("")
    province = province.mask(use_case, case_province)
    source = source.mask(use_case, "case_number_prefix")

    use_name = province.eq("") & name_province.ne("")
    province = province.mask(use_name, name_province)
    source = source.mask(use_name, "court_name_substring")

    source = source.mask(source.eq(""), "unmapped")

    out = pd.DataFrame(
        {
            "raw_court_for_region": raw_court,
            "raw_case_number_for_region": raw_case_number,
            "region_province": province,
            "region_city": cpca_city,
            "region_district": cpca_district,
            "region_adcode": cpca_adcode,
            "region_source": source,
            "region_cpca_available": int(cpca_ok),
        },
        index=df.index,
    )
    out["region_macro"] = out["region_province"].map(REGION_MACRO).fillna("未映射")
    out["region_big4"] = out["region_province"].isin(["北京", "上海", "广东", "浙江"]).astype(int)
    return out


def classify_contract_validity(value: Any) -> float:
    s = "" if pd.isna(value) else str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return np.nan
    if re.search(r"无效|未成立|不成立|部分无效|部分有效|不适用|可撤销", s):
        return 1.0
    if "有效" in s:
        return 0.0
    return np.nan


def classify_contract_validity_strict(value: Any) -> float:
    s = "" if pd.isna(value) else str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return np.nan
    if re.search(r"无效|未成立|不成立|部分无效", s):
        return 1.0
    if s == "有效":
        return 0.0
    return np.nan


def classify_case_domain(row: pd.Series) -> str:
    merged = " ".join(
        str(row.get(col, "") or "")
        for col in ["case_number", "index_case_number", "case_type_primary", "doc_type", "index_case_cause"]
    )
    if "刑" in merged or str(row.get("index_case_cause", "")).endswith("罪"):
        return "刑事"
    if "民" in merged or any(x in merged for x in ["合同", "借贷", "不当得利", "侵权", "纠纷"]):
        return "民商事"
    if "行" in merged:
        return "行政"
    if "执" in merged:
        return "执行"
    return "其他"


def normalize_court_level(value: Any) -> str:
    s = "" if pd.isna(value) else str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return "未分类"
    if "最高" in s:
        return "最高人民法院"
    if "高级" in s or s == "高院":
        return "高级法院"
    if "中级" in s or s == "中院":
        return "中级法院"
    if "基层" in s:
        return "基层法院"
    return s


def grouped_summary(df: pd.DataFrame, by: str, min_validity_n: int = 0) -> pd.DataFrame:
    table = (
        df.groupby(by, dropna=False)
        .agg(
            rows=("doc_id", "size"),
            validity_n=("contract_invalid", "count"),
            invalid_n=("contract_invalid", "sum"),
            invalid_rate=("contract_invalid", "mean"),
            amount_n=("amount_master_cny", "count"),
            amount_mean=("amount_master_cny", "mean"),
            amount_median=("amount_master_cny", "median"),
            llm_amount_n=("llm_top_case_amount_cny", "count"),
            regex_amount_n=("regex_text_amount_max_cny", "count"),
        )
        .reset_index()
    )
    table = table[table["validity_n"] >= min_validity_n].copy()
    return table.sort_values(["validity_n", "rows"], ascending=False)


def numeric_summary(series: pd.Series) -> dict[str, Any]:
    s = to_num(series).dropna()
    if s.empty:
        return {"n": 0}
    quantiles = s.quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    return {
        "n": int(s.shape[0]),
        "mean": float(s.mean()),
        "std": float(s.std()),
        "min": float(s.min()),
        "p01": float(quantiles.loc[0.01]),
        "p05": float(quantiles.loc[0.05]),
        "p25": float(quantiles.loc[0.25]),
        "p50": float(quantiles.loc[0.5]),
        "p75": float(quantiles.loc[0.75]),
        "p95": float(quantiles.loc[0.95]),
        "p99": float(quantiles.loc[0.99]),
        "max": float(s.max()),
    }


def coverage_record(df: pd.DataFrame, col: str) -> dict[str, Any]:
    s = df[col]
    if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s) or isinstance(s.dtype, pd.CategoricalDtype):
        present = clean_text(s.astype("string")).ne("")
    else:
        present = s.notna()
    return {"variable": col, "nonmissing": int(present.sum()), "coverage": float(present.mean())}


def fit_ols(formula: str, data: pd.DataFrame, model_name: str, note: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        model = smf.ols(formula=formula, data=data).fit(cov_type="HC1")
        rows = []
        for term, coef in model.params.items():
            rows.append(
                {
                    "model": model_name,
                    "term": term,
                    "coef": float(coef),
                    "std_err": float(model.bse[term]),
                    "p_value": float(model.pvalues[term]),
                    "ci_low": float(model.conf_int().loc[term, 0]),
                    "ci_high": float(model.conf_int().loc[term, 1]),
                    "nobs": int(model.nobs),
                    "rsquared": float(model.rsquared),
                    "dep_mean": float(np.mean(model.model.endog)),
                    "note": note,
                    "error": "",
                }
            )
        meta = {
            "model": model_name,
            "type": "OLS/LPM",
            "nobs": int(model.nobs),
            "rsquared": float(model.rsquared),
            "dep_mean": float(np.mean(model.model.endog)),
            "note": note,
            "error": "",
        }
        return rows, meta
    except Exception as exc:
        error = {
            "model": model_name,
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
        return [error], {"model": model_name, "type": "OLS/LPM", "note": note, "error": str(exc)}


def fit_logit(formula: str, data: pd.DataFrame, model_name: str, note: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        model = smf.logit(formula=formula, data=data).fit(disp=0, maxiter=200, cov_type="HC1")
        rows = []
        for term, coef in model.params.items():
            rows.append(
                {
                    "model": model_name,
                    "term": term,
                    "coef": float(coef),
                    "std_err": float(model.bse[term]),
                    "p_value": float(model.pvalues[term]),
                    "odds_ratio": float(np.exp(coef)),
                    "nobs": int(model.nobs),
                    "pseudo_rsquared": float(model.prsquared),
                    "dep_mean": float(np.mean(model.model.endog)),
                    "note": note,
                    "error": "",
                }
            )
        meta = {
            "model": model_name,
            "type": "Logit",
            "nobs": int(model.nobs),
            "pseudo_rsquared": float(model.prsquared),
            "dep_mean": float(np.mean(model.model.endog)),
            "note": note,
            "error": "",
        }
        return rows, meta
    except Exception as exc:
        error = {
            "model": model_name,
            "term": "",
            "coef": np.nan,
            "std_err": np.nan,
            "p_value": np.nan,
            "odds_ratio": np.nan,
            "nobs": 0,
            "pseudo_rsquared": np.nan,
            "dep_mean": np.nan,
            "note": note,
            "error": str(exc),
        }
        return [error], {"model": model_name, "type": "Logit", "note": note, "error": str(exc)}


def write_csv(df: pd.DataFrame, name: str) -> None:
    df.to_csv(OUTDIR / name, index=False, encoding="utf-8-sig")


def main() -> None:
    df = pd.read_csv(MASTER, encoding="utf-8-sig")

    for col in ["judgment_date", "index_close_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["date_for_analysis"] = df["judgment_date"].fillna(df["index_close_date"])
    df["year"] = df["date_for_analysis"].dt.year
    df["year_group"] = df["year"].astype("Int64").astype("string").fillna("missing")

    amount_cols = [
        "amount_master_cny",
        "llm_top_case_amount_cny",
        "llm_total_amount_cny",
        "amount_flat_case_cny",
        "amount_flat_total_cny",
        "regex_text_amount_max_cny",
        "regex_text_amount_mean_cny",
        "regex_text_amount_median_cny",
        "regex_index_amount_max_cny",
        "amount_master_is_regex_fallback",
        "amount_llm_regex_text_conflict",
        "amount_llm_case_in_regex_text_amounts",
        "regex_text_contract_validity",
    ]
    for col in amount_cols:
        if col in df.columns:
            df[col] = to_num(df[col])

    df["log_amount_master"] = safe_log1p(df["amount_master_cny"])
    df["log_llm_case_amount"] = safe_log1p(df["llm_top_case_amount_cny"])
    df["log_regex_text_max"] = safe_log1p(df["regex_text_amount_max_cny"])
    df["amount_regex_fallback_flag"] = df["amount_master_is_regex_fallback"].fillna(0).astype(int)
    df["amount_llm_regex_conflict_flag"] = df["amount_llm_regex_text_conflict"].fillna(0).astype(int)

    df["contract_invalid"] = df["contract_validity"].map(classify_contract_validity)
    df["contract_invalid_strict"] = df["contract_validity"].map(classify_contract_validity_strict)
    df["contract_invalid_regex"] = np.where(
        df["regex_text_contract_validity"].eq(0),
        1.0,
        np.where(df["regex_text_contract_validity"].eq(1), 0.0, np.nan),
    )

    df["post2017"] = np.where(df["year"].notna(), (df["year"] >= 2017).astype(int), np.nan)
    df["post2021"] = np.where(df["year"].notna(), (df["year"] >= 2021).astype(int), np.nan)
    median_amount = df["amount_master_cny"].median(skipna=True)
    df["high_amount"] = np.where(df["amount_master_cny"].notna(), (df["amount_master_cny"] >= median_amount).astype(int), np.nan)
    df["amount_quartile"] = pd.Series(["missing"] * len(df), index=df.index, dtype="object")
    positive_amount = df["amount_master_cny"].where(df["amount_master_cny"] > 0)
    try:
        df.loc[positive_amount.notna(), "amount_quartile"] = pd.qcut(
            positive_amount.dropna(),
            q=4,
            labels=["Q1最低", "Q2", "Q3", "Q4最高"],
            duplicates="drop",
        ).astype(str)
    except ValueError:
        df.loc[positive_amount.notna(), "amount_quartile"] = "positive"

    df["case_domain"] = df.apply(classify_case_domain, axis=1).astype("category")
    df["activity_group"] = top_group(df["activity_type"], 12)
    df["cause_group"] = top_group(df["index_case_cause"], 18)
    level_raw = first_nonblank(df, ["index_court_level", "court_level"])
    df["court_level_group"] = level_raw.map(normalize_court_level).astype("category")

    region_df = map_regions(df)
    df = pd.concat([df, region_df], axis=1)
    df["region_macro"] = df["region_macro"].astype("category")
    df["region_province_group"] = top_group(df["region_province"], 18, missing="未映射")

    both_amount = df[
        (df["llm_top_case_amount_cny"] > 0)
        & (df["regex_text_amount_max_cny"] > 0)
    ].copy()
    both_amount["llm_regex_ratio"] = both_amount["llm_top_case_amount_cny"] / both_amount["regex_text_amount_max_cny"]
    both_amount["abs_log_llm_regex_diff"] = (
        np.log(both_amount["llm_top_case_amount_cny"]) - np.log(both_amount["regex_text_amount_max_cny"])
    ).abs()
    both_amount["within_10pct"] = (
        (both_amount["llm_top_case_amount_cny"] - both_amount["regex_text_amount_max_cny"]).abs()
        <= 0.1 * both_amount[["llm_top_case_amount_cny", "regex_text_amount_max_cny"]].max(axis=1)
    )
    both_amount["within_50pct"] = (
        (both_amount["llm_top_case_amount_cny"] - both_amount["regex_text_amount_max_cny"]).abs()
        <= 0.5 * both_amount[["llm_top_case_amount_cny", "regex_text_amount_max_cny"]].max(axis=1)
    )
    both_amount["same_order_mag"] = both_amount["abs_log_llm_regex_diff"] <= math.log(10)

    coverage = pd.DataFrame(
        [
            coverage_record(df, col)
            for col in [
                "doc_id",
                "date_for_analysis",
                "year",
                "court_name",
                "index_court_name",
                "index_case_cause",
                "activity_type",
                "contract_validity",
                "contract_invalid",
                "amount_master_cny",
                "llm_top_case_amount_cny",
                "regex_text_amount_max_cny",
                "region_province",
                "region_city",
            ]
        ]
    )

    amount_summary = pd.DataFrame(
        [
            {"amount_variable": col, **numeric_summary(df[col])}
            for col in ["amount_master_cny", "llm_top_case_amount_cny", "regex_text_amount_max_cny"]
        ]
    )

    amount_alignment = pd.DataFrame(
        [
            {
                "metric": "both_positive_n",
                "value": int(len(both_amount)),
            },
            {
                "metric": "pearson_raw",
                "value": float(both_amount["llm_top_case_amount_cny"].corr(both_amount["regex_text_amount_max_cny"])),
            },
            {
                "metric": "spearman_raw",
                "value": float(both_amount["llm_top_case_amount_cny"].corr(both_amount["regex_text_amount_max_cny"], method="spearman")),
            },
            {
                "metric": "log_pearson",
                "value": float(np.log(both_amount["llm_top_case_amount_cny"]).corr(np.log(both_amount["regex_text_amount_max_cny"]))),
            },
            {
                "metric": "llm_in_regex_candidate_rate",
                "value": float(df["amount_llm_case_in_regex_text_amounts"].mean(skipna=True)),
            },
            {
                "metric": "llm_regex_conflict_rate",
                "value": float(df["amount_llm_regex_text_conflict"].mean(skipna=True)),
            },
            {
                "metric": "exact_equal_rate_both_positive",
                "value": float((both_amount["llm_top_case_amount_cny"] == both_amount["regex_text_amount_max_cny"]).mean()),
            },
            {
                "metric": "within_10pct_rate",
                "value": float(both_amount["within_10pct"].mean()),
            },
            {
                "metric": "within_50pct_rate",
                "value": float(both_amount["within_50pct"].mean()),
            },
            {
                "metric": "same_order_of_magnitude_rate",
                "value": float(both_amount["same_order_mag"].mean()),
            },
            {
                "metric": "median_llm_regex_ratio",
                "value": float(both_amount["llm_regex_ratio"].median()),
            },
        ]
    )

    prepost_rows = []
    for cut in [2017, 2021]:
        for label, mask in [("pre", df["year"] < cut), ("post", df["year"] >= cut)]:
            sub = df[mask]
            prepost_rows.append(
                {
                    "cut_year": cut,
                    "period": label,
                    "rows": int(len(sub)),
                    "validity_n": int(sub["contract_invalid"].notna().sum()),
                    "invalid_rate": float(sub["contract_invalid"].mean(skipna=True)),
                    "amount_median": float(sub["amount_master_cny"].median(skipna=True)),
                }
            )
    prepost = pd.DataFrame(prepost_rows)

    tables = {
        "coverage": coverage,
        "amount_summary": amount_summary,
        "amount_alignment": amount_alignment,
        "prepost": prepost,
        "year": grouped_summary(df, "year"),
        "amount_quartile": grouped_summary(df, "amount_quartile"),
        "activity": grouped_summary(df, "activity_group", min_validity_n=20),
        "cause": grouped_summary(df, "cause_group", min_validity_n=20),
        "province": grouped_summary(df, "region_province_group", min_validity_n=20),
        "macro_region": grouped_summary(df, "region_macro", min_validity_n=20),
        "court_level": grouped_summary(df, "court_level_group", min_validity_n=20),
        "case_domain": grouped_summary(df, "case_domain"),
        "contract_validity_raw": df["contract_validity"].fillna("<NA>").value_counts(dropna=False).rename_axis("contract_validity").reset_index(name="rows"),
        "amount_source": df["amount_master_source"].fillna("<NA>").value_counts(dropna=False).rename_axis("amount_master_source").reset_index(name="rows"),
        "region_source": df["region_source"].value_counts(dropna=False).rename_axis("region_source").reset_index(name="rows"),
    }

    formulas = [
        (
            "m1_lpm_baseline",
            "contract_invalid ~ post2021 + log_amount_master + amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(court_level_group) + C(cause_group)",
            df,
            "Baseline LPM: 2021 policy period, master amount, amount-quality flags, court level, cause group.",
        ),
        (
            "m2_lpm_amount_interaction",
            "contract_invalid ~ post2021 * high_amount + log_amount_master + amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(court_level_group) + C(cause_group)",
            df,
            "LPM with post-2021 by high-amount interaction.",
        ),
        (
            "m3_lpm_activity_year",
            "contract_invalid ~ log_amount_master + amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(activity_group) + C(court_level_group) + C(cause_group) + C(year_group)",
            df,
            "LPM with activity group and year fixed effects.",
        ),
        (
            "m4_lpm_region_big4",
            "contract_invalid ~ region_big4 + log_amount_master + amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(court_level_group) + C(cause_group)",
            df[df["region_province"].ne("")].copy(),
            "LPM on mapped-region sample: Beijing/Shanghai/Guangdong/Zhejiang indicator.",
        ),
        (
            "m5_lpm_region_macro",
            "contract_invalid ~ C(region_macro) + log_amount_master + amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(court_level_group) + C(cause_group)",
            df[df["region_province"].ne("")].copy(),
            "LPM on mapped-region sample: macro-region categories.",
        ),
        (
            "m6_lpm_llm_amount",
            "contract_invalid ~ post2021 + log_llm_case_amount + amount_llm_regex_conflict_flag + C(court_level_group) + C(cause_group)",
            df,
            "LPM using LLM top-level amount instead of master amount.",
        ),
        (
            "m7_lpm_regex_amount",
            "contract_invalid ~ post2021 + log_regex_text_max + amount_llm_regex_conflict_flag + C(court_level_group) + C(cause_group)",
            df,
            "LPM using regex full-text maximum amount instead of master amount.",
        ),
        (
            "m8_lpm_civil_only",
            "contract_invalid ~ post2021 + log_amount_master + amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(court_level_group) + C(cause_group)",
            df[df["case_domain"].astype(str).eq("民商事")].copy(),
            "Civil/commercial subsample LPM.",
        ),
        (
            "m9_lpm_strict_dv",
            "contract_invalid_strict ~ post2021 + log_amount_master + amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(court_level_group) + C(cause_group)",
            df,
            "Robustness LPM: strict invalid/unformed DV, excluding partial/other validity labels.",
        ),
        (
            "m10_amount_alignment_ols",
            "log_llm_case_amount ~ log_regex_text_max + C(court_level_group) + C(cause_group) + C(year_group)",
            both_amount,
            "OLS: LLM amount alignment with regex full-text maximum amount.",
        ),
        (
            "m12_lpm_amount_quartile",
            "contract_invalid ~ C(amount_quartile) + amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(court_level_group) + C(cause_group)",
            df[df["amount_quartile"].ne("missing")].copy(),
            "LPM using master-amount quartiles instead of a linear log amount.",
        ),
        (
            "m13_lpm_civil_amount_quartile",
            "contract_invalid ~ C(amount_quartile) + amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(court_level_group) + C(cause_group)",
            df[df["amount_quartile"].ne("missing") & df["case_domain"].astype(str).eq("民商事")].copy(),
            "Civil/commercial LPM using master-amount quartiles.",
        ),
        (
            "m14_lpm_policy_q4",
            "contract_invalid ~ post2021 * I(amount_quartile == 'Q4最高') + amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(court_level_group) + C(cause_group)",
            df[df["amount_quartile"].ne("missing")].copy(),
            "LPM interaction between post-2021 period and top master-amount quartile.",
        ),
    ]

    reg_rows: list[dict[str, Any]] = []
    reg_meta: list[dict[str, Any]] = []
    for name, formula, data, note in formulas:
        rows, meta = fit_ols(formula, data, name, note)
        reg_rows.extend(rows)
        reg_meta.append(meta)

    logit_rows, logit_meta = fit_logit(
        "contract_invalid ~ post2021 + log_amount_master + amount_llm_regex_conflict_flag + amount_regex_fallback_flag",
        df,
        "m11_logit_simple",
        "Low-dimensional logit; high-dimensional categorical controls caused singularity.",
    )
    reg_rows.extend(logit_rows)
    reg_meta.append(logit_meta)

    regressions = pd.DataFrame(reg_rows)
    regression_meta = pd.DataFrame(reg_meta)

    key_term_patterns = [
        "post2021",
        "log_amount_master",
        "high_amount",
        "post2021:high_amount",
        "amount_llm_regex_conflict_flag",
        "amount_regex_fallback_flag",
        "region_big4",
        "log_llm_case_amount",
        "log_regex_text_max",
        "amount_llm_regex_conflict_flag",
        "amount_regex_fallback_flag",
        "C(amount_quartile)[T.Q2]",
        "C(amount_quartile)[T.Q3]",
        "C(amount_quartile)[T.Q4最高]",
        "I(amount_quartile == 'Q4最高')[T.True]",
        "post2021:I(amount_quartile == 'Q4最高')[T.True]",
    ]
    key_regressions = regressions[regressions["term"].isin(key_term_patterns)].copy()

    region_audit = df[
        [
            "doc_id",
            "raw_court_for_region",
            "raw_case_number_for_region",
            "region_province",
            "region_city",
            "region_district",
            "region_adcode",
            "region_macro",
            "region_source",
        ]
    ].copy()

    analysis_dataset_cols = [
        "doc_id",
        "year",
        "post2017",
        "post2021",
        "case_domain",
        "contract_validity",
        "contract_invalid",
        "contract_invalid_strict",
        "amount_master_cny",
        "llm_top_case_amount_cny",
        "regex_text_amount_max_cny",
        "amount_master_source",
        "amount_regex_fallback_flag",
        "amount_llm_regex_conflict_flag",
        "log_amount_master",
        "high_amount",
        "log_llm_case_amount",
        "log_regex_text_max",
        "amount_quartile",
        "region_province",
        "region_city",
        "region_macro",
        "region_source",
        "region_big4",
        "court_level_group",
        "cause_group",
        "activity_group",
    ]
    analysis_dataset = df[analysis_dataset_cols].copy()

    for name, table in tables.items():
        write_csv(table, f"{name}.csv")
    write_csv(regressions, "regression_results_full.csv")
    write_csv(regression_meta, "regression_model_meta.csv")
    write_csv(key_regressions, "regression_key_terms.csv")
    write_csv(region_audit, "region_mapping_audit.csv")
    write_csv(analysis_dataset, "analysis_dataset_derived.csv")

    try:
        with pd.ExcelWriter(OUTDIR / "descriptive_tables.xlsx", engine="openpyxl") as writer:
            for name, table in tables.items():
                table.to_excel(writer, sheet_name=name[:31], index=False)
            key_regressions.to_excel(writer, sheet_name="reg_key_terms", index=False)
            regression_meta.to_excel(writer, sheet_name="reg_meta", index=False)
            amount_alignment.to_excel(writer, sheet_name="amount_alignment", index=False)
    except Exception as exc:
        (OUTDIR / "descriptive_tables_excel_error.txt").write_text(str(exc), encoding="utf-8")

    summary = {
        "input_master": str(MASTER),
        "rows": int(len(df)),
        "doc_id_unique": int(df["doc_id"].nunique()),
        "year_min": scalar(df["year"].min()),
        "year_max": scalar(df["year"].max()),
        "contract_invalid_nonmissing": int(df["contract_invalid"].notna().sum()),
        "contract_invalid_rate": scalar(df["contract_invalid"].mean(skipna=True)),
        "contract_invalid_strict_nonmissing": int(df["contract_invalid_strict"].notna().sum()),
        "contract_invalid_strict_rate": scalar(df["contract_invalid_strict"].mean(skipna=True)),
        "amount_master_nonmissing": int(df["amount_master_cny"].notna().sum()),
        "llm_top_case_amount_nonmissing": int(df["llm_top_case_amount_cny"].notna().sum()),
        "regex_text_amount_max_nonmissing": int(df["regex_text_amount_max_cny"].notna().sum()),
        "amount_master_source_counts": {str(k): int(v) for k, v in df["amount_master_source"].fillna("<NA>").value_counts().items()},
        "amount_alignment": {row["metric"]: scalar(row["value"]) for _, row in amount_alignment.iterrows()},
        "region_mapped": int(df["region_province"].ne("").sum()),
        "region_coverage": float(df["region_province"].ne("").mean()),
        "region_source_counts": {str(k): int(v) for k, v in df["region_source"].value_counts().items()},
        "regression_meta": regression_meta.to_dict(orient="records"),
        "key_regression_terms": key_regressions.to_dict(orient="records"),
    }
    (OUTDIR / "spec_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=scalar), encoding="utf-8")

    def pct(x: float) -> str:
        return f"{100 * x:.1f}%"

    m1 = key_regressions[(key_regressions["model"] == "m1_lpm_baseline") & (key_regressions["term"] == "log_amount_master")]
    m4 = key_regressions[(key_regressions["model"] == "m4_lpm_region_big4") & (key_regressions["term"] == "region_big4")]
    align_coef = key_regressions[(key_regressions["model"] == "m10_amount_alignment_ols") & (key_regressions["term"] == "log_regex_text_max")]
    readme = [
        "# Round 4 Spec Check Results",
        "",
        f"- Rows: {len(df):,}; unique doc_id: {df['doc_id'].nunique():,}.",
        f"- Contract-validity DV nonmissing: {df['contract_invalid'].notna().sum():,}; invalid/non-fully-valid rate: {pct(float(df['contract_invalid'].mean(skipna=True)))}.",
        f"- Master amount nonmissing: {df['amount_master_cny'].notna().sum():,}; LLM amount nonmissing: {df['llm_top_case_amount_cny'].notna().sum():,}; regex max amount nonmissing: {df['regex_text_amount_max_cny'].notna().sum():,}.",
        f"- LLM amount appears in regex candidate list rate: {pct(float(df['amount_llm_case_in_regex_text_amounts'].mean(skipna=True)))}; conflict flag rate: {pct(float(df['amount_llm_regex_text_conflict'].mean(skipna=True)))}.",
        f"- Region mapped: {df['region_province'].ne('').sum():,} ({pct(float(df['region_province'].ne('').mean()))}).",
        "",
        "## Key Coefficients",
    ]
    if not m1.empty:
        row = m1.iloc[0]
        readme.append(f"- Baseline LPM log(master amount): coef={row['coef']:.4f}, p={row['p_value']:.4g}, n={int(row['nobs']):,}.")
    if not m4.empty:
        row = m4.iloc[0]
        readme.append(f"- Region Big4 LPM: coef={row['coef']:.4f}, p={row['p_value']:.4g}, n={int(row['nobs']):,}.")
    if not align_coef.empty:
        row = align_coef.iloc[0]
        readme.append(f"- Amount alignment OLS log(regex max): coef={row['coef']:.4f}, p={row['p_value']:.4g}, n={int(row['nobs']):,}.")
    readme.extend(
        [
            "",
            "## Outputs",
            "- `descriptive_tables.xlsx`: core descriptive tables.",
            "- `regression_results_full.csv`: all regression terms.",
            "- `regression_key_terms.csv`: main terms for interpretation.",
            "- `region_mapping_audit.csv`: court/case-number region mapping audit.",
            "- `analysis_dataset_derived.csv`: derived variables for subsequent exploration.",
            "- `spec_summary.json`: machine-readable summary.",
        ]
    )
    (OUTDIR / "README.md").write_text("\n".join(readme), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=scalar))


if __name__ == "__main__":
    main()
