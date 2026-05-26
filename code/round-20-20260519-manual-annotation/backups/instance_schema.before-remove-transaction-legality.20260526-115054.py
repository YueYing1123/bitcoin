from __future__ import annotations

import json
import re
from typing import Any


CONTRACT_VALIDITY_OPTIONS = ["", "有效", "无效", "未成立", "部分有效", "部分无效", "不受法律保护", "不适用", "未明确"]
TRANSACTION_LEGALITY_OPTIONS = ["", "合法有效", "合同无效", "不受法律保护", "非法金融活动", "违反监管政策", "违背公序良俗", "涉嫌犯罪", "风险自担", "未明确", "不适用"]
REASONS_OPTIONS = [
    "违反法律强制性规定",
    "违背公序良俗",
    "扰乱金融秩序",
    "扰乱货币秩序",
    "违反金融监管政策",
    "非法金融活动",
    "非法债务",
    "不属于民事案件受理范围",
    "涉嫌犯罪",
    "证据不足",
    "请求权基础不成立",
    "投资风险自担",
    "不具有法偿性",
    "不属于法定货币",
    "不利于产业结构优化",
    "不利于节能减排",
    "其他",
]
JUDICIAL_FRAMING_OPTIONS = [
    "风险自担",
    "非法债务",
    "不受法律保护",
    "合同无效",
    "返还本金",
    "折价赔偿",
    "财产属性保护",
    "证据不足",
    "刑民交叉",
    "移送公安",
    "涉嫌犯罪",
    "扰乱金融秩序",
    "扰乱货币秩序",
    "违背公序良俗",
    "违反强制性规定",
    "监管政策影响私法效力",
    "请求权基础不成立",
    "其他",
]
POLICY_LABEL_OPTIONS = ["2013五部委通知", "2017九四公告", "2021九二四通知", "挖矿整治文件", "地方监管文件", "其他"]
PROPERTY_STATUS_OPTIONS = ["网络虚拟财产", "虚拟财产", "特定虚拟商品", "财产利益", "数据权益", "不具有法偿性", "非货币", "不属于法定货币", "未明确"]
ACTIVITY_TYPE_OPTIONS = [
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
]

CASE_AMOUNT_TYPE_OPTIONS = [
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
    "掩饰隐瞒金额",
    "涉案流水",
    "获利金额",
    "罚金",
    "其他",
    "未明确",
    "不适用",
]


METADATA_FIELDS: list[dict[str, Any]] = [
    {"key": "court_level", "label": "法院层级", "type": "select", "path": "metadata.court_level", "options": ["", "最高人民法院", "高级法院", "中级法院", "基层法院", "专门法院", "其他", "未明确"]},
    {"key": "judgment_date", "label": "裁判日期", "type": "text", "path": "metadata.judgment_date"},
    {"key": "region", "label": "省级地区", "type": "text", "path": "metadata.region"},
    {"key": "procedure_stage", "label": "程序阶段", "type": "select", "path": "case_profile.procedure_stage", "options": ["", "一审", "二审", "再审", "执行", "审判监督", "其他", "未明确"]},
    {"key": "is_appeal", "label": "是否上诉", "type": "select", "path": "case_profile.is_appeal", "options": ["", "true", "false"]},
]


