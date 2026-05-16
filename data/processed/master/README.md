# Master Dataset

Current stable master dataset: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\data\processed\master\master_dataset.csv`
Current stable JSONL mirror: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\data\processed\master\master_dataset.jsonl`
Data dictionary: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\data\processed\master\master_dataset_dictionary.csv`
Audit file: `D:\BaiduSyncdisk\Doctor\论文\数字货币\研究\newstudy\data\processed\master\master_dataset_audit.json`

This table merges the old flat analysis data, final LLM extraction JSONL, regex amount extraction from full text, regex amount extraction from index metadata, raw index metadata, and raw-text audit metadata.

The full judgment text is not embedded in the table. Use `data/raw/data-texts.json` keyed by `doc_id` when full text is needed.

Amount priority for `amount_master_cny`: llm top-level `case_amount`, LLM field `virtual_currency_info.total_amount_cny`, flat `case_amount`, flat `total_amount_cny`, regex text max, regex index max.