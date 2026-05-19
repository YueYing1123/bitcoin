from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

matplotlib.use("Agg")

ROUND = "round-11-20260517-dsv4-reanalysis"
ROOT = Path(__file__).resolve().parents[2]
OLD_MASTER = ROOT / "data" / "processed" / "master" / "master_dataset.csv"
DSV4_MASTER = ROOT / "data" / "processed" / "master" / "master_dataset_dsv4.csv"
OUTDIR = ROOT / "result" / ROUND
FIGDIR = OUTDIR / "figures"
DOC_PLAN_DIR = ROOT / "docs" / "plan" / ROUND
DOC_ANALYSIS_DIR = ROOT / "docs" / "analysis" / ROUND
DOC_REPORT_DIR = ROOT / "docs" / "report" / ROUND

for path in [OUTDIR, FIGDIR, DOC_PLAN_DIR, DOC_ANALYSIS_DIR, DOC_REPORT_DIR]:
    path.mkdir(parents=True, exist_ok=True)

PROVINCE_BY_CASE_CODE = {
    "浙": "浙江",
    "京": "北京",
    "沪": "上海",
    "粤": "广东",
    "苏": "江苏",
    "鲁": "山东",
    "豫": "河南",
    "川": "四川",
    "渝": "重庆",
    "晋": "山西",
    "冀": "河北",
    "辽": "辽宁",
    "吉": "吉林",
    "黑": "黑龙江",
    "皖": "安徽",
    "闽": "福建",
    "赣": "江西",
    "湘": "湖南",
    "鄂": "湖北",
    "桂": "广西",
    "琼": "海南",
    "贵": "贵州",
    "云": "云南",
    "陕": "陕西",
    "甘": "甘肃",
    "青": "青海",
    "宁": "宁夏",
    "新": "新疆",
    "蒙": "内蒙古",
    "藏": "西藏",
    "津": "天津",
}

PROVINCES = [
    "北京", "天津", "上海", "重庆", "广东", "浙江", "江苏", "山东", "福建", "四川", "河南", "湖北",
    "湖南", "安徽", "河北", "山西", "辽宁", "吉林", "黑龙江", "江西", "陕西", "广西", "海南", "贵州",
    "云南", "青海", "宁夏", "新疆", "西藏", "内蒙古", "甘肃",
]

REGION_MACRO = {
    "北京": "东部", "天津": "东部", "河北": "东部", "上海": "东部", "江苏": "东部", "浙江": "东部",
    "福建": "东部", "山东": "东部", "广东": "东部", "海南": "东部",
    "山西": "中部", "安徽": "中部", "江西": "中部", "河南": "中部", "湖北": "中部", "湖南": "中部",
    "内蒙古": "西部", "广西": "西部", "重庆": "西部", "四川": "西部", "贵州": "西部", "云南": "西部",
    "西藏": "西部", "陕西": "西部", "甘肃": "西部", "青海": "西部", "宁夏": "西部", "新疆": "西部",
    "辽宁": "东北", "吉林": "东北", "黑龙江": "东北",
}

TRANSACTION_ORDER = [
    "借贷",
    "投资/理财",
    "交易/买卖",
    "ICO/发币",
    "挖矿",
    "技术服务",
    "其他民商事",
    "其他/未分类",
    "未分类",
]


def scalar(value: Any) -> Any:
    try:
        if value is None or pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if math.isnan(float(value)):
            return None
        return float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


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


def to_num(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype="float64")
    return pd.to_numeric(series, errors="coerce")


def coalesce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    out = pd.Series(np.nan, index=df.index, dtype="float64")
    for col in columns:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        out = out.mask(out.isna() & s.notna(), s)
    return out


