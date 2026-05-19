# Official DS vs GPT-5.5 F1 Sample

- Sample size: 10 / 10
- Evaluated model: deepseek-v4-pro
- Gold standard: gpt-5.5
- Seed: 2026051802

## Group F1

| Group | Fields | TP | FP | FN | Precision | Recall | Micro F1 | Macro F1 active | Exact match |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| primary | 3 | 24 | 6 | 10 | 80.0% | 70.6% | 75.0% | 74.6% | 66.7% |
| secondary | 16 | 124 | 12 | 36 | 91.2% | 77.5% | 83.8% | 86.2% | 83.1% |
| primary_secondary | 19 | 148 | 18 | 46 | 89.2% | 76.3% | 82.2% | 84.3% | 80.5% |

## Field F1

| Group | Field | Kind | TP | FP | FN | Precision | Recall | F1 | Exact match |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| primary | `case_amount` | scalar | 7 | 2 | 3 | 77.8% | 70.0% | 73.7% | 70.0% |
| primary | `judicial_analysis.contract_validity` | scalar | 7 | 3 | 3 | 70.0% | 70.0% | 70.0% | 70.0% |
| primary | `virtual_currency_info.activity_types` | list | 10 | 1 | 4 | 90.9% | 71.4% | 80.0% | 60.0% |
| secondary | `case_amount_type` | scalar | 8 | 1 | 2 | 88.9% | 80.0% | 84.2% | 80.0% |
| secondary | `metadata.court_level` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.judgment_date` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.region` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_primary` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_secondary` | scalar | 9 | 1 | 1 | 90.0% | 90.0% | 90.0% | 90.0% |
| secondary | `case_profile.procedure_stage` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.is_appeal` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `virtual_currency_info.currency_types` | list | 11 | 1 | 3 | 91.7% | 78.6% | 84.6% | 70.0% |
| secondary | `judicial_analysis.legal_characterization` | scalar | 9 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.virtual_currency_property_status` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.transaction_legality_assessment` | scalar | 4 | 6 | 6 | 40.0% | 40.0% | 40.0% | 40.0% |
| secondary | `judicial_analysis.reasons_for_invalidity_or_no_protection` | list | 2 | 1 | 12 | 66.7% | 14.3% | 23.5% | 30.0% |
| secondary | `judicial_analysis.cited_policies` | list | 1 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.policy_labels` | list | 1 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.judicial_framing` | list | 9 | 2 | 12 | 81.8% | 42.9% | 56.2% | 20.0% |

## Outputs

- Summary JSON: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-14-20260518-prompt-v2-f1\summary.json`
- Field metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-14-20260518-prompt-v2-f1\field_f1.csv`
- Group metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-14-20260518-prompt-v2-f1\group_f1.csv`
- Pair JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-14-20260518-prompt-v2-f1\case_field_pairs.jsonl`
- DS JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-14-20260518-prompt-v2-f1\ds_official_outputs.jsonl`
- GPT JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-14-20260518-prompt-v2-f1\gpt55_gold_outputs.jsonl`
