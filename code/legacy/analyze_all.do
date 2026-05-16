version 19
clear all
set more off
set linesize 255

// ============================================================
//  Project: 数字货币裁判文书结构化数据 - Stata 全流程分析
//  Input : final_all.jsonl + docs/fields.yaml
//  Output: analyze/ (data, tables, figures, logs)
//  Run   : do analyze_all.do
// ============================================================

local ROOT "`c(pwd)'"
local OUTDIR "`ROOT'/analyze"
local DATADIR "`OUTDIR'/data"
local TABLEDIR "`OUTDIR'/tables"
local FIGDIR "`OUTDIR'/figures"
local LOGDIR "`OUTDIR'/logs"
local TMPDIR "`ROOT'/.temp"

cap mkdir "`OUTDIR'"
cap mkdir "`DATADIR'"
cap mkdir "`TABLEDIR'"
cap mkdir "`FIGDIR'"
cap mkdir "`LOGDIR'"
cap mkdir "`TMPDIR'"
cap mkdir "`OUTDIR'/report"

log close _all
log using "`LOGDIR'/analyze.log", replace text

di as txt "============================================================"
di as txt "Stata 全流程分析启动"
di as txt "工作目录: `ROOT'"
di as txt "输出目录: `OUTDIR'"
di as txt "============================================================"

// -----------------------------
// 1) JSONL -> 扁平 CSV（若尚未生成）
// -----------------------------
local JSONL "`ROOT'/final_all.jsonl"
local FIELDS "`ROOT'/docs/fields.yaml"
local FLATCSV "`DATADIR'/final_all_flat.csv"

cap confirm file "`JSONL'"
if _rc {
	di as err "找不到输入文件: `JSONL'"
	error 601
}
cap confirm file "`FIELDS'"
if _rc {
	di as err "找不到字段定义: `FIELDS'"
	error 601
}

cap confirm file "`FLATCSV'"
if _rc {
	di as txt "未检测到扁平化 CSV，开始生成: `FLATCSV'"

	// --- 优先：使用 Stata 19 的 Python 集成（无需系统安装额外包）
	capture noisily python:
import json, csv, os

jsonl_path = r"""`JSONL'"""
fields_path = r"""`FIELDS'"""
out_csv = r"""`FLATCSV'"""

def parse_fields_yaml(path: str):
    fields = []
    cur = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("- name:"):
                if cur:
                    fields.append(cur)
                    cur = {}
                cur["name"] = line.split(":", 1)[1].strip()
            elif line.startswith("type:"):
                cur["type"] = line.split(":", 1)[1].strip()
            elif line.startswith("target:"):
                cur["target"] = line.split(":", 1)[1].strip()
        if cur:
            fields.append(cur)
    # 保底：仅保留 name/target
    return [x for x in fields if x.get("name") and x.get("target")]

def normalize_value(v):
    # 兼容 {"value": ...}
    if isinstance(v, dict) and "value" in v:
        v = v.get("value")
    # 把字符串 "null" 视为缺失
    if isinstance(v, str) and v.strip().lower() == "null":
        return None
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, list):
        items = []
        for x in v:
            if x is None:
                continue
            if isinstance(x, dict) and "value" in x:
                x = x.get("value")
            if x is None:
                continue
            items.append(str(x))
        return ";".join(items) if items else None
    return v

fields = parse_fields_yaml(fields_path)
colnames = ["doc_id"] + [f["name"] for f in fields] + [
    "agreement_rate", "final_label_source", "models_used"
]

os.makedirs(os.path.dirname(out_csv), exist_ok=True)
with open(out_csv, "w", encoding="utf-8", newline="") as fo:
    w = csv.DictWriter(fo, fieldnames=colnames, extrasaction="ignore")
    w.writeheader()
    with open(jsonl_path, "r", encoding="utf-8") as fi:
        for line in fi:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            ff = obj.get("final_fields", {}) or {}
            row = {"doc_id": obj.get("doc_id")}
            for f in fields:
                target = f["target"]
                key = target  # final_fields 的 key 形如 "metadata.case_number"
                row[f["name"]] = normalize_value(ff.get(key))
            metrics = obj.get("metrics", {}) or {}
            row["agreement_rate"] = metrics.get("agreement_rate")
            row["final_label_source"] = metrics.get("final_label_source")
            row["models_used"] = ";".join([str(x) for x in (obj.get("models_used") or [])])
            w.writerow(row)

