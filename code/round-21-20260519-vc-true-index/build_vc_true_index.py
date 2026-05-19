from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ROUND = "round-21-20260519-vc-true-index"

RAW_INDEX = ROOT / "data" / "raw" / "data-index.json"
MASTER_CSV = ROOT / "data" / "processed" / "master" / "master_dataset.csv"
MASTER_DSV4_CSV = ROOT / "data" / "processed" / "master" / "master_dataset_dsv4.csv"
MASTER_DSV4_JSONL = ROOT / "data" / "processed" / "master" / "master_dataset_dsv4.jsonl"
OUTDIR = ROOT / "result" / ROUND

INDEX_AUGMENTED = ROOT / "data" / "processed" / "extraction" / "data-index_vc_involved_augmented.json"
INDEX_TRUE = ROOT / "data" / "processed" / "extraction" / "data-index_vc_involved_true.json"
MASTER_AUGMENTED_CSV = ROOT / "data" / "processed" / "master" / "master_dataset_vc_indexed.csv"
MASTER_TRUE_CSV = ROOT / "data" / "processed" / "master" / "master_dataset_vc_true.csv"
MASTER_DSV4_AUGMENTED_CSV = ROOT / "data" / "processed" / "master" / "master_dataset_dsv4_vc_indexed.csv"
MASTER_DSV4_TRUE_CSV = ROOT / "data" / "processed" / "master" / "master_dataset_dsv4_vc_true.csv"
MASTER_DSV4_TRUE_JSONL = ROOT / "data" / "processed" / "master" / "master_dataset_dsv4_vc_true.jsonl"
AUDIT_JSON = OUTDIR / "audit.json"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(path)