def normalize_province(value: Any) -> str:
    s = "" if pd.isna(value) else str(value).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return ""
    for old, new in [
        ("省", ""),
        ("市", ""),
        ("自治区", ""),
        ("壮族", ""),
        ("回族", ""),
        ("维吾尔", ""),
        ("特别行政区", ""),
    ]:
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
    raw_region = first_nonblank(df, ["region"])
    province = pd.Series([""] * len(df), index=df.index, dtype="object")
    source = pd.Series(["unmapped"] * len(df), index=df.index, dtype="object")
    try:
        import cpca  # type: ignore

        loc = cpca.transform(raw_court.tolist())
        if "省" in loc.columns:
            province = loc["省"].map(normalize_province).fillna("")
            source = pd.Series(np.where(province.ne(""), "cpca_court", ""), index=df.index, dtype="object")
    except Exception:
        pass
    case_province = raw_case_number.map(map_case_number_province)
    name_province = raw_court.map(map_name_province)
    region_province = raw_region.map(normalize_province)
    province = province.mask(province.eq("") & case_province.ne(""), case_province)
    source = source.mask(source.eq("") & case_province.ne(""), "case_number_prefix")
    province = province.mask(province.eq("") & name_province.ne(""), name_province)
    source = source.mask(source.eq("") & name_province.ne(""), "court_name_substring")
    province = province.mask(province.eq("") & region_province.ne(""), region_province)
    source = source.mask(source.eq("") & region_province.ne(""), "region_fallback")
    out = pd.DataFrame(index=df.index)
    out["raw_court_for_region"] = raw_court
    out["raw_case_number_for_region"] = raw_case_number
    out["region_province"] = province
    out["region_macro"] = province.map(REGION_MACRO).fillna("未映射")
    out["region_big4"] = province.isin(["北京", "上海", "广东", "浙江"]).astype(int)
    out["region_source"] = source.where(source.ne(""), "unmapped")
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


def classify_case_domain(row: pd.Series) -> str:
    text = " ".join(
        str(row.get(col, "") or "")
        for col in ["case_number", "index_case_number", "case_type_primary", "doc_type", "index_case_cause"]
    )
    if "刑" in text or str(row.get("index_case_cause", "")).endswith("罪"):
        return "刑事"
    if any(x in text for x in ["民事", "民商事", "合同", "借贷", "不当得利", "纠纷"]):
        return "民商事"
    if "行政" in text:
        return "行政"
    if "执" in text:
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


def make_amount_quartile(series: pd.Series) -> pd.Series:
    s = to_num(series)
    out = pd.Series(["missing"] * len(s), index=s.index, dtype="object")
    positive = s.where(s > 0)
    valid = positive.dropna()
    if len(valid) < 4:
        return out
    try:
        ranked = valid.rank(method="first")
        q = pd.qcut(ranked, q=4, labels=["Q1", "Q2", "Q3", "Q4"])
        out.loc[valid.index] = q.astype(str)
    except Exception:
        pass
    return out


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
        return pd.DataFrame(rows), {
            "model": model,
            "nobs": int(res.nobs),
            "rsquared": float(res.rsquared),
            "dep_mean": float(np.mean(res.model.endog)),
            "note": note,
            "error": "",
        }
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


def write_csv(df: pd.DataFrame, name: str) -> None:
    df.to_csv(OUTDIR / name, index=False, encoding="utf-8-sig")


def write_json(obj: Any, name: str) -> None:
    (OUTDIR / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=scalar), encoding="utf-8")


def load_merged_raw() -> pd.DataFrame:
    print("[1/6] 读取旧主数据与 dsv4 数据...", flush=True)
    old = pd.read_csv(OLD_MASTER, encoding="utf-8-sig")
    dsv4 = pd.read_csv(DSV4_MASTER, encoding="utf-8-sig")
    dsv4 = dsv4.rename(
        columns={
            "case_amount": "dsv4_case_amount",
            "metadata__case_number": "dsv4_case_number",
            "metadata__court_name": "dsv4_court_name",
            "metadata__court_level": "dsv4_court_level",
            "metadata__judgment_date": "dsv4_judgment_date",
            "metadata__first_instance_case_number": "dsv4_first_instance_case_number",
            "metadata__region": "dsv4_region",
            "metadata__doc_type": "dsv4_doc_type",
            "case_profile__case_type_primary": "dsv4_case_type_primary",
            "case_profile__case_type_secondary": "dsv4_case_type_secondary",
            "case_profile__procedure_stage": "dsv4_procedure_stage",
            "case_profile__is_appeal": "dsv4_is_appeal",
            "case_profile__litigant_profile__plaintiff_types": "dsv4_plaintiff_types",
            "case_profile__litigant_profile__defendant_types": "dsv4_defendant_types",
            "virtual_currency_info__involved": "dsv4_vc_involved",
            "virtual_currency_info__currency_types": "dsv4_currency_types",
            "virtual_currency_info__activity_type": "dsv4_activity_type",
            "judicial_analysis__legal_characterization": "dsv4_legal_characterization",
            "judicial_analysis__virtual_currency_property_legality": "dsv4_vc_property_legality",
            "judicial_analysis__contract_validity": "dsv4_contract_validity",
            "judicial_analysis__reason_for_invalidity": "dsv4_reason_for_invalidity",
            "judicial_analysis__cited_laws": "dsv4_cited_laws",
            "judicial_analysis__cited_policies": "dsv4_cited_policies",
            "judicial_analysis__judicial_framing": "dsv4_judicial_framing",
            "llm_summary__outcome_summary": "dsv4_outcome_summary",
            "llm_summary__reasoning_summary": "dsv4_reasoning_summary",
        }
    )
    merged = old.merge(dsv4, on="doc_id", how="left", validate="one_to_one")
    print(f"[1/6] 旧主数据 {len(old):,} 行，dsv4 {len(dsv4):,} 行，合并后 {len(merged):,} 行。", flush=True)
    return merged


