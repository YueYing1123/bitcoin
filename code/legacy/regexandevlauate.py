import csv
import json
import re
import statistics
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


DATA_TEXTS_PATH = Path("data/data-texts.json")
DATA_INDEX_PATH = Path("data/data-index.json")
FINAL_CSV_PATH = Path("analyze/data/final_all_flat.csv")


AMOUNT_PATTERN = re.compile(
    r"(?P<num>[零〇一二三四五六七八九十百千万亿两\d][零〇一二三四五六七八九十百千万亿两\d,，\.]*)\s*(?P<unit>亿|万)?\s*元"
)
CONTRACT_INVALID_PATTERN = re.compile(r"认定\s*合同\s*无效")


CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CN_SMALL_UNITS = {"十": 10, "百": 100, "千": 1000}
CN_LARGE_UNITS = {"万": 10_000, "亿": 100_000_000}


def read_text(path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", "gb18030"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"Cannot decode file: {path}")


def load_json(path: Path):
    return json.loads(read_text(path))


def clean_numeric_token(token: str) -> str:
    return token.replace(",", "").replace("，", "").strip()


def parse_mixed_number(token: str) -> Optional[float]:
    token = clean_numeric_token(token)
    if not token:
        return None

    if re.fullmatch(r"\d+(?:\.\d+)?", token):
        try:
            return float(token)
        except ValueError:
            return None

    total = 0.0
    section = 0.0
    number = None  # type: Optional[float]
    i = 0
    has_any = False

    while i < len(token):
        ch = token[i]
        if ch.isdigit() or ch == ".":
            j = i
            while j < len(token) and (token[j].isdigit() or token[j] in ".,，"):
                j += 1
            raw_num = clean_numeric_token(token[i:j])
            try:
                number = float(raw_num)
                has_any = True
            except ValueError:
                return None
            i = j
            continue

        if ch in CN_DIGITS:
            number = float(CN_DIGITS[ch])
            has_any = True
            i += 1
            continue

        if ch in CN_SMALL_UNITS:
            unit = float(CN_SMALL_UNITS[ch])
            if number is None:
                number = 1.0
            section += number * unit
            number = None
            has_any = True
            i += 1
            continue

        if ch in CN_LARGE_UNITS:
            unit = float(CN_LARGE_UNITS[ch])
            if number is not None:
                section += number
            if section == 0:
                section = 1.0
            total += section * unit
            section = 0.0
            number = None
            has_any = True
            i += 1
            continue

        return None

    if not has_any:
        return None

    if number is not None:
        section += number
    return total + section


def is_noisy_match(text: str, start: int, end: int, raw_num: str, unit: Optional[str]) -> bool:
    left = max(0, start - 16)
    right = min(len(text), end + 16)
    context = text[left:right]

    if re.search(r"第[零〇一二三四五六七八九十百千万亿两\d]{1,8}[条款项]", context):
        return True

    if re.search(r"(电话|手机号|联系方式|联系号码)", context) and re.search(r"\d{7,}", raw_num):
        return True

    if re.search(r"\d{4}[年\-/\.]\d{1,2}[月\-/\.]\d{1,2}[日号]?", context):
        return True

    plain_num = clean_numeric_token(raw_num)
    if unit is None and re.fullmatch(r"\d{11,}", plain_num):
        return True

    return False


def summarize_amounts(amounts: List[float]) -> Dict[str, Optional[float]]:
    if not amounts:
        return {"mean": None, "max": None, "median": None, "count": 0}
    return {
        "mean": float(statistics.mean(amounts)),
        "max": float(max(amounts)),
        "median": float(statistics.median(amounts)),
        "count": len(amounts),
    }


def extract_amounts_from_text(text: str) -> List[float]:
    amounts: List[float] = []
    for m in AMOUNT_PATTERN.finditer(text):
        raw_num = m.group("num")
        unit = m.group("unit")
        if is_noisy_match(text, m.start(), m.end(), raw_num, unit):
            continue

        base = parse_mixed_number(raw_num)
        if base is None:
            continue

        multiplier = 1.0
        if unit == "万":
            multiplier = 10_000.0
        elif unit == "亿":
            multiplier = 100_000_000.0

        value = base * multiplier
        if value <= 0:
            continue
        amounts.append(value)
    return amounts


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_output_path(src_path: Path) -> Path:
    return src_path.with_name(f"{src_path.stem}_amount_regex.json")


def process_data_texts(path: Path) -> Tuple[dict, Dict[str, Dict[str, Optional[float]]], Dict[str, int]]:
    data = load_json(path)
    records = []
    all_amounts: List[float] = []
    stats_map: Dict[str, Dict[str, Optional[float]]] = {}
    validity_map: Dict[str, int] = {}

    for doc_id, text in data.items():
        text = text or ""
        amounts = extract_amounts_from_text(text)
        stats = summarize_amounts(amounts)
        validity = 0 if CONTRACT_INVALID_PATTERN.search(text) else 1

        records.append(
            {
                "id": doc_id,
                "amounts": amounts,
                "stats": stats,
                "contract_validity_regex": validity,
            }
        )
        all_amounts.extend(amounts)
        stats_map[doc_id] = stats
        validity_map[doc_id] = validity

    payload = {
        "source_file": str(path),
        "records": records,
        "file_stats": summarize_amounts(all_amounts),
    }
    return payload, stats_map, validity_map


def process_data_index(path: Path) -> dict:
    data = load_json(path)
    records = []
    all_amounts: List[float] = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                rec_id = item.get("可唯一识别id") or item.get("doc_id") or item.get("id")
                merged_text = " ".join(str(v) for v in item.values() if isinstance(v, (str, int, float)))
            else:
                rec_id = None
                merged_text = str(item)

            amounts = extract_amounts_from_text(merged_text)
            stats = summarize_amounts(amounts)
            records.append({"id": rec_id, "amounts": amounts, "stats": stats})
            all_amounts.extend(amounts)

    payload = {
        "source_file": str(path),
        "records": records,
        "file_stats": summarize_amounts(all_amounts),
    }
    return payload


def process_final_csv(path: Path) -> dict:
    records = []
    all_amounts: List[float] = []

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc_id = row.get("doc_id")
            merged_text = " ".join(v for v in row.values() if isinstance(v, str))
            amounts = extract_amounts_from_text(merged_text)
            stats = summarize_amounts(amounts)
            records.append({"id": doc_id, "amounts": amounts, "stats": stats})
            all_amounts.extend(amounts)

    payload = {
        "source_file": str(path),
        "records": records,
        "file_stats": summarize_amounts(all_amounts),
    }
    return payload


def update_final_csv(
    csv_path: Path,
    stats_map: Dict[str, Dict[str, Optional[float]]],
    validity_map: Dict[str, int],
) -> None:
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    new_fields = [
        "amount_mean_regex",
        "amount_max_regex",
        "amount_median_regex",
        "amount_count_regex",
        "contract_validity_regex",
    ]
    for nf in new_fields:
        if nf not in fieldnames:
            fieldnames.append(nf)

    for row in rows:
        doc_id = row.get("doc_id", "")
        stats = stats_map.get(doc_id, {"mean": None, "max": None, "median": None, "count": 0})
        row["amount_mean_regex"] = "" if stats["mean"] is None else f"{stats['mean']:.6f}"
        row["amount_max_regex"] = "" if stats["max"] is None else f"{stats['max']:.6f}"
        row["amount_median_regex"] = "" if stats["median"] is None else f"{stats['median']:.6f}"
        row["amount_count_regex"] = str(stats["count"] if stats["count"] is not None else 0)
        row["contract_validity_regex"] = str(validity_map.get(doc_id, 1))

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_sample(data_texts_payload: dict, sample_size: int = 3) -> None:
    records = data_texts_payload.get("records", [])
    print(f"[sample] showing first {min(sample_size, len(records))} records from data-texts:")
    for rec in records[:sample_size]:
        rid = rec.get("id")
        amounts = rec.get("amounts", [])
        stats = rec.get("stats", {})
        print(f"  id={rid}, count={stats.get('count')}, max={stats.get('max')}, amounts_head={amounts[:5]}")


def main() -> None:
    data_texts_output, stats_map, validity_map = process_data_texts(DATA_TEXTS_PATH)
    data_index_output = process_data_index(DATA_INDEX_PATH)
    final_csv_output = process_final_csv(FINAL_CSV_PATH)

    write_json(build_output_path(DATA_TEXTS_PATH), data_texts_output)
    write_json(build_output_path(DATA_INDEX_PATH), data_index_output)
    write_json(build_output_path(FINAL_CSV_PATH), final_csv_output)

    update_final_csv(FINAL_CSV_PATH, stats_map, validity_map)

    print("[done] amount extraction and evaluation finished.")
    print(f"[output] {build_output_path(DATA_TEXTS_PATH)}")
    print(f"[output] {build_output_path(DATA_INDEX_PATH)}")
    print(f"[output] {build_output_path(FINAL_CSV_PATH)}")
    print(f"[updated] {FINAL_CSV_PATH}")
    print_sample(data_texts_output)


if __name__ == "__main__":
    main()
