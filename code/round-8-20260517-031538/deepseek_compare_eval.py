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
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[2]
ROUND = "round-8-20260517-031538"

MASTER_PATH = ROOT / "data" / "processed" / "master" / "master_dataset.csv"
TEXTS_PATH = ROOT / "data" / "raw" / "data-texts.json"
PROMPT_PATH = ROOT / "docs" / "legacy" / "master_prompt.md"
LEGACY_API_PATH = ROOT / "docs" / "legacy" / "批量总结-siliconflow.py"
COMPARE_PATH = ROOT / "data" / "processed" / "master" / "compare.jsonl"
OUTDIR = ROOT / "result" / ROUND

MODEL_NAME = "deepseek-ai/DeepSeek-V4-Flash"
DEFAULT_SEED = 20260517

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

FIELD_TO_MASTER = {
    "case_amount": "case_amount",
    "metadata.case_number": "case_number",
    "metadata.court_name": "court_name",
    "metadata.court_level": "court_level",
    "metadata.judgment_date": "judgment_date",
    "metadata.first_instance_case_number": "first_instance_case_number",
    "metadata.region": "region",
    "metadata.doc_type": "doc_type",
    "case_profile.case_type_primary": "case_type_primary",
    "case_profile.case_type_secondary": "case_type_secondary",
    "case_profile.procedure_stage": "procedure_stage",
    "case_profile.is_appeal": "is_appeal",
    "case_profile.litigant_profile.plaintiff_types": "plaintiff_types",
    "case_profile.litigant_profile.defendant_types": "defendant_types",
    "virtual_currency_info.involved": "vc_involved",
    "virtual_currency_info.currency_types": "currency_types",
    "virtual_currency_info.activity_type": "activity_type",
    "judicial_analysis.legal_characterization": "legal_characterization",
    "judicial_analysis.virtual_currency_property_legality": "vc_property_legality",
    "judicial_analysis.contract_validity": "contract_validity",
    "judicial_analysis.reason_for_invalidity": "reason_for_invalidity",
    "judicial_analysis.cited_laws": "cited_laws",
    "judicial_analysis.cited_policies": "cited_policies",
    "judicial_analysis.judicial_framing": "judicial_framing",
    "llm_summary.outcome_summary": "outcome_summary",
    "llm_summary.reasoning_summary": "reasoning_summary",
}

LIST_FIELDS = {
    "case_profile.litigant_profile.plaintiff_types",
    "case_profile.litigant_profile.defendant_types",
    "virtual_currency_info.currency_types",
    "judicial_analysis.reason_for_invalidity",
    "judicial_analysis.cited_laws",
    "judicial_analysis.cited_policies",
    "judicial_analysis.judicial_framing",
}

NUMERIC_FIELDS = {"case_amount"}
DATE_FIELDS = {"metadata.judgment_date"}
BOOL_FIELDS = {"case_profile.is_appeal", "virtual_currency_info.involved"}


