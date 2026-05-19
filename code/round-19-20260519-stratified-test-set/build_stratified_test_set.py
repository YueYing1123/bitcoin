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
ROUND = "round-19-20260519-stratified-test-set"

MASTER_PATH = ROOT / "data" / "processed" / "master" / "master_dataset_dsv4.csv"
OUTDIR = ROOT / "result" / ROUND
TEST_CSV = OUTDIR / "test_set_5pct_year_region_appeal_priority.csv"
TEST_JSONL = OUTDIR / "test_set_5pct_year_region_appeal_priority.jsonl"
TEST_IDS_JSON = OUTDIR / "test_set_doc_ids.json"
YEAR_ALLOCATION_CSV = OUTDIR / "year_allocation.csv"
YEAR_REGION_ALLOCATION_CSV = OUTDIR / "year_region_allocation.csv"
AUDIT_JSON = OUTDIR / "audit.json"

DOC_ID = "doc_id"
DATE_COL = "metadata__judgment_date"
REGION_COL = "metadata__region"
STAGE_COL = "case_profile__procedure_stage"


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(path)


def extract_year(value: str) -> str:
    m = re.search(r"(?:19|20)\d{2}", value or "")
    return m.group(0) if m else "未明确年份"


def normalize_region(value: str) -> str:
    value = (value or "").strip()
    return value or "未明确地区"


def normalize_stage(value: str) -> str:
    value = (value or "").strip()
    return value or "未明确程序"


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


def sample_year_region_group(rows: list[dict[str, str]], quota: int, rng: random.Random) -> list[dict[str, str]]:
    if quota <= 0:
        return []
    second_instance = [row for row in rows if normalize_stage(row.get(STAGE_COL, "")) == "二审"]
    others = [row for row in rows if normalize_stage(row.get(STAGE_COL, "")) != "二审"]
    rng.shuffle(second_instance)
    rng.shuffle(others)
    return (second_instance + others)[:quota]


