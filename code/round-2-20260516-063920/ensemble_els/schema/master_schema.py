# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class TransactionTimeSpan(BaseModel):
	start_year: Optional[str] = None
	end_year: Optional[str] = None
	crosses_2017_94_notice: Optional[bool] = None
	crosses_2021_254_notice: Optional[bool] = None


class CaseProfile(BaseModel):
	case_cause: Optional[str] = None
	procedure_stage: Optional[str] = None
	is_appeal: Optional[bool] = None
	appeal_result: Optional[str] = None
	is_default_judgment: Optional[bool] = None
	transaction_time_span: TransactionTimeSpan = Field(default_factory=TransactionTimeSpan)


class CounselRepresentation(BaseModel):
	plaintiff_has_lawyer: Optional[bool] = None
	defendant_has_lawyer: Optional[bool] = None


class LitigantProfile(BaseModel):
	plaintiff_type: Optional[str] = None
	defendant_type: Optional[str] = None
	counsel_representation: CounselRepresentation = Field(default_factory=CounselRepresentation)


class ProceduralStatus(BaseModel):
	ruling_type: Optional[str] = None
	criminal_civil_intersection: Optional[bool] = None
	jurisdiction_challenge: Optional[bool] = None


class Metadata(BaseModel):
	case_number: Optional[str] = None
	court_name: Optional[str] = None
	court_level: Optional[str] = None
	province: Optional[str] = None
	judgment_date: Optional[str] = None
	judgment_year: Optional[str] = None
	case_class: Optional[str] = None


class VirtualCurrencyAmounts(BaseModel):
	plaintiff_claimed_cny: Optional[float] = None
	court_recognized_cny: Optional[float] = None


class VirtualCurrencyInfo(BaseModel):
	involved_currencies: List[str] = Field(default_factory=list)
	is_usdt_involved: Optional[bool] = None
	activity_type: Optional[str] = None
	transaction_venue: Optional[str] = None
	amounts: VirtualCurrencyAmounts = Field(default_factory=VirtualCurrencyAmounts)


class EvidenceAnalysis(BaseModel):
	key_evidence_types: List[str] = Field(default_factory=list)
	burden_of_proof_ruling: Optional[str] = None
	wallet_ownership_proven: Optional[bool] = None


class RemedyMechanics(BaseModel):
	method: Optional[str] = None
	fiat_conversion_logic: Optional[str] = None
	interest_or_fee: Optional[str] = None


class CitedNorms(BaseModel):
	laws: List[str] = Field(default_factory=list)
	policies: List[str] = Field(default_factory=list)
	is_public_order_cited: Optional[bool] = None


class JudicialAnalysis(BaseModel):
	legal_characterization: Optional[str] = None
	contract_validity: Optional[str] = None
	validity_ground: Optional[str] = None
	illegal_debt_determination: Optional[bool] = None
	moral_judgment_tags: List[str] = Field(default_factory=list)
	remedy_mechanics: RemedyMechanics = Field(default_factory=RemedyMechanics)
	cited_norms: CitedNorms = Field(default_factory=CitedNorms)


class MetaEnsemble(BaseModel):
	confidence_mean: Optional[float] = None
	validation_status: Optional[str] = None


class LLMSummary(BaseModel):
	outcome_text: Optional[str] = None
	core_issue: Optional[str] = None


