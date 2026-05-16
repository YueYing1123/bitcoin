# DeepSeek Gold vs Master Dataset F1

- Gold file: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\data\processed\master\compare.jsonl`
- Master file: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\data\processed\master\master_dataset.csv`
- Gold docs: 122
- Scored docs: 122
- Micro precision: 0.8333
- Micro recall: 0.2694
- Micro F1: 0.4072
- Micro TP/FP/FN: 930 / 186 / 2522
- Macro F1: 0.3157

## Field Scores

| Field | Master column | TP | FP | FN | Gold support | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| case_amount | case_amount | 75 | 41 | 34 | 109 | 0.6466 | 0.6881 | 0.6667 |
| metadata.case_number | case_number | 122 | 0 | 0 | 122 | 1.0000 | 1.0000 | 1.0000 |
| metadata.court_name | court_name | 119 | 3 | 3 | 122 | 0.9754 | 0.9754 | 0.9754 |
| metadata.court_level | court_level | 99 | 23 | 23 | 122 | 0.8115 | 0.8115 | 0.8115 |
| metadata.judgment_date | judgment_date | 122 | 0 | 0 | 122 | 1.0000 | 1.0000 | 1.0000 |
| metadata.first_instance_case_number | first_instance_case_number | 0 | 6 | 0 | 0 | 0.0000 | 0.0000 | 0.0000 |
| metadata.region | region | 0 | 0 | 122 | 122 | 0.0000 | 0.0000 | 0.0000 |
| metadata.doc_type | doc_type | 0 | 0 | 122 | 122 | 0.0000 | 0.0000 | 0.0000 |
| case_profile.case_type_primary | case_type_primary | 0 | 0 | 122 | 122 | 0.0000 | 0.0000 | 0.0000 |
| case_profile.case_type_secondary | case_type_secondary | 0 | 0 | 122 | 122 | 0.0000 | 0.0000 | 0.0000 |
| case_profile.procedure_stage | procedure_stage | 121 | 1 | 1 | 122 | 0.9918 | 0.9918 | 0.9918 |
| case_profile.is_appeal | is_appeal | 122 | 0 | 0 | 122 | 1.0000 | 1.0000 | 1.0000 |
| case_profile.litigant_profile.plaintiff_types | plaintiff_types | 0 | 0 | 118 | 118 | 0.0000 | 0.0000 | 0.0000 |
| case_profile.litigant_profile.defendant_types | defendant_types | 0 | 0 | 130 | 130 | 0.0000 | 0.0000 | 0.0000 |
| virtual_currency_info.involved | vc_involved | 0 | 0 | 122 | 122 | 0.0000 | 0.0000 | 0.0000 |
| virtual_currency_info.currency_types | currency_types | 0 | 0 | 137 | 137 | 0.0000 | 0.0000 | 0.0000 |
| virtual_currency_info.activity_type | activity_type | 26 | 57 | 77 | 103 | 0.3133 | 0.2524 | 0.2796 |
| judicial_analysis.legal_characterization | legal_characterization | 87 | 35 | 35 | 122 | 0.7131 | 0.7131 | 0.7131 |
| judicial_analysis.virtual_currency_property_legality | vc_property_legality | 0 | 0 | 98 | 98 | 0.0000 | 0.0000 | 0.0000 |
| judicial_analysis.contract_validity | contract_validity | 37 | 20 | 2 | 39 | 0.6491 | 0.9487 | 0.7708 |
| judicial_analysis.reason_for_invalidity | reason_for_invalidity | 0 | 0 | 29 | 29 | 0.0000 | 0.0000 | 0.0000 |
| judicial_analysis.cited_laws | cited_laws | 0 | 0 | 717 | 717 | 0.0000 | 0.0000 | 0.0000 |
| judicial_analysis.cited_policies | cited_policies | 0 | 0 | 21 | 21 | 0.0000 | 0.0000 | 0.0000 |
| judicial_analysis.judicial_framing | judicial_framing | 0 | 0 | 243 | 243 | 0.0000 | 0.0000 | 0.0000 |
| llm_summary.outcome_summary | outcome_summary | 0 | 0 | 122 | 122 | 0.0000 | 0.0000 | 0.0000 |
| llm_summary.reasoning_summary | reasoning_summary | 0 | 0 | 122 | 122 | 0.0000 | 0.0000 | 0.0000 |