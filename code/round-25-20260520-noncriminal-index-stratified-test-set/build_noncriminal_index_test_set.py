from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ROUND = "round-25-20260520-noncriminal-index-stratified-test-set"

RAW_INDEX = ROOT / "data" / "raw" / "data-index.json"
TEXTS = ROOT / "data" / "raw" / "data-texts.json"
MASTER_DIR = ROOT / "data" / "processed" / "master"
OUTDIR = ROOT / "result" / ROUND

BASE_CSV = MASTER_DIR / "data_index_noncriminal_base.csv"
BASE_JSONL = MASTER_DIR / "data_index_noncriminal_base.jsonl"
EXCLUDED_CSV = OUTDIR / "data_index_criminal_excluded_by_case_reason_contains_zui.csv"
EXCLUDED_JSONL = OUTDIR / "data_index_criminal_excluded_by_case_reason_contains_zui.jsonl"
TEST_CSV = OUTDIR / "test_set_5pct_year_region_appeal_priority.csv"
TEST_JSONL = OUTDIR / "test_set_5pct_year_region_appeal_priority.jsonl"
TEST_IDS_JSON = OUTDIR / "test_set_doc_ids.json"
YEAR_ALLOCATION_CSV = OUTDIR / "year_allocation.csv"
YEAR_REGION_ALLOCATION_CSV = OUTDIR / "year_region_allocation.csv"
CASE_REASON_COUNTS_CSV = OUTDIR / "case_reason_filter_counts.csv"
AUDIT_JSON = OUTDIR / "audit.json"

RAW_TITLE = "文书标题"
RAW_CASE_REASON = "案由/罪名"
RAW_CASE_NUMBER = "案号"
RAW_CLOSE_DATE = "审结时间"
RAW_COURT_NAME = "审理法院"
RAW_COURT_LEVEL = "法院级别"
RAW_PROCEDURE = "审理程序"
RAW_DOC_ID = "可唯一识别id"
RAW_ROW_INDEX = "__row_index__"

DOC_ID = "doc_id"
DATE_COL = "index_close_date"
REGION_COL = "metadata__region"
STAGE_COL = "index_procedure"

REGION_NAMES = [
    ("北京", ["北京市", "北京"]),
    ("天津", ["天津市", "天津"]),
    ("河北", ["河北省", "河北"]),
    ("山西", ["山西省", "山西"]),
    ("内蒙古", ["内蒙古自治区", "内蒙古"]),
    ("辽宁", ["辽宁省", "辽宁"]),
    ("吉林", ["吉林省", "吉林"]),
    ("黑龙江", ["黑龙江省", "黑龙江"]),
    ("上海", ["上海市", "上海"]),
    ("江苏", ["江苏省", "江苏"]),
    ("浙江", ["浙江省", "浙江"]),
    ("安徽", ["安徽省", "安徽"]),
    ("福建", ["福建省", "福建"]),
    ("江西", ["江西省", "江西"]),
    ("山东", ["山东省", "山东"]),
    ("河南", ["河南省", "河南"]),
    ("湖北", ["湖北省", "湖北"]),
    ("湖南", ["湖南省", "湖南"]),
    ("广东", ["广东省", "广东"]),
    ("广西", ["广西壮族自治区", "广西"]),
    ("海南", ["海南省", "海南"]),
    ("重庆", ["重庆市", "重庆"]),
    ("四川", ["四川省", "四川"]),
    ("贵州", ["贵州省", "贵州"]),
    ("云南", ["云南省", "云南"]),
    ("西藏", ["西藏自治区", "西藏"]),
    ("陕西", ["陕西省", "陕西"]),
    ("甘肃", ["甘肃省", "甘肃"]),
    ("青海", ["青海省", "青海"]),
    ("宁夏", ["宁夏回族自治区", "宁夏"]),
    ("新疆", ["新疆维吾尔自治区", "新疆"]),
    ("最高人民法院", ["最高人民法院"]),
]

CASE_NUMBER_REGION = {
    "京": "北京",
    "津": "天津",
    "冀": "河北",
    "晋": "山西",
    "内": "内蒙古",
    "辽": "辽宁",
    "吉": "吉林",
    "黑": "黑龙江",
    "沪": "上海",
    "苏": "江苏",
    "浙": "浙江",
    "皖": "安徽",
    "闽": "福建",
    "赣": "江西",
    "鲁": "山东",
    "豫": "河南",
    "鄂": "湖北",
    "湘": "湖南",
    "粤": "广东",
    "桂": "广西",
    "琼": "海南",
    "渝": "重庆",
    "川": "四川",
    "黔": "贵州",
    "贵": "贵州",
    "云": "云南",
    "藏": "西藏",
    "陕": "陕西",
    "秦": "陕西",
    "甘": "甘肃",
    "青": "青海",
    "宁": "宁夏",
    "新": "新疆",
    "兵": "新疆",
}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def extract_year(*values: Any) -> str:
    for value in values:
        match = re.search(r"(?:19|20)\d{2}", str(value or ""))
        if match:
            return match.group(0)
    return "未明确年份"


