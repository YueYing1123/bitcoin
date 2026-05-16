version 19
clear all
set more off
set linesize 255

// ============================================================
//  民事组单独验证：不同金额口径下 activity_type 的影响
//  场景：
//   1) 不控制金额
//   2) amount_mean_regex
//   3) amount_max_regex
//   4) amount_median_regex
//   5) amount_count_regex
//   6) case_amount
// ============================================================

local ROOT "`c(pwd)'"
local OUTROOT "`ROOT'/analyze/civil_amount_scenarios"
local DATADIR "`OUTROOT'/data"
local TABLEDIR "`OUTROOT'/tables"
local LOGDIR "`OUTROOT'/logs"

cap mkdir "`ROOT'/analyze"
cap mkdir "`OUTROOT'"
cap mkdir "`DATADIR'"
cap mkdir "`TABLEDIR'"
cap mkdir "`LOGDIR'"

log close _all
log using "`LOGDIR'/civil_amount_scenarios.log", replace text

di as txt "============================================================"
di as txt "民事组金额口径敏感性检验启动"
di as txt "工作目录: `ROOT'"
di as txt "输出目录: `OUTROOT'"
di as txt "============================================================"

// -----------------------------
// 0) 载入数据
// -----------------------------
local CSV "`ROOT'/analyze/data/final_all_flat.csv"
cap confirm file "`CSV'"
if _rc {
	di as err "找不到输入数据：`CSV'"
	error 601
}
import delimited using "`CSV'", clear varnames(1) encoding(UTF-8) stringcols(_all)
compress

// 统一字符串缺失
foreach v of varlist _all {
	capture confirm string variable `v'
	if !_rc replace `v' = "" if lower(trim(`v')) == "null"
}

// -----------------------------
// 1) 核心变量构造
// -----------------------------
// 金额与关键字段：字符串安全转数值
foreach v in case_amount amount_mean_regex amount_max_regex amount_median_regex amount_count_regex contract_validity_regex {
	capture confirm variable `v'
	if !_rc {
		capture confirm numeric variable `v'
		if _rc {
			tempvar __num
			gen double `__num' = real(subinstr(subinstr(trim(`v'), ",", "", .), " ", "", .))
			drop `v'
			rename `__num' `v'
		}
	}
}

// judgment_year
capture confirm variable judgment_year
if _rc {
	gen double judgment_date_d = daily(judgment_date, "YMD")
	format judgment_date_d %td
	gen int judgment_year = year(judgment_date_d)
}

// is_appeal
capture confirm variable is_appeal_b
if _rc {
	gen byte is_appeal_b = .
	replace is_appeal_b = 1 if inlist(lower(trim(is_appeal)), "true", "1", "yes")
	replace is_appeal_b = 0 if inlist(lower(trim(is_appeal)), "false", "0", "no")
}
gen byte is_appeal_miss = missing(is_appeal_b)
replace is_appeal_b = 0 if missing(is_appeal_b)

// 主因变量：1=无效/未成立，0=有效
capture confirm variable contract_invalid
if _rc {
	gen byte contract_invalid = .
	replace contract_invalid = 1 if regexm(trim(contract_validity), "无效|未成立")
	replace contract_invalid = 0 if contract_invalid==. & regexm(trim(contract_validity), "有效")
}

