from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROUND = "round-11-20260517-dsv4-reanalysis"
ROOT = Path(__file__).resolve().parents[2]
MASTER = ROOT / "data" / "processed" / "master" / "master_dataset_dsv4.csv"
OUTDIR = ROOT / "result" / ROUND
FIGDIR = OUTDIR / "figures"
OUTDIR.mkdir(parents=True, exist_ok=True)
FIGDIR.mkdir(parents=True, exist_ok=True)

PROVINCE_BY_CASE_CODE = {
    "浙": "浙江", "京": "北京", "沪": "上海", "粤": "广东", "苏": "江苏", "鲁": "山东", "豫": "河南", "川": "四川",
    "渝": "重庆", "晋": "山西", "冀": "河北", "辽": "辽宁", "吉": "吉林", "黑": "黑龙江", "皖": "安徽", "闽": "福建",
    "赣": "江西", "湘": "湖南", "鄂": "湖北", "桂": "广西", "琼": "海南", "贵": "贵州", "云": "云南", "陕": "陕西",
    "甘": "甘肃", "青": "青海", "宁": "宁夏", "新": "新疆", "蒙": "内蒙古", "藏": "西藏", "津": "天津", "冀": "河北",
}

PROVINCES = ["北京", "天津", "上海", "重庆", "广东", "浙江", "江苏", "山东", "福建", "四川", "河南", "湖北", "湖南", "安徽", "河北", "山西", "辽宁", "吉林", "黑龙江", "江西", "陕西", "广西", "海南", "贵州", "云南", "青海", "宁夏", "新疆", "西藏", "内蒙古", "甘肃"]
REGION_MACRO = {"北京":"东部","天津":"东部","河北":"东部","上海":"东部","江苏":"东部","浙江":"东部","福建":"东部","山东":"东部","广东":"东部","海南":"东部","山西":"中部","安徽":"中部","江西":"中部","河南":"中部","湖北":"中部","湖南":"中部","内蒙古":"西部","广西":"西部","重庆":"西部","四川":"西部","贵州":"西部","云南":"西部","西藏":"西部","陕西":"西部","甘肃":"西部","青海":"西部","宁夏":"西部","新疆":"西部","辽宁":"东北","吉林":"东北","黑龙江":"东北"}


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


def classify_transaction_type(activity: Any, cause: Any) -> str:
    text = f"{activity or ''} {cause or ''}"
    if any(x in text for x in ["发币", "ICO", "首次代币", "代币发行", "非法集资"]):
        return "ICO/发币"
    if any(x in text for x in ["委托理财", "代投", "投资", "炒币", "理财"]):
        return "投资/理财"
    if any(x in text for x in ["场外交易", "OTC", "虚拟货币交易", "虚拟货币买卖", "虚拟货币兑换", "买卖合同", "买卖", "交易"]):
        return "交易/买卖"
    if any(x in text for x in ["借贷", "借款", "民间借贷"]):
        return "借贷"
    if "挖矿" in text:
        return "挖矿"
    if any(x in text for x in ["技术服务", "网络服务", "服务合同", "信息网络传播"]):
        return "技术服务"
    if any(x in text for x in ["赌博", "赌场", "诈骗", "传销", "掩饰", "洗钱", "帮助信息网络犯罪活动"]):
        return "其他/未分类"
    if any(x in text for x in ["合同", "不当得利"]):
        return "其他民商事"
    return "其他/未分类"


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


def normalize_province(value: Any) -> str:
    s = "" if pd.isna(value) else str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return ""
    for old, new in [("省", ""), ("市", ""), ("自治区", ""), ("壮族", ""), ("回族", ""), ("维吾尔", ""), ("特别行政区", "")]:
        s = s.replace(old, new)
    return s


def map_name_province(court_name: str) -> str:
    for province in PROVINCES:
        if province in court_name:
            return province
    return ""