def build_test_set(args: argparse.Namespace) -> dict[str, Any]:
    fieldnames, rows = read_csv_rows(Path(args.master_path))
    for required in [DOC_ID, DATE_COL, REGION_COL, STAGE_COL]:
        if required not in fieldnames:
            raise KeyError(f"Missing required column: {required}")

    rows = [row for row in rows if row.get(DOC_ID)]
    total_rows = len(rows)
    target_n = math.floor(total_rows * args.fraction)
    if args.n is not None:
        target_n = min(args.n, total_rows)

    rng = random.Random(args.seed)

    by_year: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_year_region: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        year = extract_year(row.get(DATE_COL, ""))
        region = normalize_region(row.get(REGION_COL, ""))
        row["_sample_year"] = year
        row["_sample_region"] = region
        row["_sample_stage"] = normalize_stage(row.get(STAGE_COL, ""))
        by_year[year].append(row)
        by_year_region[(year, region)].append(row)

    year_counts = {year: len(group) for year, group in by_year.items()}
    year_quota = largest_remainder_allocation(year_counts, target_n)

    selected: list[dict[str, str]] = []
    year_region_rows: list[dict[str, Any]] = []
    for year in sorted(by_year):
        region_counts = {
            region: len(by_year_region[(year, region)])
            for region in sorted({region for y, region in by_year_region if y == year})
        }
        region_quota = largest_remainder_allocation(region_counts, year_quota[year])
        for region in sorted(region_counts):
            group = by_year_region[(year, region)]
            quota = region_quota[region]
            picked = sample_year_region_group(group, quota, rng)
            selected.extend(picked)
            stage_counter = Counter(normalize_stage(row.get(STAGE_COL, "")) for row in group)
            picked_stage_counter = Counter(normalize_stage(row.get(STAGE_COL, "")) for row in picked)
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

    selected_clean = []
    for row in selected:
        clean = {key: value for key, value in row.items() if not key.startswith("_sample_")}
        clean["test_sample_year"] = row["_sample_year"]
        clean["test_sample_region"] = row["_sample_region"]
        clean["test_sample_stage"] = row["_sample_stage"]
        selected_clean.append(clean)

    year_rows = []
    selected_by_year = Counter(row["_sample_year"] for row in selected)
    second_by_year = Counter(row["_sample_year"] for row in selected if row["_sample_stage"] == "二审")
    for year in sorted(year_counts):
        year_rows.append(
            {
                "year": year,
                "population": year_counts[year],
                "population_share": year_counts[year] / total_rows,
                "quota": year_quota[year],
                "selected": selected_by_year[year],
                "selected_share": selected_by_year[year] / len(selected),
                "selected_second_instance": second_by_year[year],
            }
        )

    outdir = Path(args.outdir)
    test_csv = Path(args.test_csv) if args.test_csv else outdir / TEST_CSV.name
    test_jsonl = Path(args.test_jsonl) if args.test_jsonl else outdir / TEST_JSONL.name
    ids_json = Path(args.ids_json) if args.ids_json else outdir / TEST_IDS_JSON.name
    year_csv = Path(args.year_allocation_csv) if args.year_allocation_csv else outdir / YEAR_ALLOCATION_CSV.name
    year_region_csv = Path(args.year_region_allocation_csv) if args.year_region_allocation_csv else outdir / YEAR_REGION_ALLOCATION_CSV.name
    audit_json = Path(args.audit_json) if args.audit_json else outdir / AUDIT_JSON.name

    output_fieldnames = fieldnames + ["test_sample_year", "test_sample_region", "test_sample_stage"]
    write_csv(test_csv, selected_clean, output_fieldnames)
    write_jsonl(test_jsonl, selected_clean)
    write_json(ids_json, {"seed": args.seed, "doc_ids": selected_ids})
    write_csv(
        year_csv,
        year_rows,
        ["year", "population", "population_share", "quota", "selected", "selected_share", "selected_second_instance"],
    )
    write_csv(
        year_region_csv,
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

    stage_population = Counter(normalize_stage(row.get(STAGE_COL, "")) for row in rows)
    stage_selected = Counter(row["_sample_stage"] for row in selected)
    audit = {
        "round": ROUND,
        "source": str(Path(args.master_path)),
        "seed": args.seed,
        "fraction": args.fraction,
        "population_rows": total_rows,
        "target_n": target_n,
        "actual_n": len(selected),
        "actual_fraction": len(selected) / total_rows if total_rows else 0,
        "allocation_method": "largest_remainder_by_year_then_by_region",
        "within_year_region_sampling": "shuffle second-instance cases first, then non-second-instance cases",
        "year_count": len(year_counts),
        "year_region_group_count": len(year_region_rows),
        "population_stage_counts": dict(stage_population),
        "selected_stage_counts": dict(stage_selected),
        "outputs": {
            "test_csv": str(test_csv),
            "test_jsonl": str(test_jsonl),
            "ids_json": str(ids_json),
            "year_allocation_csv": str(year_csv),
            "year_region_allocation_csv": str(year_region_csv),
            "audit_json": str(audit_json),
        },
    }
    write_json(audit_json, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-path", default=str(MASTER_PATH))
    parser.add_argument("--outdir", default=str(OUTDIR))
    parser.add_argument("--test-csv", default="")
    parser.add_argument("--test-jsonl", default="")
    parser.add_argument("--ids-json", default="")
    parser.add_argument("--year-allocation-csv", default="")
    parser.add_argument("--year-region-allocation-csv", default="")
    parser.add_argument("--audit-json", default="")
    parser.add_argument("--fraction", type=float, default=0.05)
    parser.add_argument("--n", type=int)
    parser.add_argument("--seed", type=int, default=2026051904)
    return parser


def main() -> None:
    build_test_set(build_parser().parse_args())


if __name__ == "__main__":
    main()