print(f"[python] wrote: {out_csv}")
end

	if _rc {
		di as err "Stata 内置 Python 执行失败，尝试调用系统 python 作为降级路径..."

		// --- 降级：写出一个临时 python 脚本并 shell 调用
		local PYFILE "`TMPDIR'/flatten_final_all.py"
		cap erase "`PYFILE'"
		tempname fh
		file open `fh' using "`PYFILE'", write text replace
		file write `fh' "import json, csv, os" _n
		file write `fh' "" _n
		file write `fh' "JSONL = r'''`JSONL''''" _n
		file write `fh' "FIELDS = r'''`FIELDS''''" _n
		file write `fh' "OUTCSV = r'''`FLATCSV''''" _n
		file write `fh' "" _n
		file write `fh' "def parse_fields_yaml(path):" _n
		file write `fh' "    fields=[]" _n
		file write `fh' "    cur={}" _n
		file write `fh' "    with open(path,'r',encoding='utf-8') as f:" _n
		file write `fh' "        for raw in f:" _n
		file write `fh' "            line=raw.strip()" _n
		file write `fh' "            if not line or line.startswith('#'): continue" _n
		file write `fh' "            if line.startswith('- name:'):" _n
		file write `fh' "                if cur: fields.append(cur); cur={}" _n
		file write `fh' "                cur['name']=line.split(':',1)[1].strip()" _n
		file write `fh' "            elif line.startswith('type:'):" _n
		file write `fh' "                cur['type']=line.split(':',1)[1].strip()" _n
		file write `fh' "            elif line.startswith('target:'):" _n
		file write `fh' "                cur['target']=line.split(':',1)[1].strip()" _n
		file write `fh' "    if cur: fields.append(cur)" _n
		file write `fh' "    return [x for x in fields if x.get('name') and x.get('target')]" _n
		file write `fh' "" _n
		file write `fh' "def normalize_value(v):" _n
		file write `fh' "    if isinstance(v,dict) and 'value' in v: v=v.get('value')" _n
		file write `fh' "    if isinstance(v,str) and v.strip().lower()=='null': return None" _n
		file write `fh' "    if v is None: return None" _n
		file write `fh' "    if isinstance(v,bool): return int(v)" _n
		file write `fh' "    if isinstance(v,list):" _n
		file write `fh' "        items=[]" _n
		file write `fh' "        for x in v:" _n
		file write `fh' "            if x is None: continue" _n
		file write `fh' "            if isinstance(x,dict) and 'value' in x: x=x.get('value')" _n
		file write `fh' "            if x is None: continue" _n
		file write `fh' "            items.append(str(x))" _n
		file write `fh' "        return ';'.join(items) if items else None" _n
		file write `fh' "    return v" _n
		file write `fh' "" _n
		file write `fh' "fields=parse_fields_yaml(FIELDS)" _n
		file write `fh' "cols=['doc_id']+[f['name'] for f in fields]+['agreement_rate','final_label_source','models_used']" _n
		file write `fh' "os.makedirs(os.path.dirname(OUTCSV), exist_ok=True)" _n
		file write `fh' "with open(OUTCSV,'w',encoding='utf-8',newline='') as fo:" _n
		file write `fh' "    w=csv.DictWriter(fo, fieldnames=cols, extrasaction='ignore')" _n
		file write `fh' "    w.writeheader()" _n
		file write `fh' "    with open(JSONL,'r',encoding='utf-8') as fi:" _n
		file write `fh' "        for line in fi:" _n
		file write `fh' "            line=line.strip()" _n
		file write `fh' "            if not line: continue" _n
		file write `fh' "            obj=json.loads(line)" _n
		file write `fh' "            ff=obj.get('final_fields') or {}" _n
		file write `fh' "            row={'doc_id': obj.get('doc_id')}" _n
		file write `fh' "            for f in fields:" _n
		file write `fh' "                row[f['name']] = normalize_value(ff.get(f['target']))" _n
		file write `fh' "            metrics=obj.get('metrics') or {}" _n
		file write `fh' "            row['agreement_rate']=metrics.get('agreement_rate')" _n
		file write `fh' "            row['final_label_source']=metrics.get('final_label_source')" _n
		file write `fh' "            row['models_used']=';'.join([str(x) for x in (obj.get('models_used') or [])])" _n
		file write `fh' "            w.writerow(row)" _n
		file write `fh' "print('wrote', OUTCSV)" _n
		file close `fh'

		capture noisily shell python "`PYFILE'"
		if _rc {
			di as err "系统 python 也执行失败。请确认："
			di as err "1) Stata 已配置 python（推荐），或 2) 系统 PATH 中可直接运行 python"
			error 9
		}
		// 清理临时脚本（保留 .temp 目录本身）
		cap erase "`PYFILE'"
	}
}
else {
	di as txt "检测到已有扁平化数据: `FLATCSV'（跳过生成）"
}

// -----------------------------
// 2) 导入与基础清洗
// -----------------------------
import delimited using "`FLATCSV'", clear varnames(1) encoding(UTF-8) stringcols(_all)
compress

// 统一缺失值："" 与 "null" 视为缺失
foreach v of varlist _all {
	capture confirm string variable `v'
	if !_rc {
		replace `v' = "" if lower(trim(`v')) == "null"
	}
}

// 数值列：金额、agreement_rate（其余保持字符串更稳）
capture destring total_amount_cny, replace ignore(" ,")
capture destring agreement_rate, replace ignore(" ,")

// 日期 -> 年份
gen double judgment_date_d = daily(judgment_date, "YMD")
format judgment_date_d %td
gen int judgment_year = year(judgment_date_d)

// bool 字段（可能来自 True/False 或 0/1）
gen byte is_appeal_b = .
replace is_appeal_b = 1 if inlist(lower(trim(is_appeal)), "true","1","yes")
replace is_appeal_b = 0 if inlist(lower(trim(is_appeal)), "false","0","no")

gen byte vc_involved_b = .
replace vc_involved_b = 1 if inlist(lower(trim(vc_involved)), "true","1","yes")
replace vc_involved_b = 0 if inlist(lower(trim(vc_involved)), "false","0","no")

// 合同效力：构造更易建模的分类/二元变量
// 注意：数据里常见“未成立”、以及更长的文本表述；因此这里用正则匹配保证不漏样本。
gen byte contract_validity_cat = .
replace contract_validity_cat = 1 if regexm(trim(contract_validity), "有效")
replace contract_validity_cat = 2 if regexm(trim(contract_validity), "无效")
replace contract_validity_cat = 3 if regexm(trim(contract_validity), "部分无效")
replace contract_validity_cat = 4 if regexm(trim(contract_validity), "未成立")
replace contract_validity_cat = 5 if contract_validity_cat==. & trim(contract_validity)!=""
label define contract_validity_cat 1 "有效" 2 "无效" 3 "部分无效" 4 "未成立" 5 "其他"
label values contract_validity_cat contract_validity_cat