def map_case_number_province(case_number: str) -> str:
    m = re.search(r"[(（][0-9]{4}[)）]([京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼])", case_number)
    if not m:
        return ""
    return PROVINCE_BY_CASE_CODE.get(m.group(1), "")


def map_regions(df: pd.DataFrame) -> pd.DataFrame:
    raw_court = first_nonblank(df, ["court_name", "index_court_name"])
    raw_case_number = first_nonblank(df, ["case_number", "index_case_number", "first_instance_case_number"])
    province = pd.Series([""] * len(df), index=df.index, dtype="object")
    source = pd.Series(["unmapped"] * len(df), index=df.index, dtype="object")
    try:
        import cpca
        loc = cpca.transform(raw_court.tolist())
        if "省" in loc.columns:
            province = loc["省"].map(normalize_province).fillna("")
            source = pd.Series(np.where(province.ne(""), "cpca_court", ""), index=df.index, dtype="object")
    except Exception:
        pass
    case_province = raw_case_number.map(map_case_number_province)
    name_province = raw_court.map(map_name_province)
    province = province.mask(province.eq("") & case_province.ne(""), case_province)
    source = source.mask(source.eq("") & case_province.ne(""), "case_number_prefix")
    province = province.mask(province.eq("") & name_province.ne(""), name_province)
    source = source.mask(source.eq("") & name_province.ne(""), "court_name_substring")
    out = pd.DataFrame(index=df.index)
    out["raw_court_for_region"] = raw_court
    out["raw_case_number_for_region"] = raw_case_number
    out["region_province"] = province
    out["region_macro"] = province.map(REGION_MACRO).fillna("未映射")
    out["region_big4"] = province.isin(["北京", "上海", "广东", "浙江"]).astype(int)
    out["region_source"] = source.where(source.ne(""), "unmapped")
    return out


def classify_case_domain(row: pd.Series) -> str:
    merged = " ".join(str(row.get(col, "") or "") for col in ["case_number", "index_case_number", "case_type_primary", "doc_type", "index_case_cause"])
    if "刑" in merged or str(row.get("index_case_cause", "")).endswith("罪"):
        return "刑事"
    if any(x in merged for x in ["合同", "借贷", "不当得利", "渗透", "纠纷"]):
        return "民商事"
    if "行" in merged:
        return "行政"
    if "执" in merged:
        return "执行"
    return "其他"


def normalize_court_level(value: Any) -> str:
    s = "" if pd.isna(value) else str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return "未分级"
    if "最高" in s:
        return "最高人民法院"
    if "高" in s:
        return "高级法院"
    if "中" in s:
        return "中级法院"
    if "基层" in s:
        return "基层法院"
    return s


