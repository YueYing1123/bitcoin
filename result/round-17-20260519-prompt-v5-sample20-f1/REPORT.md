# Official DS vs GPT-5.5 F1 Sample

- Sample size: 18 / 20
- Evaluated model: deepseek-v4-pro
- Gold standard: gpt-5.5
- Seed: 2026051902

## Group F1

| Group | Fields | TP | FP | FN | Precision | Recall | Micro F1 | Macro F1 active | Exact match |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| primary | 3 | 60 | 7 | 20 | 89.6% | 75.0% | 81.6% | 82.6% | 66.7% |
| secondary | 16 | 243 | 16 | 46 | 93.8% | 84.1% | 88.7% | 88.5% | 87.8% |
| primary_secondary | 19 | 303 | 23 | 66 | 92.9% | 82.1% | 87.2% | 87.6% | 84.5% |

## Field F1

| Group | Field | Kind | TP | FP | FN | Precision | Recall | F1 | Exact match |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| primary | `case_amount` | scalar | 13 | 4 | 5 | 76.5% | 72.2% | 74.3% | 72.2% |
| primary | `judicial_analysis.contract_validity` | scalar | 17 | 1 | 1 | 94.4% | 94.4% | 94.4% | 94.4% |
| primary | `virtual_currency_info.activity_types` | list | 30 | 2 | 14 | 93.8% | 68.2% | 78.9% | 33.3% |
| secondary | `case_amount_type` | scalar | 14 | 3 | 4 | 82.4% | 77.8% | 80.0% | 77.8% |
| secondary | `metadata.court_level` | scalar | 18 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.judgment_date` | scalar | 18 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.region` | scalar | 18 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_primary` | scalar | 18 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_secondary` | scalar | 17 | 1 | 1 | 94.4% | 94.4% | 94.4% | 94.4% |
| secondary | `case_profile.procedure_stage` | scalar | 18 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.is_appeal` | scalar | 18 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `virtual_currency_info.currency_types` | list | 27 | 1 | 19 | 96.4% | 58.7% | 73.0% | 44.4% |
| secondary | `judicial_analysis.legal_characterization` | scalar | 15 | 3 | 3 | 83.3% | 83.3% | 83.3% | 83.3% |
| secondary | `judicial_analysis.virtual_currency_property_status` | scalar | 17 | 1 | 1 | 94.4% | 94.4% | 94.4% | 94.4% |
| secondary | `judicial_analysis.transaction_legality_assessment` | scalar | 15 | 3 | 3 | 83.3% | 83.3% | 83.3% | 83.3% |
| secondary | `judicial_analysis.reasons_for_invalidity_or_no_protection` | list | 5 | 1 | 7 | 83.3% | 41.7% | 55.6% | 72.2% |
| secondary | `judicial_analysis.cited_policies` | list | 3 | 0 | 1 | 100.0% | 75.0% | 85.7% | 94.4% |
| secondary | `judicial_analysis.policy_labels` | list | 3 | 0 | 1 | 100.0% | 75.0% | 85.7% | 94.4% |
| secondary | `judicial_analysis.judicial_framing` | list | 19 | 3 | 6 | 86.4% | 76.0% | 80.9% | 66.7% |

## Outputs

- Summary JSON: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-17-20260519-prompt-v5-sample20-f1\summary.json`
- Field metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-17-20260519-prompt-v5-sample20-f1\field_f1.csv`
- Group metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-17-20260519-prompt-v5-sample20-f1\group_f1.csv`
- Pair JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-17-20260519-prompt-v5-sample20-f1\case_field_pairs.jsonl`
- DS JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-17-20260519-prompt-v5-sample20-f1\ds_official_outputs.jsonl`
- GPT JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-17-20260519-prompt-v5-sample20-f1\gpt55_gold_outputs.jsonl`