// 二元因变量：无效/部分无效/未成立 = 1；有效 = 0；其余缺失
gen byte contract_invalid = .
replace contract_invalid = 1 if regexm(trim(contract_validity), "无效|未成立")
replace contract_invalid = 0 if contract_invalid==. & regexm(trim(contract_validity), "有效")

// 金额对数（用于回归）
gen double ln_amount = ln(total_amount_cny + 1) if !missing(total_amount_cny)

// 编码分类变量（方便回归与聚类）——做成“尽量生成，不阻塞流程”
// activity_type_id
capture confirm variable activity_type
if !_rc {
	capture confirm string variable activity_type
	if !_rc {
		capture encode activity_type, gen(activity_type_id)
		if _rc {
			gen long activity_type_id = .
		}
	}
	else {
		// 若已是数值，直接复制
		gen long activity_type_id = activity_type
	}
}
else {
	gen long activity_type_id = .
}

// court_level_id
capture confirm variable court_level
if !_rc {
	capture confirm string variable court_level
	if !_rc {
		capture encode court_level, gen(court_level_id)
		if _rc {
			gen long court_level_id = .
		}
	}
	else {
		gen long court_level_id = court_level
	}
}
else {
	gen long court_level_id = .
}

// region_id
capture confirm variable region
if !_rc {
	capture confirm string variable region
	if !_rc {
		capture encode region, gen(region_id)
		if _rc {
			gen long region_id = .
		}
	}
	else {
		gen long region_id = region
	}
}
else {
	gen long region_id = .
}

// court_name_id
capture confirm variable court_name
if !_rc {
	capture confirm string variable court_name
	if !_rc {
		capture encode court_name, gen(court_name_id)
		if _rc {
			gen long court_name_id = .
		}
	}
	else {
		gen long court_name_id = court_name
	}
}
else {
	gen long court_name_id = .
}

// procedure_stage_id（用于 DID/回归控制）
capture confirm variable procedure_stage
if !_rc {
	capture confirm string variable procedure_stage
	if !_rc {
		capture encode procedure_stage, gen(procedure_stage_id)
		if _rc gen long procedure_stage_id = .
	}
	else gen long procedure_stage_id = procedure_stage
}
else gen long procedure_stage_id = .

// doc_type_id（可选控制）
capture confirm variable doc_type
if !_rc {
	capture confirm string variable doc_type
	if !_rc {
		capture encode doc_type, gen(doc_type_id)
		if _rc gen long doc_type_id = .
	}
	else gen long doc_type_id = doc_type
}
else gen long doc_type_id = .

// case_type_primary_id / case_type_secondary_id（可选控制）
capture confirm variable case_type_primary
if !_rc {
	capture confirm string variable case_type_primary
	if !_rc {
		capture encode case_type_primary, gen(case_type_primary_id)
		if _rc gen long case_type_primary_id = .
	}
	else gen long case_type_primary_id = case_type_primary
}
else gen long case_type_primary_id = .

capture confirm variable case_type_secondary
if !_rc {
	capture confirm string variable case_type_secondary
	if !_rc {
		capture encode case_type_secondary, gen(case_type_secondary_id)
		if _rc gen long case_type_secondary_id = .
	}
	else gen long case_type_secondary_id = case_type_secondary
}
else gen long case_type_secondary_id = .

// 保存一份 dta 供后续直接使用
save "`DATADIR'/final_all_flat.dta", replace

// -----------------------------
// 3) 描述统计 & 建表（导出到 Excel）
// -----------------------------
di as txt "开始描述统计与建表..."

// 表1：按年份案件量
preserve
keep if !missing(judgment_year)
gen byte one = 1
collapse (sum) N=one, by(judgment_year)
sort judgment_year
export excel using "`TABLEDIR'/tab_cases_by_year.xlsx", firstrow(variables) replace
restore

// 表2：合同效力分布
preserve
gen byte one = 1
collapse (sum) N=one, by(contract_validity_cat)
export excel using "`TABLEDIR'/tab_contract_validity_dist.xlsx", firstrow(variables) replace
restore

// 表3：活动类型 Top20
preserve
keep if trim(activity_type)!=""
gen byte one = 1
collapse (sum) N=one, by(activity_type)
gsort -N
keep in 1/20
export excel using "`TABLEDIR'/tab_activity_type_top20.xlsx", firstrow(variables) replace
restore

// -----------------------------
// 4) 回归分析（logit）& 输出系数表
// -----------------------------
di as txt "开始回归分析（logit）..."
local REG_STATUS "not_run"
local REG_NOTE ""

// 预备：esttab（estout）用于导出 RTF 表格
local HAVE_ESTTAB = 0
cap which esttab
if _rc {
	capture noisily ssc install estout, replace
	cap which esttab
}
if !_rc local HAVE_ESTTAB = 1

// 聚类变量：优先 region（如果 region_id 有足够非缺失），否则 court_name
local CLUSTER_ID "court_name_id"
quietly count if !missing(region_id)
if r(N) > 0 {
	local CLUSTER_ID "region_id"
}

