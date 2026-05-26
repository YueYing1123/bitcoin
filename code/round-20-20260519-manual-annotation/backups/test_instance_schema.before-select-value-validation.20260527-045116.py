from __future__ import annotations

from instance_schema import ALL_FIELDS, field_key_to_csv_column, get_field_value, normalize_record


def assert_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def test_first_instance_legacy_mapping() -> None:
    legacy = {
        "document_id": "one",
        "case_amount": 29000,
        "case_amount_type": "借款本金",
        "case_profile": {"procedure_stage": {"value": "一审"}},
        "virtual_currency_info": {"typical_virtual_currency": {"value": "是"}},
        "judicial_analysis": {"direct_related_contract_validity": {"value": "有效"}},
    }
    record = normalize_record(legacy)
    assert "instance_fields" in record
    assert "final_output_pointer" in record
    field_map = {f["key"]: f for f in ALL_FIELDS}
    assert "court_level" not in field_map
    assert "procedure_stage" not in field_map
    assert "direct_transaction_legality_assessment_first_instance" not in field_map
    assert "indirect_transaction_legality_assessment_first_instance" not in field_map
    assert "部分无效" not in field_map["direct_related_contract_validity_first_instance"]["options"]
    assert "不受法律保护" not in field_map["direct_related_contract_validity_first_instance"]["options"]
    assert "不适用" not in field_map["direct_related_contract_validity_first_instance"]["options"]
    assert "返还本金或原物" in field_map["judicial_framing_first_instance"]["options"]
    assert "返还本金" not in field_map["judicial_framing_first_instance"]["options"]
    assert "咨询服务" in field_map["activity_types_first_instance"]["options"]
    assert_equal(get_field_value(record, field_map["case_amount_first_instance"]), 29000, "first amount")
    assert_equal(get_field_value(record, field_map["case_amount_second_instance"]), "", "second amount empty")
    assert_equal(get_field_value(record, field_map["appeal_outcome"]), "", "first appeal outcome empty")
    assert_equal(get_field_value(record, field_map["use_fields_suffix"]), "_first_instance", "first pointer")
    assert_equal(get_field_value(record, field_map["reasoning_changed"]), "", "first reasoning changed empty")
    assert_equal(get_field_value(record, field_map["result_changed"]), "", "first result changed empty")
    assert_equal(get_field_value(record, field_map["procedural_only"]), "", "first procedural only empty")
    assert_equal(get_field_value(record, field_map["changed_fields_between_instances"]), [], "first changed fields empty")


def test_second_instance_legacy_mapping() -> None:
    legacy = {
        "document_id": "two",
        "case_amount": 49800,
        "case_profile": {"procedure_stage": {"value": "二审"}},
        "judicial_analysis": {"judicial_framing": {"value": ["证据不足"]}},
    }
    record = normalize_record(legacy)
    field_map = {f["key"]: f for f in ALL_FIELDS}
    assert_equal(get_field_value(record, field_map["case_amount_first_instance"]), "", "first amount empty")
    assert_equal(get_field_value(record, field_map["case_amount_second_instance"]), 49800, "second amount")
    assert_equal(get_field_value(record, field_map["judicial_framing_second_instance"]), ["证据不足"], "second framing")


def test_native_instance_record() -> None:
    record = {
        "document_id": "three",
        "case_profile": {"procedure_stage": {"value": "二审"}},
        "instance_fields": {
            "case_amount_first_instance": 100,
            "case_amount_second_instance": 80,
            "judicial_framing_first_instance": {"value": ["合同无效"], "evidence": None},
            "judicial_framing_second_instance": {"value": ["证据不足"], "evidence": None},
        },
        "final_output_pointer": {
            "appeal_outcome": {"value": "部分改判", "evidence": None},
            "final_effective_instance": {"value": "二审", "evidence": None},
            "use_fields_suffix": {"value": "_second_instance", "evidence": None},
            "reasoning_changed": {"value": True, "evidence": None},
            "result_changed": {"value": True, "evidence": None},
            "procedural_only": {"value": False, "evidence": None},
            "changed_fields_between_instances": {"value": ["case_amount", "judicial_framing"], "evidence": None},
        },
    }
    field_map = {f["key"]: f for f in ALL_FIELDS}
    assert_equal(get_field_value(record, field_map["case_amount_first_instance"]), 100, "native first amount")
    assert_equal(get_field_value(record, field_map["case_amount_second_instance"]), 80, "native second amount")
    assert_equal(get_field_value(record, field_map["result_changed"]), "true", "result changed bool")
    assert_equal(field_key_to_csv_column("case_amount_first_instance", use_labels=True), "案件金额_一审", "csv label")


if __name__ == "__main__":
    test_first_instance_legacy_mapping()
    test_second_instance_legacy_mapping()
    test_native_instance_record()
    print("instance schema tests passed")
