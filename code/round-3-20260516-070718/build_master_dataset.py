from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


ROUND = "round-3-20260516-070718"


RAW_INDEX_KEY_MAP = {
    "文书标题": "index_title",
    "案由/罪名": "index_case_cause",
    "案号": "index_case_number",
    "审结时间": "index_close_date",
    "审理法院": "index_court_name",
    "法院级别": "index_court_level",
    "审理程序": "index_procedure",
    "__row_index__": "index_row_index",
}


BASE_COLUMNS = [
    "doc_id",
    "in_flat",
    "in_final_jsonl",
    "in_raw_index",
    "in_raw_text",
    "in_regex_text",
    "in_regex_index",
]

RAW_INDEX_COLUMNS = list(RAW_INDEX_KEY_MAP.values())

LLM_COLUMNS = [
    "llm_top_case_amount_raw",
    "llm_top_case_amount_cny",
    "llm_total_amount_cny_raw",
    "llm_total_amount_cny",
    "llm_agreement_rate",
    "llm_final_label_source",
    "llm_models_used",
]

REGEX_COLUMNS = [
    "regex_text_amounts_json",
    "regex_text_amount_count",
    "regex_text_amount_mean_cny",
    "regex_text_amount_max_cny",
    "regex_text_amount_median_cny",
    "regex_text_contract_validity",
    "regex_index_amounts_json",
    "regex_index_amount_count",
    "regex_index_amount_mean_cny",
    "regex_index_amount_max_cny",
    "regex_index_amount_median_cny",
]

TEXT_COLUMNS = [
    "raw_text_length",
    "raw_text_sha256",
    "raw_text_excerpt",
]

