from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import re
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
ROUND = "round-20-20260519-manual-annotation"

DEFAULT_TEST_SET = ROOT / "result" / "round-22-20260519-vc-true-stratified-test-set" / "test_set_5pct_year_region_appeal_priority.csv"
DEFAULT_TEXTS = ROOT / "data" / "raw" / "data-texts.json"
DEFAULT_OUTDIR = ROOT / "result" / ROUND
DEFAULT_ANNOTATIONS = DEFAULT_OUTDIR / "manual_annotations.jsonl"
DEFAULT_STATE = DEFAULT_OUTDIR / "manual_annotations_state.json"
DEFAULT_ANNOTATION_TABLE = DEFAULT_OUTDIR / "manual_annotation_table.csv"
DEFAULT_BASELINE = DEFAULT_OUTDIR / "ds_v4_pro_testset_baseline.jsonl"
DEFAULT_GOLD_CSV = DEFAULT_OUTDIR / "manual_gold_standard_final.csv"
DEFAULT_GOLD_JSONL = DEFAULT_OUTDIR / "manual_gold_standard_final.jsonl"
DEFAULT_GOLD_METRICS = DEFAULT_OUTDIR / "manual_gold_standard_metrics.json"

PRIMARY_FIELDS = [
    {
        "key": "case_amount",
        "label": "案件金额",
        "type": "number",
        "source": "case_amount",
        "help": "人民币元；无法判断留空。",
    },
    {
        "key": "case_amount_type",
        "label": "金额类型",
        "type": "select",
        "source": "case_amount_type",
        "options": [
            "",
            "交易本金",
            "返还本金",
            "合同价款",
            "投资款",
            "借款本金",
            "购买价款",
            "原告诉请本金",
            "诈骗金额",
            "犯罪金额",
            "被害人损失",
            "违法所得",
            "支付结算金额",
            "掩隐金额",
            "涉案流水",
            "罚金",
            "其他",
        ],
    },
    {
        "key": "contract_validity",
        "label": "合同效力",
        "type": "select",
        "source": "judicial_analysis__contract_validity",
        "options": ["", "有效", "无效", "未成立", "部分有效", "部分无效", "不受法律保护", "不适用", "未明确"],
    },
    {
        "key": "activity_types",
        "label": "涉币活动类型",
        "type": "multi",
        "source": "virtual_currency_info__activity_type",
        "options": [
            "挖矿",
            "场外交易OTC",
            "交易所交易",
            "买卖/兑换",
            "虚拟货币借贷",
            "委托理财/代投",
            "技术服务",
            "发币/ICO",
            "赌博",
            "洗钱/掩隐",
            "帮助信息网络犯罪活动",
            "诈骗",
            "传销",
            "支付结算",
            "其他",
        ],
    },
]

SECONDARY_FIELDS = [
    {"key": "court_level", "label": "法院层级", "type": "select", "source": "metadata__court_level", "options": ["", "最高人民法院", "高级法院", "中级法院", "基层法院", "专门法院", "其他", "未明确"]},
    {"key": "judgment_date", "label": "裁判日期", "type": "text", "source": "metadata__judgment_date"},
    {"key": "region", "label": "省级地区", "type": "text", "source": "metadata__region"},
    {"key": "case_type_primary", "label": "案件类型", "type": "select", "source": "case_profile__case_type_primary", "options": ["", "民事", "刑事", "行政", "执行", "其他", "未明确"]},
    {"key": "case_type_secondary", "label": "具体案由", "type": "text", "source": "case_profile__case_type_secondary"},
    {"key": "procedure_stage", "label": "程序阶段", "type": "select", "source": "case_profile__procedure_stage", "options": ["", "一审", "二审", "再审", "执行", "审判监督", "其他", "未明确"]},
    {"key": "is_appeal", "label": "是否上诉", "type": "select", "source": "case_profile__is_appeal", "options": ["", "true", "false"]},
    {"key": "currency_types", "label": "币种", "type": "list_text", "source": "virtual_currency_info__currency_types"},
    {"key": "legal_characterization", "label": "法律定性", "type": "text", "source": "judicial_analysis__legal_characterization"},
    {"key": "virtual_currency_property_status", "label": "财产属性", "type": "select", "source": "judicial_analysis__virtual_currency_property_legality", "options": ["", "网络虚拟财产", "虚拟财产", "特定虚拟商品", "财产利益", "数据权益", "不具有法偿性", "非货币", "不属于法定货币", "未明确"]},
    {"key": "transaction_legality_assessment", "label": "交易合法性", "type": "select", "source": "judicial_analysis__transaction_legality_assessment", "options": ["", "合法有效", "合同无效", "不受法律保护", "非法金融活动", "违反监管政策", "违背公序良俗", "涉嫌犯罪", "风险自担", "未明确", "不适用"]},
    {"key": "reasons_for_invalidity_or_no_protection", "label": "无效/不保护理由", "type": "multi", "source": "judicial_analysis__reason_for_invalidity", "options": ["违反法律强制性规定", "违背公序良俗", "扰乱金融秩序", "扰乱货币秩序", "违反金融监管政策", "非法金融活动", "非法债务", "不属于民事案件受理范围", "涉嫌犯罪", "证据不足", "请求权基础不成立", "投资风险自担", "不具有法偿性", "不属于法定货币", "其他"]},
    {"key": "cited_policies", "label": "监管政策", "type": "list_text", "source": "judicial_analysis__cited_policies"},
    {"key": "policy_labels", "label": "政策标签", "type": "multi", "source": "judicial_analysis__policy_labels", "options": ["2013五部委通知", "2017九四公告", "2021九二四通知", "挖矿整治文件", "地方监管文件", "其他"]},
    {"key": "judicial_framing", "label": "司法裁判框架", "type": "multi", "source": "judicial_analysis__judicial_framing", "options": ["风险自担", "非法债务", "不受法律保护", "合同无效", "返还本金", "折价赔偿", "财产属性保护", "证据不足", "刑民交叉", "移送公安", "涉嫌犯罪", "扰乱金融秩序", "扰乱货币秩序", "违背公序良俗", "违反强制性规定", "监管政策影响私法效力", "请求权基础不成立", "其他"]},
]

