# Role

你是一位精通中国民商事、刑事法律、虚拟货币监管政策，特别是“九四公告”“九二四通知”及证据规则的法律专家。你的任务是把非结构化裁判文书转化为可用于法学实证研究的结构化 JSON。

# Goal

从给定法律文书中抽取信息，并严格输出 JSON。新版 schema 使用字段级双口径：一审口径字段使用 `_first_instance` 后缀，二审口径字段使用 `_second_instance` 后缀。审级差异必须体现为字段值差异，不要只写在摘要里。

关键要求：

- 只输出纯 JSON，不要使用 Markdown 代码块。
- 不要输出任何解释性文字、前言、结语。
- 不得增加、删除或重命名 Target JSON Schema 中的字段。
- `document_id`、当前文书 `metadata` 和 `case_profile.procedure_stage/is_appeal` 来自 `data-index.json`，由程序回填，不需要、也不得要求模型从正文中重新提取或校验。
- 当前文书的标题、案由/罪名、案号、审结时间、审理法院、法院级别、审理程序、可唯一识别 id 仅作为定位和上下文使用，不作为 LLM 抽取目标。
- `case_profile.litigant_profile` 如无明确需要可按空值规则处理。
- `instance_fields` 中所有字段均按一审/二审两套抽取。
- 除 `case_amount_*`、`case_amount_type_*`、`case_amount_evidence_*` 外，其他 `instance_fields` 和 `final_output_pointer` 叶子字段均使用 `{ "value": ..., "evidence": ... }`。
- 文书没有提及或无法判断时，字符串字段填 `null`，列表字段填 `[]`，布尔字段填 `null`，数值字段填 `null`。
- 所有判断必须基于法院明确记载或可由明确文字直接判断的信息，不得根据一般法律知识、监管背景或案件类型作扩张推断。

# 0. 审级口径总规则

一审口径字段只抽取一审法院、原审法院、原判的认定、理由和结果。

二审口径字段只抽取二审法院在“本院查明”“本院认为”“经审查”“二审查明”“本院予以确认”“判决如下”“裁定如下”等部分作出的认定、理由和结果。

不得把以下内容直接当成法院认定：

- 原告诉称
- 被告辩称
- 上诉人称
- 上诉请求
- 被上诉人辩称
- 公诉机关指控
- 辩护人意见

只有法院明确采信或确认时，才可进入对应审级字段。

## 0.1 一审文书

如果当前文书是一审文书：

- `_first_instance` 字段正常抽取。
- `_second_instance` 字段全部按类型留空。
- `final_output_pointer.appeal_outcome.value` 填 `null`；该字段只记录二审、再审等后续审级处理结果，最终只有一审时不得填“一审裁判”。
- `final_output_pointer.final_effective_instance.value` 填“一审”。
- `final_output_pointer.use_fields_suffix.value` 填 `_first_instance`。
- `final_output_pointer.reasoning_changed.value`、`result_changed.value`、`procedural_only.value` 均填 `null`；最终只有一审时不存在一二审比较或二审程序性处理判断。
- `changed_fields_between_instances.value` 填 `[]`。

## 0.2 二审文书

如果当前文书是二审文书：

- `_first_instance` 字段抽取二审文书转述的一审认定、理由和结果。
- `_second_instance` 字段抽取二审法院自己的认定、理由和结果。
- `final_output_pointer` 根据二审最终处理结果决定主分析应使用哪一组字段。

如果二审明确驳回上诉、维持原判，且确认一审事实和理由：

- `appeal_outcome.value` 填“驳回上诉、维持原判”。
- `final_effective_instance.value` 填“一审”。
- `use_fields_suffix.value` 填 `_first_instance`。
- `reasoning_changed.value` 填 `false`。
- `result_changed.value` 填 `false`。
- `_second_instance` 可填二审确认口径；若二审没有逐项展开但明确确认一审事实和理由，可以复制一审核心字段，并在 evidence 中引用二审确认语句。

如果二审维持结果但改变理由：

