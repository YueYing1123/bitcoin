from __future__ import annotations

import argparse
import ast
import concurrent.futures as futures
import csv
import json
import math
import random
import re
import threading
import time
import unicodedata
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[2]
ROUND = "round-10-20260517-kimi-k26-f1"

MASTER_PATH = ROOT / "data" / "processed" / "master" / "master_dataset.csv"
TEXTS_PATH = ROOT / "data" / "raw" / "data-texts.json"
PROMPT_PATH = ROOT / "docs" / "legacy" / "master_prompt.md"
LEGACY_API_PATH = next(
    (ROOT / "docs" / "legacy").glob("*siliconflow.py"),
    ROOT / "docs" / "legacy" / "batch-summary-siliconflow.py",
)
DSV4_JSONL_PATH = ROOT / "data" / "processed" / "master" / "master_dataset_dsv4.jsonl"
OUTDIR = ROOT / "result" / ROUND

MODEL_NAME = "Pro/moonshotai/Kimi-K2.6"
DS_MODEL_NAME = "deepseek-ai/DeepSeek-V4-Flash"

GOLD_JSONL_PATH = OUTDIR / "kimi_k26_gold_1pct.jsonl"
GOLD_CSV_PATH = OUTDIR / "kimi_k26_gold_1pct.csv"
FAIL_PATH = OUTDIR / "kimi_k26_gold_failures.jsonl"
SAMPLE_PLAN_PATH = OUTDIR / "sample_plan.json"
PAIR_PATH = OUTDIR / "dsv4_vs_kimi_pairs.jsonl"
FIELD_METRICS_CSV = OUTDIR / "field_metrics.csv"
SUMMARY_JSON = OUTDIR / "metrics_summary.json"
REPORT_PATH = OUTDIR / "REPORT.md"
AUDIT_PATH = OUTDIR / "audit.json"

CONTENT_FIELDS = [
    "case_amount",
    "metadata.case_number",
    "metadata.court_name",
    "metadata.court_level",
    "metadata.judgment_date",
    "metadata.first_instance_case_number",
    "metadata.region",
    "metadata.doc_type",
    "case_profile.case_type_primary",
    "case_profile.case_type_secondary",
    "case_profile.procedure_stage",
    "case_profile.is_appeal",
    "case_profile.litigant_profile.plaintiff_types",
    "case_profile.litigant_profile.defendant_types",
    "virtual_currency_info.involved",
    "virtual_currency_info.currency_types",
    "virtual_currency_info.activity_type",
    "judicial_analysis.legal_characterization",
    "judicial_analysis.virtual_currency_property_legality",
    "judicial_analysis.contract_validity",
    "judicial_analysis.reason_for_invalidity",
    "judicial_analysis.cited_laws",
    "judicial_analysis.cited_policies",
    "judicial_analysis.judicial_framing",
    "llm_summary.outcome_summary",
    "llm_summary.reasoning_summary",
]

LIST_FIELDS = {
    "case_profile.litigant_profile.plaintiff_types",
    "case_profile.litigant_profile.defendant_types",
    "virtual_currency_info.currency_types",
    "judicial_analysis.reason_for_invalidity",
    "judicial_analysis.cited_laws",
    "judicial_analysis.cited_policies",
    "judicial_analysis.judicial_framing",
}

BOOLEAN_FIELDS = {
    "case_profile.is_appeal",
    "virtual_currency_info.involved",
}

DATE_FIELDS = {
    "metadata.judgment_date",
}

NUMERIC_FIELDS = {
    "case_amount",
}

CSV_COLUMNS = [
    "doc_id",
    "kimi_status",
    "kimi_model",
    "kimi_temperature",
] + [field.replace(".", "__") for field in CONTENT_FIELDS]


