from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import json
import random
import re
import shutil
import threading
import time
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from openai import OpenAI
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
ROUND = "round-18-20260519-dsflash-vs-dspro-f1"

MASTER_PATH = ROOT / "data" / "processed" / "master" / "master_dataset.csv"
TEXTS_PATH = ROOT / "data" / "raw" / "data-texts.json"
PROMPT_PATH = ROOT / "docs" / "legacy" / "master_prompt-260518.md"
ENV_PATH = PROJECT_ROOT / ".env"

PREVIOUS_SAMPLE_PATH = ROOT / "result" / "round-11-20260518-221344" / "sample_10.json"
PREVIOUS_DS_JSONL = ROOT / "data" / "processed" / "master" / "master_dataset_ds_official.jsonl"
PREVIOUS_GPT_JSONL = ROOT / "data" / "processed" / "master" / "master_dataset_gpt_concurrent.jsonl"

OUTDIR = ROOT / "result" / ROUND
SAMPLE_PATH = OUTDIR / "sample_10.json"
DS_JSONL = OUTDIR / "deepseek_v4_flash_outputs.jsonl"
GPT_JSONL = OUTDIR / "deepseek_v4_pro_gold_outputs.jsonl"
FAIL_PATH = OUTDIR / "failures.jsonl"
FIELD_METRICS_CSV = OUTDIR / "field_f1.csv"
GROUP_METRICS_CSV = OUTDIR / "group_f1.csv"
PAIR_PATH = OUTDIR / "case_field_pairs.jsonl"
SUMMARY_JSON = OUTDIR / "summary.json"
REPORT_PATH = OUTDIR / "REPORT.md"

DS_MODEL = "deepseek-v4-flash"
GPT_MODEL = "deepseek-v4-pro"

PRIMARY_FIELDS = [
    "case_amount",
    "judicial_analysis.contract_validity",
    "virtual_currency_info.activity_types",
]

SECONDARY_FIELDS = [
    "case_amount_type",
    "metadata.court_level",
    "metadata.judgment_date",
    "metadata.region",
    "case_profile.case_type_primary",
    "case_profile.case_type_secondary",
    "case_profile.procedure_stage",
    "case_profile.is_appeal",
    "virtual_currency_info.currency_types",
    "judicial_analysis.legal_characterization",
    "judicial_analysis.virtual_currency_property_status",
    "judicial_analysis.transaction_legality_assessment",
    "judicial_analysis.reasons_for_invalidity_or_no_protection",
    "judicial_analysis.cited_policies",
    "judicial_analysis.policy_labels",
    "judicial_analysis.judicial_framing",
]

EVAL_FIELDS = PRIMARY_FIELDS + SECONDARY_FIELDS

LIST_FIELDS = {
    "virtual_currency_info.activity_types",
    "virtual_currency_info.currency_types",
    "judicial_analysis.reasons_for_invalidity_or_no_protection",
    "judicial_analysis.cited_policies",
    "judicial_analysis.policy_labels",
    "judicial_analysis.judicial_framing",
}

NUMERIC_FIELDS = {"case_amount"}
BOOLEAN_FIELDS = {"case_profile.is_appeal"}
DATE_FIELDS = {"metadata.judgment_date"}


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


