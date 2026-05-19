from __future__ import annotations

import argparse
import ast
import concurrent.futures as futures
import csv
import json
import math
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[2]
ROUND = "round-9-20260517-033120"

MASTER_PATH = ROOT / "data" / "processed" / "master" / "master_dataset.csv"
TEXTS_PATH = ROOT / "data" / "raw" / "data-texts.json"
PROMPT_PATH = ROOT / "docs" / "legacy" / "master_prompt.md"
LEGACY_API_PATH = next((ROOT / "docs" / "legacy").glob("*siliconflow.py"), ROOT / "docs" / "legacy" / "batch-summary-siliconflow.py")
OUTDIR = ROOT / "result" / ROUND
MASTER_DIR = ROOT / "data" / "processed" / "master"
JSONL_PATH = MASTER_DIR / "master_dataset_dsv4.jsonl"
CSV_PATH = MASTER_DIR / "master_dataset_dsv4.csv"
AUDIT_PATH = MASTER_DIR / "master_dataset_dsv4_audit.json"
FAIL_PATH = OUTDIR / "master_dataset_dsv4_failures.jsonl"

MODEL_NAME = "deepseek-ai/DeepSeek-V4-Flash"
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

CSV_COLUMNS = [
    "doc_id",
    "dsv4_status",
    "dsv4_error",
    "dsv4_model",
    "dsv4_temperature",
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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_master(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
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


def prompt_body(prompt_text: str) -> str:
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
    lowered = s.lower()

    # Valid JSON is a usable extraction. Do not mark it as a refusal just
    # because the JSON contains field names such as cited_policies.
    try:
        parse_json_content(s)
        return False
    except Exception:
        pass

    explicit_phrases = [
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
    if any(phrase in lowered for phrase in explicit_phrases):
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
                    time.sleep(min(60, 2 ** attempt))
                    continue
            time.sleep(min(10, 1 + attempt))
        except requests.RequestException as exc:
            last_error = f"request_error: {exc}"
            time.sleep(min(60, 2 ** attempt))
    return "failed", None, last_error


def validate_record(obj: dict[str, Any], expected_doc_id: str) -> dict[str, Any]:
    obj["document_id"] = str(obj.get("document_id") or expected_doc_id)
    if obj["document_id"] != expected_doc_id:
        obj["_model_document_id"] = obj["document_id"]
        obj["document_id"] = expected_doc_id
    obj["_dsv4_meta"] = {
        "model": MODEL_NAME,
        "temperature": 0,
        "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return obj


def get_path_value(obj: dict[str, Any], path: str) -> Any:
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


def flatten_record(obj: dict[str, Any], status: str = "ok", error: str = "") -> dict[str, str]:
    row = {col: "" for col in CSV_COLUMNS}
    doc_id = str(obj.get("document_id") or "")
    row["doc_id"] = doc_id
    row["dsv4_status"] = status
    row["dsv4_error"] = error
    row["dsv4_model"] = MODEL_NAME
    row["dsv4_temperature"] = "0"
    for field in CONTENT_FIELDS:
        value = obj.get("case_amount") if field == "case_amount" else get_path_value(obj, field)
        row[field.replace(".", "__")] = cell(value)
    return row


def write_flat_csv(jsonl_path: Path, csv_path: Path) -> int:
    rows = load_jsonl(jsonl_path)
    tmp_path = csv_path.with_suffix(".csv.tmp")
    with tmp_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for obj in rows:
            writer.writerow(flatten_record(obj))
    shutil.move(str(tmp_path), str(csv_path))
    return len(rows)


def run_extract(args: argparse.Namespace) -> dict[str, Any]:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    MASTER_DIR.mkdir(parents=True, exist_ok=True)

    master_rows = load_master(Path(args.master_path))
    texts = read_json(Path(args.texts_path))
    prompt_template = prompt_body(read_text(Path(args.prompt_path)))
    api_url = extract_literal_assignment(Path(args.legacy_api_path), "API_URL")
    api_key = extract_literal_assignment(Path(args.legacy_api_path), "API_KEY")

    rows_by_doc = {r["doc_id"]: r for r in master_rows if r.get("doc_id")}
    existing_rows = load_jsonl(Path(args.output_jsonl))
    existing_ok = {str(x.get("document_id")) for x in existing_rows if x.get("document_id")}
    failure_rows = load_jsonl(Path(args.fail_path))
    failed_docs = {str(x.get("document_id")) for x in failure_rows if x.get("document_id") and x.get("status") == "missing_text"}

    candidates = [
        doc_id
        for doc_id in rows_by_doc
        if doc_id in texts and doc_id not in existing_ok and doc_id not in failed_docs
    ]
    if args.limit:
        candidates = candidates[: args.limit]
    target_total = sum(1 for doc_id in rows_by_doc if doc_id in texts)

    limiter = RateLimiter(rpm=args.rpm, tpm=args.tpm)
    write_lock = threading.Lock()
    fail_lock = threading.Lock()
    submitted = 0
    ok_this_run = 0
    safety_this_run = 0
    failed_this_run = 0

    missing_text_docs = [doc_id for doc_id in rows_by_doc if doc_id not in texts]
    for doc_id in missing_text_docs:
        if doc_id not in failed_docs:
            append_jsonl(
                Path(args.fail_path),
                {
                    "document_id": doc_id,
                    "status": "missing_text",
                    "error_excerpt": "No source text in data/raw/data-texts.json",
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
                fail_lock,
            )

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
            append_jsonl(Path(args.output_jsonl), validate_record(obj, doc_id), write_lock)
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

    pbar = tqdm(total=len(candidates), desc="DeepSeek V4 full extraction")
    pending: dict[futures.Future[tuple[str, str]], str] = {}
    idx = 0
    with futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        while idx < len(candidates) or pending:
            while len(pending) < args.workers and idx < len(candidates):
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
                    ok_this_run += 1
                elif status == "safety_refusal":
                    safety_this_run += 1
                else:
                    failed_this_run += 1
                pbar.update(1)
    pbar.close()

    csv_rows = write_flat_csv(Path(args.output_jsonl), Path(args.output_csv))
    final_rows = load_jsonl(Path(args.output_jsonl))
    failures = load_jsonl(Path(args.fail_path))
    audit = {
        "round": ROUND,
        "model": MODEL_NAME,
        "temperature": 0,
        "rpm": args.rpm,
        "tpm": args.tpm,
        "workers": args.workers,
        "max_tokens": args.max_tokens,
        "master_rows": len(master_rows),
        "target_docs_with_text": target_total,
        "missing_text_docs": len(missing_text_docs),
        "existing_ok_before_run": len(existing_ok),
        "submitted_this_run": submitted,
        "ok_this_run": ok_this_run,
        "safety_refusals_this_run": safety_this_run,
        "failed_this_run": failed_this_run,
        "jsonl_rows": len(final_rows),
        "csv_rows": csv_rows,
        "failure_rows": len(failures),
        "output_jsonl": str(args.output_jsonl),
        "output_csv": str(args.output_csv),
        "fail_path": str(args.fail_path),
    }
    write_json(Path(args.audit_path), audit)
    write_json(OUTDIR / "master_dataset_dsv4_audit.json", audit)
    return audit


def run_flatten(args: argparse.Namespace) -> dict[str, Any]:
    rows = write_flat_csv(Path(args.output_jsonl), Path(args.output_csv))
    audit = {
        "output_jsonl": str(args.output_jsonl),
        "output_csv": str(args.output_csv),
        "csv_rows": rows,
    }
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-path", default=str(MASTER_PATH))
    parser.add_argument("--texts-path", default=str(TEXTS_PATH))
    parser.add_argument("--prompt-path", default=str(PROMPT_PATH))
    parser.add_argument("--legacy-api-path", default=str(LEGACY_API_PATH))
    parser.add_argument("--output-jsonl", default=str(JSONL_PATH))
    parser.add_argument("--output-csv", default=str(CSV_PATH))
    parser.add_argument("--audit-path", default=str(AUDIT_PATH))
    parser.add_argument("--fail-path", default=str(FAIL_PATH))
    parser.add_argument("--rpm", type=int, default=500)
    parser.add_argument("--tpm", type=int, default=2_000_000)
    parser.add_argument("--workers", type=int, default=96)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-retries", type=int, default=6)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--flatten-only", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.flatten_only:
        run_flatten(args)
        return
    audit = run_extract(args)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
