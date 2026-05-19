# Official DS vs GPT-5.5 F1 Sample

- Sample size: 10 / 10
- Evaluated model: deepseek-v4-pro
- Gold standard: gpt-5.5
- Seed: 2026051802

## Group F1

| Group | Fields | TP | FP | FN | Precision | Recall | Micro F1 | Macro F1 active | Exact match |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| primary | 3 | 22 | 7 | 13 | 75.9% | 62.9% | 68.8% | 69.9% | 60.0% |
| secondary | 16 | 114 | 23 | 43 | 83.2% | 72.6% | 77.6% | 74.1% | 77.5% |
| primary_secondary | 19 | 136 | 30 | 56 | 81.9% | 70.8% | 76.0% | 73.4% | 74.7% |

## Field F1

| Group | Field | Kind | TP | FP | FN | Precision | Recall | F1 | Exact match |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| primary | `case_amount` | scalar | 7 | 2 | 3 | 77.8% | 70.0% | 73.7% | 70.0% |
| primary | `judicial_analysis.contract_validity` | scalar | 8 | 2 | 2 | 80.0% | 80.0% | 80.0% | 80.0% |
| primary | `virtual_currency_info.activity_types` | list | 7 | 3 | 8 | 70.0% | 46.7% | 56.0% | 30.0% |
| secondary | `case_amount_type` | scalar | 6 | 3 | 4 | 66.7% | 60.0% | 63.2% | 60.0% |
| secondary | `metadata.court_level` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.judgment_date` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.region` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_primary` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_secondary` | scalar | 9 | 1 | 1 | 90.0% | 90.0% | 90.0% | 90.0% |
| secondary | `case_profile.procedure_stage` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.is_appeal` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `virtual_currency_info.currency_types` | list | 12 | 0 | 6 | 100.0% | 66.7% | 80.0% | 50.0% |
| secondary | `judicial_analysis.legal_characterization` | scalar | 5 | 4 | 4 | 55.6% | 55.6% | 55.6% | 60.0% |
| secondary | `judicial_analysis.virtual_currency_property_status` | scalar | 10 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.transaction_legality_assessment` | scalar | 4 | 6 | 6 | 40.0% | 40.0% | 40.0% | 40.0% |
| secondary | `judicial_analysis.reasons_for_invalidity_or_no_protection` | list | 1 | 1 | 7 | 50.0% | 12.5% | 20.0% | 50.0% |
| secondary | `judicial_analysis.cited_policies` | list | 0 | 1 | 1 | 0.0% | 0.0% | 0.0% | 90.0% |
| secondary | `judicial_analysis.policy_labels` | list | 1 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.judicial_framing` | list | 6 | 7 | 14 | 46.2% | 30.0% | 36.4% | 0.0% |

## Outputs

- Summary JSON: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-13-20260518-official-ds-gpt-f1\summary.json`
- Field metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-13-20260518-official-ds-gpt-f1\field_f1.csv`
- Group metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-13-20260518-official-ds-gpt-f1\group_f1.csv`
- Pair JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-13-20260518-official-ds-gpt-f1\case_field_pairs.jsonl`
- DS JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-13-20260518-official-ds-gpt-f1\ds_official_outputs.jsonl`
- GPT JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-13-20260518-official-ds-gpt-f1\gpt55_gold_outputs.jsonl`
