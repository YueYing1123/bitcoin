# 数字货币裁判文书结构化数据：可复现分析报告（基于 `analyze/` 产出）

本报告整合当前工作区内**相对可靠**的分析结论，并对关键限制作出明确说明。文中每条核心结论后均给出对应证据文件在 `analyze/` 下的**相对路径**，便于你追溯与引用。

---

## 0. 数据与口径说明（非常重要）

- **样本来源**：`final_all.jsonl` 扁平化后得到的案件级数据表。
  - **扁平化数据（CSV）**：`analyze/data/final_all_flat.csv`
  - **扁平化数据（DTA）**：`analyze/data/final_all_flat.dta`

- **合同效力因变量口径**：在主脚本中构造了二元变量 `contract_invalid`：
  - 若 `contract_validity` 文本包含 “无效 / 部分无效 / 未成立” → `contract_invalid=1`
  - 若包含 “有效” → `contract_invalid=0`
  - 否则缺失（不进入相关回归/DID）
  - **脚本实现**：工作目录根下 `analyze_all.do`（DID/事件研究也沿用该口径）

- **金额变量不可用（当前数据事实）**：`total_amount_cny` 在现有数据中为 **100% 缺失**，因此任何包含 `ln_amount` 的模型都无法真正“控制金额”，相关项会被共线性剔除或等价于常数项。
  - **诊断证据**：`analyze/diagnostics/amount_diagnostics.log` 与 `analyze/diagnostics/amount_diagnostics.xlsx`
  - **含义**：本报告中所有与金额相关的解释均不作因果/机制推断。

---

## 1. 描述性事实：年度趋势与案件结构

### 1.1 年度案件量（基础事实）

- **输出表**：按 `judgment_year` 聚合的案件量。
  - `analyze/tables/tab_cases_by_year.xlsx`
- **输出图**：年度案件量柱状图。
  - `analyze/figures/fig_cases_by_year.png`

### 1.2 合同效力（有效/无效/未成立）的时间变化

- **输出图**：按年份的 `contract_invalid` 均值（可理解为“无效/未成立比例”）。
  - `analyze/figures/fig_invalid_rate_by_year.png`

> 解释提示：这是**描述性**比例（年度均值），不区分案件类型/地区结构变化，也不满足因果识别条件。

### 1.3 活动类型 Top10/Top20（案件结构）

- **输出表**：活动类型 Top20。
  - `analyze/tables/tab_activity_type_top20.xlsx`
- **输出图**：活动类型 Top10。
  - `analyze/figures/fig_activity_type_top10.png`

---

## 2. 政策冲击：DID（静态）结果（谨慎解释）

我们以判决日期作为时间轴，构造两个政策断点（2017-09-04 / 2021-09-24），用“交易类 vs 非交易类”作为处理组与对照组，估计政策冲击对 `contract_invalid` 的影响。

### 2.1 处理组/对照组如何划分（交易类 vs 非交易类）

在主脚本中，处理组 `trade_group=1` 的判定基于 `activity_type` 的关键词匹配（包含任一关键词则判为交易类）：

- `场外交易 | 交易 | 买卖 | 发币 | ICO | 兑换`

对照组 `trade_group=0`：不匹配关键词且 `activity_type` 非空；`activity_type` 为空则 `trade_group` 缺失并在 DID 样本中剔除。

> 这一点会影响并行趋势与识别强度：若关键词口径过宽，处理组内部异质性会很大。

### 2.2 样本限定（用于 DID/事件研究）

为减少“刑事/行政案件混入导致的合同效力含义不一致”，DID/事件研究使用了更严格样本：

- `sample_civil_commercial==1`（通过 `case_type_primary/doc_type/case_number` 文本规则近似“民事/商事”）
- 且 `contract_invalid` 非缺失（等价于确实讨论合同效力并可映射到有效/无效/未成立）

### 2.3 DID 估计结果（静态）

**表格输出（RTF）**：

- `analyze/tables/did_contract_invalid.rtf`

**关键系数（建议只引用交互项）**：

- **2017 冲击（94 公告）**：`trade_group × post2017` 的系数为 **0.134**，标准误 **0.107**，统计上**不显著**。  
  - 解释（描述性/相对变化）：2017 断点前后，“交易类相对非交易类”的合同无效/未成立概率变化，没有显著差异。  
  - 证据：`analyze/tables/did_contract_invalid.rtf`（行：`1.trade_group#1.post2017`）