class InstanceFields(BaseModel):
	case_amount_first_instance: Optional[float] = None
	case_amount_type_first_instance: Optional[str] = None
	case_amount_evidence_first_instance: Optional[str] = None
	case_amount_second_instance: Optional[float] = None
	case_amount_type_second_instance: Optional[str] = None
	case_amount_evidence_second_instance: Optional[str] = None
	case_type_primary_first_instance: Dict[str, Any] = Field(default_factory=dict)
	case_type_primary_second_instance: Dict[str, Any] = Field(default_factory=dict)
	case_type_secondary_first_instance: Dict[str, Any] = Field(default_factory=dict)
	case_type_secondary_second_instance: Dict[str, Any] = Field(default_factory=dict)
	involved_first_instance: Dict[str, Any] = Field(default_factory=dict)
	involved_second_instance: Dict[str, Any] = Field(default_factory=dict)
	typical_virtual_currency_first_instance: Dict[str, Any] = Field(default_factory=dict)
	typical_virtual_currency_second_instance: Dict[str, Any] = Field(default_factory=dict)
	currency_types_first_instance: Dict[str, Any] = Field(default_factory=dict)
	currency_types_second_instance: Dict[str, Any] = Field(default_factory=dict)
	activity_types_first_instance: Dict[str, Any] = Field(default_factory=dict)
	activity_types_second_instance: Dict[str, Any] = Field(default_factory=dict)
	legal_characterization_first_instance: Dict[str, Any] = Field(default_factory=dict)
	legal_characterization_second_instance: Dict[str, Any] = Field(default_factory=dict)
	virtual_currency_property_status_first_instance: Dict[str, Any] = Field(default_factory=dict)
	virtual_currency_property_status_second_instance: Dict[str, Any] = Field(default_factory=dict)
	direct_transaction_legality_assessment_first_instance: Dict[str, Any] = Field(default_factory=dict)
	direct_transaction_legality_assessment_second_instance: Dict[str, Any] = Field(default_factory=dict)
	indirect_transaction_legality_assessment_first_instance: Dict[str, Any] = Field(default_factory=dict)
	indirect_transaction_legality_assessment_second_instance: Dict[str, Any] = Field(default_factory=dict)
	direct_related_contract_validity_first_instance: Dict[str, Any] = Field(default_factory=dict)
	direct_related_contract_validity_second_instance: Dict[str, Any] = Field(default_factory=dict)
	indirect_related_contract_validity_first_instance: Dict[str, Any] = Field(default_factory=dict)
	indirect_related_contract_validity_second_instance: Dict[str, Any] = Field(default_factory=dict)
	reasons_for_invalidity_or_no_protection_first_instance: Dict[str, Any] = Field(default_factory=dict)
	reasons_for_invalidity_or_no_protection_second_instance: Dict[str, Any] = Field(default_factory=dict)
	cited_laws_first_instance: Dict[str, Any] = Field(default_factory=dict)
	cited_laws_second_instance: Dict[str, Any] = Field(default_factory=dict)
	cited_policies_first_instance: Dict[str, Any] = Field(default_factory=dict)
	cited_policies_second_instance: Dict[str, Any] = Field(default_factory=dict)
	policy_labels_first_instance: Dict[str, Any] = Field(default_factory=dict)
	policy_labels_second_instance: Dict[str, Any] = Field(default_factory=dict)
	judicial_framing_first_instance: Dict[str, Any] = Field(default_factory=dict)
	judicial_framing_second_instance: Dict[str, Any] = Field(default_factory=dict)
	outcome_summary_first_instance: Dict[str, Any] = Field(default_factory=dict)
	outcome_summary_second_instance: Dict[str, Any] = Field(default_factory=dict)
	reasoning_summary_first_instance: Dict[str, Any] = Field(default_factory=dict)
	reasoning_summary_second_instance: Dict[str, Any] = Field(default_factory=dict)
	low_confidence_fields_first_instance: Dict[str, Any] = Field(default_factory=dict)
	low_confidence_fields_second_instance: Dict[str, Any] = Field(default_factory=dict)


class FinalOutputPointer(BaseModel):
	appeal_outcome: Dict[str, Any] = Field(default_factory=dict)
	final_effective_instance: Dict[str, Any] = Field(default_factory=dict)
	use_fields_suffix: Dict[str, Any] = Field(default_factory=dict)
	reasoning_changed: Dict[str, Any] = Field(default_factory=dict)
	result_changed: Dict[str, Any] = Field(default_factory=dict)
	procedural_only: Dict[str, Any] = Field(default_factory=dict)
	changed_fields_between_instances: Dict[str, Any] = Field(default_factory=dict)


class MasterRecord(BaseModel):
	document_id: str
	metadata: Metadata = Field(default_factory=Metadata)
	case_profile: CaseProfile = Field(default_factory=CaseProfile)
	litigant_profile: LitigantProfile = Field(default_factory=LitigantProfile)
	procedural_status: ProceduralStatus = Field(default_factory=ProceduralStatus)
	virtual_currency_info: VirtualCurrencyInfo = Field(default_factory=VirtualCurrencyInfo)
	evidence_analysis: EvidenceAnalysis = Field(default_factory=EvidenceAnalysis)
	judicial_analysis: JudicialAnalysis = Field(default_factory=JudicialAnalysis)
	meta_ensemble: MetaEnsemble = Field(default_factory=MetaEnsemble)
	llm_summary: LLMSummary = Field(default_factory=LLMSummary)
	instance_fields: InstanceFields = Field(default_factory=InstanceFields)
	final_output_pointer: FinalOutputPointer = Field(default_factory=FinalOutputPointer)
	custom_annotations: Dict[str, Any] = Field(default_factory=dict)


