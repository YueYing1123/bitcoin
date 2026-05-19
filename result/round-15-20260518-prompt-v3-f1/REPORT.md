# Official DS vs GPT-5.5 F1 Sample

- Sample size: 10 / 10
- Evaluated model: deepseek-v4-pro
- Gold standard: gpt-5.5
- Seed: 2026051802

## Group F1

| Group | Fields | TP | FP | FN | Precision | Recall | Micro F1 | Macro F1 active | Exact match |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| primary | 3 | 25 | 5 | 11 | 83.3% | 69.4% | 75.8% | 75.1% | 63.3% |
| secondary | 16 | 126 | 11 | 41 | 92.0% | 75.4% | 82.9% | 85.7% | 80.6% |
| primary_secondary | 19 | 151 | 16 | 52 | 90.4% | 74.4% | 81.6% | 84.0% | 77.9% |

## Field F1

| Group | Field | Kind | TP | FP | FN | Precision | Recall | F1 | Exact match |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| primary | `case_amount` | scalar | 6 | 2 | 4 | 75.0% | 60.0% | 66.7% | 60.0% |
| primary | `judicial_analysis.contract_validity` | scalar | 8 | 2 | 2 | 80.0% | 80.0% | 80.0% | 80.0% |
| primary | `virtual_currency_info.activity_types` | list | 11 | 1 | 5 | 91.7% | 68.8% | 78.6% | 50.0% |
| secondary | `case_amount_type` | scalar | 6 | 2 | 4 | 75.0% | 60.0% | 66.7% | 60.0% |
| secondary | `metadata.court_level` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.judgment_date` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.region` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_primary` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_secondary` | scalar | 9 | 1 | 1 | 90.0% | 90.0% | 90.0% | 90.0% |
| secondary | `case_profile.procedure_stage` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.is_appeal` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `virtual_currency_info.currency_types` | list | 11 | 1 | 6 | 91.7% | 64.7% | 75.9% | 50.0% |
| secondary | `judicial_analysis.legal_characterization` | scalar | 8 | 2 | 1 | 80.0% | 88.9% | 84.2% | 80.0% |
| secondary | `judicial_analysis.virtual_currency_property_status` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.transaction_legality_assessment` | scalar | 6 | 4 | 4 | 60.0% | 60.0% | 60.0% | 60.0% |
| secondary | `judicial_analysis.reasons_for_invalidity_or_no_protection` | list | 3 | 0 | 12 | 100.0% | 20.0% | 33.3% | 30.0% |
| secondary | `judicial_analysis.cited_policies` | list | 1 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.policy_labels` | list | 1 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.judicial_framing` | list | 11 | 1 | 13 | 91.7% | 45.8% | 61.1% | 20.0% |

## Outputs

- Summary JSON: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-15-20260518-prompt-v3-f1\summary.json`
- Field metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-15-20260518-prompt-v3-f1\field_f1.csv`
- Group metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-15-20260518-prompt-v3-f1\group_f1.csv`
- Pair JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-15-20260518-prompt-v3-f1\case_field_pairs.jsonl`
- DS JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-15-20260518-prompt-v3-f1\ds_official_outputs.jsonl`
- GPT JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-15-20260518-prompt-v3-f1\gpt55_gold_outputs.jsonl`
