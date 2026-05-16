【先标注一些做Few Shot，然后嵌入在提示词里面。
可以先标注100个，然后做测试集，用来评估标注的F1值是否可靠。
如果可靠，可以先让两个模型标，标完后不一致的再去取第三个来裁判，这样可以大量省钱】

# Ensemble ELS 多模型一致性抽取

 读取 `比特币数据.xlsx` 与对应 TXT 文书，调用 5 个模型进行抽取（temperature=0、非流式、≥10 次重试），并通过“模型内投票 + 模型间投票”融合，输出 Master Schema 2.2 兼容 JSON。

## 安装

```bash
 pip install -r requirements.txt
```

## 环境变量（示例）

 可直接使用系统环境变量，或参考 `docs/fields.yaml` 配置抽取字段。

 必填（根据所用模型）：

- `MOONSHOT_API_KEY`（Kimi）
- `ARK_API_KEY`（Deepseek / Doubao）
- `DASHSCOPE_API_KEY`（Qwen）
- `ZHIPUAI_API_KEY`（GLM）

 可选：

- `MODELS`（默认：KIMI,DEEPSEEK,GLM,QWEN,DOUBAO）
- `RUNS_PER_MODEL`（默认：10）
- `EXTRACT_FIELDS_PATH`（默认：`docs/fields.yaml`）

## 命令

- 验证一条（5 模型 × 1 条 × 每模型 1 次）：

```bash
 python -m ensemble_els.cli validate-one \
   --excel "D:\BaiduSyncdisk\Doctor\论文\数字货币\数据构建\比特币数据.xlsx" \
   --text-dir "D:\BaiduSyncdisk\Doctor\论文\数字货币\数据构建\金融课题研究案例-比特币\金融课题案例数据全文" \
   --row-index 0 \
   --models KIMI DEEPSEEK GLM QWEN DOUBAO
```

python -m ensemble_els.cli validate-one --excel "D:\BaiduSyncdisk\Doctor\论文\数字货币\数据构建\比特币数据.xlsx" --text-dir "D:\BaiduSyncdisk\Doctor\论文\数字货币\数据构建\金融课题研究案例-比特币\金融课题案例数据全文" --row-index 0 --models KIMI DEEPSEEK GLM QWEN DOUBAO

python -m ensemble_els.cli collect --excel "D:\BaiduSyncdisk\Doctor\论文\数字货币\数据构建\比特币数据.xlsx" --text-dir "D:\BaiduSyncdisk\Doctor\论文\数字货币\数据构建\金融课题研究案例-比特币\金融课题案例数据全文" --limit 10 --models KIMI DEEPSEEK GLM QWEN DOUBAO

python -m ensemble_els.cli validate-one --excel "比特币数据.xlsx" --text-dir "金融课题研究案例-比特币/金融课题案例数据全文" --row-index 0 --output outputs

- 抽取（仅落 raw）：

```bash
 python -m ensemble_els.cli collect \
   --excel "D:\BaiduSyncdisk\Doctor\论文\数字货币\数据构建\比特币数据.xlsx" \
   --text-dir "D:\BaiduSyncdisk\Doctor\论文\数字货币\数据构建\金融课题研究案例-比特币\金融课题案例数据全文" \
   --models KIMI QWEN \
   --runs-per-model 5 \
   --limit 100
```

- 投票（对已有 raw 进行模型内与模型间投票）：

```bash
 python -m ensemble_els.cli vote --document-id <doc_id>
 python -m ensemble_els.cli vote-batch
```

## 输出目录

- `outputs/raw/{document_id}/{MODEL}/run_{k}.json`
- `outputs/consensus/{document_id}/model_level.json`
- `outputs/final/{document_id}.json`

## 说明

- 默认 temperature=0，非流式；HTTP/解析失败自动重试（≥10 次）。
- 终端参数 > 环境变量 > 程序默认值。
- 可通过 `EXTRACT_FIELDS_PATH` 或 `EXTRACT_FIELDS_JSON` 扩展字段，自动纳入抽取与投票流程。



