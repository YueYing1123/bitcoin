from __future__ import annotations

import argparse
import ast
import csv
import json
import random
import re
import time
from pathlib import Path
from typing import Any

import requests
from openai import OpenAI
from tqdm import tqdm


ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = ROOT.parent
ROUND = "round-11-20260518-221344"

MASTER_PATH = ROOT / "data" / "processed" / "master" / "master_dataset.csv"
TEXTS_PATH = ROOT / "data" / "raw" / "data-texts.json"
PROMPT_PATH = ROOT / "docs" / "legacy" / "master_prompt-260518.md"
LEGACY_API_PATH = next((ROOT / "docs" / "legacy").glob("*siliconflow.py"))
ENV_PATH = PROJECT_ROOT / ".env"
OUTDIR = ROOT / "result" / ROUND

SAMPLE_PATH = OUTDIR / "sample_10.json"
DSV4_JSONL = OUTDIR / "dsv4_outputs.jsonl"
GPT55_JSONL = OUTDIR / "gpt55_gold_outputs.jsonl"
FAIL_PATH = OUTDIR / "failures.jsonl"
FIELD_METRICS_CSV = OUTDIR / "field_f1.csv"
CASE_METRICS_CSV = OUTDIR / "case_field_scores.csv"
SUMMARY_JSON = OUTDIR / "summary.json"

DSV4_MODEL = "deepseek-ai/DeepSeek-V4-Flash"
GPT55_MODEL = "gpt-5.5"

