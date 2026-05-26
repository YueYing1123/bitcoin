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
from typing import Any, Literal

from openai import OpenAI
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
ROUND = "round-12-20260518-232605"

MASTER_PATH = ROOT / "data" / "processed" / "master" / "master_dataset_vc_true.csv"
TEXTS_PATH = ROOT / "data" / "raw" / "data-texts.json"
PROMPT_PATH = ROOT / "docs" / "legacy" / "master_prompt-260518.md"
ENV_PATH = PROJECT_ROOT / ".env"
OUTDIR = ROOT / "result" / ROUND
MASTER_DIR = ROOT / "data" / "processed" / "master"

DS_JSONL = MASTER_DIR / "master_dataset_ds_official.jsonl"
DS_CSV = MASTER_DIR / "master_dataset_ds_official.csv"
DS_AUDIT = MASTER_DIR / "master_dataset_ds_official_audit.json"
DS_FAIL = OUTDIR / "master_dataset_ds_official_failures.jsonl"

GPT_JSONL = MASTER_DIR / "master_dataset_gpt_concurrent.jsonl"
GPT_CSV = MASTER_DIR / "master_dataset_gpt_concurrent.csv"
GPT_AUDIT = MASTER_DIR / "master_dataset_gpt_concurrent_audit.json"
GPT_FAIL = OUTDIR / "master_dataset_gpt_concurrent_failures.jsonl"

DS_MODEL = "deepseek-v4-pro"
GPT_MODEL = "gpt-5.5"

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
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
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
    if any(x in lowered for x in ["401", "authentication", "api key", "unauthorized", "missing scopes", "insufficient permissions"]):
        return "auth_error"
    if any(x in lowered for x in ["refusal", "content filter", "moderation", "blocked", "unsafe"]):
        return "safety_refusal"
    if "json" in lowered and "parse" in lowered:
        return "json_parse_error"
    return "failed"


