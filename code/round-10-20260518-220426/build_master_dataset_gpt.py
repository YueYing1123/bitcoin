from __future__ import annotations

import argparse
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
ROUND = "round-10-20260518-220426"

MASTER_PATH = ROOT / "data" / "processed" / "master" / "master_dataset.csv"
TEXTS_PATH = ROOT / "data" / "raw" / "data-texts.json"
PROMPT_PATH = ROOT / "docs" / "legacy" / "master_prompt-260518.md"
ENV_PATH = PROJECT_ROOT / ".env"
OUTDIR = ROOT / "result" / ROUND
MASTER_DIR = ROOT / "data" / "processed" / "master"
JSONL_PATH = MASTER_DIR / "master_dataset_gpt.jsonl"
CSV_PATH = MASTER_DIR / "master_dataset_gpt.csv"
AUDIT_PATH = MASTER_DIR / "master_dataset_gpt_audit.json"
FAIL_PATH = OUTDIR / "master_dataset_gpt_failures.jsonl"

MODEL_NAME = "gpt-4.1-mini"
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
    "virtual_currency_info.typical_virtual_currency",
    "virtual_currency_info.currency_types",
    "virtual_currency_info.activity_types",
    "judicial_analysis.legal_characterization",
    "judicial_analysis.virtual_currency_property_status",
    "judicial_analysis.direct_transaction_legality_assessment",
    "judicial_analysis.indirect_transaction_legality_assessment",
    "judicial_analysis.direct_related_contract_validity",
    "judicial_analysis.indirect_related_contract_validity",
    "judicial_analysis.reasons_for_invalidity_or_no_protection",
    "judicial_analysis.cited_laws",
    "judicial_analysis.cited_policies",
    "judicial_analysis.policy_labels",
    "judicial_analysis.judicial_framing",
    "llm_summary.outcome_summary",
    "llm_summary.reasoning_summary",
    "low_confidence_fields",
]