这是一个非常棒的数据集构建计划。您定义的 Schema（特别是 `virtual_currency_info` 和 `judicial_analysis` 部分）为进行深入的法律计量学（Jurimetrics）或计算法学研究奠定了坚实的基础。

基于您即将生成的这个结构化数据集，您可以展开一系列非常有价值的定量研究。

---

### 🎯 可行的定量研究方向

您的 Schema 允许将判决结果（因变量）与案件特征、法院特征和法律/政策因素（自变量）联系起来。

#### 1. 关键判决结果的决定因素分析
这是最核心的研究。您可以探究哪些因素显著影响法院对关键问题的认定。

* **研究问题 1：** 什么因素（`virtual_currency_info.total_amount_cny`, `activity_type`, `metadata.court_level` 等）显著影响法院对合同效力（`judicial_analysis.contract_validity`）的认定（例如，认定为“无效”的概率）？
* **研究问题 2：** 涉案金额（`total_amount_cny`）或货币类型（`currency_types`）是否会影响法院最终的裁判结果（`llm_summary.outcome_summary`，例如“支持诉请” vs “驳回诉请”）？

#### 2. 法律定性与司法框架的演化
您可以利用时间（`metadata.judgment_date`）和政策（`judicial_analysis.cited_policies`）变量，研究法院观点的变迁。

* **研究问题 3：** 随着时间推移，法院对虚拟货币的法律定性（`legal_characterization`）是如何变化的？
* **研究问题 3（衍生）：** 法院何时、如何明确虚拟货币的“财产属性”或否认其财产地位（`virtual_currency_property_legality`），以及该认定与案件类型、政策引用之间的关系？
* **研究问题 4：** 特定的监管政策（`cited_policies`，例如中国人民银行 2017 年或 2021 年的通知）出台后，法院对合同效力（`contract_validity`）的认定是否在时间上出现了显著的“断点”或结构性变化？

#### 3. 司法裁判的地域差异性分析
您可以利用 `metadata.region`（您 Schema 中的 `region` 字段）来研究不同地区的司法差异。

* **研究问题 5：** 在控制了案件类型（`activity_type`）和涉案金额（`total_amount_cny`）后，不同地区（例如，金融发达地区 vs. 其他地区）的法院在判决上是否存在系统性差异？

---

### 📊 适用的计量模型与数学假设

针对上述研究问题，您可以选用以下模型。我将重点解释它们依赖的数学假设，特别是您提到的**观测独立性**。

#### 模型一：Logit / Probit 模型 (Logistic Regression)

* **适用场景：** 研究问题 1 和 2。当您的**因变量 (DV)** 是二元的（Binary）时。
    * 例如：`contract_validity` = {1 = 无效, 0 = 有效}
    * 例如：`outcome_summary` = {1 = 驳回诉请, 0 = 支持诉请}
* **模型解释：** 估计一组自变量（X）如何影响一个二元结果（Y）发生的**概率**。
* **数学假设：**
    1.  **观测独立性 (Independence of Observations)：** 这是最关键也最容易被违反的假设。它假定一个案件（观测点 $i$）的判决结果（$Y_i$）独立于另一个案件（观测点 $j$）的判决结果（$Y_j$）。
    2.  **因变量的二元性：** Y 只能取两个值。
    3.  **自变量与 Logit 转换后的概率呈线性关系 (Linearity in the Logit)：** 自变量 $X$ 的变化与 $Y$ 发生的对数几率（Log-odds）呈线性关系。
    4.  **无严重多重共线性 (No severe multicollinearity)：** 自变量之间不应高度相关。

#### 模型二：多项 Logit 模型 (Multinomial Logistic Regression)

* **适用场景：** 研究问题 3。当您的**因变量**是无序的（Unordered）且多于两个类别时。
    * 例如：`legal_characterization` = {"A. 视为财产", "B. 视为商品", "C. 认定为非法物", "D. 不予认定"}