BASE_INSTANCE_FIELDS: list[dict[str, Any]] = [
    {"base": "case_amount", "label": "案件金额", "type": "number"},
    {"base": "case_amount_type", "label": "金额类型", "type": "select", "options": CASE_AMOUNT_TYPE_OPTIONS},
    {"base": "case_amount_evidence", "label": "金额依据", "type": "text"},
    {"base": "case_type_primary", "label": "案件类型", "type": "select", "options": ["", "民事", "刑事", "行政", "执行", "其他", "未明确"]},
    {"base": "case_type_secondary", "label": "具体案由", "type": "text"},
    {"base": "involved", "label": "是否涉及虚拟货币", "type": "select", "options": ["", "true", "false"]},
    {"base": "typical_virtual_currency", "label": "典型虚拟货币", "type": "select", "options": ["", "是", "否"], "help": "区块链、比特币、以太币、USDT等并与争议实质相关选是；仅游戏充值、直播打赏或背景性炒币选否。"},
    {"base": "currency_types", "label": "币种", "type": "list_text"},
    {"base": "activity_types", "label": "涉币活动类型", "type": "multi", "options": ACTIVITY_TYPE_OPTIONS},
    {"base": "legal_characterization", "label": "法律定性", "type": "text"},
    {"base": "virtual_currency_property_status", "label": "财产属性", "type": "multi", "options": PROPERTY_STATUS_OPTIONS},
    {"base": "direct_transaction_legality_assessment", "label": "直接交易合法性", "type": "select", "options": TRANSACTION_LEGALITY_OPTIONS},
    {"base": "indirect_transaction_legality_assessment", "label": "间接交易合法性", "type": "select", "options": TRANSACTION_LEGALITY_OPTIONS},
    {"base": "direct_related_contract_validity", "label": "直接合同效力", "type": "select", "options": CONTRACT_VALIDITY_OPTIONS},
    {"base": "indirect_related_contract_validity", "label": "间接合同效力", "type": "select", "options": CONTRACT_VALIDITY_OPTIONS},
    {"base": "reasons_for_invalidity_or_no_protection", "label": "无效/不保护理由", "type": "multi", "options": REASONS_OPTIONS},
    {"base": "cited_laws", "label": "引用法律", "type": "list_text"},
    {"base": "cited_policies", "label": "监管政策", "type": "list_text"},
    {"base": "policy_labels", "label": "政策标签", "type": "multi", "options": POLICY_LABEL_OPTIONS},
    {"base": "judicial_framing", "label": "司法裁判框架", "type": "multi", "options": JUDICIAL_FRAMING_OPTIONS},
    {"base": "outcome_summary", "label": "裁判结果摘要", "type": "text"},
    {"base": "reasoning_summary", "label": "裁判理由摘要", "type": "text"},
    {"base": "low_confidence_fields", "label": "低置信字段", "type": "list_text"},
]


FINAL_POINTER_FIELDS: list[dict[str, Any]] = [
    {"key": "appeal_outcome", "label": "二审处理结果", "type": "select", "path": "final_output_pointer.appeal_outcome", "options": ["", "驳回上诉、维持原判", "改判", "部分改判", "撤销原判、发回重审", "撤销原判并驳回起诉", "撤销原判并指令审理", "维持原裁定", "指令再审", "再审改判", "其他", "未明确", "不适用"]},
    {"key": "final_effective_instance", "label": "最终生效审级", "type": "select", "path": "final_output_pointer.final_effective_instance", "options": ["", "一审", "二审", "无最终实体口径", "未明确", "不适用"]},
    {"key": "use_fields_suffix", "label": "最终采用字段后缀", "type": "select", "path": "final_output_pointer.use_fields_suffix", "options": ["", "_first_instance", "_second_instance"]},
    {"key": "reasoning_changed", "label": "裁判理由是否变化", "type": "select", "path": "final_output_pointer.reasoning_changed", "options": ["", "true", "false"]},
    {"key": "result_changed", "label": "裁判结果是否变化", "type": "select", "path": "final_output_pointer.result_changed", "options": ["", "true", "false"]},
    {"key": "procedural_only", "label": "是否仅程序性处理", "type": "select", "path": "final_output_pointer.procedural_only", "options": ["", "true", "false"]},
    {"key": "changed_fields_between_instances", "label": "一二审变化字段", "type": "multi", "path": "final_output_pointer.changed_fields_between_instances", "options": ["case_amount", "case_amount_type", "case_type_primary", "case_type_secondary", "typical_virtual_currency", "currency_types", "activity_types", "legal_characterization", "virtual_currency_property_status", "direct_transaction_legality_assessment", "indirect_transaction_legality_assessment", "direct_related_contract_validity", "indirect_related_contract_validity", "reasons_for_invalidity_or_no_protection", "cited_laws", "cited_policies", "policy_labels", "judicial_framing", "outcome_summary", "reasoning_summary", "other"]},
]