def infer_region(court_name: str, case_number: str) -> str:
    court_name = court_name or ""
    for region, needles in REGION_NAMES:
        if any(needle in court_name for needle in needles):
            return region
    match = re.search(r"[（(]\d{4}[）)]([^0-9\d]+)", case_number or "")
    if match:
        prefix = match.group(1).strip()
        if prefix.startswith("最高法"):
            return "最高人民法院"
        if prefix:
            return CASE_NUMBER_REGION.get(prefix[0], "未明确地区")
    return "未明确地区"


def normalize_stage(value: str) -> str:
    value = (value or "").strip()
    return value or "未明确程序"


def is_explicit_criminal(case_reason: str) -> bool:
    return "罪" in (case_reason or "")


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(row.get(RAW_DOC_ID) or "").strip()
    title = str(row.get(RAW_TITLE) or "").strip()
    case_reason = str(row.get(RAW_CASE_REASON) or "").strip()
    case_number = str(row.get(RAW_CASE_NUMBER) or "").strip()
    close_date = str(row.get(RAW_CLOSE_DATE) or "").strip()
    court_name = str(row.get(RAW_COURT_NAME) or "").strip()
    court_level = str(row.get(RAW_COURT_LEVEL) or "").strip()
    procedure = str(row.get(RAW_PROCEDURE) or "").strip()
    region = infer_region(court_name, case_number)
    year = extract_year(close_date, case_number, title)

    return {
        DOC_ID: doc_id,
        "index_title": title,
        "index_case_cause": case_reason,
        "index_case_number": case_number,
        "index_close_date": close_date,
        "index_court_name": court_name,
        "index_court_level": court_level,
        "index_procedure": procedure,
        "index_row_index": row.get(RAW_ROW_INDEX, ""),
        "metadata__judgment_date": close_date,
        "metadata__region": region,
        "case_profile__procedure_stage": procedure,
        "case_profile__case_type_secondary": case_reason,
        "criminal_filter_rule": "case_reason_contains_罪",
        "criminal_filter_is_explicit_criminal": "1" if is_explicit_criminal(case_reason) else "0",
        "sample_year": year,
        "sample_region": region,
        "sample_stage": normalize_stage(procedure),
    }


def largest_remainder_allocation(counts: dict[str, int], total_quota: int) -> dict[str, int]:
    if total_quota <= 0 or not counts:
        return {key: 0 for key in counts}
    population = sum(counts.values())
    raw = {key: counts[key] * total_quota / population for key in counts}
    allocation = {key: min(counts[key], int(math.floor(raw[key]))) for key in counts}
    remaining = total_quota - sum(allocation.values())

    order = sorted(
        counts,
        key=lambda key: (raw[key] - math.floor(raw[key]), counts[key], key),
        reverse=True,
    )
    idx = 0
    while remaining > 0 and order:
        key = order[idx % len(order)]
        if allocation[key] < counts[key]:
            allocation[key] += 1
            remaining -= 1
        idx += 1
        if idx > len(order) * 2 and all(allocation[k] >= counts[k] for k in order):
            break
    return allocation


def sample_year_region_group(rows: list[dict[str, Any]], quota: int, rng: random.Random) -> list[dict[str, Any]]:
    if quota <= 0:
        return []
    second_instance = [row for row in rows if normalize_stage(str(row.get(STAGE_COL) or row.get("sample_stage") or "")) == "二审"]
    others = [row for row in rows if normalize_stage(str(row.get(STAGE_COL) or row.get("sample_stage") or "")) != "二审"]
    rng.shuffle(second_instance)
    rng.shuffle(others)
    return (second_instance + others)[:quota]


def load_text_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    payload = read_json(path)
    if isinstance(payload, dict):
        return {str(key) for key in payload.keys()}
    return set()