* **模型解释：** 估计自变量 X 如何影响 Y 属于各个类别的概率。
* **数学假设：**
    1.  **观测独立性 (Independence)：** 同上。
    2.  **无关备择项的独立性 (Independence of Irrelevant Alternatives, IIA)：** 这是该模型独有的强假设。它假定任何两个选项（例如 A 和 B）之间的选择概率比例，不受其他选项（例如 C）是否存在或改变的影响。
    3.  **无严重多重共线性。**

#### 模型三：线性概率模型 (LPM, 即使用 OLS)

* **适用场景：** 同 Logit/Probit，作为一种更简单、更易于解释（系数即为边际效应）的替代。
* **模型解释：** 直接使用普通最小二乘法 (OLS) 回归 $Y = \beta_0 + \beta_1X_1 + ... + u$，其中 Y 是 0/1 变量。
* **数学假设 (OLS 的高斯-马尔可夫假定)：**
    1.  **线性关系：** 假定模型是线性的。
    2.  **严格外生性：** $E(u|X) = 0$。即残差项 $u$ 与所有自变量 $X$ 无关。
    3.  **观测独立性 (i.i.d. 假定的一部分)：** 不同的观测点 $i$ 和 $j$ 的残差项 $u_i$ 和 $u_j$ 不相关 $Cov(u_i, u_j) = 0$。
    4.  **同方差性 (Homoskedasticity)：** $Var(u|X) = \sigma^2$。**注意：LPM 在数学上必然违反此条**，因为 $Y$ 只能取 0/1，导致残差 $u$ 的方差依赖于 $X$（即存在异方差性）。

#### 模型四：断点回归 (Regression Discontinuity, RDD)

* **适用场景：** 研究问题 4。评估一个外生事件（如政策出台）的影响。
* **模型解释：** 比较在“断点”（`metadata.judgment_date` = 政策发布日期）前后，因变量（`contract_validity`）是否发生不连续的跳跃。
* **数学假设：**
    1.  **断点处的连续性：** 假定在没有政策干预的情况下，因变量 $Y$ 会在断点处平滑连续地变化。
    2.  **不可操控性 (No Manipulation)：** 案件（个体）不能精确地操控自己位于断点的哪一侧。（在您的场景中，当事人或法院无法在政策发布前后精确“操纵”审结时间，这个假设大概率成立）。

---

### 🔍 假设验证与修正工作

您提到了如何验证假设，这在实证研究中至关重要。

#### 1. 验证“观测独立性”

* **为什么可能是个问题：** 在法律数据中，**独立性假设极易被违反**。判决不是孤立做出的。
    * **聚类 (Clustering)：** 同一个法院（`metadata.court_name`）或同一个地区（`metadata.region`）的判决可能彼此相关（例如，共享相同的司法实践或受同一上级法院指导）。
    * **序列相关 (Serial Correlation)：** 同一个法院在时间（`judgment_date`）上前后相近的判决也可能相关。
* **验证工作：** 纯粹的统计检验（如 Durbin-Watson）可能不适用。这更多是一个**理论和方法论**上的问题。您应该基于法律理论**预先假定**存在聚类。
* **修正方法 (必做)：**
    * **使用聚类稳健标准误 (Clustered Robust Standard Errors)**：这是标准做法。您可以在模型中（例如 Stata, R, Python 的 `statsmodels`）指定在哪个层面上进行聚类（例如，按 `metadata.region` 或 `metadata.court_name` 聚类）。
    * 这不会改变系数 $\beta$ 的估计值，但会修正标准误，使您的 $p$ 值和置信区间更可信，避免高估统计显著性。

#### 2. 验证“多重共线性” (适用于所有模型)

* **验证工作：** 在运行 OLS 后（即使您最终用 Logit），计算自变量的**方差膨胀因子 (Variance Inflation Factor, VIF)**。
* **修正方法：** 如果 VIF > 10（经验法则），说明共线性严重。您可能需要剔除某个变量或将它们合并。

#### 3. 验证“异方差性” (针对 LPM)