def bool_to_cell(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return ""


def get_nested_value(obj: dict[str, Any], path: list[str]) -> Any:
    cur: Any = obj
    for part in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def dsv4_involved_map(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in rows:
        doc_id = str(row.get("document_id") or "")
        if not doc_id:
            continue
        value = get_nested_value(row, ["virtual_currency_info", "involved", "value"])
        out[doc_id] = value if isinstance(value, bool) else None
    return out


def augment_csv_rows(rows: list[dict[str, str]], id_col: str, vc_map: dict[str, Any]) -> list[dict[str, Any]]:
    augmented = []
    for row in rows:
        doc_id = str(row.get(id_col) or "")
        value = vc_map.get(doc_id)
        new_row = dict(row)
        new_row["vc_involved_dsv4_value"] = bool_to_cell(value)
        new_row["vc_involved_dsv4_source"] = "master_dataset_dsv4.jsonl:virtual_currency_info.involved.value" if doc_id in vc_map else ""
        augmented.append(new_row)
    return augmented


def augment_index_rows(rows: list[dict[str, Any]], vc_map: dict[str, Any]) -> list[dict[str, Any]]:
    augmented = []
    for row in rows:
        doc_id = str(row.get("可唯一识别id") or row.get("doc_id") or "")
        value = vc_map.get(doc_id)
        new_row = dict(row)
        new_row["vc_involved_dsv4_value"] = bool_to_cell(value)
        new_row["vc_involved_dsv4_source"] = "master_dataset_dsv4.jsonl:virtual_currency_info.involved.value" if doc_id in vc_map else ""
        augmented.append(new_row)
    return augmented


def build(args: argparse.Namespace) -> dict[str, Any]:
    dsv4_jsonl_rows = read_jsonl(Path(args.master_dsv4_jsonl))
    vc_map = dsv4_involved_map(dsv4_jsonl_rows)
    true_ids = {doc_id for doc_id, value in vc_map.items() if value is True}
    false_ids = {doc_id for doc_id, value in vc_map.items() if value is False}
    null_ids = {doc_id for doc_id, value in vc_map.items() if value is None}

    raw_index = read_json(Path(args.raw_index))
    if not isinstance(raw_index, list):
        raise TypeError("data-index.json must be a list of objects")
    index_augmented = augment_index_rows(raw_index, vc_map)
    index_true = [row for row in index_augmented if row.get("vc_involved_dsv4_value") == "true"]

    master_fields, master_rows = read_csv(Path(args.master_csv))
    master_augmented = augment_csv_rows(master_rows, "doc_id", vc_map)
    master_true = [row for row in master_augmented if row.get("vc_involved_dsv4_value") == "true"]

    dsv4_fields, dsv4_rows = read_csv(Path(args.master_dsv4_csv))
    dsv4_augmented = augment_csv_rows(dsv4_rows, "doc_id", vc_map)
    dsv4_true = [row for row in dsv4_augmented if row.get("vc_involved_dsv4_value") == "true"]
    dsv4_true_jsonl = [row for row in dsv4_jsonl_rows if str(row.get("document_id") or "") in true_ids]

    index_augmented_path = Path(args.index_augmented)
    index_true_path = Path(args.index_true)
    master_augmented_path = Path(args.master_augmented_csv)
    master_true_path = Path(args.master_true_csv)
    dsv4_augmented_path = Path(args.master_dsv4_augmented_csv)
    dsv4_true_path = Path(args.master_dsv4_true_csv)
    dsv4_true_jsonl_path = Path(args.master_dsv4_true_jsonl)
    audit_path = Path(args.audit_json)

    write_json(index_augmented_path, index_augmented)
    write_json(index_true_path, index_true)
    extra_cols = ["vc_involved_dsv4_value", "vc_involved_dsv4_source"]
    write_csv(master_augmented_path, master_fields + extra_cols, master_augmented)
    write_csv(master_true_path, master_fields + extra_cols, master_true)
    write_csv(dsv4_augmented_path, dsv4_fields + extra_cols, dsv4_augmented)
    write_csv(dsv4_true_path, dsv4_fields + extra_cols, dsv4_true)
    write_jsonl(dsv4_true_jsonl_path, dsv4_true_jsonl)

    raw_index_ids = {str(row.get("可唯一识别id") or "") for row in raw_index}
    master_ids = {row.get("doc_id") for row in master_rows}
    dsv4_csv_ids = {row.get("doc_id") for row in dsv4_rows}
    audit = {
        "round": ROUND,
        "field_added": "vc_involved_dsv4_value",
        "source_field": "master_dataset_dsv4.jsonl:virtual_currency_info.involved.value",
        "dsv4_jsonl_rows": len(dsv4_jsonl_rows),
        "dsv4_involved_counts": dict(Counter(bool_to_cell(value) or "null" for value in vc_map.values())),
        "true_count": len(true_ids),
        "false_count": len(false_ids),
        "null_count": len(null_ids),
        "raw_index_rows": len(raw_index),
        "raw_index_true_rows": len(index_true),
        "master_rows": len(master_rows),
        "master_true_rows": len(master_true),
        "master_dsv4_rows": len(dsv4_rows),
        "master_dsv4_true_rows": len(dsv4_true),
        "ids_in_raw_index_missing_dsv4_value": len(raw_index_ids - set(vc_map)),
        "ids_in_master_missing_dsv4_value": len(master_ids - set(vc_map)),
        "ids_in_dsv4_csv_missing_dsv4_value": len(dsv4_csv_ids - set(vc_map)),
        "outputs": {
            "index_augmented": str(index_augmented_path),
            "index_true": str(index_true_path),
            "master_augmented_csv": str(master_augmented_path),
            "master_true_csv": str(master_true_path),
            "master_dsv4_augmented_csv": str(dsv4_augmented_path),
            "master_dsv4_true_csv": str(dsv4_true_path),
            "master_dsv4_true_jsonl": str(dsv4_true_jsonl_path),
            "audit_json": str(audit_path),
        },
    }
    write_json(audit_path, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-index", default=str(RAW_INDEX))
    parser.add_argument("--master-csv", default=str(MASTER_CSV))
    parser.add_argument("--master-dsv4-csv", default=str(MASTER_DSV4_CSV))
    parser.add_argument("--master-dsv4-jsonl", default=str(MASTER_DSV4_JSONL))
    parser.add_argument("--index-augmented", default=str(INDEX_AUGMENTED))
    parser.add_argument("--index-true", default=str(INDEX_TRUE))
    parser.add_argument("--master-augmented-csv", default=str(MASTER_AUGMENTED_CSV))
    parser.add_argument("--master-true-csv", default=str(MASTER_TRUE_CSV))
    parser.add_argument("--master-dsv4-augmented-csv", default=str(MASTER_DSV4_AUGMENTED_CSV))
    parser.add_argument("--master-dsv4-true-csv", default=str(MASTER_DSV4_TRUE_CSV))
    parser.add_argument("--master-dsv4-true-jsonl", default=str(MASTER_DSV4_TRUE_JSONL))
    parser.add_argument("--audit-json", default=str(AUDIT_JSON))
    return parser


def main() -> None:
    build(build_parser().parse_args())


if __name__ == "__main__":
    main()