EVAL_FIELDS = [
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
    "low_confidence_fields",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_jsonl(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")


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


def load_master(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
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
    out = template.replace("{{ document_id }}", row["doc_id"])
    out = out.replace("{{ document_text }}", doc_text)
    for key, value in meta.items():
        out = out.replace("{{ meta." + key + " }}", value)
    return out


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


def call_siliconflow_dsv4(
    *,
    api_url: str,
    api_key: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    max_retries: int,
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": DSV4_MODEL,
        "messages": [
            {"role": "system", "content": "你是法律文书结构化抽取助手。只输出严格 JSON，不输出解释。"},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": 0,
        "top_p": 1,
        "n": 1,
    }
    last_error = ""
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 200:
                content = response.json()["choices"][0]["message"]["content"]
                return parse_json_content(content)
            last_error = f"http_{response.status_code}: {response.text[:1000]}"
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < max_retries - 1:
            time.sleep(min(30, 2**attempt))
    raise RuntimeError(last_error)


def call_openai_gpt55(
    *,
    client: OpenAI,
    prompt: str,
    max_tokens: int,
    timeout: int,
    max_retries: int,
) -> dict[str, Any]:
    last_error = ""
    for attempt in range(max_retries):
        try:
            response = client.with_options(timeout=timeout).responses.create(
                model=GPT55_MODEL,
                instructions="你是法律文书结构化抽取助手。只输出严格 JSON，不输出解释。",
                input=prompt + "\n\n请输出 JSON。",
                text={"format": {"type": "json_object"}},
                max_output_tokens=max_tokens,
            )
            return parse_json_content(response.output_text)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < max_retries - 1:
            time.sleep(min(30, 2**attempt))
    raise RuntimeError(last_error)


def validate_record(obj: dict[str, Any], expected_doc_id: str, model: str) -> dict[str, Any]:
    obj["document_id"] = str(obj.get("document_id") or expected_doc_id)
    if obj["document_id"] != expected_doc_id:
        obj["_model_document_id"] = obj["document_id"]
        obj["document_id"] = expected_doc_id
    obj["_eval_meta"] = {
        "model": model,
        "temperature": 0,
        "extracted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return obj


def get_leaf_value(obj: dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if isinstance(cur, dict) and "value" in cur:
        return cur.get("value")
    return cur


def canonical_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return value
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return None
        return s
    return value


def canonical_value(value: Any) -> Any:
    value = canonical_scalar(value)
    if isinstance(value, list):
        return sorted({json.dumps(canonical_value(x), ensure_ascii=False, sort_keys=True) for x in value})
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def is_present(value: Any) -> bool:
    value = canonical_value(value)
    return value is not None and value != []


def values_equal(pred: Any, gold: Any) -> bool:
    return canonical_value(pred) == canonical_value(gold)


def compute_metrics(dsv4_rows: list[dict[str, Any]], gpt_rows: list[dict[str, Any]]) -> dict[str, Any]:
    dsv4_by_doc = {str(x.get("document_id")): x for x in dsv4_rows}
    gpt_by_doc = {str(x.get("document_id")): x for x in gpt_rows}
    docs = sorted(set(dsv4_by_doc) & set(gpt_by_doc))

    field_counts = {field: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for field in EVAL_FIELDS}
    case_rows = []
    for doc_id in docs:
        correct = 0
        total = 0
        for field in EVAL_FIELDS:
            pred = get_leaf_value(dsv4_by_doc[doc_id], field)
            gold = get_leaf_value(gpt_by_doc[doc_id], field)
            pred_present = is_present(pred)
            gold_present = is_present(gold)
            equal = values_equal(pred, gold)
            if pred_present and gold_present and equal:
                field_counts[field]["tp"] += 1
            elif pred_present and (not gold_present or not equal):
                field_counts[field]["fp"] += 1
                if gold_present:
                    field_counts[field]["fn"] += 1
            elif not pred_present and gold_present:
                field_counts[field]["fn"] += 1
            else:
                field_counts[field]["tn"] += 1
            correct += int(equal)
            total += 1
            case_rows.append(
                {
                    "doc_id": doc_id,
                    "field": field,
                    "match": int(equal),
                    "dsv4_value": json.dumps(canonical_value(pred), ensure_ascii=False),
                    "gpt55_gold_value": json.dumps(canonical_value(gold), ensure_ascii=False),
                }
            )
    metric_rows = []
    micro = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for field, counts in field_counts.items():
        tp, fp, fn, tn = counts["tp"], counts["fp"], counts["fn"], counts["tn"]
        for key in micro:
            micro[key] += counts[key]
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        accuracy = (tp + tn) / (tp + fp + fn + tn) if tp + fp + fn + tn else 0.0
        metric_rows.append(
            {
                "field": field,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "accuracy": accuracy,
            }
        )
    tp, fp, fn, tn = micro["tp"], micro["fp"], micro["fn"], micro["tn"]
    micro_precision = tp / (tp + fp) if tp + fp else 1.0
    micro_recall = tp / (tp + fn) if tp + fn else 1.0
    micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall) if micro_precision + micro_recall else 0.0
    macro_f1 = sum(row["f1"] for row in metric_rows) / len(metric_rows) if metric_rows else 0.0
    exact_matches = sum(row["match"] for row in case_rows)
    total_pairs = len(case_rows)
    return {
        "docs": docs,
        "field_metrics": metric_rows,
        "case_rows": case_rows,
        "summary": {
            "doc_count": len(docs),
            "field_count": len(EVAL_FIELDS),
            "micro_tp": tp,
            "micro_fp": fp,
            "micro_fn": fn,
            "micro_tn": tn,
            "micro_precision": micro_precision,
            "micro_recall": micro_recall,
            "micro_f1": micro_f1,
            "macro_f1": macro_f1,
            "exact_match_accuracy": exact_matches / total_pairs if total_pairs else 0.0,
            "exact_match_correct": exact_matches,
            "exact_match_total": total_pairs,
        },
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def select_sample(args: argparse.Namespace, master_rows: list[dict[str, str]], texts: dict[str, str]) -> list[dict[str, str]]:
    if args.reuse_sample and Path(args.sample_path).exists():
        ids = read_json(Path(args.sample_path))["doc_ids"]
        by_doc = {r["doc_id"]: r for r in master_rows}
        return [by_doc[x] for x in ids]
    candidates = [r for r in master_rows if r.get("doc_id") in texts]
    rng = random.Random(args.seed)
    sample = rng.sample(candidates, args.n)
    write_json(
        Path(args.sample_path),
        {
            "seed": args.seed,
            "n": args.n,
            "doc_ids": [r["doc_id"] for r in sample],
        },
    )
    return sample


def run(args: argparse.Namespace) -> dict[str, Any]:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    master_rows = load_master(Path(args.master_path))
    texts = read_json(Path(args.texts_path))
    prompt_template = read_text(Path(args.prompt_path)).strip()
    sample_rows = select_sample(args, master_rows, texts)
    sample_ids = [r["doc_id"] for r in sample_rows]

    dsv4_existing = {str(x.get("document_id")): x for x in load_jsonl(Path(args.dsv4_jsonl))}
    gpt_existing = {str(x.get("document_id")): x for x in load_jsonl(Path(args.gpt55_jsonl))}
    api_url = extract_literal_assignment(Path(args.legacy_api_path), "API_URL")
    silicon_key = extract_literal_assignment(Path(args.legacy_api_path), "API_KEY")
    openai_client = OpenAI(api_key=get_openai_api_key(Path(args.env_path)), max_retries=0)

    for row in tqdm(sample_rows, desc="10-case model comparison"):
        doc_id = row["doc_id"]
        prompt = render_prompt(prompt_template, row, texts[doc_id] or "")
        if doc_id not in dsv4_existing:
            try:
                obj = call_siliconflow_dsv4(
                    api_url=api_url,
                    api_key=silicon_key,
                    prompt=prompt,
                    max_tokens=args.max_tokens,
                    timeout=args.timeout,
                    max_retries=args.max_retries,
                )
                obj = validate_record(obj, doc_id, DSV4_MODEL)
                append_jsonl(Path(args.dsv4_jsonl), obj)
                dsv4_existing[doc_id] = obj
            except Exception as exc:
                append_jsonl(Path(args.fail_path), {"document_id": doc_id, "model": DSV4_MODEL, "error": str(exc)[:1200]})
        if doc_id not in gpt_existing:
            try:
                obj = call_openai_gpt55(
                    client=openai_client,
                    prompt=prompt,
                    max_tokens=args.max_tokens,
                    timeout=args.timeout,
                    max_retries=args.max_retries,
                )
                obj = validate_record(obj, doc_id, GPT55_MODEL)
                append_jsonl(Path(args.gpt55_jsonl), obj)
                gpt_existing[doc_id] = obj
            except Exception as exc:
                append_jsonl(Path(args.fail_path), {"document_id": doc_id, "model": GPT55_MODEL, "error": str(exc)[:1200]})

    dsv4_rows = [dsv4_existing[x] for x in sample_ids if x in dsv4_existing]
    gpt_rows = [gpt_existing[x] for x in sample_ids if x in gpt_existing]
    metrics = compute_metrics(dsv4_rows, gpt_rows)
    write_csv(
        Path(args.field_metrics_csv),
        metrics["field_metrics"],
        ["field", "tp", "fp", "fn", "tn", "precision", "recall", "f1", "accuracy"],
    )
    write_csv(
        Path(args.case_metrics_csv),
        metrics["case_rows"],
        ["doc_id", "field", "match", "dsv4_value", "gpt55_gold_value"],
    )
    summary = {
        "round": ROUND,
        "seed": args.seed,
        "sample_doc_ids": sample_ids,
        "dsv4_model": DSV4_MODEL,
        "gpt55_gold_model": GPT55_MODEL,
        "prompt_path": str(args.prompt_path),
        "outputs": {
            "sample": str(args.sample_path),
            "dsv4_jsonl": str(args.dsv4_jsonl),
            "gpt55_jsonl": str(args.gpt55_jsonl),
            "field_metrics_csv": str(args.field_metrics_csv),
            "case_metrics_csv": str(args.case_metrics_csv),
            "fail_path": str(args.fail_path),
        },
        **metrics["summary"],
    }
    write_json(Path(args.summary_json), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-path", default=str(MASTER_PATH))
    parser.add_argument("--texts-path", default=str(TEXTS_PATH))
    parser.add_argument("--prompt-path", default=str(PROMPT_PATH))
    parser.add_argument("--legacy-api-path", default=str(LEGACY_API_PATH))
    parser.add_argument("--env-path", default=str(ENV_PATH))
    parser.add_argument("--sample-path", default=str(SAMPLE_PATH))
    parser.add_argument("--dsv4-jsonl", default=str(DSV4_JSONL))
    parser.add_argument("--gpt55-jsonl", default=str(GPT55_JSONL))
    parser.add_argument("--fail-path", default=str(FAIL_PATH))
    parser.add_argument("--field-metrics-csv", default=str(FIELD_METRICS_CSV))
    parser.add_argument("--case-metrics-csv", default=str(CASE_METRICS_CSV))
    parser.add_argument("--summary-json", default=str(SUMMARY_JSON))
    parser.add_argument("--seed", type=int, default=20260518)
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--reuse-sample", action="store_true")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
