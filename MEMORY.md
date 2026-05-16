# MEMORY

## 项目定位

本目录用于承接法学数据分析论文项目。后续工作统一按“轮次化记录 + 代码/结果分离 + 原始材料只读 + 工作完成即同步”的方式执行。

除非用户明确要求跳过或调整，每次新任务都应先理解目标、边界和关键假设，再勘察现有目录、数据样本、代码和输出，随后制定计划、执行最小必要改动、先做小样本烟测，再进入完整计算或主样本分析，最后报告变更、产物、验证结果和剩余风险。

## 轮次命名

- 轮次目录统一命名为 `round-n-时间戳`
- 时间戳格式统一为 `yyyyMMdd-HHmmss`
- `n` 为递增整数，从 `1` 开始

## 每轮开始前必须做的事

每次接受新指令后，先创建同名轮次目录：

- `docs/plan/round-n-时间戳/`
- `docs/analysis/round-n-时间戳/`
- `docs/report/round-n-时间戳/`
- `code/round-n-时间戳/`
- `result/round-n-时间戳/`

然后按顺序生成或维护文件：

1. 先写 `docs/plan/round-n-时间戳/plan-时间戳.md`
2. 勘察、实现和实验过程中持续写 `docs/analysis/round-n-时间戳/analysis-时间戳.md`
3. 工作结束后写 `docs/report/round-n-时间戳/report-时间戳.md`

## 每轮文件保存约定

- `docs/plan/`：任务计划、拆解、假设、风险、验收口径
- `docs/analysis/`：项目勘察、数据结构分析、问题定位、实验过程中的中间判断
- `docs/report/`：本轮完成情况、变更摘要、验证结果、遗留问题
- `code/round-n-时间戳/`：本轮新增脚本、辅助工具、自动化脚本、实现草稿
- `result/round-n-时间戳/`：本轮运行结果、环境检查、日志摘要、截图或导出的产物

## 通用数据治理约定

- 原始数据、原始文本、人工标注原件、第三方下载材料默认只读，不在原路径上直接改动。
- 新增、清洗、抽取、编码、重算或合并得到的派生产物，应放入清晰的轮次目录或版本目录，避免覆盖旧口径。
- 每次数据处理都应保留输入范围、处理参数、代码版本、样本审计和可复现说明。
- 对文本抽取、正则命中、模型分类、实体识别、地名识别、金额识别、日期识别等结果，应尽量保留原文证据片段、命中规则或模型信息、质量标记，方便抽查。
- 对匿名、缺损、编码破损、来源不明或无法可靠解析的字段，不应强行推断；应保留为 `unmapped`、`unknown`、`invalid` 或转入单独审计清单。
- 外部知识库、行政区划库、行业分类表、法律法规清单等依赖项应记录来源、版本和获取日期，优先使用可复现的公开来源或稳定组件。
- 数据口径调整应另存新版本，并在报告中说明与旧口径的差异。

## 推荐基础目录

- `data/raw/`：原始材料，只读保存
- `data/interim/`：清洗、切分、解析过程中的中间数据
- `data/processed/`：可进入统计、建模或论文表格的处理后数据
- `data/external/`：外部依赖数据，如区划、法规清单、词表、映射表
- `data/audit/`：抽查样本、异常清单、人工复核记录
- `config/`：参数、路径、字段口径、实验配置
- `references/`：论文、规范、数据说明、外部资料说明

## Legacy 区说明

- `docs/legacy/`：历史说明文档、旧报告、旧根 README
- `code/legacy/`：历史根目录脚本
- `result/legacy/`：历史 benchmark、评估结果、备份、日志、样例输入

原则：

- 历史资产不删除，统一进入 `legacy`
- 新工作不继续把散乱文件直接堆在根目录

## Git / Gitee 约定

每次工作完成后，如当前目录是 git 仓库或用户要求同步，应把当前目录内容同步到 Gitee。

固定 git 身份：

```powershell
git config --global user.name "YueYing1123"
git config --global user.email "yingyue993@gmail.com"
```

远端仓库：

```powershell
git@gitee.com:yueying1123/fudan-extraction.git
```

推荐同步流程：

```powershell
git add -A
git commit -m "round-n: 简述本轮工作"
git push origin main
```

如果当前目录还不是 git 仓库，先建立与远端的关联，再推送。推送前优先验证远端是否可访问：

```powershell
git ls-remote git@gitee.com:yueying1123/fudan-extraction.git
```

## SSH 约定

用户给出的目标公钥路径是：

```powershell
cat ~/.ssh/yy_rsa.pub
```

注意：

- 不要假定固定 key 文件一定存在
- 后续推送前，以“能否访问远端”为准

## 环境约定

统一使用根目录 `.venv/` 保存虚拟环境，可按用途拆分：

- `.venv/data_cleaning`
- `.venv/text_analysis`
- `.venv/statistics`
- `.venv/visualization`

默认不要把 `.venv/` 提交到仓库。

## 当前轮次

当前已初始化轮次：

- `round-1-20260516-062855`

## 主数据集约定

后续研究默认以以下主数据集为基地：

- CSV：`data/processed/master/master_dataset.csv`
- JSONL：`data/processed/master/master_dataset.jsonl`
- 字段字典：`data/processed/master/master_dataset_dictionary.csv`
- 生成审计：`data/processed/master/master_dataset_audit.json`
- 生成脚本：`code/round-3-20260516-070718/build_master_dataset.py`