@dataclass
class FieldScore:
    field: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    support: int = 0
    compared_docs: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        if denom:
            return self.tp / denom
        if self.fn:
            return 0.0
        return math.nan

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        if denom:
            return self.tp / denom
        if self.fp:
            return 0.0
        return math.nan

    @property
    def f1(self) -> float:
        if self.tp + self.fp + self.fn == 0:
            return math.nan
        p = self.precision
        r = self.recall
        if math.isnan(p) or math.isnan(r) or p + r == 0:
            return 0.0
        return 2 * p * r / (p + r)


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_master(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


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


def prompt_body(prompt_text: str) -> str:
    marker = "## 正式提示词"
    if marker in prompt_text:
        return prompt_text.split(marker, 1)[1].strip()
    return prompt_text.strip()


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
    # Conservative enough for rate limiting; Chinese text is often denser than English.
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
    s = (text or "").lower()
    keywords = [
        "safety",
        "safe",
        "policy",
        "violate",
        "sensitive",
        "blocked",
        "refuse",
        "拒绝",
        "安全",
        "敏感",
        "违规",
        "无法提供",
        "不能提供",
        "抱歉",
    ]
    if status_code in {400, 403, 451} and any(k in s for k in keywords):
        return True
    return any(k in s for k in ["安全检查", "safety check", "content security", "content policy"])


def validate_record(obj: dict[str, Any], expected_doc_id: str) -> dict[str, Any]:
    obj["document_id"] = str(obj.get("document_id") or expected_doc_id)
    if obj["document_id"] != expected_doc_id:
        obj["_model_document_id"] = obj["document_id"]
        obj["document_id"] = expected_doc_id
    return obj


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
                if is_safety_refusal(None, content):
                    return "safety_refusal", None, content[:1000]
                try:
                    return "ok", parse_json_content(content), ""
                except Exception as exc:
                    last_error = f"json_parse_error: {exc}; content={content[:800]}"
            else:
                if is_safety_refusal(response.status_code, text):
                    return "safety_refusal", None, text[:1000]
                last_error = f"http_{response.status_code}: {text[:800]}"
                if response.status_code in {429, 500, 502, 503, 504}:
                    time.sleep(min(60, 2 ** attempt))
                    continue
                time.sleep(min(10, 1 + attempt))
        except requests.RequestException as exc:
            last_error = f"request_error: {exc}"
            time.sleep(min(60, 2 ** attempt))
    return "failed", None, last_error


def append_jsonl(path: Path, obj: dict[str, Any], lock: threading.Lock) -> None:
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def run_extraction(args: argparse.Namespace) -> dict[str, Any]:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    compare_path = Path(args.compare_path)
    skip_path = OUTDIR / "compare_skipped.jsonl"
    audit_path = OUTDIR / "deepseek_extraction_audit.json"

    master_rows = load_master(Path(args.master_path))
    target_success = args.target_success or math.ceil(len(master_rows) * args.sample_frac)
    texts = read_json(Path(args.texts_path))
    prompt_template = prompt_body(read_text(Path(args.prompt_path)))
    api_url = extract_literal_assignment(Path(args.legacy_api_path), "API_URL")
    api_key = extract_literal_assignment(Path(args.legacy_api_path), "API_KEY")

    rows_by_doc = {r["doc_id"]: r for r in master_rows if r.get("doc_id") in texts}
    existing = load_jsonl(compare_path)
    existing_ok = {str(x.get("document_id")) for x in existing if x.get("document_id")}
    skipped = load_jsonl(skip_path)
    attempted = existing_ok | {str(x.get("document_id")) for x in skipped if x.get("document_id")}

    success_count = len(existing_ok)
    if success_count >= target_success:
        return {
            "status": "already_complete",
            "target_success": target_success,
            "success_count": success_count,
            "compare_path": str(compare_path),
        }

    candidates = [doc_id for doc_id in rows_by_doc if doc_id not in attempted]
    rng = random.Random(args.seed)
    rng.shuffle(candidates)

    limiter = RateLimiter(rpm=args.rpm, tpm=args.tpm)
    write_lock = threading.Lock()
    skip_lock = threading.Lock()
    submitted = 0
    failures = 0
    safety_refusals = 0
    invalid_or_failed = 0

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
            record = validate_record(obj, doc_id)
            append_jsonl(compare_path, record, write_lock)
            return "ok", doc_id
        failure_record = {
            "document_id": doc_id,
            "status": status,
            "error_excerpt": error[:1000],
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        append_jsonl(skip_path, failure_record, skip_lock)
        return status, doc_id

    pbar = tqdm(total=target_success, initial=success_count, desc="DeepSeek gold outputs")
    pending: dict[futures.Future[tuple[str, str]], str] = {}
    idx = 0
    try:
        with futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            while success_count < target_success:
                while (
                    len(pending) < args.workers
                    and idx < len(candidates)
                    and success_count + sum(1 for fut in pending) < target_success
                ):
                    doc_id = candidates[idx]
                    idx += 1
                    submitted += 1
                    pending[executor.submit(work, doc_id)] = doc_id
                if not pending:
                    break
                done, _ = futures.wait(pending, return_when=futures.FIRST_COMPLETED)
                for fut in done:
                    pending.pop(fut, None)
                    try:
                        status, _doc_id = fut.result()
                    except Exception as exc:
                        status = "failed"
                        failures += 1
                        invalid_or_failed += 1
                        append_jsonl(
                            skip_path,
                            {"document_id": "", "status": "worker_exception", "error_excerpt": str(exc)[:1000]},
                            skip_lock,
                        )
                    if status == "ok":
                        success_count += 1
                        pbar.update(1)
                    elif status == "safety_refusal":
                        safety_refusals += 1
                    else:
                        invalid_or_failed += 1
        pbar.close()
    finally:
        pbar.close()

    audit = {
        "model": MODEL_NAME,
        "temperature": 0,
        "rpm": args.rpm,
        "tpm": args.tpm,
        "workers": args.workers,
        "seed": args.seed,
        "sample_frac": args.sample_frac,
        "target_success": target_success,
        "success_count": success_count,
        "submitted_this_run": submitted,
        "safety_refusals_this_run": safety_refusals,
        "invalid_or_failed_this_run": invalid_or_failed,
        "candidate_remaining": max(0, len(candidates) - idx),
        "compare_path": str(compare_path),
        "skip_path": str(skip_path),
    }
    write_json(audit_path, audit)
    return audit


def get_path_value(obj: dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if isinstance(cur, dict) and set(cur.keys()) >= {"value"}:
        return cur.get("value")
    return cur


def is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    s = str(value).strip()
    return s == "" or s.lower() in {"nan", "none", "null", "<na>"} or s in {"不适用", "未知", "未提及"}


def parse_decimal(value: Any) -> Decimal | None:
    if is_empty(value):
        return None
    s = str(value).strip()
    s = s.replace(",", "").replace("，", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        match = re.search(r"-?\d+(?:\.\d+)?", s)
        if not match:
            return None
        try:
            return Decimal(match.group(0))
        except InvalidOperation:
            return None


def normalize_date(value: Any) -> str:
    if is_empty(value):
        return ""
    s = str(value).strip()
    m = re.search(r"(\d{4})[年/\-.](\d{1,2})[月/\-.](\d{1,2})", s)
    if not m:
        m = re.search(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return normalize_text(s)


def normalize_bool(value: Any) -> str:
    if is_empty(value):
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    s = normalize_text(value)
    if s in {"1", "true", "是", "二审", "上诉", "有", "涉及", "yes"}:
        return "true"
    if s in {"0", "false", "否", "一审", "无", "不涉及", "no"}:
        return "false"
    return s


def normalize_text(value: Any) -> str:
    if is_empty(value):
        return ""
    s = str(value).strip()
    s = s.replace("\u3000", " ")
    s = re.sub(r"\s+", "", s)
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("，", ",").replace("；", ";").replace("：", ":")
    s = s.strip("\"'“”‘’")
    # Common harmless suffix in legal-characterization labels.
    for suffix in ["法律关系"]:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s


def normalize_scalar(value: Any, field: str) -> str:
    if field in NUMERIC_FIELDS:
        d = parse_decimal(value)
        if d is None:
            return ""
        return str(d.normalize())
    if field in DATE_FIELDS:
        return normalize_date(value)
    if field in BOOL_FIELDS:
        return normalize_bool(value)
    return normalize_text(value)


def parse_list_like(value: Any) -> list[Any]:
    if is_empty(value):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    s = str(value).strip()
    if not s:
        return []
    try:
        obj = json.loads(s)
        if isinstance(obj, list):
            return obj
        return [obj]
    except Exception:
        pass
    parts = re.split(r"[;；,，、|/]+", s)
    return [p for p in parts if not is_empty(p)]


def normalize_list(value: Any, field: str) -> set[str]:
    out = set()
    for item in parse_list_like(value):
        norm = normalize_scalar(item, field)
        if norm:
            out.add(norm)
    return out


def score_field(gold: Any, pred: Any, field: str) -> tuple[int, int, int, int]:
    if field in LIST_FIELDS:
        gold_set = normalize_list(gold, field)
        pred_set = normalize_list(pred, field)
        tp = len(gold_set & pred_set)
        fp = len(pred_set - gold_set)
        fn = len(gold_set - pred_set)
        return tp, fp, fn, len(gold_set)
    gold_norm = normalize_scalar(gold, field)
    pred_norm = normalize_scalar(pred, field)
    if not gold_norm and not pred_norm:
        return 0, 0, 0, 0
    if gold_norm and pred_norm and gold_norm == pred_norm:
        return 1, 0, 0, 1
    if gold_norm and pred_norm:
        return 0, 1, 1, 1
    if gold_norm and not pred_norm:
        return 0, 0, 1, 1
    return 0, 1, 0, 0


def run_scoring(args: argparse.Namespace) -> dict[str, Any]:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    master_rows = {r["doc_id"]: r for r in load_master(Path(args.master_path))}
    gold_rows = load_jsonl(Path(args.compare_path))
    scores = {field: FieldScore(field=field) for field in CONTENT_FIELDS}
    mismatches: list[dict[str, Any]] = []

    for gold in gold_rows:
        doc_id = str(gold.get("document_id") or "")
        pred_row = master_rows.get(doc_id)
        if not pred_row:
            continue
        for field in CONTENT_FIELDS:
            gold_value = get_path_value(gold, field) if field != "case_amount" else gold.get("case_amount")
            pred_value = pred_row.get(FIELD_TO_MASTER[field])
            tp, fp, fn, support = score_field(gold_value, pred_value, field)
            s = scores[field]
            s.tp += tp
            s.fp += fp
            s.fn += fn
            s.support += support
            s.compared_docs += 1
            if (fp or fn) and len(mismatches) < args.max_mismatch_examples:
                mismatches.append(
                    {
                        "document_id": doc_id,
                        "field": field,
                        "gold": gold_value,
                        "master": pred_value,
                        "tp": tp,
                        "fp": fp,
                        "fn": fn,
                    }
                )

    field_rows = []
    for field, score in scores.items():
        field_rows.append(
            {
                "field": field,
                "master_column": FIELD_TO_MASTER[field],
                "tp": score.tp,
                "fp": score.fp,
                "fn": score.fn,
                "gold_support": score.support,
                "precision": score.precision,
                "recall": score.recall,
                "f1": score.f1,
                "compared_docs": score.compared_docs,
            }
        )
    total_tp = sum(s.tp for s in scores.values())
    total_fp = sum(s.fp for s in scores.values())
    total_fn = sum(s.fn for s in scores.values())
    micro_precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else math.nan
    micro_recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else math.nan
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if not math.isnan(micro_precision) and not math.isnan(micro_recall) and micro_precision + micro_recall
        else math.nan
    )
    valid_f1 = [r["f1"] for r in field_rows if not math.isnan(r["f1"])]
    macro_f1 = sum(valid_f1) / len(valid_f1) if valid_f1 else math.nan
    summary = {
        "gold_compare_path": str(args.compare_path),
        "master_path": str(args.master_path),
        "gold_docs": len(gold_rows),
        "scored_docs": len({str(x.get("document_id") or "") for x in gold_rows} & set(master_rows)),
        "micro": {
            "tp": total_tp,
            "fp": total_fp,
            "fn": total_fn,
            "precision": micro_precision,
            "recall": micro_recall,
            "f1": micro_f1,
        },
        "macro_f1": macro_f1,
        "macro_fields_with_defined_f1": len(valid_f1),
    }
    write_json(OUTDIR / "f1_summary.json", summary)
    write_json(OUTDIR / "mismatch_examples.json", mismatches)
    with (OUTDIR / "field_f1.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "field",
                "master_column",
                "tp",
                "fp",
                "fn",
                "gold_support",
                "precision",
                "recall",
                "f1",
                "compared_docs",
            ],
        )
        writer.writeheader()
        writer.writerows(field_rows)
    write_score_report(summary, field_rows)
    return summary


def fmt(value: Any) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "NA"
        return f"{value:.4f}"
    return str(value)


def write_score_report(summary: dict[str, Any], field_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# DeepSeek Gold vs Master Dataset F1",
        "",
        f"- Gold file: `{summary['gold_compare_path']}`",
        f"- Master file: `{summary['master_path']}`",
        f"- Gold docs: {summary['gold_docs']}",
        f"- Scored docs: {summary['scored_docs']}",
        f"- Micro precision: {fmt(summary['micro']['precision'])}",
        f"- Micro recall: {fmt(summary['micro']['recall'])}",
        f"- Micro F1: {fmt(summary['micro']['f1'])}",
        f"- Micro TP/FP/FN: {summary['micro']['tp']} / {summary['micro']['fp']} / {summary['micro']['fn']}",
        f"- Macro F1: {fmt(summary['macro_f1'])}",
        "",
        "## Field Scores",
        "",
        "| Field | Master column | TP | FP | FN | Gold support | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in field_rows:
        lines.append(
            "| {field} | {master_column} | {tp} | {fp} | {fn} | {gold_support} | {precision} | {recall} | {f1} |".format(
                field=row["field"],
                master_column=row["master_column"],
                tp=row["tp"],
                fp=row["fp"],
                fn=row["fn"],
                gold_support=row["gold_support"],
                precision=fmt(row["precision"]),
                recall=fmt(row["recall"]),
                f1=fmt(row["f1"]),
            )
        )
    (OUTDIR / "f1_report.md").write_text("\n".join(lines), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-path", default=str(MASTER_PATH))
    parser.add_argument("--texts-path", default=str(TEXTS_PATH))
    parser.add_argument("--prompt-path", default=str(PROMPT_PATH))
    parser.add_argument("--legacy-api-path", default=str(LEGACY_API_PATH))
    parser.add_argument("--compare-path", default=str(COMPARE_PATH))
    parser.add_argument("--sample-frac", type=float, default=0.01)
    parser.add_argument("--target-success", type=int, default=0)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--rpm", type=int, default=500)
    parser.add_argument("--tpm", type=int, default=2_000_000)
    parser.add_argument("--workers", type=int, default=64)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-retries", type=int, default=6)
    parser.add_argument("--max-mismatch-examples", type=int, default=500)
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--extract-only", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.score_only:
        audit = run_extraction(args)
        print(json.dumps({"extraction": audit}, ensure_ascii=False, indent=2))
    if not args.extract_only:
        summary = run_scoring(args)
        print(json.dumps({"scoring": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