// 仅使用因变量非缺失的样本；若样本不足则跳过回归（避免 r(2000)）
quietly count if !missing(contract_invalid)
if r(N) < 30 {
	di as err "回归被跳过：contract_invalid 非缺失样本量不足（N=" r(N) "）。请检查 contract_validity 字段质量。"
	local REG_STATUS "skipped"
	local REG_NOTE "insufficient non-missing contract_invalid"
	preserve
	clear
	set obs 1
	gen note = "Regression skipped: insufficient non-missing contract_invalid (N=" + string(r(N)) + ")"
	export excel using "`TABLEDIR'/reg_logit_contract_invalid.xlsx", firstrow(variables) replace
	restore
}
else {
	preserve
	keep if !missing(contract_invalid)

	// 为回归构造“缺失可用”的自变量，避免因缺失导致全部样本被剔除
	// 1) 分类变量缺失 -> 归入 0 类
	capture confirm variable activity_type_id
	if !_rc {
		replace activity_type_id = 0 if missing(activity_type_id)
		capture label define activity_type_id 0 "缺失", add
		capture label values activity_type_id activity_type_id
	}
	capture confirm variable court_level_id
	if !_rc {
		replace court_level_id = 0 if missing(court_level_id)
		capture label define court_level_id 0 "缺失", add
		capture label values court_level_id court_level_id
	}
	replace judgment_year = 0 if missing(judgment_year)

	// 额外控制变量：procedure_stage / doc_type / case_type_primary / case_type_secondary（缺失归入 0）
	foreach vv in procedure_stage_id doc_type_id case_type_primary_id case_type_secondary_id {
		capture confirm variable `vv'
		if !_rc replace `vv' = 0 if missing(`vv')
	}

	// 2) 数值变量缺失 -> 置 0 并加缺失指示
	gen byte ln_amount_miss = missing(ln_amount)
	replace ln_amount = 0 if missing(ln_amount)

	gen byte is_appeal_miss = missing(is_appeal_b)
	replace is_appeal_b = 0 if missing(is_appeal_b)

	// 3) 聚类变量缺失 -> 归入 0 类（否则 vce(cluster) 会丢观测）
	capture confirm variable `CLUSTER_ID'
	if !_rc {
		replace `CLUSTER_ID' = 0 if missing(`CLUSTER_ID')
	}

	// 若仍无可用样本，直接跳过
	quietly count
	if r(N) < 30 {
		di as err "回归被跳过：清洗后可用样本量不足（N=" r(N) "）。"
		local REG_STATUS "skipped"
		local REG_NOTE "insufficient usable sample after handling missings"
		clear
		set obs 1
		gen note = "Regression skipped: insufficient usable sample after handling missings (N=" + string(r(N)) + ")"
		export excel using "`TABLEDIR'/reg_logit_contract_invalid.xlsx", firstrow(variables) replace
		restore
	}
	else {
	// 回归：合同“无效/部分无效/未成立”概率 ~ 活动类型 + 法院层级 + 年份 + 金额 + 是否二审
		capture noisily logit contract_invalid ///
			i.activity_type_id i.court_level_id i.judgment_year ///
			i.procedure_stage_id i.doc_type_id i.case_type_primary_id i.case_type_secondary_id ///
			c.ln_amount i.ln_amount_miss ///
			i.is_appeal_b i.is_appeal_miss, ///
			vce(cluster `CLUSTER_ID')
		if _rc {
			di as err "回归失败（已捕获，不影响后续画图/出表），rc=" _rc
			local REG_STATUS "failed"
			local REG_NOTE "logit failed"
			clear
			set obs 1
			gen note = "Regression failed (captured). rc=" + string(_rc)
			export excel using "`TABLEDIR'/reg_logit_contract_invalid.xlsx", firstrow(variables) replace
			restore
		}
		else {
			estimates store m1
			local REG_STATUS "ok"
			local REG_NOTE ""

			// 系数表导出（自实现，不依赖外部包）
			tempfile coef
			postfile __p str80 term double b se z p using "`coef'", replace
			matrix b = e(b)
			matrix V = e(V)
			local cn : colnames b
			local k : word count `cn'
			forvalues i=1/`k' {
				local term : word `i' of `cn'
				scalar bi = b[1,`i']
				scalar sei = sqrt(V[`i',`i'])
				scalar zi = bi / sei
				scalar pi = 2*normal(-abs(zi))
				post __p ("`term'") (bi) (sei) (zi) (pi)
			}
			postclose __p
			use "`coef'", clear
			export excel using "`TABLEDIR'/reg_logit_contract_invalid.xlsx", firstrow(variables) replace
			// 另存 CSV 供 RTF 报告读取（避免解析 xlsx/dta 的依赖）
			export delimited using "`DATADIR'/reg_logit_contract_invalid.csv", replace
			// 同步保存一份 dta，供 RTF 报告读取
			save "`DATADIR'/reg_logit_contract_invalid.dta", replace
			restore
		}
	}
}

// -----------------------------
// 4B) DID：2017/2021 两次政策冲击对合同效力的影响
//     处理组：交易类案件（基于 activity_type 文本匹配）
//     时间：判决日期（judgment_date）断点：2017-09-04（94公告）/ 2021-09-24（254通知）
// -----------------------------
di as txt "开始 DID（2017/2021 政策冲击）..."

// 交易类标记：尽量捕捉 OTC/交易/买卖/发币/ICO/兑换 等
gen byte trade_group = .
replace trade_group = 1 if regexm(trim(activity_type), "场外交易|交易|买卖|发币|ICO|兑换")
replace trade_group = 0 if trade_group==. & trim(activity_type)!=""
label define trade_group 0 "非交易类" 1 "交易类"
label values trade_group trade_group

