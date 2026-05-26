# 当前数据情况报告

生成时间: 2026-05-25 (Asia/Shanghai)

## 1. 原始数据

- 原始元数据: `data/raw/data-index.json`
- 原始记录数: `12135` 条

## 2. 当前主数据 / 基础数据集

- 主数据集: `data/processed/master/data_index_noncriminal_base.csv`
- CSV 记录数: `6193` 条
- JSONL 记录数: `6193` 条
- 唯一 `doc_id` 数: `6193`

### 是否过滤刑事

是。

过滤方法：基于原始 `data-index.json` 的「案由/罪名」字段，排除所有包含“罪”字的记录。

- 被排除的明确刑事 / 罪名记录数: `5942` 条
- 保留的非刑事基础记录数: `6193` 条

### 是否过滤相关性 / 涉虚拟货币

否。

当前主数据集没有使用 `ds-v4-flash`、`ds-v4-pro`、`involved=true` 或 `typical_virtual_currency=true` 进行相关性过滤；它只做了刑事排除。是否为典型虚拟货币案件，是在后续 `ds-v4-pro` 抽取和人工标注字段中判断。

## 3. 正式测试数据集

- 测试集文件: `result/round-25-20260520-noncriminal-index-stratified-test-set/test_set_5pct_year_region_appeal_priority.csv`
- 测试集记录数: `309` 条
- 测试集唯一 `doc_id` 数: `309`
- `test_set_doc_ids.json` 中 ID 数: `309`
- 测试集占当前主数据集比例: `4.9895%`
- 与当前主数据集 ID 交集: `309 / 309`

## 4. 测试集制作方法

1. 输入：原始 `data/raw/data-index.json`，而不是早先 `ds-v4-flash` 过滤后的 9000 多条数据。
2. 排除明确刑事案件：`案由/罪名` 字段只要含“罪”字即排除。
3. 在剩余 `6193` 条非刑事基础集中抽取 `5%` 总额度，目标数按 `int(6193 * 0.05)` 得到 `309` 条。
4. 按年份比例分配 `309` 条额度，使用最大余数法保持年份分布接近总体。
5. 在每个年份组内，再按省级地区分布分配该年份额度，同样使用最大余数法。
6. 在每个“年份-省级地区”子组内随机抽样，并把二审案件排在优先池中，尽可能先抽二审。

- 随机种子: `20260520`
- 年份分组数: `16`
- 年份-地区分组数: `299`

## 5. 分布概览

### 程序分布

主数据程序分布：

```json
{
  "二审": 1874,
  "一审": 4275,
  "非诉执行审查": 10,
  "再审": 28,
  "未明确程序": 5,
  "再审审查与审判监督": 1
}
```

测试集程序分布：

```json
{
  "一审": 6,
  "二审": 303
}
```

### 年份范围

- 主数据年份范围: `2010` 至 `2025`
- 测试集年份范围: `2010` 至 `2024`

### 测试集地区 Top 10

```json
{
  "广东": 49,
  "浙江": 27,
  "山东": 26,
  "北京": 24,
  "江苏": 16,
  "上海": 15,
  "四川": 15,
  "河南": 15,
  "湖南": 15,
  "福建": 14
}
```

## 6. 当前网页随机标注批次

- 当前挂载批次: `result/round-32-20260525-noncriminal-random10-annotation-web`
- 当前网页随机标注样本数: `10`
- 抽样时排除: `round-25` 正式测试集 `309` 个 ID + 此前网页随机样本 `80` 个 ID
- 与正式测试集重叠: `0`
- 手工标注状态: 已清空，`annotated_count=0`

## 7. 关键文件

- 非刑事基础集 CSV: `data/processed/master/data_index_noncriminal_base.csv`
- 非刑事基础集 JSONL: `data/processed/master/data_index_noncriminal_base.jsonl`
- 被排除刑事记录: `result/round-25-20260520-noncriminal-index-stratified-test-set/data_index_criminal_excluded_by_case_reason_contains_zui.csv`
- 正式测试集: `result/round-25-20260520-noncriminal-index-stratified-test-set/test_set_5pct_year_region_appeal_priority.csv`
- 测试集 ID: `result/round-25-20260520-noncriminal-index-stratified-test-set/test_set_doc_ids.json`
- 年份额度: `result/round-25-20260520-noncriminal-index-stratified-test-set/year_allocation.csv`
- 年份-地区额度: `result/round-25-20260520-noncriminal-index-stratified-test-set/year_region_allocation.csv`