ALL_FIELDS = PRIMARY_FIELDS + SECONDARY_FIELDS
FIELD_KEYS = {field["key"] for field in ALL_FIELDS}
LIST_FIELD_KEYS = {field["key"] for field in ALL_FIELDS if field["type"] in {"multi", "list_text"}}
NUMERIC_FIELD_KEYS = {"case_amount"}
BOOLEAN_FIELD_KEYS = {"is_appeal"}

FIELD_BASELINE_PATHS = {
    "case_amount": ["case_amount"],
    "case_amount_type": ["case_amount_type"],
    "contract_validity": ["judicial_analysis.contract_validity"],
    "activity_types": ["virtual_currency_info.activity_types", "virtual_currency_info.activity_type"],
    "court_level": ["metadata.court_level"],
    "judgment_date": ["metadata.judgment_date"],
    "region": ["metadata.region"],
    "case_type_primary": ["case_profile.case_type_primary"],
    "case_type_secondary": ["case_profile.case_type_secondary"],
    "procedure_stage": ["case_profile.procedure_stage"],
    "is_appeal": ["case_profile.is_appeal"],
    "currency_types": ["virtual_currency_info.currency_types"],
    "legal_characterization": ["judicial_analysis.legal_characterization"],
    "virtual_currency_property_status": [
        "judicial_analysis.virtual_currency_property_status",
        "judicial_analysis.virtual_currency_property_legality",
    ],
    "transaction_legality_assessment": ["judicial_analysis.transaction_legality_assessment"],
    "reasons_for_invalidity_or_no_protection": [
        "judicial_analysis.reasons_for_invalidity_or_no_protection",
        "judicial_analysis.reason_for_invalidity",
    ],
    "cited_policies": ["judicial_analysis.cited_policies"],
    "policy_labels": ["judicial_analysis.policy_labels"],
    "judicial_framing": ["judicial_analysis.judicial_framing"],
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_list_cell(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x) for x in parsed if str(x).strip()]
    except json.JSONDecodeError:
        pass
    return [x.strip() for x in re.split(r"[;；,，、\n]+", text) if x.strip()]


def get_prediction(row: dict[str, str], field: dict[str, Any]) -> Any:
    raw = row.get(field["source"], "")
    if field["type"] in {"multi", "list_text"}:
        return parse_list_cell(raw)
    if field["key"] == "is_appeal":
        if str(raw).strip() in {"1", "true", "True", "是"}:
            return "true"
        if str(raw).strip() in {"0", "false", "False", "否"}:
            return "false"
    return raw


def load_annotations(path: Path) -> dict[str, dict[str, Any]]:
    annotations: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return annotations
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            doc_id = str(obj.get("doc_id") or "")
            if doc_id:
                annotations[doc_id] = obj
    return annotations