// 样本限定：民事/商事且确实讨论合同效力
// - “讨论合同效力”：contract_invalid 非缺失（等价于 contract_validity 能映射到有效/无效/未成立）
// - “民事/商事”：优先用 case_type_primary / doc_type；若缺失则回退到案号 case_number 的“民”字识别
gen byte sample_civil_commercial = 0
capture confirm string variable case_type_primary
if !_rc {
	replace sample_civil_commercial = 1 if regexm(trim(case_type_primary), "民|商|合同|买卖|委托|借贷|不当得利|侵权") ///
		& !regexm(trim(case_type_primary), "刑|行政")
}
capture confirm string variable doc_type
if !_rc {
	replace sample_civil_commercial = 1 if sample_civil_commercial==0 ///
		& regexm(trim(doc_type), "民|商") ///
		& !regexm(trim(doc_type), "刑|行政")
}
capture confirm string variable case_number
if !_rc {
	replace sample_civil_commercial = 1 if sample_civil_commercial==0 ///
		& regexm(trim(case_number), "民") ///
		& !regexm(trim(case_number), "刑|行")
}

// 政策时间点（按判决日期近似，若你未来补充交易发生时间，可替换为 transaction_time_span）
local P2017 = td(04sep2017)
local P2021 = td(24sep2021)
gen byte post2017 = (judgment_date_d >= `P2017') if !missing(judgment_date_d)
gen byte post2021 = (judgment_date_d >= `P2021') if !missing(judgment_date_d)

// 月度时间固定效应（更细粒度）
gen int ym = mofd(judgment_date_d)
format ym %tm

// DID 样本：民事/商事 + 讨论合同效力 + trade_group 非缺失 + ym 非缺失
preserve
keep if sample_civil_commercial==1 & !missing(contract_invalid) & !missing(trade_group) & !missing(ym)

// 控制变量（缺失归入 0 / 缺失指示）
replace activity_type_id = 0 if missing(activity_type_id)
replace court_level_id = 0 if missing(court_level_id)
replace procedure_stage_id = 0 if missing(procedure_stage_id)
replace doc_type_id = 0 if missing(doc_type_id)
replace case_type_primary_id = 0 if missing(case_type_primary_id)
replace case_type_secondary_id = 0 if missing(case_type_secondary_id)
replace judgment_year = 0 if missing(judgment_year)
gen byte ln_amount_miss_did = missing(ln_amount)
replace ln_amount = 0 if missing(ln_amount)
gen byte is_appeal_miss_did = missing(is_appeal_b)
replace is_appeal_b = 0 if missing(is_appeal_b)
replace `CLUSTER_ID' = 0 if missing(`CLUSTER_ID')

// DID 2017（LPM）：TWFE + 交互项 trade_group#post2017
capture noisily regress contract_invalid ///
	i.trade_group##i.post2017 ///
	i.ym ///
	i.court_level_id i.procedure_stage_id i.doc_type_id ///
	i.case_type_primary_id i.case_type_secondary_id ///
	c.ln_amount i.ln_amount_miss_did ///
	i.is_appeal_b i.is_appeal_miss_did, ///
	vce(cluster `CLUSTER_ID')
if !_rc estimates store did2017

// DID 2021（LPM）
capture noisily regress contract_invalid ///
	i.trade_group##i.post2021 ///
	i.ym ///
	i.court_level_id i.procedure_stage_id i.doc_type_id ///
	i.case_type_primary_id i.case_type_secondary_id ///
	c.ln_amount i.ln_amount_miss_did ///
	i.is_appeal_b i.is_appeal_miss_did, ///
	vce(cluster `CLUSTER_ID')
if !_rc estimates store did2021

// 输出 DID 表（esttab）
if `HAVE_ESTTAB' {
	capture noisily esttab did2017 did2021 using "`TABLEDIR'/did_contract_invalid.rtf", ///
		replace rtf se ///
		star(* 0.10 ** 0.05 *** 0.01) ///
		b(%9.3f) se(%9.3f) ///
		title("DID: 政策冲击对合同效力(无效/未成立=1)的影响") ///
		mtitles("Post-2017(94公告)" "Post-2021(254通知)") ///
		keep(1.trade_group 1.post2017 1.trade_group#1.post2017 1.post2021 1.trade_group#1.post2021) ///
		addnotes("样本=民事/商事且讨论合同效力；处理组=交易类(activity_type含交易/OTC/买卖/ICO等); 时间FE=月度; 聚类=`CLUSTER_ID'")
}
restore

// -----------------------------
// 4C) 事件研究（动态 DID）：
//     检验并行趋势：政策前若干月×处理组 交互系数应接近 0
//     输出：esttab RTF + 系数路径图（95%CI）
// -----------------------------
di as txt "开始事件研究（动态 DID）..."

// 事件窗：前后 24 个月（可根据需要调整）
local WIN = 24

// 复用 DID 样本定义
preserve
keep if sample_civil_commercial==1 & !missing(contract_invalid) & !missing(trade_group) & !missing(ym)

// 控制变量缺失处理（同 DID）
replace court_level_id = 0 if missing(court_level_id)
replace procedure_stage_id = 0 if missing(procedure_stage_id)
replace doc_type_id = 0 if missing(doc_type_id)
replace case_type_primary_id = 0 if missing(case_type_primary_id)
replace case_type_secondary_id = 0 if missing(case_type_secondary_id)
gen byte is_appeal_miss_es = missing(is_appeal_b)
replace is_appeal_b = 0 if missing(is_appeal_b)
replace `CLUSTER_ID' = 0 if missing(`CLUSTER_ID')

// === 2017 事件研究 ===
// 将政策日转换成“月度日期”（%tm），并计算相对月份
local YM2017 = mofd(`P2017')
gen int rel2017 = ym - `YM2017'
keep if rel2017 >= -`WIN' & rel2017 <= `WIN'

// 生成处理组×相对月份的哑变量（基准期：-1）
// 命名规则：负数用 m（minus）前缀，非负用 p（plus）前缀，例如 -12 => es17_m12，0 => es17_p0
forvalues k = -`WIN'/`WIN' {
	if `k' != -1 {
		if `k' < 0 local suf "m`=abs(`k')'"
		else local suf "p`k'"
		gen byte es17_`suf' = (rel2017==`k' & trade_group==1)
	}
}