- **2021 冲击（254 通知）**：`trade_group × post2021` 的系数为 **-0.153***，标准误 **0.042**，在 1% 水平显著。  
  - 解释（描述性/相对变化）：2021 断点后，“交易类相对非交易类”的合同无效/未成立概率**下降约 15.3 个百分点**。  
  - 证据：`analyze/tables/did_contract_invalid.rtf`（行：`1.trade_group#1.post2021`）

**样本量与设定**：

- 两个 DID 回归样本量均为 **N=3984**，标准误按 **法院（`court_name_id`）聚类**，并加入**月度固定效应**与控制变量。  
  - 证据：`analyze/tables/did_contract_invalid.rtf`（底部 `N` 与备注）

**可靠性提示**：

- DID 的因果解释依赖并行趋势；因此建议结合事件研究图（下一节）一起判断，避免直接把静态 DID 当作“政策因果效应”。

---

## 3. 事件研究（动态 DID）：并行趋势诊断（建议重点看）

事件研究将 `trade_group × 相对月份(k)` 的一系列交互项放入回归（基准期为政策前 1 个月 `k=-1`），并画出系数路径及 95% 置信区间，用来检验并行趋势与冲击后的动态效应。

### 3.1 2017 事件研究

- **输出表（RTF）**：`analyze/tables/eventstudy_2017.rtf`
- **输出图（PNG）**：`analyze/figures/eventstudy_2017.png`

**怎么读**：

- \(k<0\)（政策前）系数应围绕 0 且大多不显著 → 并行趋势更可信
- \(k\ge0\)（政策后）系数的持续偏离 → 动态冲击路径

**本次结果（相对可靠的结论）**：

- 政策前出现显著偏离（例如 `es17_m18=1.157***`、`es17_m14=1.302***`），提示 **2017 并行趋势假设存在明显风险**。  
  - 证据：`analyze/tables/eventstudy_2017.rtf`（`es17_m18`、`es17_m14` 行）与 `analyze/figures/eventstudy_2017.png`
- 样本量偏小，许多月份估计为 `0.000 (.)`（通常对应样本稀疏/共线/完全预测），因此 2017 动态路径更不稳定。  
  - 证据：`analyze/tables/eventstudy_2017.rtf`（多行 `0.000 (.)`），以及表格底部的 `N`（建议打开 RTF 查看）

### 3.2 2021 事件研究

- **输出表（RTF）**：`analyze/tables/eventstudy_2021.rtf`
- **输出图（PNG）**：`analyze/figures/eventstudy_2021.png`

**本次结果（相对可靠的结论）**：

- 政策前仍存在显著项（例如 `es21_m20=0.642***`、`es21_m17=0.465**`、`es21_m11=0.370*`），说明 **并行趋势并不理想**。  
  - 证据：`analyze/tables/eventstudy_2021.rtf`（相应行）与 `analyze/figures/eventstudy_2021.png`
- 相比 2017，2021 样本更大、曲线更平滑，但政策后系数非单调，提示冲击后结构变化/处理组异质性可能较强。  
  - 证据：`analyze/figures/eventstudy_2021.png`

---

## 4. Logit 回归（结构相关性：可做描述性关联，不建议做机制因果）

- **输出表（RTF）**：`analyze/tables/logit_contract_invalid.rtf`
- **活动类型系数汇总（便于阅读）**：`analyze/tables/logit_activity_type_effects.xlsx`（同内容 CSV：`analyze/tables/logit_activity_type_effects.csv`）

**可以相对可靠地说什么**：

- 在控制多维分类变量与时间因素后，活动类型、法院层级、程序阶段等与 `contract_invalid` 存在显著相关性（部分类型系数显著）。  
  - 证据：`analyze/tables/logit_contract_invalid.rtf`

### 4.1 哪些活动类型与 `contract_invalid` 显著相关（基于 logit 系数）

说明：

- 这里的 `b` 是 **log-odds 系数**，`OR=exp(b)` 是**胜算比**（更直观）。  
- 当前回归的活动类型基准类别是 `activity_type_id=0b`（脚本把缺失归入 0 类），因此这些系数是“相对基准类别”的差异；更稳妥的用法是把它们理解为**与合同无效/未成立的相关性强弱与方向**。  
- 对 **N 很小** 的活动类型（例如 N=2、3、4、6、9 等）即便显著，也要谨慎解释（可能是样本稀疏导致的分离/极端估计）。