CSV_COLUMNS = [
    "doc_id",
    "gpt_status",
    "gpt_error",
    "gpt_model",
    "gpt_temperature",
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
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def get_openai_api_key(path: Path) -> str:
    env = load_env(path)
    key = env.get("OPENAI_API_KEY") or env.get("openai_api_key")
    if not key:
        raise RuntimeError(f"Cannot find OPENAI_API_KEY/openai_api_key in {path}")
    return key


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


def is_safety_refusal(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    try:
        parse_json_content(s)
        return False
    except Exception:
        pass
    lowered = s.lower()
    explicit_phrases = [
        "i can't help",
        "i cannot help",
        "i'm sorry",
        "sorry, but",
        "unable to assist",
        "cannot comply",
        "cannot assist",
        "refusal",
        "content filter",
        "content moderation",
        "blocked",
        "unsafe",
        "policy violation",
    ]
    return any(phrase in lowered for phrase in explicit_phrases)


def is_auth_error(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        marker in lowered
        for marker in [
            "authenticationerror",
            "error code: 401",
            "missing scopes",
            "insufficient permissions",
            "invalid api key",
            "incorrect api key",
        ]
    )


def call_api(
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
                        "content": "你是法律文书结构化抽取助手。只输出严格 JSON，不输出解释。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            try:
                return "ok", parse_json_content(content), ""
            except Exception as exc:
                if is_safety_refusal(content):
                    return "safety_refusal", None, content[:1000]
                last_error = f"json_parse_error: {exc}; content={content[:800]}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if is_auth_error(last_error):
                return "auth_error", None, last_error
            if attempt < max_retries - 1:
                time.sleep(min(60, 2**attempt))
    return "failed", None, last_error


def validate_record(obj: dict[str, Any], expected_doc_id: str, model: str) -> dict[str, Any]:
    obj["document_id"] = str(obj.get("document_id") or expected_doc_id)
    if obj["document_id"] != expected_doc_id:
        obj["_model_document_id"] = obj["document_id"]
        obj["document_id"] = expected_doc_id
    obj["_gpt_meta"] = {
        "model": model,
        "temperature": 0,
        "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "prompt_path": str(PROMPT_PATH),
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


def flatten_record(obj: dict[str, Any], model: str, status: str = "ok", error: str = "") -> dict[str, str]:
    row = {col: "" for col in CSV_COLUMNS}
    row["doc_id"] = str(obj.get("document_id") or "")
    row["gpt_status"] = status
    row["gpt_error"] = error
    row["gpt_model"] = model
    row["gpt_temperature"] = "0"
    for field in CONTENT_FIELDS:
        if field in {"case_amount", "case_amount_type"}:
            value = obj.get(field)
        else:
            value = get_path_value(obj, field)
        row[field.replace(".", "__")] = cell(value)
    return row


def write_flat_csv(jsonl_path: Path, csv_path: Path, model: str) -> int:
    rows = load_jsonl(jsonl_path)
    tmp_path = csv_path.with_suffix(".csv.tmp")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for obj in rows:
            writer.writerow(flatten_record(obj, model))
    shutil.move(str(tmp_path), str(csv_path))
    return len(rows)


def select_candidates(
    rows_by_doc: dict[str, dict[str, str]],
    texts: dict[str, str],
    existing_ok: set[str],
    doc_id: str,
    limit: int,
) -> list[str]:
    if doc_id:
        if doc_id not in rows_by_doc:
            raise KeyError(f"doc_id not found in master table: {doc_id}")
        if doc_id not in texts:
            raise KeyError(f"doc_id has no source text: {doc_id}")
        return [doc_id]
    candidates = [x for x in rows_by_doc if x in texts and x not in existing_ok]
    if limit:
        candidates = candidates[:limit]
    return candidates


def run_extract(args: argparse.Namespace) -> dict[str, Any]:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    MASTER_DIR.mkdir(parents=True, exist_ok=True)

    master_rows = load_master(Path(args.master_path))
    texts = read_json(Path(args.texts_path))
    prompt_template = prompt_body(read_text(Path(args.prompt_path)))
    api_key = get_openai_api_key(Path(args.env_path))
    client = OpenAI(api_key=api_key, max_retries=0)

    rows_by_doc = {r["doc_id"]: r for r in master_rows if r.get("doc_id")}
    existing_rows = load_jsonl(Path(args.output_jsonl))
    existing_ok = {str(x.get("document_id")) for x in existing_rows if x.get("document_id")}
    candidates = select_candidates(rows_by_doc, texts, existing_ok, args.doc_id, args.limit)

    limiter = RateLimiter(rpm=args.rpm, tpm=args.tpm)
    write_lock = threading.Lock()
    fail_lock = threading.Lock()
    submitted = 0
    ok_this_run = 0
    auth_this_run = 0
    safety_this_run = 0
    failed_this_run = 0

    pbar = tqdm(total=len(candidates), desc="OpenAI GPT extraction")
    for doc_id in candidates:
        submitted += 1
        row = rows_by_doc[doc_id]
        prompt = render_prompt(prompt_template, row, texts[doc_id] or "")
        status, obj, error = call_api(
            client=client,
            model=args.model,
            prompt=prompt,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            max_retries=args.max_retries,
            rate_limiter=limiter,
        )
        if status == "ok" and obj is not None:
            append_jsonl(Path(args.output_jsonl), validate_record(obj, doc_id, args.model), write_lock)
            ok_this_run += 1
        else:
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
            if status == "safety_refusal":
                safety_this_run += 1
            elif status == "auth_error":
                auth_this_run += 1
                pbar.update(1)
                break
            else:
                failed_this_run += 1
        pbar.update(1)
    pbar.close()

    csv_rows = write_flat_csv(Path(args.output_jsonl), Path(args.output_csv), args.model)
    final_rows = load_jsonl(Path(args.output_jsonl))
    failures = load_jsonl(Path(args.fail_path))
    audit = {
        "round": ROUND,
        "model": args.model,
        "temperature": 0,
        "prompt_path": str(args.prompt_path),
        "master_rows": len(master_rows),
        "existing_ok_before_run": len(existing_ok),
        "submitted_this_run": submitted,
        "ok_this_run": ok_this_run,
        "auth_errors_this_run": auth_this_run,
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
    write_json(OUTDIR / "master_dataset_gpt_audit.json", audit)
    return audit


def run_flatten(args: argparse.Namespace) -> dict[str, Any]:
    rows = write_flat_csv(Path(args.output_jsonl), Path(args.output_csv), args.model)
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
    parser.add_argument("--env-path", default=str(ENV_PATH))
    parser.add_argument("--output-jsonl", default=str(JSONL_PATH))
    parser.add_argument("--output-csv", default=str(CSV_PATH))
    parser.add_argument("--audit-path", default=str(AUDIT_PATH))
    parser.add_argument("--fail-path", default=str(FAIL_PATH))
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--rpm", type=int, default=60)
    parser.add_argument("--tpm", type=int, default=600_000)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--doc-id", default="")
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