INSTANCE_SUFFIXES = [("first_instance", "一审"), ("second_instance", "二审")]


def build_instance_fields(suffix: str, suffix_label: str) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for spec in BASE_INSTANCE_FIELDS:
        field = {k: v for k, v in spec.items() if k != "base"}
        field["key"] = f"{spec['base']}_{suffix}"
        field["base"] = spec["base"]
        field["path"] = f"instance_fields.{field['key']}"
        field["label"] = f"{spec['label']}_{suffix_label}"
        fields.append(field)
    return fields


FIELD_GROUPS: dict[str, list[dict[str, Any]]] = {
    "first_instance": build_instance_fields("first_instance", "一审"),
    "second_instance": build_instance_fields("second_instance", "二审"),
    "final_pointer": FINAL_POINTER_FIELDS,
}

ALL_FIELDS: list[dict[str, Any]] = [field for fields in FIELD_GROUPS.values() for field in fields]
LIST_FIELD_KEYS = {field["key"] for field in ALL_FIELDS if field["type"] in {"multi", "list_text"}}
NUMERIC_FIELD_KEYS = {field["key"] for field in ALL_FIELDS if field["type"] == "number"}
BOOLEAN_FIELD_KEYS = {"involved_first_instance", "involved_second_instance", "reasoning_changed", "result_changed", "procedural_only"}

FIELD_GROUP_LABELS = {
    "first_instance": "一审口径",
    "second_instance": "二审口径",
    "final_pointer": "最终指针",
}


OLD_FIELD_PATHS = {
    "case_amount": ["case_amount"],
    "case_amount_type": ["case_amount_type"],
    "case_amount_evidence": ["case_amount_evidence"],
    "case_type_primary": ["case_profile.case_type_primary"],
    "case_type_secondary": ["case_profile.case_type_secondary"],
    "involved": ["virtual_currency_info.involved"],
    "typical_virtual_currency": ["virtual_currency_info.typical_virtual_currency"],
    "currency_types": ["virtual_currency_info.currency_types"],
    "activity_types": ["virtual_currency_info.activity_types", "virtual_currency_info.activity_type"],
    "legal_characterization": ["judicial_analysis.legal_characterization"],
    "virtual_currency_property_status": ["judicial_analysis.virtual_currency_property_status", "judicial_analysis.virtual_currency_property_legality"],
    "direct_transaction_legality_assessment": ["judicial_analysis.direct_transaction_legality_assessment", "judicial_analysis.transaction_legality_assessment"],
    "indirect_transaction_legality_assessment": ["judicial_analysis.indirect_transaction_legality_assessment"],
    "direct_related_contract_validity": ["judicial_analysis.direct_related_contract_validity", "judicial_analysis.contract_validity"],
    "indirect_related_contract_validity": ["judicial_analysis.indirect_related_contract_validity"],
    "reasons_for_invalidity_or_no_protection": ["judicial_analysis.reasons_for_invalidity_or_no_protection", "judicial_analysis.reason_for_invalidity"],
    "cited_laws": ["judicial_analysis.cited_laws"],
    "cited_policies": ["judicial_analysis.cited_policies"],
    "policy_labels": ["judicial_analysis.policy_labels"],
    "judicial_framing": ["judicial_analysis.judicial_framing"],
    "outcome_summary": ["llm_summary.outcome_summary"],
    "reasoning_summary": ["llm_summary.reasoning_summary"],
    "low_confidence_fields": ["low_confidence_fields"],
}