MASTER_AMOUNT_COLUMNS = [
    "amount_flat_total_cny",
    "amount_flat_case_cny",
    "amount_master_cny",
    "amount_master_source",
    "amount_master_is_regex_fallback",
    "amount_llm_case_in_regex_text_amounts",
    "amount_llm_regex_text_conflict",
    "amount_flat_llm_abs_diff",
]


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def clean_scalar(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        value = value.get("value")
    if isinstance(value, list):
        return ";".join(str(clean_scalar(x)) for x in value if clean_scalar(x) not in (None, ""))
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    return value


def parse_number(value: Any) -> float | None:
    value = clean_scalar(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    text = text.replace(",", "").replace("，", "")
    try:
        return float(text)
    except ValueError:
        return None


def number_to_cell(value: float | None) -> str:
    if value is None:
        return ""
    if math.isfinite(value) and value.is_integer():
        return str(int(value))
    return repr(float(value))


def load_flat_csv(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            doc_id = (row.get("doc_id") or "").strip()
            if doc_id:
                rows[doc_id] = row
    return rows, fieldnames


def load_final_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            doc_id = str(obj.get("doc_id") or "").strip()
            if doc_id:
                rows[doc_id] = obj
    return rows


def load_regex_amounts(path: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(path)
    rows: dict[str, dict[str, Any]] = {}
    for rec in payload.get("records", []):
        doc_id = str(rec.get("id") or "").strip()
        if doc_id:
            rows[doc_id] = rec
    return rows


def load_raw_index(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in read_json(path):
        doc_id = str(item.get("可唯一识别id") or "").strip()
        if doc_id:
            rows[doc_id] = item
    return rows


def load_raw_texts(path: Path) -> dict[str, str]:
    return {str(k): (v or "") for k, v in read_json(path).items()}


def stats_value(rec: dict[str, Any] | None, key: str) -> float | None:
    if not rec:
        return None
    stats = rec.get("stats") or {}
    return parse_number(stats.get(key))


def close_enough(a: float, b: float) -> bool:
    tolerance = max(1.0, abs(a) * 0.01)
    return abs(a - b) <= tolerance


def any_close(value: float | None, candidates: list[float]) -> bool | None:
    if value is None:
        return None
    if not candidates:
        return None
    return any(close_enough(value, x) for x in candidates)


def select_master_amount(row: dict[str, str]) -> tuple[float | None, str, int]:
    candidates = [
        ("llm_top_case_amount", parse_number(row.get("llm_top_case_amount_cny")), 0),
        ("llm_total_amount_cny", parse_number(row.get("llm_total_amount_cny")), 0),
        ("flat_case_amount", parse_number(row.get("amount_flat_case_cny")), 0),
        ("flat_total_amount_cny", parse_number(row.get("amount_flat_total_cny")), 0),
        ("regex_text_amount_max", parse_number(row.get("regex_text_amount_max_cny")), 1),
        ("regex_index_amount_max", parse_number(row.get("regex_index_amount_max_cny")), 1),
    ]
    for source, value, is_regex in candidates:
        if value is not None:
            return value, source, is_regex
    return None, "", 0


def build_master(root: Path, timestamp: str) -> dict[str, Any]:
    flat_path = root / "data/processed/analysis_data/final_all_flat.csv"
    final_jsonl_path = root / "data/processed/extraction/final_all.jsonl"
    regex_text_path = root / "data/processed/extraction/data-texts_amount_regex.json"
    regex_index_path = root / "data/processed/extraction/data-index_amount_regex.json"
    raw_index_path = root / "data/raw/data-index.json"
    raw_text_path = root / "data/raw/data-texts.json"

    flat_rows, flat_cols = load_flat_csv(flat_path)
    final_rows = load_final_jsonl(final_jsonl_path)
    regex_text_rows = load_regex_amounts(regex_text_path)
    regex_index_rows = load_regex_amounts(regex_index_path)
    raw_index_rows = load_raw_index(raw_index_path)
    raw_text_rows = load_raw_texts(raw_text_path)

    flat_data_cols = [c for c in flat_cols if c != "doc_id"]
    columns = (
        BASE_COLUMNS
        + RAW_INDEX_COLUMNS
        + flat_data_cols
        + LLM_COLUMNS
        + REGEX_COLUMNS
        + TEXT_COLUMNS
        + MASTER_AMOUNT_COLUMNS
    )

    doc_ids = sorted(
        set(flat_rows)
        | set(final_rows)
        | set(regex_text_rows)
        | set(regex_index_rows)
        | set(raw_index_rows)
        | set(raw_text_rows)
    )

    rows: list[dict[str, str]] = []
    for doc_id in doc_ids:
        row: dict[str, str] = {col: "" for col in columns}
        row["doc_id"] = doc_id
        row["in_flat"] = "1" if doc_id in flat_rows else "0"
        row["in_final_jsonl"] = "1" if doc_id in final_rows else "0"
        row["in_raw_index"] = "1" if doc_id in raw_index_rows else "0"
        row["in_raw_text"] = "1" if doc_id in raw_text_rows else "0"
        row["in_regex_text"] = "1" if doc_id in regex_text_rows else "0"
        row["in_regex_index"] = "1" if doc_id in regex_index_rows else "0"

        raw_index = raw_index_rows.get(doc_id) or {}
        for source_key, target_key in RAW_INDEX_KEY_MAP.items():
            row[target_key] = str(clean_scalar(raw_index.get(source_key)))

        flat = flat_rows.get(doc_id) or {}
        for col in flat_data_cols:
            row[col] = str(clean_scalar(flat.get(col)))

        final = final_rows.get(doc_id) or {}
        final_fields = final.get("final_fields") or {}
        metrics = final.get("metrics") or {}
        llm_case_raw = clean_scalar(final.get("case_amount"))
        llm_total_raw = clean_scalar(final_fields.get("virtual_currency_info.total_amount_cny"))
        row["llm_top_case_amount_raw"] = str(llm_case_raw)
        row["llm_top_case_amount_cny"] = number_to_cell(parse_number(llm_case_raw))
        row["llm_total_amount_cny_raw"] = str(llm_total_raw)
        row["llm_total_amount_cny"] = number_to_cell(parse_number(llm_total_raw))
        row["llm_agreement_rate"] = str(clean_scalar(metrics.get("agreement_rate")))
        row["llm_final_label_source"] = str(clean_scalar(metrics.get("final_label_source")))
        row["llm_models_used"] = ";".join(str(x) for x in (final.get("models_used") or []))

        regex_text = regex_text_rows.get(doc_id)
        regex_text_amounts = [x for x in ((regex_text or {}).get("amounts") or []) if parse_number(x) is not None]
        row["regex_text_amounts_json"] = compact_json(regex_text_amounts)
        row["regex_text_amount_count"] = number_to_cell(stats_value(regex_text, "count"))
        row["regex_text_amount_mean_cny"] = number_to_cell(stats_value(regex_text, "mean"))
        row["regex_text_amount_max_cny"] = number_to_cell(stats_value(regex_text, "max"))
        row["regex_text_amount_median_cny"] = number_to_cell(stats_value(regex_text, "median"))
        row["regex_text_contract_validity"] = str(clean_scalar((regex_text or {}).get("contract_validity_regex")))

        regex_index = regex_index_rows.get(doc_id)
        regex_index_amounts = [x for x in ((regex_index or {}).get("amounts") or []) if parse_number(x) is not None]
        row["regex_index_amounts_json"] = compact_json(regex_index_amounts)
        row["regex_index_amount_count"] = number_to_cell(stats_value(regex_index, "count"))
        row["regex_index_amount_mean_cny"] = number_to_cell(stats_value(regex_index, "mean"))
        row["regex_index_amount_max_cny"] = number_to_cell(stats_value(regex_index, "max"))
        row["regex_index_amount_median_cny"] = number_to_cell(stats_value(regex_index, "median"))

        text = raw_text_rows.get(doc_id)
        if text is not None:
            row["raw_text_length"] = str(len(text))
            row["raw_text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            row["raw_text_excerpt"] = text[:300]

        row["amount_flat_total_cny"] = number_to_cell(parse_number(flat.get("total_amount_cny")))
        row["amount_flat_case_cny"] = number_to_cell(parse_number(flat.get("case_amount")))
        master_amount, master_source, master_is_regex = select_master_amount(row)
        row["amount_master_cny"] = number_to_cell(master_amount)
        row["amount_master_source"] = master_source
        row["amount_master_is_regex_fallback"] = str(master_is_regex)

        llm_case = parse_number(row["llm_top_case_amount_cny"])
        regex_text_numbers = [parse_number(x) for x in regex_text_amounts]
        regex_text_numbers = [x for x in regex_text_numbers if x is not None]
        in_regex = any_close(llm_case, regex_text_numbers)
        row["amount_llm_case_in_regex_text_amounts"] = "" if in_regex is None else str(int(in_regex))
        row["amount_llm_regex_text_conflict"] = "" if in_regex is None else str(int(not in_regex))
        flat_case = parse_number(row["amount_flat_case_cny"])
        if llm_case is not None and flat_case is not None:
            row["amount_flat_llm_abs_diff"] = number_to_cell(abs(flat_case - llm_case))

        rows.append(row)

    out_dir = root / "data/processed/master"
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamped_csv = out_dir / f"master_dataset_{timestamp}.csv"
    timestamped_jsonl = out_dir / f"master_dataset_{timestamp}.jsonl"
    latest_csv = out_dir / "master_dataset.csv"
    latest_jsonl = out_dir / "master_dataset.jsonl"

    with timestamped_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    with timestamped_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    shutil.copy2(timestamped_csv, latest_csv)
    shutil.copy2(timestamped_jsonl, latest_jsonl)

    dictionary_path = out_dir / f"master_dataset_dictionary_{timestamp}.csv"
    latest_dictionary_path = out_dir / "master_dataset_dictionary.csv"
    dictionary_rows = build_dictionary(columns, flat_data_cols)
    with dictionary_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["column", "source", "description"])
        writer.writeheader()
        writer.writerows(dictionary_rows)
    shutil.copy2(dictionary_path, latest_dictionary_path)

    source_counts = {
        "flat_csv_rows": len(flat_rows),
        "final_jsonl_rows": len(final_rows),
        "regex_text_rows": len(regex_text_rows),
        "regex_index_rows": len(regex_index_rows),
        "raw_index_rows": len(raw_index_rows),
        "raw_text_rows": len(raw_text_rows),
        "master_rows": len(rows),
    }
    amount_counts = {
        "llm_top_case_amount_nonmissing": sum(1 for r in rows if r["llm_top_case_amount_cny"]),
        "llm_total_amount_field_nonmissing": sum(1 for r in rows if r["llm_total_amount_cny"]),
        "flat_case_amount_nonmissing": sum(1 for r in rows if r["amount_flat_case_cny"]),
        "regex_text_amount_nonmissing": sum(1 for r in rows if parse_number(r["regex_text_amount_count"]) not in (None, 0)),
        "regex_index_amount_nonmissing": sum(1 for r in rows if parse_number(r["regex_index_amount_count"]) not in (None, 0)),
        "master_amount_nonmissing": sum(1 for r in rows if r["amount_master_cny"]),
        "llm_regex_text_conflicts": sum(1 for r in rows if r["amount_llm_regex_text_conflict"] == "1"),
    }
    audit = {
        "round": ROUND,
        "timestamp": timestamp,
        "inputs": {
            "flat_csv": str(flat_path),
            "final_jsonl": str(final_jsonl_path),
            "regex_text": str(regex_text_path),
            "regex_index": str(regex_index_path),
            "raw_index": str(raw_index_path),
            "raw_text": str(raw_text_path),
        },
        "outputs": {
            "master_csv": str(latest_csv),
            "master_jsonl": str(latest_jsonl),
            "timestamped_master_csv": str(timestamped_csv),
            "timestamped_master_jsonl": str(timestamped_jsonl),
            "dictionary": str(latest_dictionary_path),
        },
        "source_counts": source_counts,
        "amount_counts": amount_counts,
        "amount_master_priority": [
            "llm_top_case_amount",
            "llm_total_amount_cny",
            "flat_case_amount",
            "flat_total_amount_cny",
            "regex_text_amount_max",
            "regex_index_amount_max",
        ],
        "notes": [
            "The original full text is not embedded in the master table; use data/raw/data-texts.json as the text source keyed by doc_id.",
            "virtual_currency_info.total_amount_cny in final_all.jsonl is preserved as llm_total_amount_cny but is currently empty in this dataset.",
            "Top-level final_all.jsonl case_amount is preserved as llm_top_case_amount_cny and used first for amount_master_cny.",
            "Regex text amount arrays are preserved in regex_text_amounts_json for audit and alternative amount construction.",
        ],
    }
    audit_path = out_dir / f"master_dataset_audit_{timestamp}.json"
    latest_audit_path = out_dir / "master_dataset_audit.json"
    write_json(audit_path, audit)
    shutil.copy2(audit_path, latest_audit_path)

    readme_path = out_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# Master Dataset",
                "",
                f"Current stable master dataset: `{latest_csv}`",
                f"Current stable JSONL mirror: `{latest_jsonl}`",
                f"Data dictionary: `{latest_dictionary_path}`",
                f"Audit file: `{latest_audit_path}`",
                "",
                "This table merges the old flat analysis data, final LLM extraction JSONL, regex amount extraction from full text, regex amount extraction from index metadata, raw index metadata, and raw-text audit metadata.",
                "",
                "The full judgment text is not embedded in the table. Use `data/raw/data-texts.json` keyed by `doc_id` when full text is needed.",
                "",
                "Amount priority for `amount_master_cny`: llm top-level `case_amount`, LLM field `virtual_currency_info.total_amount_cny`, flat `case_amount`, flat `total_amount_cny`, regex text max, regex index max.",
            ]
        ),
        encoding="utf-8",
    )

    return {
        "columns": columns,
        "source_counts": source_counts,
        "amount_counts": amount_counts,
        "outputs": audit["outputs"],
    }


def build_dictionary(columns: list[str], flat_data_cols: list[str]) -> list[dict[str, str]]:
    descriptions: dict[str, tuple[str, str]] = {}
    for col in BASE_COLUMNS:
        descriptions[col] = ("merge", "Merge key or source-presence flag.")
    descriptions["doc_id"] = ("merge", "Stable document identifier used across all inputs.")
    for col in RAW_INDEX_COLUMNS:
        descriptions[col] = ("data/raw/data-index.json", "Raw index metadata copied from the original index file.")
    for col in flat_data_cols:
        descriptions[col] = ("data/processed/analysis_data/final_all_flat.csv", "Existing flat analysis variable from the old workflow.")
    descriptions.update(
        {
            "llm_top_case_amount_raw": ("data/processed/extraction/final_all.jsonl", "Raw top-level case_amount value."),
            "llm_top_case_amount_cny": ("data/processed/extraction/final_all.jsonl", "Numeric top-level case_amount value."),
            "llm_total_amount_cny_raw": ("data/processed/extraction/final_all.jsonl", "Raw final_fields virtual_currency_info.total_amount_cny value."),
            "llm_total_amount_cny": ("data/processed/extraction/final_all.jsonl", "Numeric final_fields virtual_currency_info.total_amount_cny value."),
            "llm_agreement_rate": ("data/processed/extraction/final_all.jsonl", "LLM ensemble agreement rate."),
            "llm_final_label_source": ("data/processed/extraction/final_all.jsonl", "LLM final label source, e.g. majority vote."),
            "llm_models_used": ("data/processed/extraction/final_all.jsonl", "Models used for the final extraction."),
            "regex_text_amounts_json": ("data/processed/extraction/data-texts_amount_regex.json", "All regex amount candidates extracted from full text, serialized as JSON."),
            "regex_text_amount_count": ("data/processed/extraction/data-texts_amount_regex.json", "Count of full-text regex amount candidates."),
            "regex_text_amount_mean_cny": ("data/processed/extraction/data-texts_amount_regex.json", "Mean of full-text regex amount candidates."),
            "regex_text_amount_max_cny": ("data/processed/extraction/data-texts_amount_regex.json", "Maximum full-text regex amount candidate."),
            "regex_text_amount_median_cny": ("data/processed/extraction/data-texts_amount_regex.json", "Median of full-text regex amount candidates."),
            "regex_text_contract_validity": ("data/processed/extraction/data-texts_amount_regex.json", "Regex contract validity flag from full text."),
            "regex_index_amounts_json": ("data/processed/extraction/data-index_amount_regex.json", "All regex amount candidates extracted from index metadata, serialized as JSON."),
            "regex_index_amount_count": ("data/processed/extraction/data-index_amount_regex.json", "Count of index regex amount candidates."),
            "regex_index_amount_mean_cny": ("data/processed/extraction/data-index_amount_regex.json", "Mean of index regex amount candidates."),
            "regex_index_amount_max_cny": ("data/processed/extraction/data-index_amount_regex.json", "Maximum index regex amount candidate."),
            "regex_index_amount_median_cny": ("data/processed/extraction/data-index_amount_regex.json", "Median of index regex amount candidates."),
            "raw_text_length": ("data/raw/data-texts.json", "Length of the original text in characters."),
            "raw_text_sha256": ("data/raw/data-texts.json", "SHA-256 hash of the original text."),
            "raw_text_excerpt": ("data/raw/data-texts.json", "First 300 characters of original text for quick inspection."),
            "amount_flat_total_cny": ("derived", "Numeric version of flat total_amount_cny."),
            "amount_flat_case_cny": ("derived", "Numeric version of flat case_amount."),
            "amount_master_cny": ("derived", "Preferred amount variable for downstream research."),
            "amount_master_source": ("derived", "Source selected for amount_master_cny."),
            "amount_master_is_regex_fallback": ("derived", "1 if amount_master_cny came from regex fallback."),
            "amount_llm_case_in_regex_text_amounts": ("derived", "1 if LLM top-level case amount is close to any full-text regex candidate."),
            "amount_llm_regex_text_conflict": ("derived", "1 if LLM top-level case amount is not close to any full-text regex candidate."),
            "amount_flat_llm_abs_diff": ("derived", "Absolute difference between flat case_amount and LLM top-level case_amount."),
        }
    )
    rows = []
    for col in columns:
        source, description = descriptions.get(col, ("unknown", "No description."))
        rows.append({"column": col, "source": source, "description": description})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="newstudy root directory")
    parser.add_argument("--timestamp", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    args = parser.parse_args()

    root = Path(args.root).resolve()
    summary = build_master(root, args.timestamp)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
