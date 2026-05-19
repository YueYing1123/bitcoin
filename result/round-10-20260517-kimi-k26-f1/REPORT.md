# round-10-20260517-kimi-k26-f1 DeepSeek-V4 vs Kimi-K2.6 1% 抽样评估报告

## 1. 任务说明

本轮使用 SiliconFlow 模型 `Pro/moonshotai/Kimi-K2.6` 在温度为 0 的条件下，对主数据集中随机 1% 的判决书重新抽取结构化字段，并把该结果作为代理正确答案。
被评估对象是已经生成的 `deepseek-ai/DeepSeek-V4-Flash` 全量抽取结果 `master_dataset_dsv4.jsonl`。

注意：这里的“正确答案”是 Kimi-K2.6 生成的代理金标准，不等同于人工标注真值。因此 F1 衡量的是 DeepSeek-V4 与 Kimi-K2.6 在同一提示词和同一文本上的一致性。

## 2. 抽样与运行设置

- 抽样数量：122 条。
- 字段数量：26 个。
- Kimi 模型：`Pro/moonshotai/Kimi-K2.6`。
- DeepSeek 模型：`deepseek-ai/DeepSeek-V4-Flash`。
- 温度：0。
- RPM：500。
- TPM：2,000,000。
- 抽样方式：固定随机种子生成候选顺序，抽到目标数量的正常 JSON 输出后停止；脚本支持断点续跑、并发、重试和进度条。

## 3. 指标定义

对每个字段，把 DeepSeek-V4 的抽取值与 Kimi-K2.6 的抽取值比较。

- 标量字段：两边都为空不计入 TP/FP/FN；两边相同计 TP；DeepSeek 多抽计 FP；DeepSeek 漏抽计 FN；两边非空但不同，同时计 FP 和 FN。
- 列表字段：把列表元素当作集合比较，交集为 TP，DeepSeek 独有为 FP，Kimi 独有为 FN。
- 金额字段：会把逗号、小数形式和“万/亿”等常见单位归一化后比较，避免 `1000` 与 `1,000.00` 这类格式差异造成误判。
- 日期、布尔值和空值也做了基础归一化。

## 4. 总体结果

- Micro Precision：81.34%
- Micro Recall：74.77%
- Micro F1：77.92%
- TP：2803
- FP：643
- FN：946
- Macro F1（全部字段）：75.56%
- Macro F1（有正例字段）：78.58%
- 字段级完全一致率：79.82%

## 5. 表现较好的字段

| 字段 | Precision | Recall | F1 | TP | FP | FN | Exact Match |
|---|---:|---:|---:|---:|---:|---:|---:|
| `case_profile.case_type_primary` | 100.00% | 100.00% | 100.00% | 122 | 0 | 0 | 100.00% |
| `case_profile.is_appeal` | 100.00% | 100.00% | 100.00% | 122 | 0 | 0 | 100.00% |
| `case_profile.procedure_stage` | 100.00% | 100.00% | 100.00% | 122 | 0 | 0 | 100.00% |
| `metadata.court_level` | 100.00% | 100.00% | 100.00% | 122 | 0 | 0 | 100.00% |
| `metadata.judgment_date` | 100.00% | 100.00% | 100.00% | 122 | 0 | 0 | 100.00% |
| `metadata.case_number` | 99.18% | 99.18% | 99.18% | 121 | 1 | 1 | 99.18% |
| `metadata.region` | 98.36% | 98.36% | 98.36% | 120 | 2 | 2 | 98.36% |
| `virtual_currency_info.involved` | 98.36% | 98.36% | 98.36% | 120 | 2 | 2 | 98.36% |

## 6. 表现较弱的字段

| 字段 | Precision | Recall | F1 | TP | FP | FN | Exact Match |
|---|---:|---:|---:|---:|---:|---:|---:|
| `llm_summary.reasoning_summary` | 0.00% | 0.00% | 0.00% | 0 | 122 | 122 | 0.00% |
| `metadata.first_instance_case_number` | 0.00% | 0.00% | 0.00% | 0 | 0 | 0 | 100.00% |
| `llm_summary.outcome_summary` | 11.48% | 11.48% | 11.48% | 14 | 108 | 108 | 11.48% |
| `judicial_analysis.judicial_framing` | 53.59% | 25.10% | 34.19% | 127 | 110 | 379 | 5.74% |
| `judicial_analysis.cited_policies` | 34.78% | 61.54% | 44.44% | 8 | 15 | 5 | 90.16% |
| `judicial_analysis.reason_for_invalidity` | 70.00% | 63.64% | 66.67% | 21 | 9 | 12 | 90.98% |
| `virtual_currency_info.currency_types` | 71.11% | 62.75% | 66.67% | 96 | 39 | 57 | 58.20% |
| `virtual_currency_info.activity_type` | 75.73% | 74.29% | 75.00% | 78 | 25 | 27 | 77.87% |

## 7. 全字段明细

