from __future__ import annotations

import argparse
import concurrent.futures as futures
import csv
import json
import re
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from openai import OpenAI
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
ROUND_DIR = ROOT / "result" / "round-20-20260519-manual-annotation"
DEFAULT_TEST_SET = ROOT / "result" / "round-22-20260519-vc-true-stratified-test-set" / "test_set_5pct_year_region_appeal_priority.csv"
DEFAULT_TEXTS = ROOT / "data" / "raw" / "data-texts.json"
DEFAULT_PROMPT = ROOT / "docs" / "legacy" / "master_prompt-260518.md"
DEFAULT_ENV = PROJECT_ROOT / ".env"
DEFAULT_JSONL = ROUND_DIR / "ds_v4_pro_testset_baseline.jsonl"
DEFAULT_CSV = ROUND_DIR / "ds_v4_pro_testset_baseline.csv"
DEFAULT_AUDIT = ROUND_DIR / "ds_v4_pro_testset_baseline_audit.json"
DEFAULT_FAIL = ROUND_DIR / "ds_v4_pro_testset_baseline_failures.jsonl"

MODEL = "deepseek-v4-pro"

CONTENT_FIELDS = [
    "case_amount",
    "case_amount_type",
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
    "virtual_currency_info.activity_types",
    "judicial_analysis.legal_characterization",
    "judicial_analysis.virtual_currency_property_status",
    "judicial_analysis.transaction_legality_assessment",
    "judicial_analysis.contract_validity",
    "judicial_analysis.reasons_for_invalidity_or_no_protection",
    "judicial_analysis.cited_laws",
    "judicial_analysis.cited_policies",
    "judicial_analysis.policy_labels",
    "judicial_analysis.judicial_framing",
    "llm_summary.outcome_summary",
    "llm_summary.reasoning_summary",
    "low_confidence_fields",
]


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
                wait_for = max(0.1, min([x for x in waits if x > 0] or [0.5]))
            time.sleep(wait_for)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def get_ds_key(path: Path) -> str:
    env = load_env(path)
    key = env.get("DEEPSEEK_API_KEY") or env.get("deepseek_api_key")
    if not key:
        raise RuntimeError(f"Cannot find DEEPSEEK_API_KEY/deepseek_api_key in {path}")
    return key


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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, obj: dict[str, Any], lock: threading.Lock) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


def clean_existing_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    if path.exists():
        for row in load_jsonl(path):
            doc_id = str(row.get("document_id") or row.get("doc_id") or "")
            meta = row.get("_ds_meta") if isinstance(row.get("_ds_meta"), dict) else {}
            if doc_id and meta.get("model") == MODEL:
                records[doc_id] = row
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for doc_id in sorted(records):
            f.write(json.dumps(records[doc_id], ensure_ascii=False, separators=(",", ":")) + "\n")
    tmp.replace(path)
    return records


def render_prompt(template: str, row: dict[str, str], doc_text: str) -> str:
    meta = {
        "title": row.get("index_title") or row.get("metadata__case_number") or "",
        "case_reason": row.get("index_case_cause") or row.get("case_profile__case_type_secondary") or "",
        "case_number": row.get("case_number") or row.get("index_case_number") or row.get("metadata__case_number") or "",
        "judgment_date": row.get("judgment_date") or row.get("index_close_date") or row.get("metadata__judgment_date") or "",
        "court_name": row.get("court_name") or row.get("index_court_name") or row.get("metadata__court_name") or "",
        "court_level": row.get("court_level") or row.get("index_court_level") or row.get("metadata__court_level") or "",
        "procedure_stage": row.get("procedure_stage") or row.get("index_procedure") or row.get("case_profile__procedure_stage") or "",
    }
    out = template.replace("{{ document_id }}", row["doc_id"])
    out = out.replace("{{ document_text }}", doc_text)
    for key, value in meta.items():
        out = out.replace("{{ meta." + key + " }}", value)
    return out