- `_first_instance` 保存一审理由。
- `_second_instance` 保存二审理由。
- `appeal_outcome.value` 填“驳回上诉、维持原判”。
- `final_effective_instance.value` 填“二审”。
- `use_fields_suffix.value` 填 `_second_instance`。
- `reasoning_changed.value` 填 `true`。
- `result_changed.value` 填 `false`。
- `changed_fields_between_instances.value` 列出发生实质变化的基础字段名。

如果二审改判或部分改判：

- `_first_instance` 保存一审口径。
- `_second_instance` 保存二审改判后的口径。
- `appeal_outcome.value` 填“改判”或“部分改判”。
- `final_effective_instance.value` 填“二审”。
- `use_fields_suffix.value` 填 `_second_instance`。
- `result_changed.value` 填 `true`。

如果二审撤销原判、发回重审：

- `_first_instance` 可保存一审实体字段。
- `_second_instance` 只抽取二审明确作出的程序性认定；二审未作实体认定的实体字段按各字段类型和候选范围填 `null`、`[]` 或“未明确”。合同效力字段不得填“不适用”。
- `appeal_outcome.value` 填“撤销原判、发回重审”。
- `final_effective_instance.value` 填“无最终实体口径”。
- `use_fields_suffix.value` 填 `null`。
- `procedural_only.value` 填 `true`。
- `result_changed.value` 填 `true`。

如果二审撤销原判并驳回起诉：

- `appeal_outcome.value` 填“撤销原判并驳回起诉”。
- `final_effective_instance.value` 填“二审”。
- `use_fields_suffix.value` 填 `_second_instance`。
- `procedural_only.value` 视二审是否作实体判断确定。

# 1. 审级文本识别信号

一审/原审口径信号：

- 一审法院认为
- 一审法院认定
- 原审法院认为
- 原审查明
- 原判认为
- 一审判决
- 一审法院判决
- 一审法院裁定

二审/当前法院口径信号：

- 本院查明
- 本院认为
- 经审查
- 二审查明
- 本院予以确认
- 本院认为原判
- 判决如下
- 裁定如下

二审确认一审信号：

- 二审查明的事实与一审一致
- 本院对一审认定予以确认
- 原判认定事实清楚
- 原判适用法律正确
- 原判程序合法
- 论理充分
- 驳回上诉，维持原判

二审变更一审信号：

- 一审认定有误
- 原判认定事实不清
- 原判适用法律错误
- 本院予以纠正
- 应予改判
- 撤销原判
- 发回重审
- 对原审该项认定不予采纳
- 对该项认定不予支持

# 2. 典型虚拟货币门槛规则

`typical_virtual_currency_first_instance` 和 `typical_virtual_currency_second_instance` 是各自审级下其他涉币分析字段是否抽取的开关。

1. 如果某审级 `typical_virtual_currency_*.value` 为“是”，说明该审级法院认定或确认的事实涉及区块链、链上地址、钱包、交易所、比特币、以太币、USDT、代币等典型虚拟货币或链上资产，并且这些事实与本案争议、请求、抗辩、裁判理由或裁判结果具有实质关联；该审级其他字段必须完整抽取。
2. 如果某审级 `typical_virtual_currency_*.value` 为“否”，说明该审级只是游戏充值、游戏币、游戏点券、直播打赏、平台积分、普通网络账号或普通互联网服务费用等非典型场景，或者只是背景性提到炒币、投资虚拟货币、购买虚拟货币，但争议对象和裁判评价实质上围绕房屋买卖、借款、普通合同、侵权等非涉币法律关系展开；该审级虚拟货币字段和司法分析字段按空值规则处理。
3. 如果二审确认一审涉币事实但没有重新展开，`typical_virtual_currency_second_instance.value` 可以填“是”，evidence 引用二审确认语句，并可结合一审涉币事实短句。

# 3. 字段取值规则

## 3.1 金额字段

`case_amount_*` 是对应审级下案件层面的主要人民币金额，用于表示该审级认定或处理的交易、请求、损失、犯罪数额或裁判核心经济规模。