| 字段 | 类型 | Gold正例 | Pred正例 | Precision | Recall | F1 | TP | FP | FN | Exact Match |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `case_amount` | scalar | 113 | 106 | 87.74% | 82.30% | 84.93% | 93 | 13 | 20 | 83.61% |
| `metadata.case_number` | scalar | 122 | 122 | 99.18% | 99.18% | 99.18% | 121 | 1 | 1 | 99.18% |
| `metadata.court_name` | scalar | 122 | 122 | 95.08% | 95.08% | 95.08% | 116 | 6 | 6 | 95.08% |
| `metadata.court_level` | scalar | 122 | 122 | 100.00% | 100.00% | 100.00% | 122 | 0 | 0 | 100.00% |
| `metadata.judgment_date` | scalar | 122 | 122 | 100.00% | 100.00% | 100.00% | 122 | 0 | 0 | 100.00% |
| `metadata.first_instance_case_number` | scalar | 0 | 0 | 0.00% | 0.00% | 0.00% | 0 | 0 | 0 | 100.00% |
| `metadata.region` | scalar | 122 | 122 | 98.36% | 98.36% | 98.36% | 120 | 2 | 2 | 98.36% |
| `metadata.doc_type` | scalar | 122 | 122 | 77.87% | 77.87% | 77.87% | 95 | 27 | 27 | 77.87% |
| `case_profile.case_type_primary` | scalar | 122 | 122 | 100.00% | 100.00% | 100.00% | 122 | 0 | 0 | 100.00% |
| `case_profile.case_type_secondary` | scalar | 122 | 122 | 79.51% | 79.51% | 79.51% | 97 | 25 | 25 | 79.51% |
| `case_profile.procedure_stage` | scalar | 122 | 122 | 100.00% | 100.00% | 100.00% | 122 | 0 | 0 | 100.00% |
| `case_profile.is_appeal` | scalar | 122 | 122 | 100.00% | 100.00% | 100.00% | 122 | 0 | 0 | 100.00% |
| `case_profile.litigant_profile.plaintiff_types` | list | 124 | 119 | 97.48% | 93.55% | 95.47% | 116 | 3 | 8 | 93.44% |
| `case_profile.litigant_profile.defendant_types` | list | 129 | 130 | 97.69% | 98.45% | 98.07% | 127 | 3 | 2 | 97.54% |
| `virtual_currency_info.involved` | scalar | 122 | 122 | 98.36% | 98.36% | 98.36% | 120 | 2 | 2 | 98.36% |
| `virtual_currency_info.currency_types` | list | 153 | 135 | 71.11% | 62.75% | 66.67% | 96 | 39 | 57 | 58.20% |
| `virtual_currency_info.activity_type` | scalar | 105 | 103 | 75.73% | 74.29% | 75.00% | 78 | 25 | 27 | 77.87% |
| `judicial_analysis.legal_characterization` | scalar | 122 | 122 | 81.97% | 81.97% | 81.97% | 100 | 22 | 22 | 81.97% |
| `judicial_analysis.virtual_currency_property_legality` | scalar | 91 | 93 | 77.42% | 79.12% | 78.26% | 72 | 21 | 19 | 76.23% |
| `judicial_analysis.contract_validity` | scalar | 46 | 39 | 100.00% | 84.78% | 91.76% | 39 | 0 | 7 | 94.26% |
| `judicial_analysis.reason_for_invalidity` | list | 33 | 30 | 70.00% | 63.64% | 66.67% | 21 | 9 | 12 | 90.98% |
| `judicial_analysis.cited_laws` | list | 728 | 723 | 87.55% | 86.95% | 87.25% | 633 | 90 | 95 | 65.57% |
| `judicial_analysis.cited_policies` | list | 13 | 23 | 34.78% | 61.54% | 44.44% | 8 | 15 | 5 | 90.16% |
| `judicial_analysis.judicial_framing` | list | 506 | 237 | 53.59% | 25.10% | 34.19% | 127 | 110 | 379 | 5.74% |
| `llm_summary.outcome_summary` | scalar | 122 | 122 | 11.48% | 11.48% | 11.48% | 14 | 108 | 108 | 11.48% |
| `llm_summary.reasoning_summary` | scalar | 122 | 122 | 0.00% | 0.00% | 0.00% | 0 | 122 | 122 | 0.00% |

## 8. 输出文件

- Kimi 代理金标准 JSONL：`D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-10-20260517-kimi-k26-f1\kimi_k26_gold_1pct.jsonl`
- Kimi 代理金标准 CSV：`D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-10-20260517-kimi-k26-f1\kimi_k26_gold_1pct.csv`
- 字段级指标 CSV：`D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-10-20260517-kimi-k26-f1\field_metrics.csv`
- 逐案逐字段对照 JSONL：`D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-10-20260517-kimi-k26-f1\dsv4_vs_kimi_pairs.jsonl`
- 汇总 JSON：`D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\result\round-10-20260517-kimi-k26-f1\metrics_summary.json`