def build_analysis_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = load_merged_raw()

    print("[2/6] 构造标准字段与派生变量...", flush=True)
    df["case_amount_old"] = to_num(df["case_amount"]) if "case_amount" in df.columns else np.nan
    df["case_amount_dsv4"] = coalesce_numeric(df, ["dsv4_case_amount"])
    df["case_amount"] = coalesce_numeric(df, ["dsv4_case_amount", "case_amount_old"])

    df["case_number"] = first_nonblank(df, ["dsv4_case_number", "case_number", "index_case_number"])
    df["court_name"] = first_nonblank(df, ["dsv4_court_name", "court_name", "index_court_name"])
    df["court_level"] = first_nonblank(df, ["dsv4_court_level", "court_level", "index_court_level"])
    df["judgment_date"] = first_nonblank(df, ["dsv4_judgment_date", "judgment_date", "index_close_date"])
    df["first_instance_case_number"] = first_nonblank(df, ["dsv4_first_instance_case_number", "first_instance_case_number"])
    df["region"] = first_nonblank(df, ["dsv4_region", "region"])
    df["doc_type"] = first_nonblank(df, ["dsv4_doc_type", "doc_type"])
    df["case_type_primary"] = first_nonblank(df, ["dsv4_case_type_primary", "case_type_primary"])
    df["case_type_secondary"] = first_nonblank(df, ["dsv4_case_type_secondary", "case_type_secondary"])
    df["procedure_stage"] = first_nonblank(df, ["dsv4_procedure_stage", "procedure_stage"])
    df["is_appeal"] = first_nonblank(df, ["dsv4_is_appeal", "is_appeal"])
    df["plaintiff_types"] = first_nonblank(df, ["dsv4_plaintiff_types", "plaintiff_types"])
    df["defendant_types"] = first_nonblank(df, ["dsv4_defendant_types", "defendant_types"])
    df["vc_involved"] = first_nonblank(df, ["dsv4_vc_involved", "vc_involved"])
    df["currency_types"] = first_nonblank(df, ["dsv4_currency_types", "currency_types"])
    df["activity_type"] = first_nonblank(df, ["dsv4_activity_type", "activity_type"])
    df["legal_characterization"] = first_nonblank(df, ["dsv4_legal_characterization", "legal_characterization"])
    df["vc_property_legality"] = first_nonblank(df, ["dsv4_vc_property_legality", "vc_property_legality"])
    df["contract_validity"] = first_nonblank(df, ["dsv4_contract_validity", "contract_validity"])
    df["reason_for_invalidity"] = first_nonblank(df, ["dsv4_reason_for_invalidity", "reason_for_invalidity"])
    df["cited_laws"] = first_nonblank(df, ["dsv4_cited_laws", "cited_laws"])
    df["cited_policies"] = first_nonblank(df, ["dsv4_cited_policies", "cited_policies"])
    df["judicial_framing"] = first_nonblank(df, ["dsv4_judicial_framing", "judicial_framing"])
    df["outcome_summary"] = first_nonblank(df, ["dsv4_outcome_summary", "outcome_summary"])
    df["reasoning_summary"] = first_nonblank(df, ["dsv4_reasoning_summary", "reasoning_summary"])

    df["contract_validity_regex"] = coalesce_numeric(df, ["contract_validity_regex", "regex_text_contract_validity"])
    df["amount_regex_fallback_flag"] = coalesce_numeric(df, ["amount_master_is_regex_fallback"])
    df["amount_llm_regex_conflict_flag"] = coalesce_numeric(df, ["amount_llm_regex_text_conflict"])
    df["amount_master_cny"] = coalesce_numeric(df, ["amount_master_cny"])
    df["llm_top_case_amount_cny"] = coalesce_numeric(df, ["llm_top_case_amount_cny"])
    df["regex_text_amount_max_cny"] = coalesce_numeric(df, ["regex_text_amount_max_cny"])
    df["raw_text_length"] = coalesce_numeric(df, ["raw_text_length"])

    if "year" not in df.columns:
        df["year"] = np.nan
    date_series = pd.to_datetime(df["judgment_date"], errors="coerce")
    fallback_year = pd.to_datetime(df.get("index_close_date"), errors="coerce").dt.year if "index_close_date" in df.columns else pd.Series(np.nan, index=df.index)
    df["year"] = date_series.dt.year.fillna(fallback_year)
    df["year"] = pd.to_numeric(df["year"], errors="coerce")

    df["post2021"] = np.where(df["year"].notna(), (df["year"] >= 2021).astype(int), np.nan)
    df["post2017"] = np.where(df["year"].notna(), (df["year"] >= 2017).astype(int), np.nan)

    df["region"] = first_nonblank(df, ["region", "dsv4_region"])
    region_df = map_regions(df)
    for col in region_df.columns:
        df[col] = region_df[col]

    df["court_level_group"] = df["court_level"].map(normalize_court_level)
    df["cause_group"] = df["index_case_cause"].fillna("未分类").astype(str).str.strip().replace("", "未分类").astype("category")
    df["case_domain"] = df.apply(classify_case_domain, axis=1)
    df["transaction_type"] = [classify_transaction_type(a, c) for a, c in zip(df["activity_type"], df["index_case_cause"])]
    df["transaction_type"] = pd.Categorical(df["transaction_type"], categories=TRANSACTION_ORDER, ordered=False)

    df["contract_invalid"] = df["contract_validity"].map(classify_contract_validity)
    df["contract_invalid_strict"] = df["contract_validity"].map(classify_contract_validity_strict)
    df["log_amount_master"] = np.log1p(df["amount_master_cny"].where(df["amount_master_cny"] >= 0))
    df["log_llm_case_amount"] = np.log1p(df["llm_top_case_amount_cny"].where(df["llm_top_case_amount_cny"] >= 0))
    df["log_regex_text_max"] = np.log1p(df["regex_text_amount_max_cny"].where(df["regex_text_amount_max_cny"] >= 0))
    df["high_amount"] = np.where(df["amount_master_cny"].notna(), (df["amount_master_cny"] >= df["amount_master_cny"].median(skipna=True)).astype(int), np.nan)
    df["amount_quartile"] = make_amount_quartile(df["amount_master_cny"])
    df["q4_amount"] = (df["amount_quartile"] == "Q4").astype(int)

    coverage_rows = []
    coverage_targets = [
        ("case_amount", df["case_amount"]),
        ("judgment_date", df["judgment_date"]),
        ("court_name", df["court_name"]),
        ("case_type_primary", df["case_type_primary"]),
        ("case_type_secondary", df["case_type_secondary"]),
        ("procedure_stage", df["procedure_stage"]),
        ("activity_type", df["activity_type"]),
        ("contract_validity", df["contract_validity"]),
        ("legal_characterization", df["legal_characterization"]),
        ("vc_property_legality", df["vc_property_legality"]),
        ("cited_laws", df["cited_laws"]),
        ("cited_policies", df["cited_policies"]),
        ("judicial_framing", df["judicial_framing"]),
    ]
    for name, series in coverage_targets:
        nonempty = clean_text(series).ne("") if series.dtype == object or str(series.dtype).startswith("string") else series.notna()
        coverage_rows.append(
            {
                "field": name,
                "nonempty_n": int(nonempty.sum()),
                "nonempty_rate": float(nonempty.mean()),
                "total": int(len(series)),
            }
        )
    coverage_df = pd.DataFrame(coverage_rows)

    paper_cols = [
        "doc_id",
        "dsv4_status",
        "dsv4_error",
        "dsv4_model",
        "dsv4_temperature",
        "case_amount",
        "case_amount_old",
        "case_amount_dsv4",
        "case_number",
        "court_name",
        "court_level",
        "judgment_date",
        "first_instance_case_number",
        "region",
        "doc_type",
        "case_type_primary",
        "case_type_secondary",
        "procedure_stage",
        "is_appeal",
        "plaintiff_types",
        "defendant_types",
        "vc_involved",
        "currency_types",
        "activity_type",
        "legal_characterization",
        "vc_property_legality",
        "contract_validity",
        "contract_validity_regex",
        "reason_for_invalidity",
        "cited_laws",
        "cited_policies",
        "judicial_framing",
        "outcome_summary",
        "reasoning_summary",
        "year",
        "post2017",
        "post2021",
        "case_domain",
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
        "q4_amount",
        "region_province",
        "region_macro",
        "region_big4",
        "court_level_group",
        "cause_group",
        "transaction_type",
    ]
    paper_cols = [col for col in paper_cols if col in df.columns]
    paper_df = df[paper_cols].copy()
    return df, paper_df, coverage_df