CSV_LABELS: dict[str, str] = {
    "court_level": "法院层级",
    "judgment_date": "裁判日期",
    "region": "省级地区",
    "procedure_stage": "程序阶段",
    "is_appeal": "是否上诉",
    "appeal_outcome": "二审处理结果",
    "final_effective_instance": "最终生效审级",
    "use_fields_suffix": "最终采用字段后缀",
    "reasoning_changed": "裁判理由是否变化",
    "result_changed": "裁判结果是否变化",
    "procedural_only": "是否仅程序性处理",
    "changed_fields_between_instances": "一二审变化字段",
}

for suffix, suffix_label in INSTANCE_SUFFIXES:
    for spec in BASE_INSTANCE_FIELDS:
        CSV_LABELS[f"{spec['base']}_{suffix}"] = f"{spec['label']}_{suffix_label}"


def get_path_value(obj: dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    if isinstance(cur, dict) and "value" in cur:
        return cur.get("value")
    return cur


def set_path_value(obj: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def first_value(record: dict[str, Any], paths: list[str]) -> Any:
    for path in paths:
        value = get_path_value(record, path) if "." in path else record.get(path)
        if value is not None:
            return value
    return None


def parse_list_cell(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, dict) and "value" in value:
        return parse_list_cell(value.get("value"))
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            pass
    return [x.strip() for x in re.split(r"[;；,，、\n]+", text) if x.strip()]


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


def empty_for_field(key: str) -> Any:
    return [] if key in LIST_FIELD_KEYS else ""


def scalar_leaf(value: Any = None, evidence: Any = None) -> dict[str, Any]:
    return {"value": value, "evidence": evidence}


def empty_instance_value(base: str) -> Any:
    if base in {"currency_types", "activity_types", "virtual_currency_property_status", "reasons_for_invalidity_or_no_protection", "cited_laws", "cited_policies", "policy_labels", "judicial_framing", "low_confidence_fields"}:
        return {"value": [], "evidence": None}
    return {"value": None, "evidence": None}


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    out = dict(record)
    instance_fields = out.get("instance_fields")
    if not isinstance(instance_fields, dict):
        instance_fields = {}
        procedure = first_value(out, ["case_profile.procedure_stage"])
        is_second = str(procedure or "").strip() == "二审"
        target_suffix = "second_instance" if is_second else "first_instance"
        for spec in BASE_INSTANCE_FIELDS:
            base = spec["base"]
            old_value = first_value(out, OLD_FIELD_PATHS.get(base, []))
            for suffix, _label in INSTANCE_SUFFIXES:
                key = f"{base}_{suffix}"
                if suffix == target_suffix and old_value is not None:
                    instance_fields[key] = old_value if base.startswith("case_amount") else scalar_leaf(old_value, None)
                else:
                    instance_fields[key] = None if base.startswith("case_amount") else empty_instance_value(base)
        out["instance_fields"] = instance_fields

    pointer = out.get("final_output_pointer")
    if not isinstance(pointer, dict):
        procedure = first_value(out, ["case_profile.procedure_stage"])
        is_second = str(procedure or "").strip() == "二审"
        pointer = {
            "appeal_outcome": scalar_leaf("未明确" if is_second else None, None),
            "final_effective_instance": scalar_leaf("未明确" if is_second else "一审", None),
            "use_fields_suffix": scalar_leaf("_second_instance" if is_second else "_first_instance", None),
            "reasoning_changed": scalar_leaf(None, None),
            "result_changed": scalar_leaf(None, None),
            "procedural_only": scalar_leaf(None, None),
            "changed_fields_between_instances": scalar_leaf([], None),
        }
        out["final_output_pointer"] = pointer
    return out


def get_field_value(record: dict[str, Any], field: dict[str, Any]) -> Any:
    normalized = normalize_record(record)
    value = get_path_value(normalized, field["path"])
    return coerce_field_value(field, value)


def flat_csv_columns(use_labels: bool = False) -> list[str]:
    keys = [field["key"] for field in ALL_FIELDS]
    if not use_labels:
        return keys
    return [CSV_LABELS.get(key, key) for key in keys]


def field_key_to_csv_column(key: str, use_labels: bool = False) -> str:
    return CSV_LABELS.get(key, key) if use_labels else key