* **验证工作：** 使用 **Breusch-Pagan 检验**或 **White 检验**。
* **修正方法：** (如前所述，LPM 必然存在异方差性)。**始终使用“稳健标准误” (Robust Standard Errors)**（也称 White's standard errors），这在所有主流统计软件中都是标准选项。

#### 4. 验证 IIA 假设 (针对多项 Logit)

* **验证工作：** 使用 **Hausman-McFadden 检验**或 **Small-Hsiao 检验**。
* **修正方法：** 如果 IIA 假设不成立，说明模型设定错误。您可能需要改用“嵌套 Logit (Nested Logit)”或“混合 Logit (Mixed Logit)”模型。

---

基于您的数据集 schema，我建议您可以从 **Logit 模型 + 聚类稳健标准误**（以法院地区为聚类变量）开始，分析`total_amount_cny`, `activity_type` 和 `court_level` 对 `contract_validity` (无效=1) 的影响。

您希望我针对其中某个具体的研究问题（例如问题 1）提供更详细的模型设定（包括控制变量的选择）吗？


这是一个非常深刻的问题。您构建的这个数据集，其价值远超“统计一下法院怎么判”，它真正搭建了一个桥梁，让您可以用经验数据（Empirical Data）去“检验”、“挑战”甚至“发展”一些经典的法学和社科理论。

您的两万份判决书，本质上是在中国这样一个强监管、成文法的国家中，司法系统面对一个“法律之外”的新生事物（虚拟货币）时，长达数年的“应激反应”和“规范化”过程的完整记录。

以下是几种您的研究可以“对话”的理论框架：

### 1. 法律现实主义 (Legal Realism) 与司法行为 (Judicial Behavior)

* **理论核心：** 法律现实主义（尤其是美国的）认为，法官的判决不仅是“法条主义”（Formalism）的产物，更是法官个人偏好、社会背景、政治态度（在您这里可以理解为对中央政策的响应度）的结果。
* **对话点：** 您的数据完美地设置了一个“对照实验”。
    * **“法律在书本上”(Law in Books)：** 是明确的监管政策（`judicial_analysis.cited_policies`，如 94 号、254 号文），这些政策普遍要求否定相关交易。
    * **“法律在行动中”(Law in Action)：** 是您的两万个判决结果（`contract_validity`, `outcome_summary`）。
* **您可以检验：**
    * **政策响应的地域差异：** 在控制案件类型（`activity_type`）和金额（`total_amount_cny`）后，来自不同地区（`metadata.region`）或不同层级（`metadata.court_level`）的法院，其判决的“严格程度”（例如，认定无效的概率）是否存在显著差异？
    * **对话：** 如果差异显著，这就**挑战了“法律形式主义”**（即所有法官都严格一致地适用同一政策），并**支持了“法律现实主义”**的观点——即法官在适用法律（或政策）时，受到了地方法院“惯例”、地方经济利益（例如，是否为金融中心）等法外因素的影响。

### 2. 法律与经济学 (Law & Economics)

* **理论核心：** 法律规则（或司法判决）应当（或实际上）是追求“效率”的。法官在判决时，会不自觉地（或自觉地）考虑判决的经济后果和社会成本。
* **对话点：** 虚拟货币交易的“一刀切”无效判决，在法律上是“正确”的（遵循了政策），但在经济上可能是“低效”的（例如，导致一方当事人不当得利，破坏了交易稳定性，增加了社会解决纠纷的成本）。
* **您可以检验：**
    * **效率的考量：** 法院在判决合同无效（`contract_validity` = "无效"）时，是否在判决结果（`outcome_summary`）中试图通过其他方式（例如，判令返还、过错责任分担）来“平衡”这种无效判决带来的经济后果？
    * **对话：** 如果您发现法院普遍在宣告无效的同时，会努力在判决主文中寻求“公平”或“效率”的后果（例如，不允许一方利用无效规定“恶意”获利），这就**支持了波斯纳 (Posner) 的“司法效率”理论**。这表明，即使在强监管压力下，法院（特别是民商事法庭）的“效率”本能依然在发挥作用。