def run_regressions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    civil = df[
        (df["case_domain"] == "民商事")
        & df["contract_invalid"].notna()
        & df["year"].notna()
        & (df["year"] >= 2014)
        & (df["year"] <= 2024)
    ].copy()
    civil_event = add_event_dummies(civil[(civil["year"] >= 2015) & (civil["year"] <= 2024)].copy())

    tables = {
        "sample_overview": pd.DataFrame(
            [
                {
                    "sample": "all_rows",
                    "rows": len(df),
                    "validity_n": int(df["contract_invalid"].notna().sum()),
                    "invalid_rate": float(df["contract_invalid"].mean(skipna=True)),
                },
                {
                    "sample": "civil_main_2014_2024",
                    "rows": len(civil),
                    "validity_n": int(civil["contract_invalid"].notna().sum()),
                    "invalid_rate": float(civil["contract_invalid"].mean(skipna=True)),
                },
                {
                    "sample": "criminal_reference",
                    "rows": int((df["case_domain"] == "刑事").sum()),
                    "validity_n": int(df.loc[df["case_domain"] == "刑事", "contract_invalid"].notna().sum()),
                    "invalid_rate": float(df.loc[df["case_domain"] == "刑事", "contract_invalid"].mean(skipna=True)),
                },
            ]
        ),
        "civil_by_year": grouped_rate(civil, "year"),
        "civil_by_transaction": grouped_rate(civil, "transaction_type"),
        "civil_by_amount_quartile": grouped_rate(civil, "amount_quartile"),
        "civil_by_region_macro": grouped_rate(civil, "region_macro"),
        "civil_by_province": grouped_rate(civil, "region_province"),
        "civil_by_big4": grouped_rate(civil, "region_big4"),
        "civil_by_court_level": grouped_rate(civil, "court_level_group"),
        "civil_by_cause": grouped_rate(civil, "cause_group").head(50),
    }

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
            contrasts.append(
                {
                    "group_variable": by,
                    "group": str(idx),
                    "pre2021_n": pre_n,
                    "post2021_n": post_n,
                    "pre2021_invalid_rate": pre_mean,
                    "post2021_invalid_rate": post_mean,
                    "diff_post_minus_pre": diff,
                }
            )
    tables["policy_contrasts"] = pd.DataFrame(contrasts)

    common_controls = "amount_llm_regex_conflict_flag + amount_regex_fallback_flag + C(court_level_group) + C(cause_group)"
    trans = "C(transaction_type, Treatment(reference='借贷'))"
    specs = [
        ("m0_post2017_baseline", f"contract_invalid ~ post2017 + log_amount_master + {common_controls}", civil, "2017 policy baseline."),
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
        print(f"[3/6] 回归 {name}，样本 {len(data):,}...", flush=True)
        rows, meta = fit_lpm(formula, data, name, note)
        reg_frames.append(rows)
        reg_meta.append(meta)
    regressions = pd.concat(reg_frames, ignore_index=True)
    regression_meta = pd.DataFrame(reg_meta)
    key_terms = [
        "post2017",
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
    event_df = pd.DataFrame(event_rows)

    derived_effects_df = pd.DataFrame(
        [
            {
                "metric": "policy_shift_2017",
                "value": scalar(
                    key_regressions[
                        (key_regressions["model"] == "m0_post2017_baseline")
                        & (key_regressions["term"] == "post2017")
                    ]["coef"].iloc[0]
                )
                if not key_regressions[
                    (key_regressions["model"] == "m0_post2017_baseline")
                    & (key_regressions["term"] == "post2017")
                ].empty
                else None,
            },
            {
                "metric": "policy_shift_2021",
                "value": scalar(
                    key_regressions[
                        (key_regressions["model"] == "m1_policy_baseline")
                        & (key_regressions["term"] == "post2021")
                    ]["coef"].iloc[0]
                )
                if not key_regressions[
                    (key_regressions["model"] == "m1_policy_baseline")
                    & (key_regressions["term"] == "post2021")
                ].empty
                else None,
            },
            {
                "metric": "policy_shift_transaction",
                "value": scalar(
                    key_regressions[
                        (key_regressions["model"] == "m2_transaction_types")
                        & (key_regressions["term"] == "post2021")
                    ]["coef"].iloc[0]
                )
                if not key_regressions[
                    (key_regressions["model"] == "m2_transaction_types")
                    & (key_regressions["term"] == "post2021")
                ].empty
                else None,
            },
            {
                "metric": "policy_shift_region_big4",
                "value": scalar(
                    key_regressions[
                        (key_regressions["model"] == "m8_region_big4")
                        & (key_regressions["term"] == "post2021")
                    ]["coef"].iloc[0]
                )
                if not key_regressions[
                    (key_regressions["model"] == "m8_region_big4")
                    & (key_regressions["term"] == "post2021")
                ].empty
                else None,
            },
            {
                "metric": "policy_shift_strict",
                "value": scalar(
                    key_regressions[
                        (key_regressions["model"] == "m11_strict_dv")
                        & (key_regressions["term"] == "post2021")
                    ]["coef"].iloc[0]
                )
                if not key_regressions[
                    (key_regressions["model"] == "m11_strict_dv")
                    & (key_regressions["term"] == "post2021")
                ].empty
                else None,
            },
        ]
    )
    return civil, tables, regressions, regression_meta, key_regressions, event_df, derived_effects_df


def build_f1_basis() -> dict[str, Any]:
    return {
        "source_round": "round-10-20260517-kimi-k26-f1",
        "gold_model": "Pro/moonshotai/Kimi-K2.6",
        "evaluated_model": "deepseek-ai/DeepSeek-V4-Flash",
        "temperature": 0,
        "sample_size": 122,
        "field_count": 26,
        "micro": {
            "tp": 2803,
            "fp": 643,
            "fn": 946,
            "precision": 0.8134068485200232,
            "recall": 0.7476660442784743,
            "f1": 0.7791521890201529,
        },
        "macro_f1_all_fields": 0.7555833821804797,
        "macro_f1_active_fields": 0.7858067174676989,
        "macro_precision_all_fields": 0.7672653931267561,
        "macro_recall_all_fields": 0.7516387123616295,
        "macro_f1_excluding_free_text": 0.8137672432638258,
        "excluded_free_text_fields": ["llm_summary.outcome_summary", "llm_summary.reasoning_summary"],
        "overall_field_exact_match_rate": 0.798234552332913,
        "case_amount_f1": 0.8493150684931506,
        "case_amount_precision": 0.8773584905660378,
        "case_amount_recall": 0.8230088495575221,
        "contract_validity_f1": 0.9176470588235294,
        "activity_type_f1": 0.75,
        "report_source": str(ROOT / "result" / "round-10-20260517-kimi-k26-f1" / "REPORT.md"),
    }


def build_plan_report_text(summary: dict[str, Any]) -> tuple[str, str, str]:
    plan = f"""# Round 11 Plan

1. 将旧主数据与 dsv4 数据合并，统一出新的分析底稿。
2. 保存 DeepSeek-V4 vs Kimi-K2.6 的 F1 留痕。
3. 以 dsv4 的合同效力、活动类型、法律定性为核心，重跑规格检验、事件研究和稳健性回归。
4. 输出本轮最有希望的研究方向。
"""
    analysis = f"""# Round 11 Analysis

- 合并后样本：{summary['rows_all']:,}
- 民商事主样本：{summary['rows_civil_main']:,}
- 民商事无效/非完全有效率：{summary['civil_invalid_rate']:.3f}
- 年份范围：{summary['civil_year_min']} - {summary['civil_year_max']}
"""
    report = f"""# Round 11 Report

本轮以 dsv4 为新的结构化底稿，重跑了政策冲击、交易类型、金额、地区、事件研究与稳健性检验。

当前最有希望的方向仍然是：

**虚拟货币司法裁判中政策冲击、交易类型与合同效力认定的实证研究：兼论金额规模与地区差异。**

理由：2021 政策冲击在主样本中依然最稳定，交易类型带来的解释力提升最大，金额与地区更适合作为机制和异质性变量，而不是替代主线。
"""
    return plan, analysis, report


def main() -> None:
    print("[0/6] 写入 F1 留痕...", flush=True)
    f1_basis = build_f1_basis()
    write_json(f1_basis, "f1_basis.json")

    df, paper_df, coverage_df = build_analysis_dataset()
    write_csv(coverage_df, "dsv4_field_coverage.csv")
    write_csv(df, "analysis_input_dsv4_merged.csv")
    write_csv(paper_df, "paper_analysis_dataset.csv")

    civil, tables, regressions, regression_meta, key_regressions, event_df, derived_effects_df = run_regressions(df)

    print("[4/6] 保存结果文件...", flush=True)
    for name, table in tables.items():
        write_csv(table, f"{name}.csv")
    write_csv(civil, "civil_main_sample.csv")
    write_csv(regressions, "regression_all_terms.csv")
    write_csv(key_regressions, "regression_main.csv")
    write_csv(regression_meta, "regression_model_meta.csv")
    write_csv(event_df, "event_study.csv")
    write_csv(derived_effects_df, "policy_effects_derived.csv")

    summary = {
        "round": ROUND,
        "input_old_master": str(OLD_MASTER),
        "input_dsv4_master": str(DSV4_MASTER),
        "rows_all": int(len(df)),
        "rows_civil_main": int(len(civil)),
        "civil_invalid_rate": scalar(civil["contract_invalid"].mean(skipna=True)),
        "civil_year_min": scalar(civil["year"].min()),
        "civil_year_max": scalar(civil["year"].max()),
        "transaction_counts_civil": {str(k): int(v) for k, v in civil["transaction_type"].value_counts(dropna=False).items()},
        "key_regression_terms": key_regressions.to_dict(orient="records"),
        "regression_meta": regression_meta.to_dict(orient="records"),
        "derived_policy_effects": derived_effects_df.to_dict(orient="records"),
        "f1_basis": f1_basis,
    }
    write_json(summary, "paper_summary.json")

    plan_text, analysis_text, report_text = build_plan_report_text(summary)
    (DOC_PLAN_DIR / "plan-20260517-dsv4-reanalysis.md").write_text(plan_text, encoding="utf-8")
    (DOC_ANALYSIS_DIR / "analysis-20260517-dsv4-reanalysis.md").write_text(analysis_text, encoding="utf-8")
    (DOC_REPORT_DIR / "report-20260517-dsv4-reanalysis.md").write_text(report_text, encoding="utf-8")
    (OUTDIR / "README.md").write_text(
        "\n".join(
            [
                "# Round 11 DSV4 Reanalysis",
                "",
                f"Civil main sample: {len(civil):,}; invalid/non-fully-valid rate: {civil['contract_invalid'].mean(skipna=True):.3f}.",
                "",
                "Main outputs:",
                "- `analysis_input_dsv4_merged.csv`",
                "- `paper_analysis_dataset.csv`",
                "- `civil_main_sample.csv`",
                "- `dsv4_field_coverage.csv`",
                "- `descriptive_tables.xlsx` not written in this runner",
                "- `regression_main.csv`",
                "- `regression_all_terms.csv`",
                "- `event_study.csv`",
                "- `policy_effects_derived.csv`",
                "- `f1_basis.json`",
            ]
        ),
        encoding="utf-8",
    )

    print("[5/6] 生成一张年份趋势图...", flush=True)
    try:
        set_plot_style = lambda: None  # local no-op placeholder for minimal footprint
        yearly = tables["civil_by_year"].copy()
        if not yearly.empty:
            plt.figure(figsize=(8, 4))
            plt.plot(yearly["year"], yearly["invalid_rate"], marker="o")
            plt.title("Civil invalid rate by year")
            plt.xlabel("Year")
            plt.ylabel("Invalid rate")
            plt.tight_layout()
            plt.savefig(FIGDIR / "civil_invalid_rate_by_year.png", dpi=160)
            plt.close()
    except Exception as exc:
        print(f"[5/6] 图表生成失败：{exc}", flush=True)

    print("[6/6] 完成。", flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=scalar))


if __name__ == "__main__":
    main()
