# Official DeepSeek Flash vs Pro F1 Sample

- Sample size: 20 / 20
- Evaluated model: deepseek-v4-flash
- Gold standard: deepseek-v4-pro
- Seed: 2026051903

## Group F1

| Group | Fields | TP | FP | FN | Precision | Recall | Micro F1 | Macro F1 active | Exact match |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| primary | 3 | 49 | 4 | 18 | 92.5% | 73.1% | 81.7% | 79.9% | 70.0% |
| secondary | 16 | 248 | 9 | 21 | 96.5% | 92.2% | 94.3% | 93.4% | 93.4% |
| primary_secondary | 19 | 297 | 13 | 39 | 95.8% | 88.4% | 92.0% | 91.3% | 89.7% |

## Field F1

| Group | Field | Kind | TP | FP | FN | Precision | Recall | F1 | Exact match |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| primary | `case_amount` | scalar | 9 | 3 | 9 | 75.0% | 50.0% | 60.0% | 55.0% |
| primary | `judicial_analysis.contract_validity` | scalar | 19 | 0 | 1 | 100.0% | 95.0% | 97.4% | 95.0% |
| primary | `virtual_currency_info.activity_types` | list | 21 | 1 | 8 | 95.5% | 72.4% | 82.4% | 60.0% |
| secondary | `case_amount_type` | scalar | 8 | 4 | 10 | 66.7% | 44.4% | 53.3% | 50.0% |
| secondary | `metadata.court_level` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.judgment_date` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `metadata.region` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_primary` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.case_type_secondary` | scalar | 19 | 1 | 1 | 95.0% | 95.0% | 95.0% | 95.0% |
| secondary | `case_profile.procedure_stage` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `case_profile.is_appeal` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `virtual_currency_info.currency_types` | list | 16 | 1 | 6 | 94.1% | 72.7% | 82.1% | 80.0% |
| secondary | `judicial_analysis.legal_characterization` | scalar | 19 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.virtual_currency_property_status` | scalar | 19 | 1 | 1 | 95.0% | 95.0% | 95.0% | 95.0% |
| secondary | `judicial_analysis.transaction_legality_assessment` | scalar | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.reasons_for_invalidity_or_no_protection` | list | 3 | 1 | 1 | 75.0% | 75.0% | 75.0% | 90.0% |
| secondary | `judicial_analysis.cited_policies` | list | 1 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.policy_labels` | list | 1 | 0 | 0 | 100.0% | 100.0% | 100.0% | 100.0% |
| secondary | `judicial_analysis.judicial_framing` | list | 22 | 1 | 2 | 95.7% | 91.7% | 93.6% | 85.0% |

## Outputs

- Summary JSON: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-18-20260519-dsflash-vs-dspro-f1\summary.json`
- Field metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-18-20260519-dsflash-vs-dspro-f1\field_f1.csv`
- Group metrics CSV: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-18-20260519-dsflash-vs-dspro-f1\group_f1.csv`
- Pair JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-18-20260519-dsflash-vs-dspro-f1\case_field_pairs.jsonl`
- DS JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-18-20260519-dsflash-vs-dspro-f1\deepseek_v4_flash_outputs.jsonl`
- GPT JSONL: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-18-20260519-dsflash-vs-dspro-f1\deepseek_v4_pro_gold_outputs.jsonl`
