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

## Git 同步约定

每次工作完成后，如当前目录是 git 仓库或用户要求同步，应把当前目录内容同步到远端仓库。

当前远端仓库：

```powershell
https://github.com/YueYing1123/bitcoin.git
```

推荐同步流程：

```powershell
git add -A
git commit -m "round-n: 简述本轮工作"
git push origin main
```

如果当前目录还不是 git 仓库，先建立与远端的关联，再推送。推送前优先验证远端是否可访问：

```powershell
git ls-remote https://github.com/YueYing1123/bitcoin.git
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
- `round-2-20260516-063920`
- `round-3-20260516-070718`
- `round-4-20260516-071827`
- `round-5-20260516-122140`
- `round-6-20260516-215644`
- `round-7-20260517-020639`
- `round-8-20260517-031538`

当前最新轮次为 `round-8-20260517-031538`。

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

## round-5 论文主线结果

本轮已完成主线实证：

**虚拟货币司法裁判中政策冲击、交易类型与合同效力认定的实证研究：兼论金额规模与地区差异。**

关键判断：

- 2021 政策节点后，民商事样本中合同非完全有效概率稳定上升，主效应约 8.7 到 11.2 个百分点。
- 交易类型是最强解释维度，`ICO/发币`、`投资/理财`、`交易/买卖`、`挖矿` 的效应最明显。
- 金额必须保留，但不应被写成主结论；LLM 金额、正则金额和主金额都要并列报告。
- 地区变量可用，建议用法院名称映射出的省份、宏观区域和 Big4 三层口径。
- 刑事样本更适合作为参考或对照，主回归应放在民商事样本。

主要产物：

- `code/round-5-20260516-122140/paper_analysis.py`
- `result/round-5-20260516-122140/`
- `docs/analysis/round-5-20260516-122140/analysis-20260516-122140.md`
- `docs/report/round-5-20260516-122140/report-20260516-122140.md`

## round-6 研究结果报告整理

本轮任务不是新增统计回归，而是把 round-5 的结果整理成一份面向初学者的完整研究结果报告。

写作要求：

- 详细解释合同效力、政策冲击、交易类型、金额变量、地区变量和线性概率模型。
- 用通俗语言解释每个系数的含义，尽量把“统计结果”翻译成“法学上能读懂的话”。
- 明确说明哪些结论稳健，哪些结论只能作为辅助或稳健性结果。
- 不新增主回归，不改动既有数据口径，只做报告型整合。

本轮产物：

- `docs/plan/round-6-20260516-215644/plan-20260516-215644.md`
- `docs/analysis/round-6-20260516-215644/analysis-20260516-215644.md`
- `docs/report/round-6-20260516-215644/report-20260516-215644.md`
- `code/round-6-20260516-215644/README.md`
- `result/round-6-20260516-215644/README.md`

## round-7 提示词溯源与整合

本轮任务是根据当前主数据集字段，追踪旧数据构建流程中实际使用的 LLM 提示词，并确认 `case_amount` 金额字段的来源。

关键结论：

- 基础法律字段的历史抽取提示词是 `数据构建/ensemble_els/prompts/extract_cn.jinja2`，迁移副本位于 `code/round-2-20260516-063920/ensemble_els/prompts/extract_cn.jinja2`。
- 旧字段配置为 `数据构建/docs/fields.yaml`，迁移副本位于 `data/external/fields.yaml`。
- 当前主数据集的主要 LLM 金额来自 `data/processed/extraction/final_all.jsonl` 顶层 `case_amount`，主数据集生成脚本将其保存为 `llm_top_case_amount_cny` 并优先用于 `amount_master_cny`。
- 在 `数据构建` 与 `newstudy` 现有底稿中没有找到独立的 `case_amount` 抽取提示词或 schema；因此不能声称已经找到原始 `case_amount` 提示词原件。
- 已基于旧主提示词和当前主数据集字段重构整合版提示词，保存在 `docs/legacy/master_prompt.md`。该版本不再使用 `plaintiff_claimed_cny` 与 `court_recognized_cny`，而是使用顶层 `case_amount` 作为 LLM 金额字段。
- 本次提示词溯源按用户要求不纳入正则匹配金额口径；正则金额仍只作为审计、对照和兜底数据。

本轮产物：

- `docs/legacy/master_prompt.md`
- `docs/plan/round-7-20260517-020639/plan-20260517-020639.md`
- `docs/analysis/round-7-20260517-020639/analysis-20260517-020639.md`
- `docs/report/round-7-20260517-020639/report-20260517-020639.md`

## round-8 DeepSeek 标准答案与 master F1 检验

本轮按用户要求使用 SiliconFlow 上的 `deepseek-ai/DeepSeek-V4-Flash`，温度为 0，在 TPM 2,000,000、RPM 500 口径下，以 `docs/legacy/master_prompt.md` 当前正式提示词对主数据集约 1% 样本重新抽取。DeepSeek 输出作为标准答案，已有 `master_dataset.csv` 作为被评估对象。

抽取结果：

- 主数据集总量：12,135
- 1% 目标正常输出：122
- 实际正常输出：122
- 安全拒绝：0
- 其他失败：0
- 标准答案文件：`data/processed/master/compare.jsonl`

评分结果：

- 评分脚本：`code/round-8-20260517-031538/deepseek_compare_eval.py`
- 结果目录：`result/round-8-20260517-031538/`
- `field_f1.csv`：逐字段 TP、FP、FN、precision、recall、F1
- `f1_summary.json`：总体 micro/macro 指标
- `f1_report.md`：可读报告
- Micro precision：0.8333
- Micro recall：0.2694
- Micro F1：0.4072
- Micro TP/FP/FN：930 / 186 / 2522
- Macro F1：0.3157

主要解释：

- master 在案号、裁判日期、是否上诉、程序阶段、法院名称等基础字段上表现较好。
- `case_amount` 可用但仍有错配：F1=0.6667，TP=75，FP=41，FN=34。
- `contract_validity` F1=0.7708，`legal_characterization` F1=0.7131，`activity_type` F1=0.2796。
- macro F1 低的主要原因是当前提示词要求抽取很多旧 master 中基本为空的字段，例如 region、doc_type、case_type、当事人类型、币种、引用法律政策、司法框架与摘要字段，导致大量 FN。

## ������ܽ��

- `round-11-20260517-dsv4-reanalysis` ����ɣ��Ҹ�Ϊ�� Python ·��������ʹ�� mcp-stata��
- �����ѱ���Ĺؼ��ļ���
  - `result/round-11-20260517-dsv4-reanalysis/f1_basis.json`
  - `result/round-11-20260517-dsv4-reanalysis/analysis_input_dsv4_merged.csv`
  - `result/round-11-20260517-dsv4-reanalysis/paper_analysis_dataset.csv`
  - `result/round-11-20260517-dsv4-reanalysis/paper_summary.json`
  - `docs/plan/round-11-20260517-dsv4-reanalysis/plan-20260517-dsv4-reanalysis.md`
  - `docs/analysis/round-11-20260517-dsv4-reanalysis/analysis-20260517-dsv4-reanalysis.md`
  - `docs/report/round-11-20260517-dsv4-reanalysis/report-20260517-dsv4-reanalysis.md`
- ���������ۣ�
  - 2021 ���߳����Ȼ�ȶ�����
  - �������ʹ����Ľ������������
  - ���͵������ʺ���������������
  - ��ǰ����ϣ�������������ǣ�
    `�������˾�����������߳���������������ͬЧ���϶���ʵ֤�о������۽���ģ���������`
- ���� F1 ���ۣ�
  - micro F1 = `0.7791521890201529`
  - micro precision = `0.8134068485200232`
  - micro recall = `0.7476660442784743`
  - macro F1 excluding free text = `0.8137672432638258`
## round-12 顶刊规格深化研究

本轮目录：`result/round-12-20260518-top-journal-deepening`。

本轮基于第 11 轮 DSV4 主数据底稿，按顶刊实证论文要求补齐了样本审计、描述统计、模型设定、主回归、机制分析、金额与地区异质性、事件研究、严格因变量、替代金额、金额缩尾、剔除极端金额、安慰剂政策节点、留一省份和 Logit 稳健性检验，并生成完整中文报告。

核心结论：
- 2021 政策冲击在多数核心规格中保持显著，但加入线性时间趋势后不再显著，说明需要将政策节点与整体裁判时间趋势共同解释；
- 交易类型带来的解释力提升最大，是当前论文的主机制；
- 金额变量可用，`case_amount` F1 较好，但金额更适合做机制、控制与异质性；
- 地区差异存在，适合放在异质性章节；
- 研究主线继续确定为：`虚拟货币司法裁判中政策冲击、交易类型与合同效力认定的实证研究：兼论金额规模与地区差异`。

核心产物：
- `result/round-12-20260518-top-journal-deepening/round12_summary.json`
- `result/round-12-20260518-top-journal-deepening/tables/publication_regression_table_wide.csv`
- `result/round-12-20260518-top-journal-deepening/tables/model_key_terms.csv`
- `result/round-12-20260518-top-journal-deepening/tables/event_study_2020_base.csv`
- `result/round-12-20260518-top-journal-deepening/tables/robustness_placebo_cutoffs.csv`
- `result/round-12-20260518-top-journal-deepening/tables/robustness_leave_one_province_out.csv`
- `result/round-12-20260518-top-journal-deepening/figures/`
- `docs/report/round-12-20260518-top-journal-deepening/report-20260518-top-journal-deepening.md`