capture noisily regress contract_invalid ///
		i.trade_group es17_* ///
		i.ym ///
		i.court_level_id i.procedure_stage_id i.doc_type_id ///
		i.case_type_primary_id i.case_type_secondary_id ///
		i.is_appeal_b i.is_appeal_miss_es, ///
		vce(cluster `CLUSTER_ID')
if !_rc estimates store es2017

// 将系数整理成数据并画图（外层已 preserve，避免嵌套 preserve 导致 r(621)）
capture noisily estimates restore es2017
clear
set obs `=2*`WIN'+1'
gen int k = _n - (`WIN'+1)   // -WIN ... WIN
gen double b = .
gen double se = .
gen double lb = .
gen double ub = .
forvalues i=1/`=_N' {
	local kk = k[`i']
	if `kk' != -1 {
		if `kk' < 0 local suf "m`=abs(`kk')'"
		else local suf "p`kk'"
		capture {
			replace b  = _b[es17_`suf'] in `i'
			replace se = _se[es17_`suf'] in `i'
		}
		replace lb = b - 1.96*se in `i'
		replace ub = b + 1.96*se in `i'
	}
}
twoway ///
	(rcap lb ub k, lcolor(gs10)) ///
	(connected b k, msymbol(o) mcolor(navy) lcolor(navy)) ///
	, xline(-1, lpattern(dash) lcolor(gs8)) yline(0, lpattern(solid) lcolor(gs12)) ///
	  title("事件研究：2017 政策冲击（交易类×相对月份）") ///
	  xtitle("相对月份（0=政策月）") ytitle("系数（相对基准期 -1 月）")
graph export "`FIGDIR'/eventstudy_2017.png", replace width(2400)

// 输出 esttab（仅交互项 + N）
if `HAVE_ESTTAB' {
	capture noisily esttab es2017 using "`TABLEDIR'/eventstudy_2017.rtf", ///
		replace rtf se ///
		star(* 0.10 ** 0.05 *** 0.01) ///
		b(%9.3f) se(%9.3f) ///
		title("Event study: 2017 政策冲击（交易类×相对月份，基准=-1）") ///
		addnotes("样本=民事/商事且讨论合同效力；时间FE=月度；聚类=`CLUSTER_ID'；事件窗=±`WIN'个月")
}

// === 2021 事件研究 ===
restore, preserve
keep if sample_civil_commercial==1 & !missing(contract_invalid) & !missing(trade_group) & !missing(ym)
replace court_level_id = 0 if missing(court_level_id)
replace procedure_stage_id = 0 if missing(procedure_stage_id)
replace doc_type_id = 0 if missing(doc_type_id)
replace case_type_primary_id = 0 if missing(case_type_primary_id)
replace case_type_secondary_id = 0 if missing(case_type_secondary_id)
gen byte is_appeal_miss_es2 = missing(is_appeal_b)
replace is_appeal_b = 0 if missing(is_appeal_b)
replace `CLUSTER_ID' = 0 if missing(`CLUSTER_ID')

local YM2021 = mofd(`P2021')
gen int rel2021 = ym - `YM2021'
keep if rel2021 >= -`WIN' & rel2021 <= `WIN'

forvalues k = -`WIN'/`WIN' {
	if `k' != -1 {
		if `k' < 0 local suf "m`=abs(`k')'"
		else local suf "p`k'"
		gen byte es21_`suf' = (rel2021==`k' & trade_group==1)
	}
}

capture noisily regress contract_invalid ///
		i.trade_group es21_* ///
		i.ym ///
		i.court_level_id i.procedure_stage_id i.doc_type_id ///
		i.case_type_primary_id i.case_type_secondary_id ///
		i.is_appeal_b i.is_appeal_miss_es2, ///
		vce(cluster `CLUSTER_ID')
if !_rc estimates store es2021

// 画图（外层已 preserve，避免嵌套 preserve）
capture noisily estimates restore es2021
clear
set obs `=2*`WIN'+1'
gen int k = _n - (`WIN'+1)
gen double b = .
gen double se = .
gen double lb = .
gen double ub = .
forvalues i=1/`=_N' {
	local kk = k[`i']
	if `kk' != -1 {
		if `kk' < 0 local suf "m`=abs(`kk')'"
		else local suf "p`kk'"
		capture {
			replace b  = _b[es21_`suf'] in `i'
			replace se = _se[es21_`suf'] in `i'
		}
		replace lb = b - 1.96*se in `i'
		replace ub = b + 1.96*se in `i'
	}
}
twoway ///
	(rcap lb ub k, lcolor(gs10)) ///
	(connected b k, msymbol(o) mcolor(maroon) lcolor(maroon)) ///
	, xline(-1, lpattern(dash) lcolor(gs8)) yline(0, lpattern(solid) lcolor(gs12)) ///
	  title("事件研究：2021 政策冲击（交易类×相对月份）") ///
	  xtitle("相对月份（0=政策月）") ytitle("系数（相对基准期 -1 月）")