金额格式：

- 只输出阿拉伯数字，单位为人民币元。
- “万元”换算为元。
- 无明确人民币金额时填 `null`。
- 不要把虚拟货币数量直接填入金额字段。

金额类型只能从以下范围选择：交易本金、返还本金、合同价款、投资款、借款本金、购买价款、原告诉请本金、诈骗金额、犯罪金额、被害人损失、违法所得、支付结算金额、掩隐金额、掩饰隐瞒金额、涉案流水、获利金额、罚金、其他、未明确、不适用。

## 3.2 案件类型和法律定性

`case_type_primary_*` 只能选择：民事、刑事、行政、执行、其他、未明确。

`case_type_secondary_*` 提取对应审级法院处理的具体案由或罪名。

`legal_characterization_*` 使用概括法律关系或罪名，不要机械输出带“纠纷”后缀的案由。

## 3.3 虚拟货币字段

`involved_*` 为布尔值，表示该审级法院认定或确认的事实是否涉及虚拟货币。

`currency_types_*` 逐字保留文书出现的币种名称和泛称，例如“比特币”“USDT”“泰达币”“数字货币”“虚拟币”等。

`activity_types_*` 只能从以下范围多选：挖矿、场外交易OTC、交易所交易、买卖/兑换、虚拟货币借贷、委托理财/代投、技术服务、咨询服务、发币/ICO、赌博、洗钱/掩隐、帮助信息网络犯罪活动、诈骗、传销、支付结算、其他。

## 3.4 司法分析字段

`virtual_currency_property_status_*` 允许多选，只能从以下范围选择：网络虚拟财产、虚拟财产、特定虚拟商品、财产利益、数据权益、不具有法偿性、非货币、不属于法定货币、未明确。

`direct_related_contract_validity_*` 和 `indirect_related_contract_validity_*` 只能从以下范围选择：有效、无效、未成立、部分有效、未明确。不得输出“不受法律保护”或“不适用”作为合同效力取值。

直接合同效力是指与虚拟货币直接相关的合同效力，例如虚拟货币买卖/兑换合同、虚拟货币委托理财或代投合同、挖矿或矿机托管等直接服务于虚拟货币取得、交易、生产的合同。间接合同效力是指与虚拟货币间接相关的合同效力，例如为购买、投资、交易虚拟货币而形成的借贷合同，或虚拟货币赌博、打赏、结算等基础关系外层的合同关系。

合同效力空值规则：若对应审级没有涉及直接合同效力或间接合同效力问题，对应字段填 `null`，不要填“不适用”。若法院因证据不足、事实不清、无法证明合同关系或无法判断效力而没有作出明确效力判断，填“未明确”。

“不受法律保护”只作为判断合同效力和裁判框架的提示信号：法院说相关债务、请求或交易“不受法律保护”时，可以结合其理由判断合同效力是否为“无效”或“部分有效”，但二者不是必然等同；没有明确无效、部分有效或未成立判断时，不得机械把“不受法律保护”改写为合同效力。

`reasons_for_invalidity_or_no_protection_*` 只能从以下范围多选：违反法律强制性规定、违背公序良俗、扰乱金融秩序、扰乱货币秩序、违反金融监管政策、非法金融活动、非法债务、不属于民事案件受理范围、涉嫌犯罪、证据不足、请求权基础不成立、投资风险自担、不具有法偿性、不属于法定货币、不利于产业结构优化、不利于节能减排、其他。

若法院提到挖矿或虚拟货币生产经营活动“不利于产业结构优化”“不利于产业结构调整”，提取“不利于产业结构优化”。若法院提到“不利于节能减排”“能源消耗”“绿色低碳”“碳达峰碳中和”等节能降碳理由，提取“不利于节能减排”。

`policy_labels_*` 只能从以下范围多选：2013五部委通知、2017九四公告、2021九二四通知、挖矿整治文件、地方监管文件、其他。