def grouped_rate(df: pd.DataFrame, by: str) -> pd.DataFrame:
    return (
        df.groupby(by, dropna=False)
        .agg(rows=("doc_id", "size"), validity_n=("contract_invalid", "count"), invalid_n=("contract_invalid", "sum"), invalid_rate=("contract_invalid", "mean"), amount_n=("amount_master_cny", "count"), amount_median=("amount_master_cny", "median"), llm_amount_n=("llm_top_case_amount_cny", "count"), regex_amount_n=("regex_text_amount_max_cny", "count"))
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


def fit_lpm(formula: str, data: pd.DataFrame, model: str, note: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    try:
        res = smf.ols(formula=formula, data=data).fit(cov_type="HC1")
        conf = res.conf_int()
        rows = []
        for term, coef in res.params.items():
            rows.append({"model": model, "term": term, "coef": float(coef), "std_err": float(res.bse[term]), "p_value": float(res.pvalues[term]), "ci_low": float(conf.loc[term, 0]), "ci_high": float(conf.loc[term, 1]), "nobs": int(res.nobs), "rsquared": float(res.rsquared), "dep_mean": float(np.mean(res.model.endog)), "note": note, "error": ""})
        return pd.DataFrame(rows), {"model": model, "nobs": int(res.nobs), "rsquared": float(res.rsquared), "dep_mean": float(np.mean(res.model.endog)), "note": note, "error": ""}
    except Exception as exc:
        return pd.DataFrame([{"model": model, "term": "", "coef": np.nan, "std_err": np.nan, "p_value": np.nan, "ci_low": np.nan, "ci_high": np.nan, "nobs": 0, "rsquared": np.nan, "dep_mean": np.nan, "note": note, "error": str(exc)}]), {"model": model, "note": note, "error": str(exc)}


def write_csv(df: pd.DataFrame, name: str) -> None:
    df.to_csv(OUTDIR / name, index=False, encoding="utf-8-sig")


def main() -> None:
    df = pd.read_csv(MASTER, encoding="utf-8-sig")
    for col in ["judgment_date", "index_close_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ["year", "post2017", "post2021", "contract_invalid", "contract_invalid_strict", "amount_master_cny", "llm_top_case_amount_cny", "regex_text_amount_max_cny", "amount_regex_fallback_flag", "amount_llm_regex_conflict_flag", "log_amount_master", "high_amount", "region_big4"]:
        if col in df.columns:
            df[col] = to_num(df[col])
    if "year" not in df.columns:
        df["year"] = pd.to_datetime(df["judgment_date"], errors="coerce").dt.year
    df["transaction_type"] = [classify_transaction_type(a, c) for a, c in zip(df.get("activity_type", ""), df.get("index_case_cause", ""))]
    order = ["借贷", "投资/理财", "交易/买卖", "ICO/发币", "挖矿", "技术服务", "其他民商事", "其他/未分类", "未分类"]
    df["transaction_type"] = pd.Categorical(df["transaction_type"], categories=order, ordered=False)
    df["year_group"] = df["year"].astype("Int64").astype("string")
    df["post2021"] = np.where(df["year"].notna(), (df["year"] >= 2021).astype(int), np.nan)
    df["post2017"] = np.where(df["year"].notna(), (df["year"] >= 2017).astype(int), np.nan)
    df["q4_amount"] = (df.get("amount_quartile", pd.Series(["missing"]*len(df))) == "Q4").astype(int)
    region_df = map_regions(df)
    for col in region_df.columns:
        df[col] = region_df[col]
    if "court_level" in df.columns:
        df["court_level_group"] = df["court_level"].map(normalize_court_level)
    else:
        df["court_level_group"] = "未分级"
    if "index_case_cause" in df.columns:
        df["cause_group"] = df["index_case_cause"].fillna("未分类").astype(str).str.strip().replace("", "未分类").astype("category")
    else:
        df["cause_group"] = "未分类"
    if "case_type_primary" in df.columns:
        df["case_domain"] = df.apply(classify_case_domain, axis=1)
    else:
        df["case_domain"] = "其他"
    if "contract_validity" in df.columns:
        df["contract_invalid"] = df["contract_validity"].map(classify_contract_validity)
    if "contract_validity_regex" in df.columns:
        df["contract_invalid_strict"] = df["contract_validity_regex"].map(classify_contract_validity_strict)
    df["log_amount_master"] = safe_log1p(df["amount_master_cny"])
    df["log_llm_case_amount"] = safe_log1p(df["llm_top_case_amount_cny"])
    df["log_regex_text_max"] = safe_log1p(df["regex_text_amount_max_cny"])
    df["amount_regex_fallback_flag"] = df["amount_master_is_regex_fallback"].fillna(0).astype(int) if "amount_master_is_regex_fallback" in df.columns else 0
    df["amount_llm_regex_conflict_flag"] = df["amount_llm_regex_conflict_flag"].fillna(0).astype(int) if "amount_llm_regex_conflict_flag" in df.columns else 0
    if "amount_quartile" not in df.columns:
        df["amount_quartile"] = "missing"
    median_amount = df["amount_master_cny"].median(skipna=True)
    df["high_amount"] = np.where(df["amount_master_cny"].notna(), (df["amount_master_cny"] >= median_amount).astype(int), np.nan)
    df["amount_quartile"] = pd.Series(["missing"] * len(df), index=df.index, dtype="object")
    positive_amount = df["amount_master_cny"].where(df["amount_master_cny"] > 0)
    try:
        df.loc[positive_amount.notna(), "amount_quartile"] = pd.qcut(positive_amount.dropna(), q=4, labels=["Q1", "Q2", "Q3", "Q4"])
    except Exception:
        pass
    civil = df[(df["case_domain"] == "民商事") & df["contract_invalid"].notna() & df["year"].notna() & (df["year"] >= 2014) & (df["year"] <= 2024)].copy()
    civil_event = add_event_dummies(civil[(civil["year"] >= 2015) & (civil["year"] <= 2024)].copy())
    tables = {}
    tables["sample_overview"] = pd.DataFrame([
        {"sample": "all_rows", "rows": len(df), "validity_n": int(df["contract_invalid"].notna().sum()), "invalid_rate": float(df["contract_invalid"].mean(skipna=True))},
        {"sample": "civil_main_2014_2024", "rows": len(civil), "validity_n": int(civil["contract_invalid"].notna().sum()), "invalid_rate": float(civil["contract_invalid"].mean(skipna=True))},
        {"sample": "criminal_reference", "rows": int((df["case_domain"] == "刑事").sum()), "validity_n": int(df.loc[df["case_domain"] == "刑事", "contract_invalid"].notna().sum()), "invalid_rate": float(df.loc[df["case_domain"] == "刑事", "contract_invalid"].mean(skipna=True))},
    ])
    tables["civil_by_year"] = grouped_rate(civil, "year")
    tables["civil_by_transaction"] = grouped_rate(civil, "transaction_type")
    tables["civil_by_amount_quartile"] = grouped_rate(civil, "amount_quartile")
    tables["civil_by_region_macro"] = grouped_rate(civil, "region_macro")
    tables["civil_by_province"] = grouped_rate(civil, "region_province")
    tables["civil_by_big4"] = grouped_rate(civil, "region_big4")
    tables["civil_by_court_level"] = grouped_rate(civil, "court_level_group")
    tables["civil_by_cause"] = grouped_rate(civil, "cause_group").head(50)
    contrasts = []
    for by in ["transaction_type", "amount_quartile", "region_macro", "region_big4"]:
        grouped = civil.groupby([by, "post2021"], dropna=False)["contract_invalid"].agg(["count", "mean"]).reset_index()
        wide = grouped.pivot(index=by, columns="post2021", values=["count", "mean"])
        for idx in wide.index:
            pre_n = scalar(wide.loc[idx, ("count", 0)]) if ("count", 0) in wide.columns else None
            post_n = scalar(wide.loc[idx, ("count", 1)]) if ("count", 1) in wide.columns else None
            pre_mean = scalar(wide.loc[idx, ("mean", 0)]) if ("mean", 0) in wide.columns else None
            post_mean = scalar(wide.loc[idx, ("mean", 1)]) if ("mean", 1) in wide.columns else None
            diff = None if pre_mean is None or post_mean is None else post_mean - pre_mean
            contrasts.append({"group_variable": by, "group": str(idx), "pre2021_n": pre_n, "post2021_n": post_n, "pre2021_invalid_rate": pre_mean, "post2021_invalid_rate": post_mean, "diff_post_minus_pre": diff})
    tables["policy_contrasts"] = pd.DataFrame(contrasts)
    common_controls = "amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(court_level_group) + C(cause_group)"
    trans = "C(transaction_type, Treatment(reference='借贷'))"
    specs = [
        ("m1_policy_baseline", f"contract_invalid ~ post2021 + log_amount_master + {common_controls}", civil, "Civil main sample; 2021 post indicator, master amount, amount-quality flags, court level and cause controls."),
        ("m2_transaction_types", f"contract_invalid ~ post2021 + {trans} + log_amount_master + {common_controls}", civil, "Adds compressed transaction types."),
        ("m3_policy_by_transaction", f"contract_invalid ~ post2021 * {trans} + log_amount_master + {common_controls}", civil, "Policy effect heterogeneity by transaction type."),
        ("m4_amount_quartiles", f"contract_invalid ~ post2021 + C(amount_quartile, Treatment(reference='Q1')) + {trans} + {common_controls}", civil[civil["amount_quartile"].ne("missing")].copy(), "Uses amount quartiles instead of linear log amount."),
        ("m5_policy_by_q4_amount", f"contract_invalid ~ post2021 * q4_amount + {trans} + log_amount_master + {common_controls}", civil, "Policy effect heterogeneity for top amount quartile."),
        ("m6_llm_amount", f"contract_invalid ~ post2021 + {trans} + log_llm_case_amount + amount_llm_regex_conflict_flag + C(court_level_group) + C(cause_group)", civil, "Uses LLM top-level case amount."),
        ("m7_regex_amount", f"contract_invalid ~ post2021 + {trans} + log_regex_text_max + amount_llm_regex_conflict_flag + C(court_level_group) + C(cause_group)", civil, "Uses full-text regex maximum amount."),
        ("m8_region_big4", f"contract_invalid ~ post2021 + region_big4 + {trans} + log_amount_master + {common_controls}", civil[civil["region_province"].astype(str).ne("")].copy(), "Adds Big4 region indicator."),
        ("m9_policy_by_big4", f"contract_invalid ~ post2021 * region_big4 + {trans} + log_amount_master + {common_controls}", civil[civil["region_province"].astype(str).ne("")].copy(), "Policy effect heterogeneity by Big4 region."),
        ("m10_region_macro", f"contract_invalid ~ post2021 + C(region_macro) + {trans} + log_amount_master + {common_controls}", civil[civil["region_province"].astype(str).ne("")].copy(), "Adds macro-region categories."),
        ("m11_strict_dv", f"contract_invalid_strict ~ post2021 + {trans} + log_amount_master + {common_controls}", civil[civil["contract_invalid_strict"].notna()].copy(), "Strict DV robustness."),
    ]
    event_formula = "contract_invalid ~ " + " + ".join(name for _, name in event_terms()) + f" + {trans} + log_amount_master + {common_controls}"
    specs.append(("m12_event_study", event_formula, civil_event, "Event study around 2021; 2020 is omitted reference year."))
    reg_frames = []
    reg_meta = []
    for name, formula, data, note in specs:
        rows, meta = fit_lpm(formula, data, name, note)
        reg_frames.append(rows)
        reg_meta.append(meta)
    regressions = pd.concat(reg_frames, ignore_index=True)
    regression_meta = pd.DataFrame(reg_meta)
    key_terms = ["post2021", "log_amount_master", "log_llm_case_amount", "log_regex_text_max", "q4_amount", "post2021:q4_amount", "region_big4", "post2021:region_big4", "amount_llm_regex_conflict_flag", "amount_regex_fallback_flag"]
    key_regressions = regressions[regressions["term"].isin(key_terms)].copy()
    event_rows = []
    for rel, term in event_terms():
        match = regressions[(regressions["model"] == "m12_event_study") & (regressions["term"] == term)]
        if match.empty:
            continue
        row = match.iloc[0].to_dict(); row["relative_year"] = rel; row["calendar_year"] = 2021 + rel; event_rows.append(row)
    event_df = pd.DataFrame(event_rows)
    derived_effects_df = pd.DataFrame([
        {"metric": "policy_shift_baseline", "value": scalar(key_regressions[(key_regressions["model"] == "m1_policy_baseline") & (key_regressions["term"] == "post2021")]["coef"].iloc[0]) if not key_regressions[(key_regressions["model"] == "m1_policy_baseline") & (key_regressions["term"] == "post2021")].empty else None},
        {"metric": "policy_shift_transaction", "value": scalar(key_regressions[(key_regressions["model"] == "m2_transaction_types") & (key_regressions["term"] == "post2021")]["coef"].iloc[0]) if not key_regressions[(key_regressions["model"] == "m2_transaction_types") & (key_regressions["term"] == "post2021")].empty else None},
        {"metric": "policy_shift_region_big4", "value": scalar(key_regressions[(key_regressions["model"] == "m8_region_big4") & (key_regressions["term"] == "post2021")]["coef"].iloc[0]) if not key_regressions[(key_regressions["model"] == "m8_region_big4") & (key_regressions["term"] == "post2021")].empty else None},
        {"metric": "policy_shift_strict", "value": scalar(key_regressions[(key_regressions["model"] == "m11_strict_dv") & (key_regressions["term"] == "post2021")]["coef"].iloc[0]) if not key_regressions[(key_regressions["model"] == "m11_strict_dv") & (key_regressions["term"] == "post2021")].empty else None},
    ])
    paper_cols = ["doc_id", "year", "post2017", "post2021", "case_domain", "contract_invalid", "contract_invalid_strict", "amount_master_cny", "llm_top_case_amount_cny", "regex_text_amount_max_cny", "amount_master_source", "amount_regex_fallback_flag", "amount_llm_regex_conflict_flag", "log_amount_master", "high_amount", "log_llm_case_amount", "log_regex_text_max", "amount_quartile", "q4_amount", "region_province", "region_macro", "region_big4", "court_level_group", "cause_group", "transaction_type"]
    paper_df = df[paper_cols].copy()
    for name, table in tables.items(): write_csv(table, f"{name}.csv")
    write_csv(paper_df, "paper_analysis_dataset.csv")
    write_csv(civil, "civil_main_sample.csv")
    write_csv(regressions, "regression_all_terms.csv")
    write_csv(key_regressions, "regression_main.csv")
    write_csv(regression_meta, "regression_model_meta.csv")
    write_csv(event_df, "event_study.csv")
    write_csv(derived_effects_df, "policy_effects_derived.csv")
    with pd.ExcelWriter(OUTDIR / "descriptive_tables.xlsx", engine="openpyxl") as writer:
        for name, table in tables.items(): table.to_excel(writer, sheet_name=name[:31], index=False)
        key_regressions.to_excel(writer, sheet_name="regression_main", index=False)
        regression_meta.to_excel(writer, sheet_name="regression_meta", index=False)
        event_df.to_excel(writer, sheet_name="event_study", index=False)
        derived_effects_df.to_excel(writer, sheet_name="policy_effects", index=False)
    summary = {"round": ROUND, "input_master": str(MASTER), "rows_all": int(len(df)), "rows_civil_main": int(len(civil)), "civil_invalid_rate": scalar(civil["contract_invalid"].mean(skipna=True)), "civil_year_min": scalar(civil["year"].min()), "civil_year_max": scalar(civil["year"].max()), "transaction_counts_civil": {str(k): int(v) for k, v in civil["transaction_type"].value_counts(dropna=False).items()}, "key_regression_terms": key_regressions.to_dict(orient="records"), "regression_meta": regression_meta.to_dict(orient="records"), "derived_policy_effects": derived_effects_df.to_dict(orient="records")}
    (OUTDIR / "paper_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=scalar), encoding="utf-8")
    readme = ["# Round 11 DSV4 Paper Analysis", "", f"Civil main sample: {len(civil):,}; invalid/non-fully-valid rate: {civil['contract_invalid'].mean(skipna=True):.3f}.", "", "Main outputs:", "- `paper_analysis_dataset.csv`", "- `civil_main_sample.csv`", "- `descriptive_tables.xlsx`", "- `regression_main.csv`", "- `regression_all_terms.csv`", "- `event_study.csv`", "- `policy_effects_derived.csv`", "- `figures/`"]
    (OUTDIR / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=scalar))

if __name__ == "__main__":
    main()