### 3. 法律多元主义 (Legal Pluralism)

* **理论核心：** 国家法（State Law）并不是社会中唯一的规范体系。还存在许多其他的“规范场域”（Normative Fields），例如商人群体的惯例、社区规范，甚至“代码规范”（Code is Law）。
* **对话点：** 您的数据是观察“国家法”与“技术/市场规范”之间冲突与互动的绝佳窗口。
    * **国家法：** `judicial_analysis.cited_policies` 代表的强监管规范。
    * **市场规范：** 虚拟货币交易（尤其是 OTC 交易）中形成的“行规”或基于代码的“共识”。
* **您可以检验：**
    * **规范的翻译：** 法院在判决理由（`llm_summary.reasoning_summary` 或 `judicial_framing`）中，是如何“理解”和“转述”虚拟货币交易这一市场行为的？是将其视为“赌博”、“非法金融活动”，还是（在早期）视为一种“特殊的网络商品”？
    * **对话：** 您的数据可以**实证地展示“法律多元”情境下的“规范碰撞”**。您可以分析，法院是如何通过司法判决，将一个外来的、基于技术的规范体系（虚拟货币）“拉入”国家法的管辖之下，并对其进行“法律定性”（`legal_characterization`）的。

### 4. 法律与社会变迁 (Law and Social Change)

* **理论核心：** 法律（包括司法）是社会变迁的反映，还是引导社会变迁的工具？
* **对话点：** 虚拟货币是一个急速的技术和社会变迁。
* **您可以检验：**
    * **司法适应的时间序列：** 利用 `metadata.judgment_date`，您可以清晰地描绘出司法态度的演化图。
    * **对话：** 您的研究可以**检验“司法滞后性”理论**。在 2017 年政策出台前，法院是如何判的？政策刚出台时，法院是否立刻响应，还是存在一个“学习期”或“观望期”？在 2021 年进一步收紧政策后，法院的判决（`contract_validity`）是否出现了显著的“断点”（这可以回应您之前提到的 RDD 模型）？
    * 这可以有力地证明，在中国的司法体制下，**司法（Law）主要是作为政策（Social Change/Policy）的“反映者”和“执行者”**，而非“引导者”。

### 5. 财产权理论 (Property Theory) - “权利束” (Bundle of Rights)

* **理论核心：** 财产（Property）不是一个单一的“所有权”，而是一束可以被拆分、组合和限制的权利（如使用权、收益权、排他权、处分权）。
* **对话点：** `legal_characterization` 字段。虚拟货币的法律地位极其模糊。
* **您可以检验：**
    * **权利束的拆解：** 法院是否在不同类型的案件（例如，民事合同纠纷 vs. 刑事追赃 vs. 继承案件）中，对虚拟货币的“法律定性”不同？
    * **对话：** 您的数据很可能证明，法院在实践中正在对虚拟货币进行**“权利束”的拆解**。例如，法院在**民事合同案**中可能因政策而否认其“合法性”（`contract_validity` = "无效"，即限制了“处分权”）；但在**刑事案件或继承案件**中，又可能承认其“财产属性”（`legal_characterization` = "虚拟财产"，即承认了“占有权”和“排他权”）。
    * 这完美地**支持了“财产权束”理论**，表明“财产”不是一个非黑即白的概念，而是法律系统根据具体情境（Context）所赋予的一系列权能的组合。

---

总而言之，您的这个实证研究项目，使其具备了与法学核心理论进行深入对话的潜力。您可以选择一个理论作为您论文的“靶子”或“框架”，用您的数据去支持、反驳或精炼它。

您对哪个理论方向的“对话”最感兴趣？我们可以深入探讨如何围绕它来设计您的实证分析策略。

【关键是法律多元主义、法律与社会变迁】


【test命令】
python -c "from ensemble_els.cli import main; main()" test-gemini --excel "比特币数据.xlsx" --text-dir "金融课题研究案例-比特币/金融课题案例数据全文" --sample 10