graph export "`FIGDIR'/eventstudy_2021.png", replace width(2400)

if `HAVE_ESTTAB' {
	capture noisily esttab es2021 using "`TABLEDIR'/eventstudy_2021.rtf", ///
		replace rtf se ///
		star(* 0.10 ** 0.05 *** 0.01) ///
		b(%9.3f) se(%9.3f) ///
		title("Event study: 2021 政策冲击（交易类×相对月份，基准=-1）") ///
		addnotes("样本=民事/商事且讨论合同效力；时间FE=月度；聚类=`CLUSTER_ID'；事件窗=±`WIN'个月")
}

restore

// 回归（logit）也用 esttab 输出一份（若可用）
if `HAVE_ESTTAB' {
	cap which esttab
	if !_rc {
		capture noisily esttab m1 using "`TABLEDIR'/logit_contract_invalid.rtf", ///
			replace rtf se ///
			star(* 0.10 ** 0.05 *** 0.01) ///
			b(%9.3f) se(%9.3f) ///
			title("Logit: 合同效力(无效/未成立=1) 及控制变量") ///
			addnotes("聚类稳健标准误: `CLUSTER_ID'；缺失值：金额/是否二审用缺失指示；分类缺失归入0类")
	}
}

// -----------------------------
// 5) 画图（导出 PNG）
// -----------------------------
di as txt "开始画图..."

// 图1：年度案件量
preserve
keep if !missing(judgment_year)
gen byte one = 1
graph bar (sum) one, over(judgment_year, sort(1) label(angle(45))) ///
	title("年度案件量") ytitle("案件数")
graph export "`FIGDIR'/fig_cases_by_year.png", replace width(2000)
restore

// 图2：合同无效比例（按年份）
preserve
keep if !missing(judgment_year) & !missing(contract_invalid)
gen byte one = 1
collapse (mean) invalid_rate=contract_invalid (sum) N=one, by(judgment_year)
twoway (line invalid_rate judgment_year, lwidth(medthick)) ///
	, title("合同无效/部分无效比例（按年份）") ///
	  ytitle("比例") xtitle("年份") ylabel(0(0.1)1)
graph export "`FIGDIR'/fig_invalid_rate_by_year.png", replace width(2000)
restore

// 图3：活动类型 Top10（条形图）
preserve
keep if trim(activity_type)!=""
gen byte one = 1
collapse (sum) N=one, by(activity_type)
gsort -N
keep in 1/10
graph bar N, over(activity_type, sort(1) label(angle(30))) ///
	title("活动类型 Top10") ytitle("案件数")
graph export "`FIGDIR'/fig_activity_type_top10.png", replace width(2400)
restore

// -----------------------------
// 6) 生成 RTF 报告（便于阅读/粘贴，解决中文乱码：全部写为 RTF \uXXXX?）
// -----------------------------
di as txt "开始生成 RTF 报告..."

local REPORTDIR "`OUTDIR'/report"
local RTF "`REPORTDIR'/report.rtf"

capture noisily python:
import os, csv, re
from collections import Counter

report_dir = r"""`REPORTDIR'"""
rtf_path = r"""`RTF'"""
figdir = r"""`FIGDIR'"""
datadir = r"""`DATADIR'"""
root = r"""`ROOT'"""
outdir = r"""`OUTDIR'"""
cluster_id = r"""`CLUSTER_ID'"""
reg_status = r"""`REG_STATUS'"""
reg_note = r"""`REG_NOTE'"""
flat_csv = os.path.join(datadir, "final_all_flat.csv")

os.makedirs(report_dir, exist_ok=True)

def rtf_escape(text: str) -> str:
    if text is None:
        return ""
    s = str(text)
    out = []
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == "{":
            out.append("\\{")
        elif ch == "}":
            out.append("\\}")
        elif ch == "\n":
            out.append("\\par\n")
        else:
            code = ord(ch)
            if code < 128:
                out.append(ch)
            else:
                # RTF \uN uses signed 16-bit integers
                if code > 0x7FFF:
                    code -= 0x10000
                out.append(f"\\u{code}?")
    return "".join(out)

def nonempty_str(x):
    return x is not None and str(x).strip() != ""

def parse_year(date_str: str):
    # 期待格式 YYYY-MM-DD；若不是则尝试抓取前4位数字
    if not nonempty_str(date_str):
        return None
    s = str(date_str).strip()
    m = re.match(r"^(\d{4})", s)
    if m:
        return int(m.group(1))
    return None

def cv_cat_and_invalid(cv: str):
    if not nonempty_str(cv):
        return (None, None)
    s = str(cv).strip()
    # 分类：尽量对齐 do 文件里的逻辑（优先更具体的“部分无效”）
    if "部分无效" in s:
        cat = 3
    elif "无效" in s:
        cat = 2
    elif "未成立" in s:
        cat = 4
    elif "有效" in s:
        cat = 1
    else:
        cat = 5
    # 二元：无效/部分无效/未成立=1；有效=0；其他缺失
    if ("无效" in s) or ("未成立" in s):
        inv = 1
    elif "有效" in s:
        inv = 0
    else:
        inv = None
    return (cat, inv)

# 从扁平 CSV 统计（不依赖 sfi API）
N_ALL = 0
N_CV = 0
N_INV = 0
N_VAL = 0
year_counts = Counter()
cv_counts = Counter()
act_counts = Counter()