def load_jsonl_by_document_id(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            doc_id = str(obj.get("document_id") or obj.get("doc_id") or "")
            if doc_id:
                rows[doc_id] = obj
    return rows


def get_path_value(obj: dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if isinstance(cur, dict) and "value" in cur:
        return cur.get("value")
    return cur


def coerce_field_value(field: dict[str, Any], value: Any) -> Any:
    key = field["key"]
    if isinstance(value, dict) and "value" in value:
        value = value.get("value")
    if key in LIST_FIELD_KEYS:
        return parse_list_cell(value)
    if key in BOOLEAN_FIELD_KEYS:
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y", "是"}:
            return "true"
        if text in {"0", "false", "no", "n", "否"}:
            return "false"
        return "" if value in {None, ""} else str(value)
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def baseline_fields_from_record(record: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for field in ALL_FIELDS:
        value = None
        found = False
        for path in FIELD_BASELINE_PATHS[field["key"]]:
            value = get_path_value(record, path) if "." in path else record.get(path)
            if value is not None:
                found = True
                break
        if found:
            fields[field["key"]] = coerce_field_value(field, value)
        elif field["key"] in LIST_FIELD_KEYS:
            fields[field["key"]] = []
        else:
            fields[field["key"]] = ""
    return fields


def empty_field_values() -> dict[str, Any]:
    return {field["key"]: [] if field["key"] in LIST_FIELD_KEYS else "" for field in ALL_FIELDS}


def load_baselines(path: Path) -> dict[str, dict[str, Any]]:
    records = load_jsonl_by_document_id(path)
    return {doc_id: baseline_fields_from_record(record) for doc_id, record in records.items()}


def write_annotation(path: Path, obj: dict[str, Any], lock: threading.Lock) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with lock:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def write_state(path: Path, payload: dict[str, Any], lock: threading.Lock) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with lock:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def table_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def current_gold_fields(doc_id: str, baseline: dict[str, Any], annotations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fields = dict(baseline)
    annotation = annotations.get(doc_id)
    manual_fields = annotation.get("fields") if annotation else None
    if isinstance(manual_fields, dict):
        fields.update(manual_fields)
    return fields


def normalized_scalar(field_key: str, value: Any) -> str | None:
    if isinstance(value, dict) and "value" in value:
        value = value.get("value")
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        value = " ".join(str(x) for x in value)
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"none", "null", "nan", "未明确", "不明确", "无法判断"}:
        return None
    if field_key in NUMERIC_FIELD_KEYS:
        cleaned = re.sub(r"[,，\s元人民币]", "", text)
        try:
            return str(round(float(cleaned), 6)).rstrip("0").rstrip(".")
        except ValueError:
            return text
    if field_key in BOOLEAN_FIELD_KEYS:
        if lowered in {"1", "true", "yes", "y", "是"}:
            return "true"
        if lowered in {"0", "false", "no", "n", "否"}:
            return "false"
    return re.sub(r"\s+", "", text)


def value_items(field_key: str, value: Any) -> set[str]:
    if field_key in LIST_FIELD_KEYS:
        raw_items = parse_list_cell(value)
        return {norm for item in raw_items if (norm := normalized_scalar(field_key, item))}
    norm = normalized_scalar(field_key, value)
    return {norm} if norm else set()


def prf(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def compute_metrics(rows: list[dict[str, str]], baselines: dict[str, dict[str, Any]], annotations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    field_rows: list[dict[str, Any]] = []
    total = {"tp": 0, "fp": 0, "fn": 0, "docs": 0, "exact_docs": 0}
    scored_rows = [row for row in rows if str(row.get("doc_id") or "") in baselines]
    for group_name, group_fields in [("primary", PRIMARY_FIELDS), ("secondary", SECONDARY_FIELDS)]:
        for field in group_fields:
            counts = {"tp": 0, "fp": 0, "fn": 0, "docs": 0, "exact_docs": 0}
            key = field["key"]
            for row in scored_rows:
                doc_id = str(row.get("doc_id") or "")
                baseline = baselines[doc_id]
                gold = current_gold_fields(doc_id, baseline, annotations)
                pred_items = value_items(key, baseline.get(key))
                gold_items = value_items(key, gold.get(key))
                counts["tp"] += len(pred_items & gold_items)
                counts["fp"] += len(pred_items - gold_items)
                counts["fn"] += len(gold_items - pred_items)
                counts["docs"] += 1
                if pred_items == gold_items:
                    counts["exact_docs"] += 1
            metric = {**counts, **prf(counts["tp"], counts["fp"], counts["fn"])}
            metric["field"] = key
            metric["label"] = field["label"]
            metric["group"] = group_name
            metric["kind"] = "list" if key in LIST_FIELD_KEYS else "scalar"
            metric["exact_match_rate"] = counts["exact_docs"] / counts["docs"] if counts["docs"] else 1.0
            field_rows.append(metric)
            for k in total:
                total[k] += counts[k]

    groups: dict[str, Any] = {}
    for name, fields in {
        "primary": [f["key"] for f in PRIMARY_FIELDS],
        "secondary": [f["key"] for f in SECONDARY_FIELDS],
        "all": [f["key"] for f in ALL_FIELDS],
    }.items():
        selected = [r for r in field_rows if r["field"] in fields]
        tp = sum(int(r["tp"]) for r in selected)
        fp = sum(int(r["fp"]) for r in selected)
        fn = sum(int(r["fn"]) for r in selected)
        docs = sum(int(r["docs"]) for r in selected)
        exact_docs = sum(int(r["exact_docs"]) for r in selected)
        groups[name] = {
            "field_count": len(selected),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            **prf(tp, fp, fn),
            "macro_f1": sum(float(r["f1"]) for r in selected) / len(selected) if selected else 1.0,
            "exact_match_rate": exact_docs / docs if docs else 1.0,
        }

    return {
        "case_count": len(rows),
        "scored_case_count": len(scored_rows),
        "annotated_count": len(annotations),
        "baseline_count": len(baselines),
        "baseline_complete": len(baselines) >= len(rows) and len(rows) > 0,
        "micro": {**total, **prf(total["tp"], total["fp"], total["fn"])},
        "groups": groups,
        "fields": field_rows,
    }


def write_annotation_table(
    test_set: Path,
    annotations_path: Path,
    table_path: Path,
    lock: threading.Lock | None = None,
    baseline_path: Path | None = None,
) -> None:
    rows = read_csv(test_set)
    baselines = load_baselines(baseline_path) if baseline_path else {}
    generated_columns = ["annotation_saved_at"]
    generated_columns.extend(f"manual__{field['key']}" for field in ALL_FIELDS)
    generated_columns.append("annotation_notes")
    generated_columns.extend(f"gold__{field['key']}" for field in ALL_FIELDS)
    generated_columns.append("annotated")

    base_columns = []
    if rows:
        base_columns = [key for key in rows[0].keys() if key not in set(generated_columns)]
    fieldnames = base_columns + generated_columns

    def write_locked() -> None:
        annotations = load_annotations(annotations_path)
        table_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = table_path.with_suffix(table_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                doc_id = str(row.get("doc_id") or "")
                annotation = annotations.get(doc_id)
                fields = annotation.get("fields") if annotation else {}
                if not isinstance(fields, dict):
                    fields = {}
                baseline = baselines.get(doc_id) or empty_field_values()
                gold = current_gold_fields(doc_id, baseline, annotations)
                out = {key: row.get(key, "") for key in base_columns}
                out["annotation_saved_at"] = table_cell(annotation.get("saved_at")) if annotation else ""
                for field in ALL_FIELDS:
                    out[f"manual__{field['key']}"] = table_cell(fields.get(field["key"]))
                out["annotation_notes"] = table_cell(annotation.get("notes")) if annotation else ""
                for field in ALL_FIELDS:
                    out[f"gold__{field['key']}"] = table_cell(gold.get(field["key"]))
                out["annotated"] = "1" if annotation else "0"
                writer.writerow(out)
        tmp.replace(table_path)

    if lock is None:
        write_locked()
    else:
        with lock:
            write_locked()


def write_final_gold(
    test_set: Path,
    annotations_path: Path,
    baseline_path: Path,
    csv_path: Path,
    jsonl_path: Path,
    metrics_path: Path,
    lock: threading.Lock | None = None,
) -> dict[str, Any]:
    rows = read_csv(test_set)
    baselines = load_baselines(baseline_path)

    def write_locked() -> dict[str, Any]:
        annotations = load_annotations(annotations_path)
        metrics = compute_metrics(rows, baselines, annotations)
        generated_columns = ["gold_source", "annotation_saved_at"]
        generated_columns.extend(f"gold__{field['key']}" for field in ALL_FIELDS)
        base_columns = []
        if rows:
            base_columns = [key for key in rows[0].keys() if key not in set(generated_columns)]
        fieldnames = base_columns + generated_columns
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_csv = csv_path.with_suffix(csv_path.suffix + ".tmp")
        tmp_jsonl = jsonl_path.with_suffix(jsonl_path.suffix + ".tmp")
        with tmp_csv.open("w", encoding="utf-8-sig", newline="") as f_csv, tmp_jsonl.open("w", encoding="utf-8") as f_jsonl:
            writer = csv.DictWriter(f_csv, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                doc_id = str(row.get("doc_id") or "")
                baseline = baselines.get(doc_id) or empty_field_values()
                annotation = annotations.get(doc_id)
                gold = current_gold_fields(doc_id, baseline, annotations)
                out = {key: row.get(key, "") for key in base_columns}
                out["gold_source"] = "manual" if annotation else "ds_v4_pro_baseline"
                out["annotation_saved_at"] = table_cell(annotation.get("saved_at")) if annotation else ""
                for field in ALL_FIELDS:
                    out[f"gold__{field['key']}"] = table_cell(gold.get(field["key"]))
                writer.writerow(out)
                f_jsonl.write(
                    json.dumps(
                        {
                            "doc_id": doc_id,
                            "gold_source": out["gold_source"],
                            "annotation_saved_at": out["annotation_saved_at"],
                            "fields": gold,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
        tmp_csv.replace(csv_path)
        tmp_jsonl.replace(jsonl_path)
        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "ok": True,
            "count": len(rows),
            "annotated_count": len(load_annotations(annotations_path)),
            "csv_path": str(csv_path),
            "jsonl_path": str(jsonl_path),
            "metrics_path": str(metrics_path),
            "metrics": metrics,
        }

    if lock is None:
        return write_locked()
    with lock:
        return write_locked()


def make_app_state(test_set: Path, texts_path: Path, annotations_path: Path, baseline_path: Path) -> dict[str, Any]:
    rows = read_csv(test_set)
    texts = read_json(texts_path)
    annotations = load_annotations(annotations_path)
    baselines = load_baselines(baseline_path)
    cases = []
    for i, row in enumerate(rows):
        doc_id = row["doc_id"]
        prediction = baselines.get(doc_id) or empty_field_values()
        cases.append(
            {
                "index": i,
                "doc_id": doc_id,
                "title": row.get("metadata__case_number") or doc_id,
                "court": row.get("metadata__court_name") or "",
                "year": row.get("test_sample_year") or "",
                "region": row.get("test_sample_region") or row.get("metadata__region") or "",
                "stage": row.get("test_sample_stage") or row.get("case_profile__procedure_stage") or "",
                "case_type": row.get("case_profile__case_type_secondary") or row.get("case_profile__case_type_primary") or "",
                "prediction": prediction,
                "baseline_ready": doc_id in baselines,
                "source": {},
                "text": texts.get(doc_id, ""),
                "annotation": annotations.get(doc_id),
            }
        )
    metrics = compute_metrics(rows, baselines, annotations)
    return {
        "round": ROUND,
        "case_count": len(cases),
        "annotated_count": len(annotations),
        "baseline_count": len(baselines),
        "baseline_complete": len(baselines) >= len(cases) and len(cases) > 0,
        "baseline_path": str(baseline_path),
        "metrics": metrics,
        "fields": {"primary": PRIMARY_FIELDS, "secondary": SECONDARY_FIELDS},
        "cases": cases,
    }


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>测试集人工标注</title>
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>
  <div id="app">
    <aside class="sidebar">
      <div class="brand">
        <h1>测试集标注</h1>
        <div id="progressText" class="muted">加载中</div>
        <div id="scoreSummary" class="score-summary"></div>
      </div>
      <div class="toolbar">
        <input id="searchInput" type="search" placeholder="检索案号、地区、案由、正文" />
        <select id="statusFilter">
          <option value="all">全部</option>
          <option value="todo">未标</option>
          <option value="done">已标</option>
        </select>
      </div>
      <div id="caseList" class="case-list"></div>
    </aside>

    <main class="main">
      <section class="topbar">
        <button id="prevBtn" type="button" title="上一个">‹</button>
        <button id="nextBtn" type="button" title="下一个">›</button>
        <div class="case-head">
          <div id="caseTitle" class="case-title">请选择案件</div>
          <div id="caseMeta" class="case-meta"></div>
        </div>
        <button id="saveBtn" class="primary" type="button">保存</button>
        <button id="copyPredBtn" type="button">复制模型值</button>
        <button id="exportBtn" type="button">导出</button>
      </section>
      <section id="metricsPanel" class="metrics-panel"></section>

      <section class="workspace">
        <article class="document-pane">
          <div class="pane-header">
            <strong>裁判文书</strong>
            <input id="textSearchInput" type="search" placeholder="文内搜索" />
          </div>
          <pre id="documentText"></pre>
        </article>

        <section class="form-pane">
          <div class="tabs">
            <button class="tab active" data-tab="primary" type="button">重点字段</button>
            <button class="tab" data-tab="secondary" type="button">次重点字段</button>
            <button class="tab" data-tab="notes" type="button">备注</button>
          </div>
          <form id="annotationForm"></form>
        </section>
      </section>
    </main>
  </div>
  <div id="toast"></div>
  <script src="/static/app.js"></script>
</body>
</html>
"""


STYLE_CSS = r"""
:root {
  --bg: #f7f8fa;
  --panel: #ffffff;
  --line: #d9dee7;
  --text: #1d2430;
  --muted: #657182;
  --accent: #2367d1;
  --accent-dark: #194f9f;
  --warn: #b15d00;
  --done: #1f7a4d;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
}
button, input, select, textarea { font: inherit; }
button {
  border: 1px solid var(--line);
  background: #fff;
  color: var(--text);
  border-radius: 6px;
  padding: 7px 10px;
  cursor: pointer;
}
button:hover { border-color: #aab4c4; }
button.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
button.primary:hover { background: var(--accent-dark); }
input, select, textarea {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  color: var(--text);
  padding: 8px 10px;
  min-width: 0;
}
#app {
  display: grid;
  grid-template-columns: 330px minmax(0, 1fr);
  height: 100vh;
}
.sidebar {
  border-right: 1px solid var(--line);
  background: var(--panel);
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.brand { padding: 16px; border-bottom: 1px solid var(--line); }
.brand h1 {
  margin: 0 0 6px;
  font-size: 19px;
  font-weight: 650;
}
.muted { color: var(--muted); }
.score-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin-top: 10px;
}
.score-chip {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px 7px;
  background: #f8fafc;
}
.score-label {
  display: block;
  color: var(--muted);
  font-size: 11px;
}
.score-value {
  display: block;
  font-weight: 700;
  color: #172033;
}
.toolbar {
  display: grid;
  grid-template-columns: 1fr 88px;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid var(--line);
}
.case-list {
  overflow: auto;
  padding: 8px;
}
.case-item {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 7px;
  padding: 9px;
  margin-bottom: 6px;
  background: transparent;
}
.case-item.active {
  border-color: #8eb5f0;
  background: #edf4ff;
}
.case-item.done .case-num::after {
  content: "已标";
  float: right;
  color: var(--done);
  font-size: 12px;
}
.case-num {
  font-weight: 650;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.case-sub {
  color: var(--muted);
  font-size: 12px;
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 62px;
  background: var(--panel);
  border-bottom: 1px solid var(--line);
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto auto auto;
  gap: 8px;
  align-items: center;
  padding: 10px 14px;
}
.case-head { min-width: 0; }
.case-title {
  font-weight: 650;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.case-meta {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.metrics-panel {
  background: #fbfcfe;
  border-bottom: 1px solid var(--line);
  display: grid;
  grid-template-columns: 250px 250px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 10px 14px;
}
.metric-card {
  border: 1px solid var(--line);
  border-radius: 7px;
  background: #fff;
  padding: 8px 10px;
}
.metric-card strong {
  display: block;
  margin-bottom: 3px;
}
.field-score-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 6px;
}
.field-score {
  border: 1px solid #e2e7ef;
  border-radius: 6px;
  padding: 5px 6px;
  min-width: 0;
}
.field-score b,
.field-score span {
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.field-score b { font-size: 12px; }
.field-score span { color: var(--muted); font-size: 11px; }
.workspace {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(420px, 1fr) minmax(430px, 520px);
  gap: 0;
  flex: 1;
}
.document-pane,
.form-pane {
  min-width: 0;
  min-height: 0;
  background: var(--panel);
}
.document-pane {
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
}
.pane-header {
  height: 50px;
  border-bottom: 1px solid var(--line);
  display: grid;
  grid-template-columns: 1fr 210px;
  gap: 10px;
  align-items: center;
  padding: 8px 12px;
}
#documentText {
  margin: 0;
  padding: 16px 18px 40px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: "Microsoft YaHei", system-ui, sans-serif;
  line-height: 1.75;
  flex: 1;
}
mark {
  background: #ffe48a;
  padding: 1px 2px;
  border-radius: 2px;
}
.form-pane {
  display: flex;
  flex-direction: column;
}
.tabs {
  display: flex;
  gap: 6px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
}
.tab.active {
  background: #edf4ff;
  border-color: #8eb5f0;
  color: var(--accent-dark);
}
#annotationForm {
  overflow: auto;
  padding: 12px;
}
.field-card {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px;
  margin-bottom: 10px;
  background: #fff;
}
.field-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 7px;
}
.field-label {
  font-weight: 650;
}
.field-key {
  color: var(--muted);
  font-size: 12px;
}
.prediction {
  color: var(--muted);
  font-size: 12px;
  border-left: 3px solid #cad3e1;
  padding-left: 8px;
  margin: 6px 0 8px;
  word-break: break-word;
}
.field-input {
  width: 100%;
}
.multi-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 8px;
}
.check-row {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #293241;
}
.check-row input { padding: 0; }
.notes-area {
  width: 100%;
  min-height: 160px;
  resize: vertical;
}
#toast {
  position: fixed;
  right: 18px;
  bottom: 18px;
  background: #1d2430;
  color: #fff;
  padding: 10px 13px;
  border-radius: 7px;
  opacity: 0;
  transform: translateY(8px);
  transition: 160ms ease;
  pointer-events: none;
}
#toast.show {
  opacity: 1;
  transform: translateY(0);
}
@media (max-width: 1100px) {
  #app { grid-template-columns: 280px minmax(0, 1fr); }
  .metrics-panel { grid-template-columns: 1fr; }
  .field-score-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workspace { grid-template-columns: 1fr; }
  .form-pane { border-top: 1px solid var(--line); }
}
"""


APP_JS = r"""
let state = null;
let cases = [];
let filtered = [];
let currentIndex = 0;
let activeTab = "primary";

const $ = (id) => document.getElementById(id);

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 1600);
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}

function normalizeText(v) {
  if (Array.isArray(v)) return v.join("、");
  if (v === null || v === undefined) return "";
  return String(v);
}

function pct(v) {
  if (!Number.isFinite(Number(v))) return "100.0%";
  return `${(Number(v) * 100).toFixed(1)}%`;
}

function allFields() {
  return [...state.fields.primary, ...state.fields.secondary];
}

function listFieldKeys() {
  return new Set(allFields().filter(f => f.type === "multi" || f.type === "list_text").map(f => f.key));
}

function normalizeItem(key, value) {
  if (value && typeof value === "object" && !Array.isArray(value) && Object.prototype.hasOwnProperty.call(value, "value")) {
    value = value.value;
  }
  if (value === null || value === undefined) return null;
  if (Array.isArray(value)) value = value.join(" ");
  let text = String(value).trim();
  if (!text) return null;
  const lowered = text.toLowerCase();
  if (["none", "null", "nan", "未明确", "不明确", "无法判断"].includes(lowered)) return null;
  if (key === "case_amount") {
    const numeric = Number(text.replace(/[,，\s元人民币]/g, ""));
    if (Number.isFinite(numeric)) return String(Math.round(numeric * 1000000) / 1000000).replace(/\.0+$/, "");
  }
  if (key === "is_appeal") {
    if (["1", "true", "yes", "y", "是"].includes(lowered)) return "true";
    if (["0", "false", "no", "n", "否"].includes(lowered)) return "false";
  }
  return text.replace(/\s+/g, "");
}

function parseListValue(value) {
  if (Array.isArray(value)) return value;
  if (value === null || value === undefined) return [];
  const text = String(value).trim();
  if (!text) return [];
  try {
    const parsed = JSON.parse(text);
    if (Array.isArray(parsed)) return parsed;
  } catch (_err) {}
  return text.split(/[;；,，、\n]+/).map(x => x.trim()).filter(Boolean);
}

function valueItems(key, value) {
  if (listFieldKeys().has(key)) {
    return new Set(parseListValue(value).map(x => normalizeItem(key, x)).filter(Boolean));
  }
  const norm = normalizeItem(key, value);
  return norm ? new Set([norm]) : new Set();
}

function currentGold(c) {
  return {...(c.prediction || {}), ...(c.annotation?.fields || {})};
}

function scoreCounts(predItems, goldItems) {
  let tp = 0;
  predItems.forEach(x => { if (goldItems.has(x)) tp += 1; });
  const fp = [...predItems].filter(x => !goldItems.has(x)).length;
  const fn = [...goldItems].filter(x => !predItems.has(x)).length;
  return {tp, fp, fn, exact: predItems.size === goldItems.size && tp === predItems.size};
}

function prf(tp, fp, fn) {
  const precision = tp + fp ? tp / (tp + fp) : 1;
  const recall = tp + fn ? tp / (tp + fn) : 1;
  const f1 = precision + recall ? 2 * precision * recall / (precision + recall) : 0;
  return {precision, recall, f1};
}

function computeClientMetrics() {
  const fieldRows = [];
  ["primary", "secondary"].forEach(group => {
    state.fields[group].forEach(field => {
      const counts = {tp: 0, fp: 0, fn: 0, docs: 0, exact_docs: 0};
      cases.forEach(c => {
        const pred = valueItems(field.key, c.prediction?.[field.key]);
        const gold = valueItems(field.key, currentGold(c)[field.key]);
        const one = scoreCounts(pred, gold);
        counts.tp += one.tp;
        counts.fp += one.fp;
        counts.fn += one.fn;
        counts.docs += 1;
        if (one.exact) counts.exact_docs += 1;
      });
      fieldRows.push({
        field: field.key,
        label: field.label,
        group,
        ...counts,
        ...prf(counts.tp, counts.fp, counts.fn),
        exact_match_rate: counts.docs ? counts.exact_docs / counts.docs : 1,
      });
    });
  });
  const groupMetrics = {};
  [["primary", state.fields.primary.map(f => f.key)], ["secondary", state.fields.secondary.map(f => f.key)], ["all", allFields().map(f => f.key)]].forEach(([name, keys]) => {
    const selected = fieldRows.filter(r => keys.includes(r.field));
    const tp = selected.reduce((s, r) => s + r.tp, 0);
    const fp = selected.reduce((s, r) => s + r.fp, 0);
    const fn = selected.reduce((s, r) => s + r.fn, 0);
    const docs = selected.reduce((s, r) => s + r.docs, 0);
    const exact = selected.reduce((s, r) => s + r.exact_docs, 0);
    groupMetrics[name] = {
      field_count: selected.length,
      tp, fp, fn,
      ...prf(tp, fp, fn),
      macro_f1: selected.length ? selected.reduce((s, r) => s + r.f1, 0) / selected.length : 1,
      exact_match_rate: docs ? exact / docs : 1,
    };
  });
  return {
    case_count: cases.length,
    annotated_count: cases.filter(isDone).length,
    baseline_count: cases.filter(c => c.baseline_ready).length,
    groups: groupMetrics,
    fields: fieldRows,
  };
}

function currentCase() {
  return cases[currentIndex] || null;
}

function annotationFor(c) {
  return c.annotation?.fields || {};
}

function fieldValue(c, field) {
  const ann = annotationFor(c);
  if (Object.prototype.hasOwnProperty.call(ann, field.key)) return ann[field.key];
  return c.prediction[field.key] ?? (field.type === "multi" || field.type === "list_text" ? [] : "");
}

function isDone(c) {
  return Boolean(c.annotation?.saved_at);
}

function renderProgress() {
  const done = cases.filter(isDone).length;
  $("progressText").textContent = `${done}/${cases.length} 已标注`;
  const baselineReady = Boolean(state?.baseline_complete);
  $("progressText").title = baselineReady ? "基线已完成" : "等待 DS-v4-pro 基线完成";
  $("saveBtn").disabled = !baselineReady;
  $("exportBtn").disabled = !baselineReady;
  renderMetrics();
}

function renderMetrics() {
  if (!state || !cases.length) return;
  const metrics = computeClientMetrics();
  const all = metrics.groups.all || {};
  const primary = metrics.groups.primary || {};
  const secondary = metrics.groups.secondary || {};
  $("scoreSummary").innerHTML = `
    <div class="score-chip"><span class="score-label">总体 F1</span><span class="score-value">${pct(all.f1)}</span></div>
    <div class="score-chip"><span class="score-label">重点 F1</span><span class="score-value">${pct(primary.f1)}</span></div>
    <div class="score-chip"><span class="score-label">次重点 F1</span><span class="score-value">${pct(secondary.f1)}</span></div>
    <div class="score-chip"><span class="score-label">基线</span><span class="score-value">${metrics.baseline_count}/${metrics.case_count}</span></div>
  `;
  const weak = metrics.fields
    .slice()
    .sort((a, b) => a.f1 - b.f1 || a.field.localeCompare(b.field))
    .slice(0, 8);
  $("metricsPanel").innerHTML = `
    <div class="metric-card">
      <strong>总体</strong>
      <div>Micro F1 ${pct(all.f1)}，Macro F1 ${pct(all.macro_f1)}</div>
      <div class="muted">TP/FP/FN ${all.tp ?? 0}/${all.fp ?? 0}/${all.fn ?? 0}</div>
    </div>
    <div class="metric-card">
      <strong>分组</strong>
      <div>重点 ${pct(primary.f1)}，精确 ${pct(primary.exact_match_rate)}</div>
      <div>次重点 ${pct(secondary.f1)}，精确 ${pct(secondary.exact_match_rate)}</div>
    </div>
    <div class="field-score-grid">
      ${weak.map(r => `
        <div class="field-score" title="${escapeHtml(r.field)}">
          <b>${escapeHtml(r.label || r.field)}</b>
          <span>${escapeHtml(r.group)} F1 ${pct(r.f1)} · ${r.tp}/${r.fp}/${r.fn}</span>
        </div>
      `).join("")}
    </div>
  `;
}

function applyFilter() {
  const q = $("searchInput").value.trim().toLowerCase();
  const status = $("statusFilter").value;
  filtered = cases.filter(c => {
    if (status === "todo" && isDone(c)) return false;
    if (status === "done" && !isDone(c)) return false;
    if (!q) return true;
    const haystack = [
      c.doc_id, c.title, c.court, c.year, c.region, c.stage, c.case_type, c.text
    ].join(" ").toLowerCase();
    return haystack.includes(q);
  });
  renderCaseList();
}

function renderCaseList() {
  const list = $("caseList");
  list.innerHTML = "";
  const selected = currentCase()?.doc_id;
  filtered.forEach(c => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `case-item ${c.doc_id === selected ? "active" : ""} ${isDone(c) ? "done" : ""}`;
    btn.innerHTML = `
      <div class="case-num">${escapeHtml(c.title || c.doc_id)}</div>
      <div class="case-sub">${escapeHtml([c.year, c.region, c.stage, c.case_type].filter(Boolean).join(" · "))}</div>
    `;
    btn.addEventListener("click", () => {
      currentIndex = cases.findIndex(x => x.doc_id === c.doc_id);
      renderCurrent();
    });
    list.appendChild(btn);
  });
}

function renderDocument(c) {
  const q = $("textSearchInput").value.trim();
  let text = escapeHtml(c.text || "无正文");
  if (q) {
    const safe = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    text = text.replace(new RegExp(safe, "gi"), m => `<mark>${m}</mark>`);
  }
  $("documentText").innerHTML = text;
}

function predictionHtml(c, field) {
  const raw = c.prediction[field.key];
  const source = c.source[field.key];
  const pred = normalizeText(raw) || "空";
  const sourceText = normalizeText(source);
  return `<div class="prediction">模型值：${escapeHtml(pred)}${sourceText && sourceText !== pred ? `<br>原始单元格：${escapeHtml(sourceText)}` : ""}</div>`;
}

function renderInput(c, field) {
  const value = fieldValue(c, field);
  if (field.type === "select") {
    const opts = field.options.map(opt => `<option value="${escapeHtml(opt)}" ${String(value) === String(opt) ? "selected" : ""}>${escapeHtml(opt || "空")}</option>`).join("");
    return `<select class="field-input" data-key="${escapeHtml(field.key)}">${opts}</select>`;
  }
  if (field.type === "multi") {
    const values = new Set(Array.isArray(value) ? value : normalizeText(value).split(/[;；,，、\n]+/).filter(Boolean));
    const checks = field.options.map(opt => `
      <label class="check-row">
        <input type="checkbox" data-key="${escapeHtml(field.key)}" value="${escapeHtml(opt)}" ${values.has(opt) ? "checked" : ""}>
        <span>${escapeHtml(opt)}</span>
      </label>
    `).join("");
    return `<div class="multi-grid">${checks}</div>`;
  }
  if (field.type === "list_text") {
    const text = Array.isArray(value) ? value.join("\n") : normalizeText(value);
    return `<textarea class="field-input" rows="3" data-key="${escapeHtml(field.key)}" placeholder="一行一个值">${escapeHtml(text)}</textarea>`;
  }
  if (field.type === "number") {
    return `<input class="field-input" data-key="${escapeHtml(field.key)}" type="number" step="0.01" value="${escapeHtml(value)}" />`;
  }
  return `<input class="field-input" data-key="${escapeHtml(field.key)}" type="text" value="${escapeHtml(value)}" />`;
}

function renderForm(c) {
  const form = $("annotationForm");
  if (activeTab === "notes") {
    const notes = c.annotation?.notes || "";
    form.innerHTML = `
      <div class="field-card">
        <div class="field-head"><div class="field-label">标注意见</div></div>
        <textarea id="notesInput" class="notes-area" placeholder="记录争议、无法判断原因、复核建议">${escapeHtml(notes)}</textarea>
      </div>
    `;
    return;
  }
  const fields = state.fields[activeTab];
  form.innerHTML = fields.map(field => `
    <div class="field-card">
      <div class="field-head">
        <div>
          <div class="field-label">${escapeHtml(field.label)}</div>
          <div class="field-key">${escapeHtml(field.key)}</div>
        </div>
      </div>
      ${predictionHtml(c, field)}
      ${renderInput(c, field)}
      ${field.help ? `<div class="field-key">${escapeHtml(field.help)}</div>` : ""}
    </div>
  `).join("");
}

function collectFields() {
  const c = currentCase();
  const fields = {};
  [...state.fields.primary, ...state.fields.secondary].forEach(field => {
    if (field.type === "multi") {
      fields[field.key] = Array.from(document.querySelectorAll(`[data-key="${CSS.escape(field.key)}"]:checked`)).map(x => x.value);
      if (fields[field.key].length === 0 && c.annotation?.fields && Object.prototype.hasOwnProperty.call(c.annotation.fields, field.key)) {
        fields[field.key] = [];
      }
    } else if (field.type === "list_text") {
      const el = document.querySelector(`[data-key="${CSS.escape(field.key)}"]`);
      fields[field.key] = el ? el.value.split(/\n+/).map(x => x.trim()).filter(Boolean) : (annotationFor(c)[field.key] || []);
    } else {
      const el = document.querySelector(`[data-key="${CSS.escape(field.key)}"]`);
      if (el) fields[field.key] = el.value === "" ? null : el.value;
      else if (Object.prototype.hasOwnProperty.call(annotationFor(c), field.key)) fields[field.key] = annotationFor(c)[field.key];
    }
  });
  return {...annotationFor(c), ...fields};
}

async function saveCurrent() {
  const c = currentCase();
  if (!c) return;
  const payload = {
    doc_id: c.doc_id,
    index: c.index,
    fields: collectFields(),
    notes: $("notesInput") ? $("notesInput").value : (c.annotation?.notes || ""),
  };
  const res = await fetch("/api/annotation", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    toast("保存失败");
    return;
  }
  const data = await res.json();
  c.annotation = data.annotation;
  renderProgress();
  renderForm(c);
  renderCaseList();
  toast("已保存");
}

function copyPrediction() {
  const c = currentCase();
  if (!c) return;
  c.annotation = c.annotation || {};
  c.annotation.fields = {...c.prediction};
  renderForm(c);
  toast("已复制模型值");
}

async function exportGold() {
  const res = await fetch("/api/export-gold", {method: "POST"});
  if (!res.ok) {
    toast("导出失败");
    return;
  }
  const data = await res.json();
  state.metrics = data.metrics;
  renderProgress();
  toast("已导出最终黄金标准");
  window.open("/api/export", "_blank");
}

function move(delta) {
  if (!cases.length) return;
  currentIndex = Math.max(0, Math.min(cases.length - 1, currentIndex + delta));
  renderCurrent();
}

function renderCurrent() {
  const c = currentCase();
  if (!c) return;
  $("caseTitle").textContent = c.title || c.doc_id;
  $("caseMeta").textContent = [c.doc_id, c.court, c.year, c.region, c.stage, c.case_type].filter(Boolean).join(" · ");
  renderDocument(c);
  renderForm(c);
  renderProgress();
  renderCaseList();
}

async function loadApp() {
  const res = await fetch("/api/data");
  state = await res.json();
  cases = state.cases;
  filtered = cases.slice();
  renderCurrent();
}

document.addEventListener("DOMContentLoaded", () => {
  $("searchInput").addEventListener("input", applyFilter);
  $("statusFilter").addEventListener("change", applyFilter);
  $("textSearchInput").addEventListener("input", () => currentCase() && renderDocument(currentCase()));
  $("saveBtn").addEventListener("click", saveCurrent);
  $("copyPredBtn").addEventListener("click", copyPrediction);
  $("exportBtn").addEventListener("click", exportGold);
  $("prevBtn").addEventListener("click", () => move(-1));
  $("nextBtn").addEventListener("click", () => move(1));
  document.querySelectorAll(".tab").forEach(btn => {
    btn.addEventListener("click", () => {
      activeTab = btn.dataset.tab;
      document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === btn));
      if (currentCase()) renderForm(currentCase());
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key.toLowerCase() === "s") {
      e.preventDefault();
      saveCurrent();
    } else if (e.altKey && e.key === "ArrowLeft") {
      move(-1);
    } else if (e.altKey && e.key === "ArrowRight") {
      move(1);
    }
  });
  loadApp();
});
"""


class AnnotationServer(BaseHTTPRequestHandler):
    app_config: dict[str, Any] = {}
    write_lock = threading.Lock()

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} {fmt % args}")

    def send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, content_type: str = "text/html; charset=utf-8", status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path in {"/", "/index.html"}:
            self.send_text(INDEX_HTML)
            return
        if path == "/static/style.css":
            self.send_text(STYLE_CSS, "text/css; charset=utf-8")
            return
        if path == "/static/app.js":
            self.send_text(APP_JS, "application/javascript; charset=utf-8")
            return
        if path == "/api/data":
            cfg = self.app_config
            self.send_json(make_app_state(cfg["test_set"], cfg["texts"], cfg["annotations"], cfg["baseline"]))
            return
        if path == "/api/export":
            cfg = self.app_config
            annotations = load_annotations(cfg["annotations"])
            rows = list(annotations.values())
            metrics = compute_metrics(read_csv(cfg["test_set"]), load_baselines(cfg["baseline"]), annotations)
            self.send_json(
                {
                    "count": len(rows),
                    "annotations": rows,
                    "annotation_table": str(cfg["annotation_table"]),
                    "gold_csv": str(cfg["gold_csv"]),
                    "gold_jsonl": str(cfg["gold_jsonl"]),
                    "metrics_path": str(cfg["gold_metrics"]),
                    "metrics": metrics,
                }
            )
            return
        self.send_text("Not found", "text/plain; charset=utf-8", 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/export-gold":
            cfg = self.app_config
            payload = write_final_gold(
                cfg["test_set"],
                cfg["annotations"],
                cfg["baseline"],
                cfg["gold_csv"],
                cfg["gold_jsonl"],
                cfg["gold_metrics"],
                self.write_lock,
            )
            self.send_json(payload)
            return
        if parsed.path != "/api/annotation":
            self.send_text("Not found", "text/plain; charset=utf-8", 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self.send_json({"error": str(exc)}, 400)
            return
        doc_id = str(payload.get("doc_id") or "").strip()
        if not doc_id:
            self.send_json({"error": "doc_id is required"}, 400)
            return
        annotation = {
            "doc_id": doc_id,
            "index": payload.get("index"),
            "fields": payload.get("fields") or {},
            "notes": payload.get("notes") or "",
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        cfg = self.app_config
        write_annotation(cfg["annotations"], annotation, self.write_lock)
        write_annotation_table(cfg["test_set"], cfg["annotations"], cfg["annotation_table"], self.write_lock, cfg["baseline"])
        metrics = compute_metrics(read_csv(cfg["test_set"]), load_baselines(cfg["baseline"]), load_annotations(cfg["annotations"]))
        state = {
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "annotations_path": str(cfg["annotations"]),
            "annotation_table_path": str(cfg["annotation_table"]),
            "baseline_path": str(cfg["baseline"]),
            "latest_doc_id": doc_id,
            "annotated_count": len(load_annotations(cfg["annotations"])),
            "metrics": metrics,
        }
        write_state(cfg["state"], state, self.write_lock)
        self.send_json({"ok": True, "annotation": annotation, "annotation_table": str(cfg["annotation_table"]), "metrics": metrics})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-set", default=str(DEFAULT_TEST_SET))
    parser.add_argument("--texts", default=str(DEFAULT_TEXTS))
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    parser.add_argument("--annotations", default="")
    parser.add_argument("--state", default="")
    parser.add_argument("--annotation-table", default="")
    parser.add_argument("--baseline", default="")
    parser.add_argument("--gold-csv", default="")
    parser.add_argument("--gold-jsonl", default="")
    parser.add_argument("--gold-metrics", default="")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    annotations = Path(args.annotations) if args.annotations else outdir / DEFAULT_ANNOTATIONS.name
    state_path = Path(args.state) if args.state else outdir / DEFAULT_STATE.name
    annotation_table = Path(args.annotation_table) if args.annotation_table else outdir / DEFAULT_ANNOTATION_TABLE.name
    baseline = Path(args.baseline) if args.baseline else outdir / DEFAULT_BASELINE.name
    gold_csv = Path(args.gold_csv) if args.gold_csv else outdir / DEFAULT_GOLD_CSV.name
    gold_jsonl = Path(args.gold_jsonl) if args.gold_jsonl else outdir / DEFAULT_GOLD_JSONL.name
    gold_metrics = Path(args.gold_metrics) if args.gold_metrics else outdir / DEFAULT_GOLD_METRICS.name
    AnnotationServer.app_config = {
        "test_set": Path(args.test_set),
        "texts": Path(args.texts),
        "annotations": annotations,
        "state": state_path,
        "annotation_table": annotation_table,
        "baseline": baseline,
        "gold_csv": gold_csv,
        "gold_jsonl": gold_jsonl,
        "gold_metrics": gold_metrics,
    }
    write_annotation_table(Path(args.test_set), annotations, annotation_table, AnnotationServer.write_lock, baseline)
    server = ThreadingHTTPServer((args.host, args.port), AnnotationServer)
    url = f"http://{args.host}:{args.port}/"
    print(f"Manual annotation server: {url}")
    print(f"Annotations: {annotations}")
    print(f"Annotation table: {annotation_table}")
    print(f"Baseline: {baseline}")
    print(f"Gold CSV: {gold_csv}")
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped.")


if __name__ == "__main__":
    main()