当前主数据集由 `round-3-20260516-070718` 生成。稳定文件名始终指向最新主数据，同时保留带时间戳版本。

主数据集合并了旧扁平分析表、LLM 最终抽取 JSONL、LLM 顶层金额、LLM 原始金额字段、全文正则金额、索引正则金额、原始索引字段和原始文本审计信息。全文不直接嵌入主表；需要全文时，以 `data/raw/data-texts.json` 为准，通过 `doc_id` 关联。

金额变量使用约定：

- `llm_top_case_amount_cny`：来自 `final_all.jsonl` 顶层 `case_amount`，当前是主要 LLM 金额来源。
- `llm_total_amount_cny`：来自 `final_fields.virtual_currency_info.total_amount_cny`，当前数据中该字段为空，但保留用于兼容后续重抽取。
- `regex_text_amounts_json` 及其统计字段：来自全文正则匹配，保留候选列表和统计值，适合审计与替代口径。
- `amount_master_cny`：后续默认金额变量；优先级为 `llm_top_case_amount_cny`、`llm_total_amount_cny`、旧扁平表 `case_amount`、旧扁平表 `total_amount_cny`、全文正则最大值、索引正则最大值。
- `amount_master_source` 与 `amount_master_is_regex_fallback` 必须随金额结果一起报告，避免混淆 LLM 金额和正则兜底金额。

当前生成审计结果：

- 主表行数：12,135
- `doc_id` 唯一数：12,135
- `amount_master_cny` 非空：12,102
- LLM 顶层金额非空：11,684
- LLM 字段 `virtual_currency_info.total_amount_cny` 非空：0
- 全文正则金额非空：12,100
- LLM 顶层金额与全文正则候选不一致标记：1,720

## round-4 规格检验结论

当前最新规格检验产物：

- 脚本：`code/round-4-20260516-071827/spec_check.py`
- 结果目录：`result/round-4-20260516-071827/`
- 派生分析数据：`result/round-4-20260516-071827/analysis_dataset_derived.csv`
- 描述统计：`result/round-4-20260516-071827/descriptive_tables.xlsx`
- 主要回归项：`result/round-4-20260516-071827/regression_key_terms.csv`
- 完整回归：`result/round-4-20260516-071827/regression_results_full.csv`
- 地区映射审计：`result/round-4-20260516-071827/region_mapping_audit.csv`

变量口径：

- `contract_invalid`：完全有效记为 0；无效、未成立、不成立、部分无效、部分有效、不适用、可撤销等非完全有效状态记为 1。
- 地区变量优先用 `cpca` 从 `court_name` / `index_court_name` 识别；未映射时用案号省级简称兜底。不要继续依赖原始空 `region` 字段。
- 金额分析必须同时报告主金额、LLM 金额、正则最大金额、`amount_master_source`、`amount_master_is_regex_fallback`、`amount_llm_regex_text_conflict`。

本轮实证结论：

- 金额不是不可用：`amount_master_cny` 非空 12,102，LLM 金额非空 11,684，正则最大金额非空 12,100。LLM 金额出现在正则候选列表中的比例为 85.3%，冲突比例为 14.7%。
- 但金额作为单一主解释变量不稳：主 LPM 中 `log_amount_master` 系数 0.0025，p=0.429；加入活动类型和年份后仍不显著。正则最大金额口径显著为负，说明金额结论对口径敏感。
- 地区变量可用：省份映射 12,103 条，覆盖率 99.7%；其中 `cpca_court` 12,019 条，案号兜底 84 条，未映射 32 条。
- Big4 地区（北京、上海、广东、浙江）在控制金额、金额质量标记、法院层级和案由后，非完全有效概率低约 8.2 个百分点，p<0.001。
- 2021 政策后效应最稳：主 LPM 中 `post2021` 系数 0.0767，p<0.001；民商事子样本中为 0.0945，p<0.001；严格因变量口径下为 0.0784，p<0.001。

下一阶段主研究方向暂定为：

**虚拟货币司法裁判中政策冲击、交易类型与合同效力认定的实证研究：兼论金额规模与地区差异。**

后续优先：

1. 主回归限定民商事样本，刑事样本作为对照或排除。
2. 将活动类型压缩为投资/理财、交易/OTC、借贷、挖矿、技术服务、ICO/发币、其他等可解释类别。
3. 围绕 2021 政策节点做事件研究或分年份趋势图。
4. 金额作为机制、异质性和稳健性变量，不直接把线性金额效应作为主结论。
5. 地区使用省份、宏观区域、Big4 三层口径。


## round-5 ????????

?????????????

**???????????????????????????????????????????**

???????

- ????????????????????/???
- ??????????????/?????/???ICO/???????????????????/????????
- ???????????LLM ???????????? `amount_master_source`?`amount_master_is_regex_fallback`?`amount_llm_regex_text_conflict`?
- ????????????????????????????????? `region` ???

???????

- 2021 ?????????????????? 8.7 ? 11.2 ?????
- ????????????ICO/?????/?????/??????????????
- ??????????????????/?????/???ICO/???????????
- ????????????????????????????????????
- Big4 ??????????? 2021 ?????????

?? round-5 ?????

- ???`code/round-5-20260516-122140/paper_analysis.py`
- ???`result/round-5-20260516-122140/`
- ???`docs/report/round-5-20260516-122140/report-20260516-122140.md`
- ???`docs/analysis/round-5-20260516-122140/analysis-20260516-122140.md`