class RateLimiter:
    def __init__(self, rpm: int, tpm: int) -> None:
        self.rpm = rpm
        self.tpm = tpm
        self.lock = threading.Lock()
        self.request_times: list[float] = []
        self.token_times: list[tuple[float, int]] = []

    def wait(self, tokens: int) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                cutoff = now - 60
                self.request_times = [x for x in self.request_times if x >= cutoff]
                self.token_times = [(ts, n) for ts, n in self.token_times if ts >= cutoff]
                used_tokens = sum(n for _, n in self.token_times)
                if len(self.request_times) < self.rpm and used_tokens + tokens <= self.tpm:
                    self.request_times.append(now)
                    self.token_times.append((now, tokens))
                    return
                waits = []
                if len(self.request_times) >= self.rpm and self.request_times:
                    waits.append(60 - (now - self.request_times[0]))
                if used_tokens + tokens > self.tpm and self.token_times:
                    waits.append(60 - (now - self.token_times[0][0]))
                wait_for = max(0.05, min([x for x in waits if x > 0] or [0.25]))
            time.sleep(wait_for)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_master(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, obj: dict[str, Any], lock: threading.Lock) -> None:
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def extract_literal_assignment(path: Path, name: str) -> str:
    tree = ast.parse(read_text(path), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = ast.literal_eval(node.value)
                    if not isinstance(value, str) or not value:
                        raise ValueError(f"{name} is empty or not a string in {path}")
                    return value
    raise KeyError(f"Cannot find {name} in {path}")


def render_prompt(template: str, row: dict[str, str], doc_text: str) -> str:
    meta = {
        "title": row.get("index_title") or "",
        "case_reason": row.get("index_case_cause") or "",
        "case_number": row.get("case_number") or row.get("index_case_number") or "",
        "judgment_date": row.get("judgment_date") or row.get("index_close_date") or "",
        "court_name": row.get("court_name") or row.get("index_court_name") or "",
        "court_level": row.get("court_level") or row.get("index_court_level") or "",
        "procedure_stage": row.get("procedure_stage") or row.get("index_procedure") or "",
    }
    out = template.strip().replace("{{ document_id }}", row["doc_id"])
    out = out.replace("{{ document_text }}", doc_text)
    for key, value in meta.items():
        out = out.replace("{{ meta." + key + " }}", value)
    return out


def estimate_tokens(text: str, max_tokens: int) -> int:
    return max(1, len(text) // 2 + max_tokens)


def strip_code_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def parse_json_content(content: str) -> dict[str, Any]:
    s = strip_code_fence(content)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        start = s.find("{")
        end = s.rfind("}")
        if start < 0 or end <= start:
            raise
        obj = json.loads(s[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("model output is not a JSON object")
    return obj


def is_safety_refusal(status_code: int | None, text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    try:
        parse_json_content(s)
        return False
    except Exception:
        pass
    lowered = s.lower()
    phrases = [
        "i can't help",
        "i cannot help",
        "i'm sorry",
        "sorry, but",
        "unable to assist",
        "cannot comply",
        "cannot assist",
        "refuse",
        "refusal",
        "content filter",
        "content moderation",
        "blocked by",
        "unsafe",
        "policy violation",
    ]
    if any(phrase in lowered for phrase in phrases):
        return True
    if status_code in {400, 403, 451} and any(
        phrase in lowered for phrase in ["safety", "moderation", "blocked", "refuse", "unsafe"]
    ):
        return True
    return False


def call_api(
    *,
    api_url: str,
    api_key: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    max_retries: int,
    rate_limiter: RateLimiter,
) -> tuple[str, dict[str, Any] | None, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "n": 1,
    }
    tokens = estimate_tokens(prompt, max_tokens)
    last_error = ""
    for attempt in range(max_retries):
        rate_limiter.wait(tokens)
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
            text = response.text
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                try:
                    return "ok", parse_json_content(content), ""
                except Exception as exc:
                    if is_safety_refusal(None, content):
                        return "safety_refusal", None, content[:1000]
                    last_error = f"json_parse_error: {exc}; content={content[:800]}"
            else:
                if is_safety_refusal(response.status_code, text):
                    return "safety_refusal", None, text[:1000]
                last_error = f"http_{response.status_code}: {text[:800]}"
                if response.status_code in {429, 500, 502, 503, 504}:
                    time.sleep(min(60, 2**attempt))
                    continue
            time.sleep(min(10, 1 + attempt))
        except requests.RequestException as exc:
            last_error = f"request_error: {exc}"
            time.sleep(min(60, 2**attempt))
    return "failed", None, last_error


def validate_record(obj: dict[str, Any], expected_doc_id: str) -> dict[str, Any]:
    obj["document_id"] = str(obj.get("document_id") or expected_doc_id)
    if obj["document_id"] != expected_doc_id:
        obj["_model_document_id"] = obj["document_id"]
        obj["document_id"] = expected_doc_id
    obj["_kimi_meta"] = {
        "model": MODEL_NAME,
        "temperature": 0,
        "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return obj


def get_path_value(obj: dict[str, Any], path: str) -> Any:
    if path == "case_amount":
        return obj.get("case_amount")
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if isinstance(cur, dict) and "value" in cur:
        return cur.get("value")
    return cur


def cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def flatten_record(obj: dict[str, Any]) -> dict[str, str]:
    row = {col: "" for col in CSV_COLUMNS}
    row["doc_id"] = str(obj.get("document_id") or "")
    row["kimi_status"] = "ok"
    row["kimi_model"] = MODEL_NAME
    row["kimi_temperature"] = "0"
    for field in CONTENT_FIELDS:
        row[field.replace(".", "__")] = cell(get_path_value(obj, field))
    return row


def write_gold_csv(jsonl_path: Path, csv_path: Path) -> int:
    rows = load_jsonl(jsonl_path)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for obj in rows:
            writer.writerow(flatten_record(obj))
    return len(rows)


def normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    s = str(value).strip()
    if not s or s.lower() in {"null", "none", "nan", "[]", "{}"}:
        return None
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", "", s)
    s = s.strip(" \t\r\n\"'`")
    return s or None


def normalize_number(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    s = unicodedata.normalize("NFKC", str(value)).strip()
    if not s or s.lower() in {"null", "none", "nan"}:
        return None
    multiplier = Decimal("1")
    if "亿" in s:
        multiplier = Decimal("100000000")
    elif "万" in s:
        multiplier = Decimal("10000")
    s = s.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", s)
    if not match:
        return None
    try:
        number = Decimal(match.group(0)) * multiplier
    except InvalidOperation:
        return None
    number = number.quantize(Decimal("0.000001")).normalize()
    if number == number.to_integral():
        return str(number.to_integral())
    return format(number, "f").rstrip("0").rstrip(".")


def normalize_bool(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    s = normalize_string(value)
    if s is None:
        return None
    lowered = s.lower()
    if lowered in {"true", "1", "yes", "y", "是", "有", "涉及"}:
        return "true"
    if lowered in {"false", "0", "no", "n", "否", "无", "不涉及"}:
        return "false"
    return lowered


def normalize_date(value: Any) -> str | None:
    s = normalize_string(value)
    if s is None:
        return None
    m = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s


def normalize_value(field: str, value: Any) -> str | None:
    if field in NUMERIC_FIELDS:
        return normalize_number(value)
    if field in BOOLEAN_FIELDS:
        return normalize_bool(value)
    if field in DATE_FIELDS:
        return normalize_date(value)
    return normalize_string(value)


def value_items(field: str, value: Any) -> set[str]:
    if field in LIST_FIELDS:
        if value is None:
            return set()
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                try:
                    value = json.loads(stripped)
                except Exception:
                    value = [value]
            else:
                value = [value]
        if not isinstance(value, list):
            value = [value]
        out = set()
        for item in value:
            norm = normalize_value(field, item)
            if norm is not None:
                out.add(norm)
        return out
    norm = normalize_value(field, value)
    return {norm} if norm is not None else set()


def score_items(pred_items: set[str], gold_items: set[str]) -> tuple[int, int, int, bool]:
    tp = len(pred_items & gold_items)
    fp = len(pred_items - gold_items)
    fn = len(gold_items - pred_items)
    return tp, fp, fn, pred_items == gold_items


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = safe_div(tp, tp + fp)
    recall = safe_div(tp, tp + fn)
    f1 = safe_div(2 * precision * recall, precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}


def ensure_sample_plan(
    *,
    target_docs: list[str],
    sample_fraction: float,
    seed: int,
    target_count: int | None,
) -> dict[str, Any]:
    if SAMPLE_PLAN_PATH.exists():
        return read_json(SAMPLE_PLAN_PATH)
    rnd = random.Random(seed)
    shuffled = list(target_docs)
    rnd.shuffle(shuffled)
    count = target_count if target_count is not None else math.ceil(len(shuffled) * sample_fraction)
    plan = {
        "round": ROUND,
        "seed": seed,
        "sample_fraction": sample_fraction,
        "target_docs_total": len(shuffled),
        "target_success_count": count,
        "candidate_order": shuffled,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    write_json(SAMPLE_PLAN_PATH, plan)
    return plan


def extract_gold(args: argparse.Namespace) -> dict[str, Any]:
    OUTDIR.mkdir(parents=True, exist_ok=True)

    master_rows = load_master(Path(args.master_path))
    texts = read_json(Path(args.texts_path))
    dsv4_rows = load_jsonl(Path(args.dsv4_jsonl_path))
    prompt_template = read_text(Path(args.prompt_path)).strip()
    api_url = extract_literal_assignment(Path(args.legacy_api_path), "API_URL")
    api_key = extract_literal_assignment(Path(args.legacy_api_path), "API_KEY")

    rows_by_doc = {r["doc_id"]: r for r in master_rows if r.get("doc_id")}
    dsv4_by_doc = {str(r.get("document_id")): r for r in dsv4_rows if r.get("document_id")}
    target_docs = sorted(set(rows_by_doc) & set(texts) & set(dsv4_by_doc))
    plan = ensure_sample_plan(
        target_docs=target_docs,
        sample_fraction=args.sample_fraction,
        seed=args.seed,
        target_count=args.target_count if args.target_count > 0 else None,
    )
    target_success_count = int(plan["target_success_count"])
    candidate_order = [doc_id for doc_id in plan["candidate_order"] if doc_id in target_docs]

    existing_gold = load_jsonl(Path(args.gold_jsonl_path))
    existing_ok = {str(r.get("document_id")) for r in existing_gold if r.get("document_id")}
    failure_rows = load_jsonl(Path(args.fail_path))
    failed_docs = {
        str(r.get("document_id"))
        for r in failure_rows
        if r.get("document_id") and not args.retry_failures
    }

    limiter = RateLimiter(rpm=args.rpm, tpm=args.tpm)
    write_lock = threading.Lock()
    fail_lock = threading.Lock()
    submitted = 0
    ok_this_run = 0
    safety_this_run = 0
    failed_this_run = 0
    consecutive_failures = 0

    def work(doc_id: str) -> tuple[str, str]:
        row = rows_by_doc[doc_id]
        prompt = render_prompt(prompt_template, row, texts[doc_id] or "")
        status, obj, error = call_api(
            api_url=api_url,
            api_key=api_key,
            prompt=prompt,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            max_retries=args.max_retries,
            rate_limiter=limiter,
        )
        if status == "ok" and obj is not None:
            append_jsonl(Path(args.gold_jsonl_path), validate_record(obj, doc_id), write_lock)
            return "ok", doc_id
        append_jsonl(
            Path(args.fail_path),
            {
                "document_id": doc_id,
                "status": status,
                "error_excerpt": error[:1000],
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            fail_lock,
        )
        return status, doc_id

    success_count = len(existing_ok)
    candidates = [doc_id for doc_id in candidate_order if doc_id not in existing_ok and doc_id not in failed_docs]
    idx = 0
    pending: dict[futures.Future[tuple[str, str]], str] = {}
    pbar = tqdm(total=target_success_count, initial=min(success_count, target_success_count), desc="Kimi K2.6 gold")
    with futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        while success_count < target_success_count:
            slots = min(args.workers, target_success_count - success_count) - len(pending)
            while slots > 0 and idx < len(candidates):
                doc_id = candidates[idx]
                idx += 1
                submitted += 1
                pending[executor.submit(work, doc_id)] = doc_id
                slots -= 1
            if not pending:
                break
            done, _ = futures.wait(pending, return_when=futures.FIRST_COMPLETED)
            for fut in done:
                pending.pop(fut, None)
                try:
                    status, _doc_id = fut.result()
                except Exception as exc:
                    status = "worker_exception"
                    append_jsonl(
                        Path(args.fail_path),
                        {
                            "document_id": "",
                            "status": status,
                            "error_excerpt": str(exc)[:1000],
                            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        },
                        fail_lock,
                    )
                if status == "ok":
                    success_count += 1
                    ok_this_run += 1
                    consecutive_failures = 0
                    pbar.update(1)
                elif status == "safety_refusal":
                    safety_this_run += 1
                    consecutive_failures += 1
                else:
                    failed_this_run += 1
                    consecutive_failures += 1
                if (
                    success_count == 0
                    and consecutive_failures >= args.abort_after_consecutive_failures
                ):
                    raise RuntimeError(
                        f"Aborting after {consecutive_failures} consecutive non-ok API outputs. "
                        f"Check model name/API availability. Last status={status}"
                    )
    pbar.close()

    gold_rows = load_jsonl(Path(args.gold_jsonl_path))
    # Keep exactly the requested number, preserving first successful random-order sample.
    by_doc = {str(r.get("document_id")): r for r in gold_rows if r.get("document_id")}
    selected_ids = [doc_id for doc_id in candidate_order if doc_id in by_doc][:target_success_count]
    selected_rows = [by_doc[doc_id] for doc_id in selected_ids]
    with Path(args.gold_jsonl_path).open("w", encoding="utf-8") as f:
        for row in selected_rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    csv_rows = write_gold_csv(Path(args.gold_jsonl_path), Path(args.gold_csv_path))

    audit = {
        "round": ROUND,
        "model": MODEL_NAME,
        "temperature": 0,
        "rpm": args.rpm,
        "tpm": args.tpm,
        "workers": args.workers,
        "max_tokens": args.max_tokens,
        "sample_fraction": args.sample_fraction,
        "seed": args.seed,
        "target_docs_total": len(target_docs),
        "target_success_count": target_success_count,
        "existing_gold_before_run": len(existing_ok),
        "submitted_this_run": submitted,
        "ok_this_run": ok_this_run,
        "safety_refusals_this_run": safety_this_run,
        "failed_this_run": failed_this_run,
        "gold_jsonl_rows": len(selected_rows),
        "gold_csv_rows": csv_rows,
        "output_gold_jsonl": str(Path(args.gold_jsonl_path).resolve()),
        "output_gold_csv": str(Path(args.gold_csv_path).resolve()),
        "fail_path": str(Path(args.fail_path).resolve()),
    }
    write_json(Path(args.audit_path), audit)
    return audit


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    dsv4_rows = load_jsonl(Path(args.dsv4_jsonl_path))
    gold_rows = load_jsonl(Path(args.gold_jsonl_path))
    dsv4_by_doc = {str(r.get("document_id")): r for r in dsv4_rows if r.get("document_id")}

    field_counts: dict[str, Counter[str]] = {field: Counter() for field in CONTENT_FIELDS}
    field_doc_counts: dict[str, Counter[str]] = {field: Counter() for field in CONTENT_FIELDS}
    pair_rows = []

    for gold in gold_rows:
        doc_id = str(gold.get("document_id") or "")
        pred = dsv4_by_doc.get(doc_id, {})
        pair: dict[str, Any] = {"document_id": doc_id, "fields": {}}
        for field in CONTENT_FIELDS:
            pred_raw = get_path_value(pred, field)
            gold_raw = get_path_value(gold, field)
            pred_items = value_items(field, pred_raw)
            gold_items = value_items(field, gold_raw)
            tp, fp, fn, exact = score_items(pred_items, gold_items)
            field_counts[field]["tp"] += tp
            field_counts[field]["fp"] += fp
            field_counts[field]["fn"] += fn
            field_doc_counts[field]["docs"] += 1
            field_doc_counts[field]["exact"] += int(exact)
            field_doc_counts[field]["gold_nonempty"] += int(bool(gold_items))
            field_doc_counts[field]["pred_nonempty"] += int(bool(pred_items))
            pair["fields"][field] = {
                "pred_raw": pred_raw,
                "gold_raw": gold_raw,
                "pred_norm": sorted(pred_items),
                "gold_norm": sorted(gold_items),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "exact": exact,
            }
        pair_rows.append(pair)

    with Path(args.pair_path).open("w", encoding="utf-8") as f:
        for row in pair_rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    metric_rows = []
    total_tp = total_fp = total_fn = 0
    exact_all = docs_all = 0
    for field in CONTENT_FIELDS:
        counts = field_counts[field]
        docs = field_doc_counts[field]["docs"]
        exact_docs = field_doc_counts[field]["exact"]
        metrics = prf(counts["tp"], counts["fp"], counts["fn"])
        row = {
            "field": field,
            "kind": "list" if field in LIST_FIELDS else "scalar",
            "tp": counts["tp"],
            "fp": counts["fp"],
            "fn": counts["fn"],
            "gold_positive": counts["tp"] + counts["fn"],
            "pred_positive": counts["tp"] + counts["fp"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "documents": docs,
            "exact_documents": exact_docs,
            "exact_match_rate": safe_div(exact_docs, docs),
            "gold_nonempty_docs": field_doc_counts[field]["gold_nonempty"],
            "pred_nonempty_docs": field_doc_counts[field]["pred_nonempty"],
        }
        metric_rows.append(row)
        total_tp += counts["tp"]
        total_fp += counts["fp"]
        total_fn += counts["fn"]
        exact_all += exact_docs
        docs_all += docs

    with Path(args.field_metrics_csv).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(metric_rows[0].keys()))
        writer.writeheader()
        writer.writerows(metric_rows)

    micro = prf(total_tp, total_fp, total_fn)
    active_rows = [r for r in metric_rows if r["gold_positive"] or r["pred_positive"]]
    summary = {
        "round": ROUND,
        "gold_model": MODEL_NAME,
        "evaluated_model": DS_MODEL_NAME,
        "temperature": 0,
        "sample_size": len(gold_rows),
        "field_count": len(CONTENT_FIELDS),
        "micro": {
            "tp": total_tp,
            "fp": total_fp,
            "fn": total_fn,
            **micro,
        },
        "macro_f1_all_fields": safe_div(sum(float(r["f1"]) for r in metric_rows), len(metric_rows)),
        "macro_f1_active_fields": safe_div(sum(float(r["f1"]) for r in active_rows), len(active_rows)),
        "macro_precision_all_fields": safe_div(sum(float(r["precision"]) for r in metric_rows), len(metric_rows)),
        "macro_recall_all_fields": safe_div(sum(float(r["recall"]) for r in metric_rows), len(metric_rows)),
        "overall_field_exact_match_rate": safe_div(exact_all, docs_all),
        "outputs": {
            "gold_jsonl": str(Path(args.gold_jsonl_path).resolve()),
            "gold_csv": str(Path(args.gold_csv_path).resolve()),
            "field_metrics_csv": str(Path(args.field_metrics_csv).resolve()),
            "pairs_jsonl": str(Path(args.pair_path).resolve()),
            "report": str(Path(args.report_path).resolve()),
        },
    }
    write_json(Path(args.summary_json), summary)
    write_report(summary, metric_rows, Path(args.report_path))
    return summary


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def write_report(summary: dict[str, Any], metric_rows: list[dict[str, Any]], path: Path) -> None:
    sorted_by_f1 = sorted(metric_rows, key=lambda x: (float(x["f1"]), x["field"]))
    best = sorted(metric_rows, key=lambda x: (-float(x["f1"]), x["field"]))[:8]
    worst = sorted_by_f1[:8]
    micro = summary["micro"]

    lines = [
        f"# {ROUND} DeepSeek-V4 vs Kimi-K2.6 1% 抽样评估报告",
        "",
        "## 1. 任务说明",
        "",
        f"本轮使用 SiliconFlow 模型 `{MODEL_NAME}` 在温度为 0 的条件下，对主数据集中随机 1% 的判决书重新抽取结构化字段，并把该结果作为代理正确答案。",
        f"被评估对象是已经生成的 `{DS_MODEL_NAME}` 全量抽取结果 `master_dataset_dsv4.jsonl`。",
        "",
        "注意：这里的“正确答案”是 Kimi-K2.6 生成的代理金标准，不等同于人工标注真值。因此 F1 衡量的是 DeepSeek-V4 与 Kimi-K2.6 在同一提示词和同一文本上的一致性。",
        "",
        "## 2. 抽样与运行设置",
        "",
        f"- 抽样数量：{summary['sample_size']} 条。",
        f"- 字段数量：{summary['field_count']} 个。",
        f"- Kimi 模型：`{summary['gold_model']}`。",
        f"- DeepSeek 模型：`{summary['evaluated_model']}`。",
        "- 温度：0。",
        "- RPM：500。",
        "- TPM：2,000,000。",
        "- 抽样方式：固定随机种子生成候选顺序，抽到目标数量的正常 JSON 输出后停止；脚本支持断点续跑、并发、重试和进度条。",
        "",
        "## 3. 指标定义",
        "",
        "对每个字段，把 DeepSeek-V4 的抽取值与 Kimi-K2.6 的抽取值比较。",
        "",
        "- 标量字段：两边都为空不计入 TP/FP/FN；两边相同计 TP；DeepSeek 多抽计 FP；DeepSeek 漏抽计 FN；两边非空但不同，同时计 FP 和 FN。",
        "- 列表字段：把列表元素当作集合比较，交集为 TP，DeepSeek 独有为 FP，Kimi 独有为 FN。",
        "- 金额字段：会把逗号、小数形式和“万/亿”等常见单位归一化后比较，避免 `1000` 与 `1,000.00` 这类格式差异造成误判。",
        "- 日期、布尔值和空值也做了基础归一化。",
        "",
        "## 4. 总体结果",
        "",
        f"- Micro Precision：{pct(micro['precision'])}",
        f"- Micro Recall：{pct(micro['recall'])}",
        f"- Micro F1：{pct(micro['f1'])}",
        f"- TP：{micro['tp']}",
        f"- FP：{micro['fp']}",
        f"- FN：{micro['fn']}",
        f"- Macro F1（全部字段）：{pct(summary['macro_f1_all_fields'])}",
        f"- Macro F1（有正例字段）：{pct(summary['macro_f1_active_fields'])}",
        f"- 字段级完全一致率：{pct(summary['overall_field_exact_match_rate'])}",
        "",
        "## 5. 表现较好的字段",
        "",
        "| 字段 | Precision | Recall | F1 | TP | FP | FN | Exact Match |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in best:
        lines.append(
            f"| `{row['field']}` | {pct(row['precision'])} | {pct(row['recall'])} | {pct(row['f1'])} | "
            f"{row['tp']} | {row['fp']} | {row['fn']} | {pct(row['exact_match_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## 6. 表现较弱的字段",
            "",
            "| 字段 | Precision | Recall | F1 | TP | FP | FN | Exact Match |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in worst:
        lines.append(
            f"| `{row['field']}` | {pct(row['precision'])} | {pct(row['recall'])} | {pct(row['f1'])} | "
            f"{row['tp']} | {row['fp']} | {row['fn']} | {pct(row['exact_match_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## 7. 全字段明细",
            "",
            "| 字段 | 类型 | Gold正例 | Pred正例 | Precision | Recall | F1 | TP | FP | FN | Exact Match |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in metric_rows:
        lines.append(
            f"| `{row['field']}` | {row['kind']} | {row['gold_positive']} | {row['pred_positive']} | "
            f"{pct(row['precision'])} | {pct(row['recall'])} | {pct(row['f1'])} | "
            f"{row['tp']} | {row['fp']} | {row['fn']} | {pct(row['exact_match_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## 8. 输出文件",
            "",
            f"- Kimi 代理金标准 JSONL：`{summary['outputs']['gold_jsonl']}`",
            f"- Kimi 代理金标准 CSV：`{summary['outputs']['gold_csv']}`",
            f"- 字段级指标 CSV：`{summary['outputs']['field_metrics_csv']}`",
            f"- 逐案逐字段对照 JSONL：`{summary['outputs']['pairs_jsonl']}`",
            f"- 汇总 JSON：`{Path(SUMMARY_JSON).resolve()}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-path", default=str(MASTER_PATH))
    parser.add_argument("--texts-path", default=str(TEXTS_PATH))
    parser.add_argument("--prompt-path", default=str(PROMPT_PATH))
    parser.add_argument("--legacy-api-path", default=str(LEGACY_API_PATH))
    parser.add_argument("--dsv4-jsonl-path", default=str(DSV4_JSONL_PATH))
    parser.add_argument("--gold-jsonl-path", default=str(GOLD_JSONL_PATH))
    parser.add_argument("--gold-csv-path", default=str(GOLD_CSV_PATH))
    parser.add_argument("--fail-path", default=str(FAIL_PATH))
    parser.add_argument("--sample-plan-path", default=str(SAMPLE_PLAN_PATH))
    parser.add_argument("--pair-path", default=str(PAIR_PATH))
    parser.add_argument("--field-metrics-csv", default=str(FIELD_METRICS_CSV))
    parser.add_argument("--summary-json", default=str(SUMMARY_JSON))
    parser.add_argument("--report-path", default=str(REPORT_PATH))
    parser.add_argument("--audit-path", default=str(AUDIT_PATH))
    parser.add_argument("--rpm", type=int, default=500)
    parser.add_argument("--tpm", type=int, default=2_000_000)
    parser.add_argument("--workers", type=int, default=96)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-retries", type=int, default=6)
    parser.add_argument("--sample-fraction", type=float, default=0.01)
    parser.add_argument("--target-count", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260517)
    parser.add_argument("--retry-failures", action="store_true")
    parser.add_argument("--abort-after-consecutive-failures", type=int, default=200)
    parser.add_argument("--evaluate-only", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.evaluate_only:
        audit = extract_gold(args)
        print(json.dumps(audit, ensure_ascii=False, indent=2))
    summary = evaluate(args)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