def build(args: argparse.Namespace) -> dict[str, Any]:
    raw_rows = read_json(Path(args.raw_index))
    if not isinstance(raw_rows, list):
        raise TypeError("data-index.json must be a list of objects")

    normalized = [normalize_row(row) for row in raw_rows]
    rows_with_id = [row for row in normalized if row[DOC_ID]]
    missing_id = len(normalized) - len(rows_with_id)

    criminal_rows = [row for row in rows_with_id if row["criminal_filter_is_explicit_criminal"] == "1"]
    base_rows = [row for row in rows_with_id if row["criminal_filter_is_explicit_criminal"] != "1"]

    total_rows = len(base_rows)
    target_n = math.floor(total_rows * args.fraction)
    if args.n is not None:
        target_n = min(args.n, total_rows)

    rng = random.Random(args.seed)
    by_year: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_year_region: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in base_rows:
        year = str(row["sample_year"])
        region = str(row["sample_region"])
        by_year[year].append(row)
        by_year_region[(year, region)].append(row)

    year_counts = {year: len(group) for year, group in by_year.items()}
    year_quota = largest_remainder_allocation(year_counts, target_n)

    selected: list[dict[str, Any]] = []
    year_region_rows: list[dict[str, Any]] = []
    for year in sorted(by_year):
        regions = sorted(region for y, region in by_year_region if y == year)
        region_counts = {region: len(by_year_region[(year, region)]) for region in regions}
        region_quota = largest_remainder_allocation(region_counts, year_quota[year])
        for region in regions:
            group = by_year_region[(year, region)]
            quota = region_quota[region]
            picked = sample_year_region_group(group, quota, rng)
            selected.extend(picked)
            stage_counter = Counter(str(row.get("sample_stage") or "") for row in group)
            picked_stage_counter = Counter(str(row.get("sample_stage") or "") for row in picked)
            year_region_rows.append(
                {
                    "year": year,
                    "region": region,
                    "population": len(group),
                    "quota": quota,
                    "selected": len(picked),
                    "population_second_instance": stage_counter.get("二审", 0),
                    "selected_second_instance": picked_stage_counter.get("二审", 0),
                    "selected_first_instance": picked_stage_counter.get("一审", 0),
                    "selected_other_stage": len(picked) - picked_stage_counter.get("二审", 0) - picked_stage_counter.get("一审", 0),
                }
            )

    selected_ids = [row[DOC_ID] for row in selected]
    if len(selected_ids) != len(set(selected_ids)):
        raise RuntimeError("Duplicate doc_id selected")
    if len(selected) != target_n:
        raise RuntimeError(f"Selected {len(selected)} rows, expected {target_n}")

    base_csv = Path(args.base_csv)
    base_jsonl = Path(args.base_jsonl)
    excluded_csv = Path(args.excluded_csv)
    excluded_jsonl = Path(args.excluded_jsonl)
    test_csv = Path(args.test_csv)
    test_jsonl = Path(args.test_jsonl)
    ids_json = Path(args.ids_json)
    year_allocation_csv = Path(args.year_allocation_csv)
    year_region_allocation_csv = Path(args.year_region_allocation_csv)
    case_reason_counts_csv = Path(args.case_reason_counts_csv)
    audit_json = Path(args.audit_json)

    fieldnames = [
        DOC_ID,
        "index_title",
        "index_case_cause",
        "index_case_number",
        "index_close_date",
        "index_court_name",
        "index_court_level",
        "index_procedure",
        "index_row_index",
        "metadata__judgment_date",
        "metadata__region",
        "case_profile__procedure_stage",
        "case_profile__case_type_secondary",
        "criminal_filter_rule",
        "criminal_filter_is_explicit_criminal",
        "sample_year",
        "sample_region",
        "sample_stage",
    ]

    write_csv(base_csv, base_rows, fieldnames)
    write_jsonl(base_jsonl, base_rows)
    write_csv(excluded_csv, criminal_rows, fieldnames)
    write_jsonl(excluded_jsonl, criminal_rows)
    write_csv(test_csv, selected, fieldnames)
    write_jsonl(test_jsonl, selected)
    write_json(ids_json, {"seed": args.seed, "doc_ids": selected_ids})

    selected_by_year = Counter(str(row["sample_year"]) for row in selected)
    second_by_year = Counter(str(row["sample_year"]) for row in selected if row["sample_stage"] == "二审")
    year_rows = []
    for year in sorted(year_counts):
        year_rows.append(
            {
                "year": year,
                "population": year_counts[year],
                "population_share": year_counts[year] / total_rows if total_rows else 0,
                "quota": year_quota[year],
                "selected": selected_by_year[year],
                "selected_share": selected_by_year[year] / len(selected) if selected else 0,
                "selected_second_instance": second_by_year[year],
            }
        )
    write_csv(
        year_allocation_csv,
        year_rows,
        ["year", "population", "population_share", "quota", "selected", "selected_share", "selected_second_instance"],
    )
    write_csv(
        year_region_allocation_csv,
        year_region_rows,
        [
            "year",
            "region",
            "population",
            "quota",
            "selected",
            "population_second_instance",
            "selected_second_instance",
            "selected_first_instance",
            "selected_other_stage",
        ],
    )

    reason_counts = []
    base_reason_counter = Counter(str(row.get("index_case_cause") or "") for row in base_rows)
    criminal_reason_counter = Counter(str(row.get("index_case_cause") or "") for row in criminal_rows)
    all_reasons = sorted(set(base_reason_counter) | set(criminal_reason_counter))
    for reason in all_reasons:
        reason_counts.append(
            {
                "case_reason": reason,
                "kept_noncriminal": base_reason_counter[reason],
                "excluded_criminal": criminal_reason_counter[reason],
                "filter_rule": "excluded if case_reason contains 罪",
            }
        )
    write_csv(case_reason_counts_csv, reason_counts, ["case_reason", "kept_noncriminal", "excluded_criminal", "filter_rule"])

    text_ids = load_text_ids(Path(args.texts))
    base_ids = {row[DOC_ID] for row in base_rows}
    selected_stage = Counter(str(row.get("sample_stage") or "") for row in selected)
    base_stage = Counter(str(row.get("sample_stage") or "") for row in base_rows)
    audit = {
        "round": ROUND,
        "source": str(Path(args.raw_index)),
        "filter_rule": "exclude rows where 案由/罪名 contains 罪",
        "seed": args.seed,
        "fraction": args.fraction,
        "raw_rows": len(raw_rows),
        "rows_with_doc_id": len(rows_with_id),
        "missing_doc_id": missing_id,
        "excluded_criminal_rows": len(criminal_rows),
        "base_noncriminal_rows": len(base_rows),
        "target_n": target_n,
        "actual_n": len(selected),
        "actual_fraction": len(selected) / len(base_rows) if base_rows else 0,
        "allocation_method": "largest_remainder_by_year_then_by_region",
        "within_year_region_sampling": "shuffle second-instance cases first, then non-second-instance cases",
        "year_count": len(year_counts),
        "year_region_group_count": len(year_region_rows),
        "base_stage_counts": dict(base_stage),
        "selected_stage_counts": dict(selected_stage),
        "base_region_counts": dict(Counter(str(row["sample_region"]) for row in base_rows)),
        "selected_region_counts": dict(Counter(str(row["sample_region"]) for row in selected)),
        "base_rows_missing_text": len(base_ids - text_ids) if text_ids else None,
        "top_excluded_case_reasons": criminal_reason_counter.most_common(30),
        "top_kept_case_reasons": base_reason_counter.most_common(30),
        "outputs": {
            "base_csv": str(base_csv),
            "base_jsonl": str(base_jsonl),
            "excluded_csv": str(excluded_csv),
            "excluded_jsonl": str(excluded_jsonl),
            "test_csv": str(test_csv),
            "test_jsonl": str(test_jsonl),
            "ids_json": str(ids_json),
            "year_allocation_csv": str(year_allocation_csv),
            "year_region_allocation_csv": str(year_region_allocation_csv),
            "case_reason_counts_csv": str(case_reason_counts_csv),
            "audit_json": str(audit_json),
        },
    }
    write_json(audit_json, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-index", default=str(RAW_INDEX))
    parser.add_argument("--texts", default=str(TEXTS))
    parser.add_argument("--base-csv", default=str(BASE_CSV))
    parser.add_argument("--base-jsonl", default=str(BASE_JSONL))
    parser.add_argument("--excluded-csv", default=str(EXCLUDED_CSV))
    parser.add_argument("--excluded-jsonl", default=str(EXCLUDED_JSONL))
    parser.add_argument("--test-csv", default=str(TEST_CSV))
    parser.add_argument("--test-jsonl", default=str(TEST_JSONL))
    parser.add_argument("--ids-json", default=str(TEST_IDS_JSON))
    parser.add_argument("--year-allocation-csv", default=str(YEAR_ALLOCATION_CSV))
    parser.add_argument("--year-region-allocation-csv", default=str(YEAR_REGION_ALLOCATION_CSV))
    parser.add_argument("--case-reason-counts-csv", default=str(CASE_REASON_COUNTS_CSV))
    parser.add_argument("--audit-json", default=str(AUDIT_JSON))
    parser.add_argument("--fraction", type=float, default=0.05)
    parser.add_argument("--n", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20260520)
    return parser


if __name__ == "__main__":
    build(build_parser().parse_args())