// activity_type 主解释变量：合并低频
local MIN_ACTIVITY_N = 20
gen strL activity_type_main = trim(activity_type)
replace activity_type_main = "未分类" if activity_type_main==""
bysort activity_type_main: gen long activity_n = _N
replace activity_type_main = "其他(稀疏)" if activity_n < `MIN_ACTIVITY_N'
drop activity_n
encode activity_type_main, gen(activity_type_main_id)

// 固定主基准组（优先“买卖合同”），便于与主回归脚本对齐
local BASE_ACTIVITY_ID = .
quietly levelsof activity_type_main_id if activity_type_main=="买卖合同", local(__base_act)
if "`__base_act'" != "" {
	local BASE_ACTIVITY_ID : word 1 of `__base_act'
}
else {
	quietly summarize activity_type_main_id if !missing(activity_type_main_id), meanonly
	local BASE_ACTIVITY_ID = r(min)
}

// 控制变量编码
capture confirm variable court_level_id
if _rc {
	capture encode court_level, gen(court_level_id)
	if _rc gen long court_level_id = .
}
capture confirm variable procedure_stage_id
if _rc {
	capture encode procedure_stage, gen(procedure_stage_id)
	if _rc gen long procedure_stage_id = .
}
capture confirm variable doc_type_id
if _rc {
	capture encode doc_type, gen(doc_type_id)
	if _rc gen long doc_type_id = .
}
capture confirm variable region_id
if _rc {
	capture encode region, gen(region_id)
	if _rc gen long region_id = .
}
capture confirm variable court_name_id
if _rc {
	capture encode court_name, gen(court_name_id)
	if _rc gen long court_name_id = .
}

replace court_level_id = 0 if missing(court_level_id)
replace procedure_stage_id = 0 if missing(procedure_stage_id)
replace doc_type_id = 0 if missing(doc_type_id)
replace judgment_year = 0 if missing(judgment_year)
replace region_id = 0 if missing(region_id)
replace court_name_id = 0 if missing(court_name_id)

// 刑民识别：只保留民事组
gen byte is_criminal = .
replace is_criminal = 1 if regexm(trim(case_type_primary), "刑") | regexm(trim(doc_type), "刑") | regexm(trim(case_number), "刑")
replace is_criminal = 0 if is_criminal==. & (regexm(trim(case_type_primary), "民|商|合同") | regexm(trim(doc_type), "民|商") | regexm(trim(case_number), "民"))

// 金额变量与缺失指示
gen byte amt_case_miss = missing(case_amount)
gen byte amt_mean_miss = missing(amount_mean_regex)
gen byte amt_max_miss = missing(amount_max_regex)
gen byte amt_median_miss = missing(amount_median_regex)
gen byte amt_count_miss = missing(amount_count_regex)

gen double ln_amt_case = ln(case_amount + 1) if !missing(case_amount)
gen double ln_amt_mean = ln(amount_mean_regex + 1) if !missing(amount_mean_regex)
gen double ln_amt_max = ln(amount_max_regex + 1) if !missing(amount_max_regex)
gen double ln_amt_median = ln(amount_median_regex + 1) if !missing(amount_median_regex)
gen double ln_amt_count = ln(amount_count_regex + 1) if !missing(amount_count_regex)

replace ln_amt_case = 0 if missing(ln_amt_case)
replace ln_amt_mean = 0 if missing(ln_amt_mean)
replace ln_amt_max = 0 if missing(ln_amt_max)
replace ln_amt_median = 0 if missing(ln_amt_median)
replace ln_amt_count = 0 if missing(ln_amt_count)

// 仅民事组 + 因变量非缺失
keep if is_criminal==0 & !missing(contract_invalid)
quietly count
if r(N) < 100 {
	di as err "民事组有效样本量不足，N=" r(N)
	error 2001
}

// 若民事样本中不存在全局基准组，回退到民事样本最小ID
quietly count if activity_type_main_id==`BASE_ACTIVITY_ID'
if r(N) == 0 {
	quietly summarize activity_type_main_id if !missing(activity_type_main_id), meanonly
	local BASE_ACTIVITY_ID = r(min)
}
local BASE_ACTIVITY_LABEL : label (activity_type_main_id) `BASE_ACTIVITY_ID'
di as txt "民事组 activity_type 基准组ID: `BASE_ACTIVITY_ID'，标签: `BASE_ACTIVITY_LABEL'"

// 聚类层级：优先 region，否则 court_name
local CLUSTER_ID "court_name_id"
quietly count if region_id != 0
if r(N) > 0 local CLUSTER_ID "region_id"
replace `CLUSTER_ID' = 0 if missing(`CLUSTER_ID')

// 输出 activity_type 编码映射（便于解释 id）
preserve
decode activity_type_main_id, gen(activity_type_label)
keep activity_type_main_id activity_type_label
bysort activity_type_main_id activity_type_label: keep if _n==1
sort activity_type_main_id
export delimited using "`DATADIR'/activity_type_id_map.csv", replace nolabel
export excel using "`DATADIR'/activity_type_id_map.xlsx", firstrow(variables) replace
restore

// esttab 可用性
local HAVE_ESTTAB = 0
cap which esttab
if _rc {
	capture noisily ssc install estout, replace
	cap which esttab
}
if !_rc local HAVE_ESTTAB = 1

local base_ctrl "i.court_level_id i.procedure_stage_id i.judgment_year i.doc_type_id i.is_appeal_b i.is_appeal_miss"
local fitopt "vce(cluster `CLUSTER_ID') iterate(50)"
local act_term "ib`BASE_ACTIVITY_ID'.activity_type_main_id"

tempfile coefdetail
postfile __coef str20 model_id str24 scenario int activity_id str120 activity_label ///
	double b se z p using "`coefdetail'", replace

local models ""
local titles ""