def call_ds_official(
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
            if attempt < max_retries - 1:
                time.sleep(min(60, 2**attempt))
    return classify_error(last_error), None, last_error


def call_gpt(
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
            response = client.with_options(timeout=timeout).responses.create(
                model=model,
                instructions="你是法律文书结构化抽取助手。只输出严格 JSON，不输出解释。",
                input=prompt + "\n\n请输出 JSON。",
                text={"format": {"type": "json_object"}},
                max_output_tokens=max_tokens,
            )
            return "ok", parse_json_content(response.output_text), ""
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
        obj["_model_document_id"] = obj["document_id"]
        obj["document_id"] = expected_doc_id
    obj[f"_{provider}_meta"] = {
        "provider": provider,
        "model": model,
        "temperature": 0,
        "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "prompt_path": str(prompt_path),
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


def csv_columns(prefix: str) -> list[str]:
    return ["doc_id", f"{prefix}_status", f"{prefix}_error", f"{prefix}_model", f"{prefix}_temperature"] + [
        field.replace(".", "__") for field in CONTENT_FIELDS
    ]


def flatten_record(obj: dict[str, Any], *, prefix: str, model: str, status: str = "ok", error: str = "") -> dict[str, str]:
    row = {col: "" for col in csv_columns(prefix)}
    row["doc_id"] = str(obj.get("document_id") or "")
    row[f"{prefix}_status"] = status
    row[f"{prefix}_error"] = error
    row[f"{prefix}_model"] = model
    row[f"{prefix}_temperature"] = "0"
    for field in CONTENT_FIELDS:
        value = obj.get(field) if field in {"case_amount", "case_amount_type"} else get_path_value(obj, field)
        row[field.replace(".", "__")] = cell(value)
    return row


def write_flat_csv(jsonl_path: Path, csv_path: Path, *, prefix: str, model: str) -> int:
    rows = load_jsonl(jsonl_path)
    tmp_path = csv_path.with_suffix(".csv.tmp")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with tmp_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns(prefix))
        writer.writeheader()
        for obj in rows:
            writer.writerow(flatten_record(obj, prefix=prefix, model=model))
    shutil.move(str(tmp_path), str(csv_path))
    return len(rows)


def select_candidates(
    rows_by_doc: dict[str, dict[str, str]],
    texts: dict[str, str],
    existing_ok: set[str],
    doc_id: str,
    limit: int,
) -> list[str]:
    def is_vc_true(row: dict[str, str]) -> bool:
        marker = (row.get("vc_involved_dsv4_value") or "").strip().lower()
        return marker in {"true", "1", "yes", "y", "是"}

    if doc_id:
        if doc_id not in rows_by_doc:
            raise KeyError(f"doc_id not found in master table: {doc_id}")
        if doc_id not in texts:
            raise KeyError(f"doc_id has no source text: {doc_id}")
        if not is_vc_true(rows_by_doc[doc_id]):
            raise ValueError(f"doc_id is not vc_involved=true and will not be extracted: {doc_id}")
        return [] if doc_id in existing_ok else [doc_id]
    candidates = [
        doc_id
        for doc_id, row in rows_by_doc.items()
        if doc_id in texts and doc_id not in existing_ok and is_vc_true(row)
    ]
    if limit:
        candidates = candidates[:limit]
    return candidates


def provider_paths(provider: Literal["ds", "gpt"], args: argparse.Namespace) -> tuple[Path, Path, Path, Path, str, str]:
    if provider == "ds":
        return Path(args.ds_jsonl), Path(args.ds_csv), Path(args.ds_audit), Path(args.ds_fail), "ds", args.ds_model
    return Path(args.gpt_jsonl), Path(args.gpt_csv), Path(args.gpt_audit), Path(args.gpt_fail), "gpt", args.gpt_model


def run_provider(provider: Literal["ds", "gpt"], args: argparse.Namespace) -> dict[str, Any]:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    output_jsonl, output_csv, audit_path, fail_path, prefix, model = provider_paths(provider, args)

    master_rows = load_master(Path(args.master_path))
    texts = read_json(Path(args.texts_path))
    prompt_template = read_text(Path(args.prompt_path)).strip()
    rows_by_doc = {r["doc_id"]: r for r in master_rows if r.get("doc_id")}
    existing_rows = load_jsonl(output_jsonl)
    existing_ok = {str(row.get("document_id")) for row in existing_rows if row.get("document_id")}
    candidates = select_candidates(rows_by_doc, texts, existing_ok, args.doc_id, args.limit)

    if provider == "ds":
        client = OpenAI(api_key=get_api_key(Path(args.env_path), "ds"), base_url="https://api.deepseek.com", max_retries=0)
        call_fn = call_ds_official
        rpm, tpm = args.ds_rpm, args.ds_tpm
    else:
        client = OpenAI(api_key=get_api_key(Path(args.env_path), "gpt"), max_retries=0)
        call_fn = call_gpt
        rpm, tpm = args.gpt_rpm, args.gpt_tpm

    limiter = RateLimiter(rpm=rpm, tpm=tpm)
    write_lock = threading.Lock()
    fail_lock = threading.Lock()
    counters = {
        "submitted_this_run": 0,
        "ok_this_run": 0,
        "auth_errors_this_run": 0,
        "safety_refusals_this_run": 0,
        "json_parse_errors_this_run": 0,
        "failed_this_run": 0,
    }

    def work(doc_id: str) -> tuple[str, str]:
        prompt = render_prompt(prompt_template, rows_by_doc[doc_id], texts[doc_id] or "")
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
            append_jsonl(output_jsonl, validate_record(obj, doc_id, provider, model, Path(args.prompt_path)), write_lock)
        else:
            append_jsonl(
                fail_path,
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

    pbar = tqdm(total=len(candidates), desc=f"{provider.upper()} extraction")
    pending: dict[futures.Future[tuple[str, str]], str] = {}
    idx = 0
    stop_for_auth = False
    with futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        while (idx < len(candidates) and not stop_for_auth) or pending:
            while len(pending) < args.workers and idx < len(candidates) and not stop_for_auth:
                doc_id = candidates[idx]
                idx += 1
                counters["submitted_this_run"] += 1
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
                    append_jsonl(
                        fail_path,
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
                    counters["ok_this_run"] += 1
                elif status == "auth_error":
                    counters["auth_errors_this_run"] += 1
                    stop_for_auth = True
                elif status == "safety_refusal":
                    counters["safety_refusals_this_run"] += 1
                elif status == "json_parse_error":
                    counters["json_parse_errors_this_run"] += 1
                else:
                    counters["failed_this_run"] += 1
                pbar.update(1)
    pbar.close()

    csv_rows = write_flat_csv(output_jsonl, output_csv, prefix=prefix, model=model)
    final_rows = load_jsonl(output_jsonl)
    failures = load_jsonl(fail_path)
    audit = {
        "round": ROUND,
        "provider": provider,
        "model": model,
        "temperature": 0,
        "workers": args.workers,
        "prompt_path": str(args.prompt_path),
        "master_rows": len(master_rows),
        "existing_ok_before_run": len(existing_ok),
        **counters,
        "jsonl_rows": len(final_rows),
        "csv_rows": csv_rows,
        "failure_rows": len(failures),
        "output_jsonl": str(output_jsonl),
        "output_csv": str(output_csv),
        "fail_path": str(fail_path),
    }
    write_json(audit_path, audit)
    write_json(OUTDIR / f"{prefix}_audit.json", audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["ds", "gpt", "both"], default="both")
    parser.add_argument("--master-path", default=str(MASTER_PATH))
    parser.add_argument("--texts-path", default=str(TEXTS_PATH))
    parser.add_argument("--prompt-path", default=str(PROMPT_PATH))
    parser.add_argument("--env-path", default=str(ENV_PATH))
    parser.add_argument("--ds-jsonl", default=str(DS_JSONL))
    parser.add_argument("--ds-csv", default=str(DS_CSV))
    parser.add_argument("--ds-audit", default=str(DS_AUDIT))
    parser.add_argument("--ds-fail", default=str(DS_FAIL))
    parser.add_argument("--gpt-jsonl", default=str(GPT_JSONL))
    parser.add_argument("--gpt-csv", default=str(GPT_CSV))
    parser.add_argument("--gpt-audit", default=str(GPT_AUDIT))
    parser.add_argument("--gpt-fail", default=str(GPT_FAIL))
    parser.add_argument("--ds-model", default=DS_MODEL)
    parser.add_argument("--gpt-model", default=GPT_MODEL)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--ds-rpm", type=int, default=120)
    parser.add_argument("--ds-tpm", type=int, default=1_000_000)
    parser.add_argument("--gpt-rpm", type=int, default=60)
    parser.add_argument("--gpt-tpm", type=int, default=600_000)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--doc-id", default="")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    providers: list[Literal["ds", "gpt"]] = ["ds", "gpt"] if args.provider == "both" else [args.provider]  # type: ignore[list-item]
    for provider in providers:
        run_provider(provider, args)


if __name__ == "__main__":
    main()