with open(flat_csv, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        N_ALL += 1
        cv = row.get("contract_validity", "")
        if nonempty_str(cv):
            N_CV += 1
        cat, inv = cv_cat_and_invalid(cv)
        if cat is not None:
            cv_counts[cat] += 1
        if inv == 1:
            N_INV += 1
        elif inv == 0:
            N_VAL += 1
        y = parse_year(row.get("judgment_date", ""))
        if y is not None:
            year_counts[y] += 1
        at = row.get("activity_type", "")
        if nonempty_str(at):
            act_counts[str(at).strip()] += 1

top20_act = act_counts.most_common(20)
cv_labels = {1: "有效", 2: "无效", 3: "部分无效", 4: "未成立", 5: "其他"}

# 回归系数（如有）
coef_rows = []
coef_csv = os.path.join(datadir, "reg_logit_contract_invalid.csv")
if os.path.exists(coef_csv):
    with open(coef_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            coef_rows.append(row)

lines = []
lines.append(r"{\rtf1\ansi\uc1\deff0{\fonttbl{\f0 Arial;}}")
lines.append(r"\f0\b " + rtf_escape("数字货币裁判文书结构化数据：Stata 分析报告") + r" \b0\par")
lines.append(rtf_escape(f"工作目录：{root}") + r"\par")
lines.append(rtf_escape(f"输出目录：{outdir}") + r"\par\par")

lines.append(r"\b " + rtf_escape("1. 数据概览") + r" \b0\par")
lines.append(rtf_escape(f"总样本量 (N)：{N_ALL}") + r"\par")
lines.append(rtf_escape(f"contract_validity 非空样本量：{N_CV}") + r"\par")
lines.append(rtf_escape(f"contract_invalid=1 (无效/部分无效/未成立)：{N_INV}") + r"\par")
lines.append(rtf_escape(f"contract_invalid=0 (有效)：{N_VAL}") + r"\par\par")

lines.append(r"\b " + rtf_escape("2. 描述统计表") + r" \b0\par")
lines.append(r"\b " + rtf_escape("2.1 按年份案件量") + r" \b0\par")
lines.append(rtf_escape("年份\t案件数") + r"\par")
for y in sorted(year_counts):
    lines.append(rtf_escape(f"{y}\t{year_counts[y]}") + r"\par")
lines.append(r"\par")

lines.append(r"\b " + rtf_escape("2.2 合同效力分布（contract_validity_cat）") + r" \b0\par")
lines.append(rtf_escape("类别\t案件数") + r"\par")
for k in sorted(cv_counts):
    lab = cv_labels.get(k, str(k))
    lines.append(rtf_escape(f"{lab}\t{cv_counts[k]}") + r"\par")
lines.append(r"\par")

lines.append(r"\b " + rtf_escape("2.3 活动类型 Top20") + r" \b0\par")
lines.append(rtf_escape("活动类型\t案件数") + r"\par")
for a, n in top20_act:
    lines.append(rtf_escape(f"{a}\t{n}") + r"\par")
lines.append(r"\par")

lines.append(r"\b " + rtf_escape("3. 回归模型") + r" \b0\par")
lines.append(rtf_escape("模型：Logit(二元因变量)") + r"\par")
lines.append(rtf_escape("因变量：contract_invalid（无效/部分无效/未成立=1；有效=0）") + r"\par")
lines.append(rtf_escape("自变量：activity_type(类别) + court_level(类别) + judgment_year(年份虚拟变量) + ln(涉案金额+1) + 是否二审") + r"\par")
lines.append(rtf_escape("缺失处理：对 ln_amount / is_appeal 生成缺失指示，并将缺失值置0；分类变量缺失归入0类") + r"\par")
lines.append(rtf_escape(f"稳健标准误：按 {cluster_id} 聚类（优先 region，否则 court_name）") + r"\par\par")
lines.append(rtf_escape(f"回归状态：{reg_status}") + r"\par")
if reg_note and reg_note.strip():
    lines.append(rtf_escape(f"备注：{reg_note}") + r"\par")

if coef_rows:
    lines.append(r"\par\b " + rtf_escape("3.1 系数表（logit）") + r" \b0\par")
    lines.append(rtf_escape("term\tb\tse\tz\tp") + r"\par")
    for row in coef_rows[:500]:
        term = row.get("term","")
        b = row.get("b","")
        se = row.get("se","")
        z = row.get("z","")
        p = row.get("p","")
        lines.append(rtf_escape(f"{term}\t{b}\t{se}\t{z}\t{p}") + r"\par")

lines.append(r"\par\b " + rtf_escape("4. 图形输出（PNG 文件）") + r" \b0\par")
lines.append(rtf_escape(os.path.join(figdir, "fig_cases_by_year.png")) + r"\par")
lines.append(rtf_escape(os.path.join(figdir, "fig_invalid_rate_by_year.png")) + r"\par")
lines.append(rtf_escape(os.path.join(figdir, "fig_activity_type_top10.png")) + r"\par")

lines.append("}")
with open(rtf_path, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines))
print("[python] wrote rtf:", rtf_path)
end

if _rc {
	di as err "RTF 报告生成失败（python rc=" _rc "）。请检查 Stata 的 python 配置。"
}
else {
	di as txt "RTF 报告已生成: `RTF'"
}

di as txt "============================================================"
di as txt "分析完成：请查看 analyze/ 目录下 data/tables/figures/logs"
di as txt "============================================================"

log close