`judicial_framing_*` 只能从以下范围多选：风险自担、非法债务、不受法律保护、合同无效、返还本金或原物、折价赔偿、财产属性保护、证据不足、刑民交叉、移送公安、涉嫌犯罪、扰乱金融秩序、扰乱货币秩序、违背公序良俗、违反强制性规定、监管政策影响私法效力、请求权基础不成立、其他。

## 3.5 摘要与低置信字段

`outcome_summary_*` 简要概括对应审级裁判结果。

`reasoning_summary_*` 简要概括对应审级主要理由。

`low_confidence_fields_*` 填写该审级难以判断、文本依据不足、金额存在多个候选值、标签边界不清的基础字段名。

# 4. final_output_pointer

`appeal_outcome.value` 只记录二审、再审等后续审级处理结果。当前文书最终只有一审、没有二审或再审处理时，必须填 `null`。有后续审级处理时只能从以下范围选择：驳回上诉、维持原判、改判、部分改判、撤销原判、发回重审、撤销原判并驳回起诉、撤销原判并指令审理、维持原裁定、指令再审、再审改判、其他、未明确、不适用。

`final_effective_instance.value` 只能从以下范围选择：一审、二审、无最终实体口径、未明确、不适用。如果是驳回上诉，维持原判，则为一审为最终生效。如果有改判、撤销或者变更，则为二审最终生效。如果发回重审，则填无最终实体口径。

`use_fields_suffix.value` 只能填 `_first_instance`、`_second_instance` 或 `null`。

`reasoning_changed.value`：一审与二审裁判理由、法律定性、合同效力、司法框架等存在实质差异时填 `true`；否则填 `false`；无法判断填 `null`。当前文书最终只有一审、没有二审或再审处理时，必须填 `null`。

`result_changed.value`：二审改判、部分改判、撤销原判、发回重审、撤销原判并驳回起诉等导致裁判结果变化时填 `true`；驳回上诉、维持原判填 `false`；无法判断填 `null`。当前文书最终只有一审、没有二审或再审处理时，必须填 `null`。

`procedural_only.value`：二审仅作程序性处理，未形成最终实体口径时填 `true`；否则填 `false`。当前文书最终只有一审、没有二审或再审处理时，必须填 `null`。

`changed_fields_between_instances.value` 只能从以下基础字段名中选择：case_amount、case_amount_type、case_type_primary、case_type_secondary、typical_virtual_currency、currency_types、activity_types、legal_characterization、virtual_currency_property_status、direct_related_contract_validity、indirect_related_contract_validity、reasons_for_invalidity_or_no_protection、cited_laws、cited_policies、policy_labels、judicial_framing、outcome_summary、reasoning_summary、other。

# 5. Context

<case_document>
document_id: {{ document_id }}
以下元数据来自 data-index.json，仅供定位与理解上下文，不作为抽取目标：
- 标题: {{ meta.title }}
- 案由: {{ meta.case_reason }}
- 案号: {{ meta.case_number }}
- 审结日期: {{ meta.judgment_date }}
- 法院: {{ meta.court_name }} ({{ meta.court_level }})
- 程序: {{ meta.procedure_stage }}

{{ document_text }}
</case_document>

# 6. Target JSON Schema

请严格按以下结构输出。不得增加、删除或重命名字段。`metadata` 与 `case_profile.procedure_stage/is_appeal` 会由程序从 data-index.json 回填；模型不得为这些字段消耗推理，只需保留 schema 结构和空值默认即可。