def append_jsonl(path: Path, obj: dict[str, Any], lock: threading.Lock | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    if lock is None:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return
    with lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def get_api_key(path: Path, provider: Literal["ds", "gpt"]) -> str:
    env = load_env(path)
    if provider == "ds":
        key = env.get("DEEPSEEK_API_KEY") or env.get("deepseek_api_key")
        if not key:
            raise RuntimeError(f"Cannot find DEEPSEEK_API_KEY/deepseek_api_key in {path}")
        return key
    key = env.get("OPENAI_API_KEY") or env.get("openai_api_key")
    if not key:
        raise RuntimeError(f"Cannot find OPENAI_API_KEY/openai_api_key in {path}")
    return key


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
    out = template.replace("{{ document_id }}", row["doc_id"])
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


def classify_error(error: str) -> str:
    lowered = error.lower()
    if any(x in lowered for x in ["401", "authentication", "api key", "unauthorized", "missing scopes"]):
        return "auth_error"
    if any(x in lowered for x in ["refusal", "content filter", "moderation", "blocked", "unsafe"]):
        return "safety_refusal"
    if "json" in lowered and "parse" in lowered:
        return "json_parse_error"
    return "failed"


def call_ds(
    *,
    client: OpenAI,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    max_retries: int,
    rate_limiter: RateLimiter,
) -> tuple[str, dict[str, Any] | None, str]:
    tokens = estimate_tokens(prompt, max_tokens)
    last_error = ""
    for attempt in range(max_retries):
        rate_limiter.wait(tokens)
        try:
            response = client.with_options(timeout=timeout).chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a legal document structured extraction assistant. Output strict JSON only.",
                    },
                    {"role": "user", "content": prompt + "\n\nOutput JSON."},
                ],
                stream=False,
                temperature=0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = response.choices[0].message.content or ""
            return "ok", parse_json_content(content), ""
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if classify_error(last_error) == "auth_error":
                return "auth_error", None, last_error
            if attempt < max_retries - 1:
                time.sleep(min(60, 2**attempt))
    return classify_error(last_error), None, last_error


def call_ds_gold(
    *,
    client: OpenAI,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    max_retries: int,
    rate_limiter: RateLimiter,
) -> tuple[str, dict[str, Any] | None, str]:
    tokens = estimate_tokens(prompt, max_tokens)
    last_error = ""
    for attempt in range(max_retries):
        rate_limiter.wait(tokens)
        try:
            response = client.with_options(timeout=timeout).chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a legal document structured extraction assistant. Output strict JSON only.",
                    },
                    {"role": "user", "content": prompt + "\n\nOutput JSON."},
                ],
                stream=False,
                temperature=0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
            )
            content = response.choices[0].message.content or ""
            return "ok", parse_json_content(content), ""
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if classify_error(last_error) == "auth_error":
                return "auth_error", None, last_error
            if attempt < max_retries - 1:
                time.sleep(min(60, 2**attempt))
    return classify_error(last_error), None, last_error


def validate_record(obj: dict[str, Any], expected_doc_id: str, provider: str, model: str, prompt_path: Path) -> dict[str, Any]:
    obj["document_id"] = str(obj.get("document_id") or expected_doc_id)
    if obj["document_id"] != expected_doc_id:
        obj[f"_{provider}_model_document_id"] = obj["document_id"]
        obj["document_id"] = expected_doc_id
    obj[f"_{provider}_meta"] = {
        "provider": provider,
        "model": model,
        "temperature": 0,
        "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "prompt_path": str(prompt_path),
    }
    return obj


def previous_doc_ids(*paths: Path) -> set[str]:
    out: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        if path.suffix.lower() == ".json":
            obj = read_json(path)
            out.update(str(x) for x in obj.get("doc_ids", []) or obj.get("sample_doc_ids", []))
        elif path.suffix.lower() == ".jsonl":
            out.update(str(x.get("document_id")) for x in load_jsonl(path) if x.get("document_id"))
    return out


def select_sample(args: argparse.Namespace, master_rows: list[dict[str, str]], texts: dict[str, str]) -> list[dict[str, str]]:
    sample_path = Path(args.sample_path)
    by_doc = {r["doc_id"]: r for r in master_rows if r.get("doc_id")}
    if sample_path.exists() and not args.resample:
        ids = read_json(sample_path)["doc_ids"]
        return [by_doc[x] for x in ids if x in by_doc]

    excluded = previous_doc_ids(PREVIOUS_SAMPLE_PATH, PREVIOUS_DS_JSONL, PREVIOUS_GPT_JSONL)
    candidates = [r for r in master_rows if r.get("doc_id") in texts and r.get("doc_id") not in excluded]
    rng = random.Random(args.seed)
    sample = rng.sample(candidates, args.n)
    write_json(
        sample_path,
        {
            "round": ROUND,
            "seed": args.seed,
            "n": args.n,
            "excluded_previous_doc_count": len(excluded),
            "doc_ids": [r["doc_id"] for r in sample],
        },
    )
    return sample


