# Official DS vs GPT-5.5 F1 Sample

- Sample size: 20 / 20
- Evaluated model: deepseek-v4-pro
- Gold standard: gpt-5.5
- Seed: 2026051901

## Group F1

| Group | Fields | TP | FP | FN | Precision | Recall | Micro F1 | Macro F1 active | Exact match |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| primary | 3 | 61 | 6 | 15 | 91.0% | 80.3% | 85.3% | 86.3% | 76.7% |
| secondary | 16 | 244 | 29 | 76 | 89.4% | 76.2% | 82.3% | 81.5% | 83.8% |
| primary_secondary | 19 | 305 | 35 | 91 | 89.7% | 77.0% | 82.9% | 82.2% | 82.6% |

## Field F1

| Group | Field | Kind | TP | FP | FN | Precision | Recall | F1 | Exact match |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| primary | `case_amount` | scalar | 15 | 4 | 4 | 78.9% | 78.9% | 78.9% | 80.0% |
| primary | `judicial_analysis.contract_validity` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| primary | `virtual_currency_info.activity_types` | list | 26 | 2 | 11 | 92.9% | 70.3% | 80.0% | 50.0% |
| secondary | `case_amount_type` | scalar | 12 | 7 | 7 | 63.2% | 63.2% | 63.2% | 65.0% |
| secondary | `metadata.court_level` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.judgment_date` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.region` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_primary` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_secondary` | scalar | 17 | 3 | 3 | 85.0% | 85.0% | 85.0% | 85.0% |
| secondary | `case_profile.procedure_stage` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.is_appeal` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `virtual_currency_info.currency_types` | list | 17 | 5 | 13 | 77.3% | 56.7% | 65.4% | 50.0% |
| secondary | `judicial_analysis.legal_characterization` | scalar | 18 | 2 | 2 | 90.0% | 90.0% | 90.0% | 90.0% |
| secondary | `judicial_analysis.virtual_currency_property_status` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.transaction_legality_assessment` | scalar | 16 | 4 | 4 | 80.0% | 80.0% | 80.0% | 80.0% |
| secondary | `judicial_analysis.reasons_for_invalidity_or_no_protection` | list | 6 | 1 | 19 | 85.7% | 24.0% | 37.5% | 60.0% |
| secondary | `judicial_analysis.cited_policies` | list | 1 | 1 | 0 | 50.0% | 100.0% | 66.7% | 95.0% |
| secondary | `judicial_analysis.policy_labels` | list | 1 | 1 | 0 | 50.0% | 100.0% | 66.7% | 95.0% |
| secondary | `judicial_analysis.judicial_framing` | list | 16 | 5 | 28 | 76.2% | 36.4% | 49.2% | 20.0% |

## Outputs

- Summary JSON: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-16-20260519-prompt-v4-sample20-f1\summary.json`
- Field metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-16-20260519-prompt-v4-sample20-f1\field_f1.csv`
- Group metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-16-20260519-prompt-v4-sample20-f1\group_f1.csv`
- Pair JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-16-20260519-prompt-v4-sample20-f1\case_field_pairs.jsonl`
- DS JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-16-20260519-prompt-v4-sample20-f1\ds_official_outputs.jsonl`
- GPT JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-16-20260519-prompt-v4-sample20-f1\gpt55_gold_outputs.jsonl`