def estimate_tokens(prompt: str, max_tokens: int) -> int:
    return max(1, len(prompt) // 2 + max_tokens)


def classify_error(error: str) -> str:
    lowered = error.lower()
    if any(x in lowered for x in ["401", "authentication", "api key", "unauthorized"]):
        return "auth_error"
    if "json" in lowered and ("parse" in lowered or "decode" in lowered):
        return "json_parse_error"
    if any(x in lowered for x in ["timeout", "timed out", "readtimeout"]):
        return "timeout"
    return "failed"


def call_ds(
    client: OpenAI,
    model: str,
    prompt: str,
    limiter: RateLimiter,
    max_tokens: int,
    timeout: int,
    retries: int,
) -> tuple[str, dict[str, Any] | None, str]:
    last_error = ""
    tokens = estimate_tokens(prompt, max_tokens)
    for attempt in range(retries):
        limiter.wait(tokens)
        try:
            response = client.with_options(timeout=timeout).chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是法律文书结构化抽取助手。只输出严格 JSON，不输出解释。"},
                    {"role": "user", "content": prompt + "\n\n请输出 JSON。"},
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
            if attempt < retries - 1:
                time.sleep(min(30, 2**attempt))
    return classify_error(last_error), None, last_error


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
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def write_flat_csv(jsonl_path: Path, csv_path: Path) -> int:
    rows = load_jsonl(jsonl_path)
    cols = ["doc_id", "status", "model", "temperature"] + [field.replace(".", "__") for field in CONTENT_FIELDS]
    tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for obj in rows:
            out = {col: "" for col in cols}
            out["doc_id"] = str(obj.get("document_id") or "")
            out["status"] = "ok"
            out["model"] = MODEL
            out["temperature"] = "0"
            for field in CONTENT_FIELDS:
                value = obj.get(field) if field in {"case_amount", "case_amount_type"} else get_path_value(obj, field)
                out[field.replace(".", "__")] = cell(value)
            writer.writerow(out)
    shutil.move(str(tmp), str(csv_path))
    return len(rows)


def run(args: argparse.Namespace) -> dict[str, Any]:
    test_set = read_csv(Path(args.test_set))
    texts = read_json(Path(args.texts))
    prompt_template = Path(args.prompt).read_text(encoding="utf-8").strip()
    output_jsonl = Path(args.output_jsonl)
    existing = clean_existing_jsonl(output_jsonl)
    rows_by_doc = {row["doc_id"]: row for row in test_set if row.get("doc_id")}
    candidates = [doc_id for doc_id in rows_by_doc if doc_id in texts and doc_id not in existing]
    if args.limit:
        candidates = candidates[: args.limit]

    client = OpenAI(api_key=get_ds_key(Path(args.env)), base_url="https://api.deepseek.com", max_retries=0)
    limiter = RateLimiter(args.rpm, args.tpm)
    write_lock = threading.Lock()
    fail_lock = threading.Lock()
    counters = {"submitted": 0, "ok": 0, "auth_error": 0, "timeout": 0, "json_parse_error": 0, "failed": 0}

    def work(doc_id: str) -> tuple[str, str]:
        prompt = render_prompt(prompt_template, rows_by_doc[doc_id], texts.get(doc_id, ""))
        status, obj, error = call_ds(client, args.model, prompt, limiter, args.max_tokens, args.timeout, args.retries)
        if status == "ok" and obj is not None:
            obj["document_id"] = doc_id
            obj["_ds_meta"] = {
                "provider": "official_deepseek",
                "model": args.model,
                "temperature": 0,
                "thinking": "disabled",
                "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "prompt_path": str(Path(args.prompt)),
            }
            append_jsonl(output_jsonl, obj, write_lock)
        else:
            append_jsonl(
                Path(args.fail),
                {
                    "document_id": doc_id,
                    "provider": "official_deepseek",
                    "model": args.model,
                    "status": status,
                    "error_excerpt": error[:1200],
                    "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
                fail_lock,
            )
        return status, doc_id

    pbar = tqdm(total=len(candidates), desc="DS pro baseline")
    with futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {}
        idx = 0
        stop = False
        while (idx < len(candidates) and not stop) or future_map:
            while len(future_map) < args.workers and idx < len(candidates) and not stop:
                doc_id = candidates[idx]
                idx += 1
                counters["submitted"] += 1
                future_map[executor.submit(work, doc_id)] = doc_id
            done, _ = futures.wait(future_map, return_when=futures.FIRST_COMPLETED)
            for fut in done:
                future_map.pop(fut, None)
                try:
                    status, _doc_id = fut.result()
                except Exception as exc:
                    status = "failed"
                    append_jsonl(
                        Path(args.fail),
                        {
                            "document_id": "",
                            "provider": "official_deepseek",
                            "model": args.model,
                            "status": "worker_exception",
                            "error_excerpt": str(exc)[:1200],
                            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                        },
                        fail_lock,
                    )
                counters[status if status in counters else "failed"] += 1
                if status == "auth_error":
                    stop = True
                pbar.update(1)
    pbar.close()

    csv_rows = write_flat_csv(output_jsonl, Path(args.output_csv))
    final_rows = load_jsonl(output_jsonl)
    audit = {
        "provider": "official_deepseek",
        "model": args.model,
        "temperature": 0,
        "thinking": "disabled",
        "test_rows": len(test_set),
        "existing_before_run": len(existing),
        "jsonl_rows": len(final_rows),
        "csv_rows": csv_rows,
        "remaining": len(test_set) - len({str(x.get("document_id") or "") for x in final_rows}),
        "output_jsonl": str(output_jsonl),
        "output_csv": str(args.output_csv),
        "fail_path": str(args.fail),
        **counters,
    }
    write_json(Path(args.audit), audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-set", default=str(DEFAULT_TEST_SET))
    parser.add_argument("--texts", default=str(DEFAULT_TEXTS))
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT))
    parser.add_argument("--env", default=str(DEFAULT_ENV))
    parser.add_argument("--output-jsonl", default=str(DEFAULT_JSONL))
    parser.add_argument("--output-csv", default=str(DEFAULT_CSV))
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--fail", default=str(DEFAULT_FAIL))
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--rpm", type=int, default=80)
    parser.add_argument("--tpm", type=int, default=800_000)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=75)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--limit", type=int, default=0)
    return parser


if __name__ == "__main__":
    run(build_parser().parse_args())