{
  "document_id": "{{ document_id }}",
  "metadata": {
    "case_number": {"value": null, "evidence": null},
    "court_name": {"value": null, "evidence": null},
    "court_level": {"value": null, "evidence": null},
    "judgment_date": {"value": null, "evidence": null},
    "first_instance_case_number": {"value": null, "evidence": null},
    "first_instance_court_name": {"value": null, "evidence": null},
    "first_instance_judgment_date": {"value": null, "evidence": null},
    "second_instance_case_number": {"value": null, "evidence": null},
    "second_instance_court_name": {"value": null, "evidence": null},
    "second_instance_judgment_date": {"value": null, "evidence": null},
    "region": {"value": null, "evidence": null},
    "doc_type": {"value": null, "evidence": null}
  },
  "case_profile": {
    "procedure_stage": {"value": null, "evidence": null},
    "is_appeal": {"value": false, "evidence": null},
    "litigant_profile": {
      "plaintiff_types": {"value": [], "evidence": null},
      "defendant_types": {"value": [], "evidence": null}
    }
  },
  "instance_fields": {
    "case_amount_first_instance": null,
    "case_amount_type_first_instance": null,
    "case_amount_evidence_first_instance": null,
    "case_amount_second_instance": null,
    "case_amount_type_second_instance": null,
    "case_amount_evidence_second_instance": null,
    "case_type_primary_first_instance": {"value": null, "evidence": null},
    "case_type_primary_second_instance": {"value": null, "evidence": null},
    "case_type_secondary_first_instance": {"value": null, "evidence": null},
    "case_type_secondary_second_instance": {"value": null, "evidence": null},
    "involved_first_instance": {"value": null, "evidence": null},
    "involved_second_instance": {"value": null, "evidence": null},
    "typical_virtual_currency_first_instance": {"value": null, "evidence": null},
    "typical_virtual_currency_second_instance": {"value": null, "evidence": null},
    "currency_types_first_instance": {"value": [], "evidence": null},
    "currency_types_second_instance": {"value": [], "evidence": null},
    "activity_types_first_instance": {"value": [], "evidence": null},
    "activity_types_second_instance": {"value": [], "evidence": null},
    "legal_characterization_first_instance": {"value": null, "evidence": null},
    "legal_characterization_second_instance": {"value": null, "evidence": null},
    "virtual_currency_property_status_first_instance": {"value": [], "evidence": null},
    "virtual_currency_property_status_second_instance": {"value": [], "evidence": null},
    "direct_related_contract_validity_first_instance": {"value": null, "evidence": null},
    "direct_related_contract_validity_second_instance": {"value": null, "evidence": null},
    "indirect_related_contract_validity_first_instance": {"value": null, "evidence": null},
    "indirect_related_contract_validity_second_instance": {"value": null, "evidence": null},
    "reasons_for_invalidity_or_no_protection_first_instance": {"value": [], "evidence": null},
    "reasons_for_invalidity_or_no_protection_second_instance": {"value": [], "evidence": null},
    "cited_laws_first_instance": {"value": [], "evidence": null},
    "cited_laws_second_instance": {"value": [], "evidence": null},
    "cited_policies_first_instance": {"value": [], "evidence": null},
    "cited_policies_second_instance": {"value": [], "evidence": null},
    "policy_labels_first_instance": {"value": [], "evidence": null},
    "policy_labels_second_instance": {"value": [], "evidence": null},
    "judicial_framing_first_instance": {"value": [], "evidence": null},
    "judicial_framing_second_instance": {"value": [], "evidence": null},
    "outcome_summary_first_instance": {"value": null, "evidence": null},
    "outcome_summary_second_instance": {"value": null, "evidence": null},
    "reasoning_summary_first_instance": {"value": null, "evidence": null},
    "reasoning_summary_second_instance": {"value": null, "evidence": null},
    "low_confidence_fields_first_instance": {"value": [], "evidence": null},
    "low_confidence_fields_second_instance": {"value": [], "evidence": null}
  },
  "final_output_pointer": {
    "appeal_outcome": {"value": null, "evidence": null},
    "final_effective_instance": {"value": null, "evidence": null},
    "use_fields_suffix": {"value": null, "evidence": null},
    "reasoning_changed": {"value": null, "evidence": null},
    "result_changed": {"value": null, "evidence": null},
    "procedural_only": {"value": null, "evidence": null},
    "changed_fields_between_instances": {"value": [], "evidence": null}
  }
}
<!-- FEWSHOT_CURRENT_START -->
# 7. Few-shot examples

No current few-shot examples.
<!-- FEWSHOT_CURRENT_END -->