在样本量较大的活动类型中，以下类别与 `contract_invalid=1` **显著正相关**（p 值见表；OR 供直觉理解）：

- **发币/ICO（N=1034）**：\(b=3.625\)，\(OR=37.51\)，p≈0  
- **场外交易(OTC)（N=989）**：\(b=2.455\)，\(OR=11.65\)，p≈\(4.6\times10^{-33}\)  
- **虚拟货币交易（N=381）**：\(b=2.297\)，\(OR=9.94\)，p≈\(3.5\times10^{-17}\)  
- **挖矿（N=846）**：\(b=1.221\)，\(OR=3.39\)，p≈\(6.5\times10^{-16}\)  
- **委托理财/代投（N=1680）**：\(b=1.623\)，\(OR=5.07\)，p≈0  
- **技术服务（N=687）**：\(b=1.136\)，\(OR=3.11\)，p≈\(8.6\times10^{-6}\)  
- **虚拟货币借贷（N=731）**：\(b=0.734\)，\(OR=2.08\)，p≈\(1.8\times10^{-6}\)  
- **交易所炒币（N=204）**：\(b=2.008\)，\(OR=7.45\)，p≈\(2.1\times10^{-13}\)  
- **虚拟货币投资（N=282）**：\(b=1.474\)，\(OR=4.37\)，p≈\(2.8\times10^{-15}\)  

证据文件：

- `analyze/tables/logit_activity_type_effects.xlsx`（列：`activity_type_label, N_cases, b, p, OR, sig`）

**不建议强解释的点**：

- 由于 `total_amount_cny` 全缺失，金额相关变量不具备可解释性（在回归中会被 omitted / 等价于常数）。  
  - 证据：`analyze/diagnostics/amount_diagnostics.log`

---

## 5. 地域分布与案由分布的关系（描述性：较可靠）

该部分使用独立脚本对地域与案由的分布关系做表格与可视化呈现。地域变量在 `region` 缺失时会从案号 `case_number` 提取省份简称推断（属于“可复现的近似口径”，粒度为省级）。

- **脚本**：工作目录根下 `analyze_region_cause.do`

### 5.1 地域分布（Top20）

- 表：`analyze/region_cause/tables/tab_region_top20.xlsx`
- 图：`analyze/region_cause/figures/fig_region_top20.png`

### 5.2 案由/法律定性分布（Top20）

- 表：`analyze/region_cause/tables/tab_cause_top20.xlsx`
- 图：`analyze/region_cause/figures/fig_cause_top20.png`

### 5.3 地域与案由分组的关系

- 表（Top10 地域 × 案由分组，行内份额）：`analyze/region_cause/tables/tab_region_by_causegroup_top10.xlsx`
- 图（Top8 地域内份额，小多图）：`analyze/region_cause/figures/fig_region_causegroup_share_top8.png`
- **热力图（Top10 地域 × 案由分组；色阶=地域内份额）**：`analyze/region_cause/figures/fig_region_cause_heatmap_top10.png`
- 卡方检验结果（独立性检验）写入日志：`analyze/region_cause/logs/region_cause.log`（搜索 `chi2` 段落）

---

## 6. 建议的下一步（如果要写成更强的实证论文）

1) **补齐可用金额字段**：用 `fields.yaml.backup` 中的 `court_recognized_cny / plaintiff_claimed_cny` 替代 `total_amount_cny`，重新扁平化再估计。  
2) **改进处理组定义**：将 `activity_type` 多标签拆分并归并成少量大类，减少处理组内部异质性。  
3) **事件研究分箱**：把相对月份按季度/半年分箱，并报告政策前交互项的联合显著性检验。  
4) **更严格样本**：进一步明确限制为民商事合同纠纷，并确保文书中确实讨论合同效力。

---

## 7. 产出清单（便于引用）

- **主表/主图**：`analyze/tables/`、`analyze/figures/`
- **DID/事件研究**：`analyze/tables/did_contract_invalid.rtf`、`analyze/tables/eventstudy_2017.rtf`、`analyze/tables/eventstudy_2021.rtf`、`analyze/figures/eventstudy_2017.png`、`analyze/figures/eventstudy_2021.png`
- **地域×案由**：`analyze/region_cause/`（tables/figures/logs）
- **金额诊断**：`analyze/diagnostics/amount_diagnostics.log`、`analyze/diagnostics/amount_diagnostics.xlsx`