capture program drop run_one_model
program define run_one_model, rclass
	syntax, MODELID(string) SCENARIO(string) [AMTVAR(name) MISSVAR(name)]

	local rhs "$ACT_TERM $BASE_CTRL"
	if "`amtvar'" != "" {
		local rhs "`rhs' c.`amtvar' i.`missvar'"
	}

	capture noisily logit contract_invalid `rhs', $FITOPT
	if _rc capture noisily logit contract_invalid `rhs', $FITOPT technique(nr)
	if _rc capture noisily logit contract_invalid `rhs', $FITOPT technique(bhhh)
	if _rc {
		return scalar ok = 0
		exit
	}

	estimates store `modelid'

	matrix b = e(b)
	matrix V = e(V)
	local cn : colnames b
	local k : word count `cn'
	forvalues i = 1/`k' {
		local term : word `i' of `cn'
		if regexm("`term'", "^[0-9]+\.activity_type_main_id$") {
			local dot = strpos("`term'", ".")
			local aid = real(substr("`term'", 1, `dot'-1))
			local alabel : label (activity_type_main_id) `aid'

			scalar bi = b[1,`i']
			scalar sei = sqrt(V[`i',`i'])
			scalar zi = bi / sei
			scalar pi = 2*normal(-abs(zi))

			post __coef ("`modelid'") ("`scenario'") (`aid') ("`alabel'") (bi) (sei) (zi) (pi)
		}
	}

	return scalar ok = 1
end

global BASE_CTRL "`base_ctrl'"
global FITOPT "`fitopt'"
global ACT_TERM "`act_term'"

// -----------------------------
// 2) 六种金额情形回归
// -----------------------------
quietly run_one_model, modelid(m_noamt) scenario(no_amount)
if r(ok)==1 {
	local models "`models' m_noamt"
	local titles `"`titles' "NoAmount""'
}

quietly run_one_model, modelid(m_mean) scenario(amount_mean_regex) amtvar(ln_amt_mean) missvar(amt_mean_miss)
if r(ok)==1 {
	local models "`models' m_mean"
	local titles `"`titles' "AmtMeanRegex""'
}

quietly run_one_model, modelid(m_max) scenario(amount_max_regex) amtvar(ln_amt_max) missvar(amt_max_miss)
if r(ok)==1 {
	local models "`models' m_max"
	local titles `"`titles' "AmtMaxRegex""'
}

quietly run_one_model, modelid(m_median) scenario(amount_median_regex) amtvar(ln_amt_median) missvar(amt_median_miss)
if r(ok)==1 {
	local models "`models' m_median"
	local titles `"`titles' "AmtMedianRegex""'
}

quietly run_one_model, modelid(m_count) scenario(amount_count_regex) amtvar(ln_amt_count) missvar(amt_count_miss)
if r(ok)==1 {
	local models "`models' m_count"
	local titles `"`titles' "AmtCountRegex""'
}

quietly run_one_model, modelid(m_case) scenario(case_amount) amtvar(ln_amt_case) missvar(amt_case_miss)
if r(ok)==1 {
	local models "`models' m_case"
	local titles `"`titles' "CaseAmount""'
}

if "`models'" == "" {
	di as err "所有模型都估计失败。"
	postclose __coef
	error 430
}

// 主回归表
if `HAVE_ESTTAB' {
	capture noisily esttab `models' using "`TABLEDIR'/reg_civil_amount_scenarios.rtf", ///
		replace rtf se star(* 0.10 ** 0.05 *** 0.01) ///
		b(%9.3f) se(%9.3f) ///
		mtitles(`titles') ///
		addnotes("Sample=civil only (is_criminal==0)", "DV=contract_invalid", "cluster=`CLUSTER_ID'", ///
		         "activity_type low-frequency merged: N<20 => 其他(稀疏)", "logit: iterate(50)+fallback(nr/bhhh)")
}
foreach m of local models {
	estimates save "`DATADIR'/`m'.ster", replace
}

// 案由系数明细导出
postclose __coef
use "`coefdetail'", clear
gen str8 sign = cond(b>0, "positive", cond(b<0, "negative", "zero"))
gen str6 sig = cond(p<0.01, "***", cond(p<0.05, "**", cond(p<0.10, "*", "")))
sort scenario activity_id
export delimited using "`DATADIR'/civil_activity_effects_by_amount_model.csv", replace
export excel using "`DATADIR'/civil_activity_effects_by_amount_model.xlsx", firstrow(variables) replace
save "`DATADIR'/civil_activity_effects_by_amount_model.dta", replace

di as txt "完成：民事组金额口径敏感性回归已输出。"
di as txt "输出目录：`OUTROOT'"
log close