def run_provider(
    provider: Literal["ds", "gold"],
    *,
    sample_rows: list[dict[str, str]],
    texts: dict[str, str],
    prompt_template: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    if provider == "ds":
        output_path = Path(args.ds_jsonl)
        model = args.ds_model
        client = OpenAI(api_key=get_api_key(Path(args.env_path), "ds"), base_url="https://api.deepseek.com", max_retries=0)
        call_fn = call_ds
        limiter = RateLimiter(args.ds_rpm, args.ds_tpm)
    else:
        output_path = Path(args.gpt_jsonl)
        model = args.gpt_model
        client = OpenAI(api_key=get_api_key(Path(args.env_path), "ds"), base_url="https://api.deepseek.com", max_retries=0)
        call_fn = call_ds_gold
        limiter = RateLimiter(args.gpt_rpm, args.gpt_tpm)

    existing = {str(x.get("document_id")): x for x in load_jsonl(output_path) if x.get("document_id")}
    work_rows = [row for row in sample_rows if row["doc_id"] not in existing]
    write_lock = threading.Lock()
    fail_lock = threading.Lock()
    counters = {
        "submitted": 0,
        "ok": 0,
        "auth_error": 0,
        "safety_refusal": 0,
        "json_parse_error": 0,
        "failed": 0,
    }

    def work(row: dict[str, str]) -> tuple[str, str]:
        doc_id = row["doc_id"]
        prompt = render_prompt(prompt_template, row, texts[doc_id] or "")
        status, obj, error = call_fn(
            client=client,
            model=model,
            prompt=prompt,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            max_retries=args.max_retries,
            rate_limiter=limiter,
        )
        if status == "ok" and obj is not None:
            append_jsonl(output_path, validate_record(obj, doc_id, provider, model, Path(args.prompt_path)), write_lock)
        else:
            append_jsonl(
                Path(args.fail_path),
                {
                    "document_id": doc_id,
                    "provider": provider,
                    "model": model,
                    "status": status,
                    "error_excerpt": error[:1200],
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
                fail_lock,
            )
        return status, doc_id

    stop_for_auth = False
    pending: dict[futures.Future[tuple[str, str]], str] = {}
    idx = 0
    with futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        with tqdm(total=len(work_rows), desc=f"{provider.upper()} sample extraction") as pbar:
            while (idx < len(work_rows) and not stop_for_auth) or pending:
                while len(pending) < args.workers and idx < len(work_rows) and not stop_for_auth:
                    row = work_rows[idx]
                    idx += 1
                    counters["submitted"] += 1
                    pending[executor.submit(work, row)] = row["doc_id"]
                if not pending:
                    break
                done, _ = futures.wait(pending, return_when=futures.FIRST_COMPLETED)
                for fut in done:
                    pending.pop(fut, None)
                    try:
                        status, _doc_id = fut.result()
                    except Exception as exc:
                        status = "failed"
                        append_jsonl(
                            Path(args.fail_path),
                            {
                                "document_id": "",
                                "provider": provider,
                                "model": model,
                                "status": "worker_exception",
                                "error_excerpt": str(exc)[:1200],
                                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                            },
                            fail_lock,
                        )
                    if status == "ok":
                        counters["ok"] += 1
                    elif status == "auth_error":
                        counters["auth_error"] += 1
                        stop_for_auth = True
                    elif status == "safety_refusal":
                        counters["safety_refusal"] += 1
                    elif status == "json_parse_error":
                        counters["json_parse_error"] += 1
                    else:
                        counters["failed"] += 1
                    pbar.update(1)

    final = {str(x.get("document_id")): x for x in load_jsonl(output_path) if x.get("document_id")}
    return {
        "provider": provider,
        "model": model,
        "existing_before": len(existing),
        "needed_this_run": len(work_rows),
        "available_after": len(final),
        **counters,
    }


def get_path_value(obj: dict[str, Any], path: str) -> Any:
    if path in {"case_amount", "case_amount_type"}:
        return obj.get(path)
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if isinstance(cur, dict) and "value" in cur:
        return cur.get("value")
    return cur


def normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    s = str(value).strip()
    if s == "" or s.lower() in {"null", "none", "nan"}:
        return None
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", "", s)
    s = s.strip(" \t\r\n\"'`")
    return s or None


def normalize_number(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    s = unicodedata.normalize("NFKC", str(value)).strip()
    if not s or s.lower() in {"null", "none", "nan"}:
        return None
    multiplier = Decimal("1")
    if "亿" in s:
        multiplier = Decimal("100000000")
    elif "万" in s:
        multiplier = Decimal("10000")
    s = s.replace(",", "").replace("，", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        number = Decimal(m.group(0)) * multiplier
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
                    parsed = json.loads(stripped)
                    value = parsed
                except json.JSONDecodeError:
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


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def compute_metrics(
    *,
    ds_rows: list[dict[str, Any]],
    gpt_rows: list[dict[str, Any]],
    sample_ids: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    ds_by_doc = {str(x.get("document_id")): x for x in ds_rows}
    gpt_by_doc = {str(x.get("document_id")): x for x in gpt_rows}
    docs = [doc_id for doc_id in sample_ids if doc_id in ds_by_doc and doc_id in gpt_by_doc]

    field_counts = {field: {"tp": 0, "fp": 0, "fn": 0, "docs": 0, "exact_docs": 0} for field in EVAL_FIELDS}
    pair_rows: list[dict[str, Any]] = []
    for doc_id in docs:
        for field in EVAL_FIELDS:
            pred_raw = get_path_value(ds_by_doc[doc_id], field)
            gold_raw = get_path_value(gpt_by_doc[doc_id], field)
            pred_items = value_items(field, pred_raw)
            gold_items = value_items(field, gold_raw)
            tp = len(pred_items & gold_items)
            fp = len(pred_items - gold_items)
            fn = len(gold_items - pred_items)
            exact = pred_items == gold_items
            counts = field_counts[field]
            counts["tp"] += tp
            counts["fp"] += fp
            counts["fn"] += fn
            counts["docs"] += 1
            counts["exact_docs"] += int(exact)
            pair_rows.append(
                {
                    "document_id": doc_id,
                    "field": field,
                    "group": "primary" if field in PRIMARY_FIELDS else "secondary",
                    "tp": tp,
                    "fp": fp,
                    "fn": fn,
                    "exact": int(exact),
                    "ds_items": sorted(pred_items),
                    "gpt_gold_items": sorted(gold_items),
                }
            )

    field_rows: list[dict[str, Any]] = []
    for field in EVAL_FIELDS:
        counts = field_counts[field]
        metrics = prf(counts["tp"], counts["fp"], counts["fn"])
        docs_n = counts["docs"]
        row = {
            "field": field,
            "group": "primary" if field in PRIMARY_FIELDS else "secondary",
            "kind": "list" if field in LIST_FIELDS else "scalar",
            "tp": counts["tp"],
            "fp": counts["fp"],
            "fn": counts["fn"],
            "gold_positive": counts["tp"] + counts["fn"],
            "pred_positive": counts["tp"] + counts["fp"],
            **metrics,
            "documents": docs_n,
            "exact_documents": counts["exact_docs"],
            "exact_match_rate": counts["exact_docs"] / docs_n if docs_n else 0.0,
        }
        field_rows.append(row)

    group_rows: list[dict[str, Any]] = []
    for name, fields in [("primary", PRIMARY_FIELDS), ("secondary", SECONDARY_FIELDS), ("primary_secondary", EVAL_FIELDS)]:
        rows = [row for row in field_rows if row["field"] in fields]
        tp = sum(int(row["tp"]) for row in rows)
        fp = sum(int(row["fp"]) for row in rows)
        fn = sum(int(row["fn"]) for row in rows)
        metrics = prf(tp, fp, fn)
        active = [row for row in rows if int(row["gold_positive"]) or int(row["pred_positive"])]
        group_rows.append(
            {
                "group": name,
                "field_count": len(rows),
                "active_field_count": len(active),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                **metrics,
                "macro_f1": sum(float(row["f1"]) for row in rows) / len(rows) if rows else 0.0,
                "macro_f1_active": sum(float(row["f1"]) for row in active) / len(active) if active else 0.0,
                "exact_match_rate": (
                    sum(int(row["exact_documents"]) for row in rows) / sum(int(row["documents"]) for row in rows)
                    if rows and sum(int(row["documents"]) for row in rows)
                    else 0.0
                ),
            }
        )

    all_tp = sum(int(row["tp"]) for row in field_rows)
    all_fp = sum(int(row["fp"]) for row in field_rows)
    all_fn = sum(int(row["fn"]) for row in field_rows)
    summary = {
        "doc_count": len(docs),
        "requested_doc_count": len(sample_ids),
        "missing_ds_doc_ids": [doc_id for doc_id in sample_ids if doc_id not in ds_by_doc],
        "missing_gpt_doc_ids": [doc_id for doc_id in sample_ids if doc_id not in gpt_by_doc],
        "field_count": len(EVAL_FIELDS),
        "primary_fields": PRIMARY_FIELDS,
        "secondary_fields": SECONDARY_FIELDS,
        "micro": {"tp": all_tp, "fp": all_fp, "fn": all_fn, **prf(all_tp, all_fp, all_fn)},
        "macro_f1": sum(float(row["f1"]) for row in field_rows) / len(field_rows) if field_rows else 0.0,
        "exact_match_rate": (
            sum(int(row["exact_documents"]) for row in field_rows) / sum(int(row["documents"]) for row in field_rows)
            if field_rows and sum(int(row["documents"]) for row in field_rows)
            else 0.0
        ),
    }
    return field_rows, group_rows, pair_rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and fieldnames is None:
        fieldnames = []
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    shutil.move(str(tmp_path), str(path))


def write_pair_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    shutil.move(str(tmp_path), str(path))


def pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return ""


def write_report(summary: dict[str, Any], field_rows: list[dict[str, Any]], group_rows: list[dict[str, Any]], path: Path) -> None:
    groups = {row["group"]: row for row in group_rows}
    lines = [
        "# Official DeepSeek Flash vs Pro F1 Sample",
        "",
        f"- Sample size: {summary['doc_count']} / {summary['requested_doc_count']}",
        f"- Evaluated model: {summary['evaluated_model']}",
        f"- Gold standard: {summary['gold_model']}",
        f"- Seed: {summary['seed']}",
        "",
        "## Group F1",
        "",
        "| Group | Fields | TP | FP | FN | Precision | Recall | Micro F1 | Macro F1 active | Exact match |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ["primary", "secondary", "primary_secondary"]:
        row = groups[key]
        lines.append(
            f"| {key} | {row['field_count']} | {row['tp']} | {row['fp']} | {row['fn']} | "
            f"{pct(row['precision'])} | {pct(row['recall'])} | {pct(row['f1'])} | "
            f"{pct(row['macro_f1_active'])} | {pct(row['exact_match_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Field F1",
            "",
            "| Group | Field | Kind | TP | FP | FN | Precision | Recall | F1 | Exact match |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in field_rows:
        lines.append(
            f"| {row['group']} | `{row['field']}` | {row['kind']} | {row['tp']} | {row['fp']} | {row['fn']} | "
            f"{pct(row['precision'])} | {pct(row['recall'])} | {pct(row['f1'])} | {pct(row['exact_match_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Summary JSON: `{summary['outputs']['summary_json']}`",
            f"- Field metrics CSV: `{summary['outputs']['field_metrics_csv']}`",
            f"- Group metrics CSV: `{summary['outputs']['group_metrics_csv']}`",
            f"- Pair JSONL: `{summary['outputs']['pair_jsonl']}`",
            f"- DS JSONL: `{summary['outputs']['ds_jsonl']}`",
            f"- GPT JSONL: `{summary['outputs']['gpt_jsonl']}`",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    master_rows = load_master(Path(args.master_path))
    texts = read_json(Path(args.texts_path))
    prompt_template = read_text(Path(args.prompt_path)).strip()
    sample_rows = select_sample(args, master_rows, texts)
    sample_ids = [row["doc_id"] for row in sample_rows]

    provider_audits = [
        run_provider("ds", sample_rows=sample_rows, texts=texts, prompt_template=prompt_template, args=args),
        run_provider("gold", sample_rows=sample_rows, texts=texts, prompt_template=prompt_template, args=args),
    ]

    ds_rows_all = load_jsonl(Path(args.ds_jsonl))
    gpt_rows_all = load_jsonl(Path(args.gpt_jsonl))
    ds_rows = [row for row in ds_rows_all if str(row.get("document_id")) in set(sample_ids)]
    gpt_rows = [row for row in gpt_rows_all if str(row.get("document_id")) in set(sample_ids)]
    field_rows, group_rows, pair_rows, metric_summary = compute_metrics(ds_rows=ds_rows, gpt_rows=gpt_rows, sample_ids=sample_ids)

    write_csv(Path(args.field_metrics_csv), field_rows)
    write_csv(Path(args.group_metrics_csv), group_rows)
    write_pair_jsonl(Path(args.pair_path), pair_rows)

    summary = {
        "round": ROUND,
        "seed": args.seed,
        "sample_doc_ids": sample_ids,
        "evaluated_model": args.ds_model,
        "gold_model": args.gpt_model,
        "temperature": 0,
        "workers": args.workers,
        "prompt_path": str(Path(args.prompt_path)),
        "provider_audits": provider_audits,
        **metric_summary,
        "group_metrics": group_rows,
        "outputs": {
            "sample": str(Path(args.sample_path)),
            "ds_jsonl": str(Path(args.ds_jsonl)),
            "gpt_jsonl": str(Path(args.gpt_jsonl)),
            "fail_path": str(Path(args.fail_path)),
            "field_metrics_csv": str(Path(args.field_metrics_csv)),
            "group_metrics_csv": str(Path(args.group_metrics_csv)),
            "pair_jsonl": str(Path(args.pair_path)),
            "summary_json": str(Path(args.summary_json)),
            "report": str(Path(args.report_path)),
        },
    }
    write_json(Path(args.summary_json), summary)
    write_report(summary, field_rows, group_rows, Path(args.report_path))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-path", default=str(MASTER_PATH))
    parser.add_argument("--texts-path", default=str(TEXTS_PATH))
    parser.add_argument("--prompt-path", default=str(PROMPT_PATH))
    parser.add_argument("--env-path", default=str(ENV_PATH))
    parser.add_argument("--sample-path", default=str(SAMPLE_PATH))
    parser.add_argument("--ds-jsonl", default=str(DS_JSONL))
    parser.add_argument("--gpt-jsonl", default=str(GPT_JSONL))
    parser.add_argument("--fail-path", default=str(FAIL_PATH))
    parser.add_argument("--field-metrics-csv", default=str(FIELD_METRICS_CSV))
    parser.add_argument("--group-metrics-csv", default=str(GROUP_METRICS_CSV))
    parser.add_argument("--pair-path", default=str(PAIR_PATH))
    parser.add_argument("--summary-json", default=str(SUMMARY_JSON))
    parser.add_argument("--report-path", default=str(REPORT_PATH))
    parser.add_argument("--ds-model", default=DS_MODEL)
    parser.add_argument("--gpt-model", default=GPT_MODEL)
    parser.add_argument("--seed", type=int, default=2026051802)
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--ds-rpm", type=int, default=120)
    parser.add_argument("--ds-tpm", type=int, default=1_000_000)
    parser.add_argument("--gpt-rpm", type=int, default=60)
    parser.add_argument("--gpt-tpm", type=int, default=600_000)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--resample", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
