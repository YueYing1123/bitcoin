version 19
clear all
set more off
set linesize 255

// ============================================================
//  目标：
//  1) 复现“案由/罪名 -> 合同无效”的回归，并采用单调递增控制变量
//  2) 金额控制轮询：均值 / 中位数 / 最大值
//  3) 比较：不含交互项 vs 含交互项（刑/民 × 案由、刑/民 × 金额）
//  4) 稳健性：使用 contract_validity_regex 重新回归
//  5) 分组：刑事 / 民事分别回归
// ============================================================

local ROOT "`c(pwd)'"
local OUTDIR "`ROOT'/analyze"
local DATADIR "`OUTDIR'/data"
local TABLEDIR "`OUTDIR'/tables"
local LOGDIR "`OUTDIR'/logs"

cap mkdir "`OUTDIR'"
cap mkdir "`DATADIR'"
cap mkdir "`TABLEDIR'"
cap mkdir "`LOGDIR'"

log close _all
log using "`LOGDIR'/analyze_incremental_case_cause.log", replace text

di as txt "============================================================"
di as txt "增量控制 + 交互项 + 分组回归启动"
di as txt "工作目录: `ROOT'"
di as txt "============================================================"

// -----------------------------
// 0) 载入数据（优先 dta，若缺少 regex 列则回退 csv）
// -----------------------------
local DTA "`DATADIR'/final_all_flat.dta"
local CSV "`DATADIR'/final_all_flat.csv"

local LOADED_FROM_DTA 0
cap confirm file "`DTA'"
if !_rc {
	use "`DTA'", clear
	local LOADED_FROM_DTA 1
}
else {
	cap confirm file "`CSV'"
	if _rc {
		di as err "找不到输入数据：`DTA' 与 `CSV'"
		error 601
	}
	import delimited using "`CSV'", clear varnames(1) encoding(UTF-8) stringcols(_all)
}

// 如果 dta 里没有 regex 列，说明 dta 版本偏旧；改读 csv 以保证稳健性变量可用
if `LOADED_FROM_DTA' {
	capture confirm variable contract_validity_regex
	local HAS_REGEX = 0
	if !_rc local HAS_REGEX = 1

	if `HAS_REGEX' == 0 {
		di as txt "检测到 dta 缺少 contract_validity_regex，自动回退读取 CSV..."
		cap confirm file "`CSV'"
		if _rc {
			di as err "CSV 不存在，无法回退：`CSV'"
			error 601
		}
		import delimited using "`CSV'", clear varnames(1) encoding(UTF-8) stringcols(_all)
		local LOADED_FROM_DTA 0
	}
}
compress

// 统一 "null" 字符串为缺失
foreach v of varlist _all {
	capture confirm string variable `v'
	if !_rc replace `v' = "" if lower(trim(`v')) == "null"
}

// -----------------------------
// 1) 核心变量构造
// -----------------------------
// 注意：CSV 以 stringcols(_all) 导入后，金额列通常是 strL。
// 这里显式把关键金额字段从字符串安全转换为数值，避免 ln() type mismatch。
foreach v in total_amount_cny case_amount amount_mean_regex amount_median_regex amount_max_regex contract_validity_regex {
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

local HAS_REGEX_DV 1
capture confirm variable contract_validity_regex
if _rc local HAS_REGEX_DV 0

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
	replace is_appeal_b = 1 if inlist(lower(trim(is_appeal)), "true","1","yes")
	replace is_appeal_b = 0 if inlist(lower(trim(is_appeal)), "false","0","no")
}
gen byte is_appeal_miss = missing(is_appeal_b)
replace is_appeal_b = 0 if missing(is_appeal_b)

// 二元因变量（主）
capture confirm variable contract_invalid
if _rc {
	gen byte contract_invalid = .
	replace contract_invalid = 1 if regexm(trim(contract_validity), "无效|未成立")
	replace contract_invalid = 0 if contract_invalid==. & regexm(trim(contract_validity), "有效")
}

// 二元因变量（稳健性）：contract_validity_regex 里 0=无效，1=有效
gen byte contract_invalid_regex = .
if `HAS_REGEX_DV' {
	replace contract_invalid_regex = 1 if contract_validity_regex==0
	replace contract_invalid_regex = 0 if contract_validity_regex==1
}
else {
	di as err "警告：contract_validity_regex 不存在，将跳过 regex 稳健性回归。"
}

// 主解释变量：activity_type
// 并把低频类别合并为“其他(稀疏)”以提高收敛稳定性
local MIN_ACTIVITY_N = 20
gen strL activity_type_main = trim(activity_type)
replace activity_type_main = "未分类" if activity_type_main==""
bysort activity_type_main: gen long activity_n = _N
replace activity_type_main = "其他(稀疏)" if activity_n < `MIN_ACTIVITY_N'
drop activity_n
encode activity_type_main, gen(activity_type_main_id)

// 固定主基准组（优先“买卖合同”），便于跨脚本/跨分组对齐解释口径
local BASE_ACTIVITY_ID = .
quietly levelsof activity_type_main_id if activity_type_main=="买卖合同", local(__base_act)
if "`__base_act'" != "" {
	local BASE_ACTIVITY_ID : word 1 of `__base_act'
}
else {
	quietly summarize activity_type_main_id if !missing(activity_type_main_id), meanonly
	local BASE_ACTIVITY_ID = r(min)
}
local BASE_ACTIVITY_LABEL : label (activity_type_main_id) `BASE_ACTIVITY_ID'
di as txt "activity_type 主基准组ID: `BASE_ACTIVITY_ID'，标签: `BASE_ACTIVITY_LABEL'"

// 导出“数值ID-标签”映射，确保与回归输出可一一对齐
preserve
keep activity_type_main_id activity_type_main
bysort activity_type_main_id activity_type_main: keep if _n==1
sort activity_type_main_id
export delimited using "`DATADIR'/activity_type_id_map_main.csv", replace nolabel
export excel using "`DATADIR'/activity_type_id_map_main.xlsx", firstrow(variables) replace
restore

quietly count if !missing(activity_type_main_id)
di as txt "activity_type_main_id 非缺失样本量: " r(N)

// 分类控制变量编码
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

// 缺失归入 0 类（用于 factor 控制）
replace court_level_id = 0 if missing(court_level_id)
replace procedure_stage_id = 0 if missing(procedure_stage_id)
replace doc_type_id = 0 if missing(doc_type_id)
replace judgment_year = 0 if missing(judgment_year)
replace region_id = 0 if missing(region_id)
replace court_name_id = 0 if missing(court_name_id)

// 金额变量（log + 缺失指示）
// 主金额变量切换为 case_amount（来自最新大模型抽取）
gen byte amt_main_miss = missing(case_amount)
gen double ln_amt_main = ln(case_amount + 1) if !missing(case_amount)
replace ln_amt_main = 0 if missing(ln_amt_main)

gen byte amt_mean_miss = missing(amount_mean_regex)
gen byte amt_median_miss = missing(amount_median_regex)
gen byte amt_max_miss = missing(amount_max_regex)

gen double ln_amt_mean = ln(amount_mean_regex + 1) if !missing(amount_mean_regex)
gen double ln_amt_median = ln(amount_median_regex + 1) if !missing(amount_median_regex)
gen double ln_amt_max = ln(amount_max_regex + 1) if !missing(amount_max_regex)

replace ln_amt_mean = 0 if missing(ln_amt_mean)
replace ln_amt_median = 0 if missing(ln_amt_median)
replace ln_amt_max = 0 if missing(ln_amt_max)

// 刑事/民事标记
gen byte is_criminal = .
replace is_criminal = 1 if regexm(trim(case_type_primary), "刑") | regexm(trim(doc_type), "刑") | regexm(trim(case_number), "刑")
replace is_criminal = 0 if is_criminal==. & (regexm(trim(case_type_primary), "民|商|合同") | regexm(trim(doc_type), "民|商") | regexm(trim(case_number), "民"))

// 聚类层级：优先 region，否则 court_name
local CLUSTER_ID "court_name_id"
quietly count if region_id!=0
if r(N) > 0 local CLUSTER_ID "region_id"
replace `CLUSTER_ID' = 0 if missing(`CLUSTER_ID')

// esttab 可用性
local HAVE_ESTTAB = 0
cap which esttab
if _rc {
	capture noisily ssc install estout, replace
	cap which esttab
}
if !_rc local HAVE_ESTTAB = 1

// -----------------------------
// 2) 先做你关心的分布检查（刑/民 × 因变量）
// -----------------------------
preserve
keep if !missing(is_criminal) & !missing(contract_invalid)
contract is_criminal contract_invalid, freq(N)
label define is_cr 0 "civil/commercial" 1 "criminal", replace
label values is_criminal is_cr
export excel using "`TABLEDIR'/tab_cross_criminal_civil_contract_invalid.xlsx", firstrow(variables) replace
restore

preserve
if `HAS_REGEX_DV' {
	keep if !missing(is_criminal) & !missing(contract_invalid_regex)
	contract is_criminal contract_invalid_regex, freq(N)
	label values is_criminal is_cr
	export excel using "`TABLEDIR'/tab_cross_criminal_civil_contract_invalid_regex.xlsx", firstrow(variables) replace
}
restore

// -----------------------------
// 3) 回归程序：单调加控制 + 交互项
// -----------------------------
capture program drop run_incremental_block
program define run_incremental_block
	syntax , DV(name) PREFIX(string) [SAMPLE(string)]

	local cond "!missing(`dv')"
	if "`sample'" != "" local cond "`cond' & (`sample')"

	quietly count if `cond'
	if r(N) < 80 {
		di as err "跳过 `prefix'：样本过小，N=" r(N)
		exit
	}

	local cluster "$CLUSTER_USED"
	local base_ctrl "i.court_level_id i.procedure_stage_id i.judgment_year i.doc_type_id i.is_appeal_b i.is_appeal_miss"
	local base_act_id = $BASE_ACTIVITY_USED

	local model_list ""
	// esttab 会在内部给模型名加前缀 "_est_"，因此这里把内部存储名压短（<=27）
	local pfx_short = substr("`prefix'", 1, 12)
	local fitopt "vce(cluster `cluster') iterate(50)"

	quietly count if `cond' & is_criminal==1
	local n_cr = r(N)
	quietly count if `cond' & is_criminal==0
	local n_cv = r(N)
	local has_both_type = (`n_cr' > 0 & `n_cv' > 0)

	// 分组样本内若没有全局基准组，则回退到该样本最小ID，避免基准组缺失导致估计异常
	local act_term "i.activity_type_main_id"
	quietly count if `cond' & activity_type_main_id==`base_act_id'
	if r(N) > 0 {
		local act_term "ib`base_act_id'.activity_type_main_id"
	}
	else {
		quietly levelsof activity_type_main_id if `cond', local(__lv_act)
		local __fallback : word 1 of `__lv_act'
		local act_term "ib`__fallback'.activity_type_main_id"
	}

	// M0: 基准模型（不含高维案由 FE）
	capture noisily logit `dv' c.ln_amt_main i.amt_main_miss if `cond', `fitopt'
	if _rc capture noisily logit `dv' c.ln_amt_main i.amt_main_miss if `cond', `fitopt' technique(nr)
	if _rc capture noisily logit `dv' c.ln_amt_main i.amt_main_miss if `cond', `fitopt' technique(bhhh)
	if !_rc {
		estimates store `pfx_short'_m0
		local model_list "`model_list' `pfx_short'_m0"
	}

	// M1: 仅 activity_type
	capture noisily logit `dv' `act_term' if `cond', `fitopt'
	if _rc capture noisily logit `dv' `act_term' if `cond', `fitopt' technique(nr)
	if _rc capture noisily logit `dv' `act_term' if `cond', `fitopt' technique(bhhh)
	if !_rc {
		estimates store `pfx_short'_m1
		local model_list "`model_list' `pfx_short'_m1"
	}

	// M2: + 法院层级
	capture noisily logit `dv' `act_term' i.court_level_id if `cond', `fitopt'
	if _rc capture noisily logit `dv' `act_term' i.court_level_id if `cond', `fitopt' technique(nr)
	if _rc capture noisily logit `dv' `act_term' i.court_level_id if `cond', `fitopt' technique(bhhh)
	if !_rc {
		estimates store `pfx_short'_m2
		local model_list "`model_list' `pfx_short'_m2"
	}

	// M3: + 其余基础控制（不含金额）
	capture noisily logit `dv' `act_term' `base_ctrl' if `cond', `fitopt'
	if _rc capture noisily logit `dv' `act_term' `base_ctrl' if `cond', `fitopt' technique(nr)
	if _rc capture noisily logit `dv' `act_term' `base_ctrl' if `cond', `fitopt' technique(bhhh)
	if !_rc {
		estimates store `pfx_short'_m3
		local model_list "`model_list' `pfx_short'_m3"
	}

	// M4a/M4b/M4c: 依次轮询金额控制（均值/中位/最大）
	capture noisily logit `dv' `act_term' `base_ctrl' ///
		c.ln_amt_main i.amt_main_miss if `cond', `fitopt'
	if _rc capture noisily logit `dv' `act_term' `base_ctrl' ///
		c.ln_amt_main i.amt_main_miss if `cond', `fitopt' technique(nr)
	if _rc capture noisily logit `dv' `act_term' `base_ctrl' ///
		c.ln_amt_main i.amt_main_miss if `cond', `fitopt' technique(bhhh)
	if !_rc {
		estimates store `pfx_short'_m4mean
		local model_list "`model_list' `pfx_short'_m4mean"
	}

	capture noisily logit `dv' `act_term' `base_ctrl' ///
		c.ln_amt_median i.amt_median_miss if `cond', `fitopt'
	if _rc capture noisily logit `dv' `act_term' `base_ctrl' ///
		c.ln_amt_median i.amt_median_miss if `cond', `fitopt' technique(nr)
	if _rc capture noisily logit `dv' `act_term' `base_ctrl' ///
		c.ln_amt_median i.amt_median_miss if `cond', `fitopt' technique(bhhh)
	if !_rc {
		estimates store `pfx_short'_m4med
		local model_list "`model_list' `pfx_short'_m4med"
	}

	capture noisily logit `dv' `act_term' `base_ctrl' ///
		c.ln_amt_max i.amt_max_miss if `cond', `fitopt'
	if _rc capture noisily logit `dv' `act_term' `base_ctrl' ///
		c.ln_amt_max i.amt_max_miss if `cond', `fitopt' technique(nr)
	if _rc capture noisily logit `dv' `act_term' `base_ctrl' ///
		c.ln_amt_max i.amt_max_miss if `cond', `fitopt' technique(bhhh)
	if !_rc {
		estimates store `pfx_short'_m4max
		local model_list "`model_list' `pfx_short'_m4max"
	}

	// M5: 不含高维交互，仅主效应
	if `has_both_type' {
		capture noisily logit `dv' `act_term' i.is_criminal `base_ctrl' ///
			c.ln_amt_main i.amt_main_miss if `cond' & !missing(is_criminal), `fitopt'
		if _rc capture noisily logit `dv' `act_term' i.is_criminal `base_ctrl' ///
			c.ln_amt_main i.amt_main_miss if `cond' & !missing(is_criminal), `fitopt' technique(nr)
		if _rc capture noisily logit `dv' `act_term' i.is_criminal `base_ctrl' ///
			c.ln_amt_main i.amt_main_miss if `cond' & !missing(is_criminal), `fitopt' technique(bhhh)
		if !_rc {
			estimates store `pfx_short'_m5ni
			local model_list "`model_list' `pfx_short'_m5ni"
		}
	}

	// M6: 仅保留“刑/民 × 金额”交互（降阶，避免 i.is_criminal##i.activity_type_main_id）
	if `has_both_type' {
		capture noisily logit `dv' `act_term' i.is_criminal##c.ln_amt_main `base_ctrl' ///
			i.amt_main_miss if `cond' & !missing(is_criminal), `fitopt'
		if _rc capture noisily logit `dv' `act_term' i.is_criminal##c.ln_amt_main `base_ctrl' ///
			i.amt_main_miss if `cond' & !missing(is_criminal), `fitopt' technique(nr)
		if _rc capture noisily logit `dv' `act_term' i.is_criminal##c.ln_amt_main `base_ctrl' ///
			i.amt_main_miss if `cond' & !missing(is_criminal), `fitopt' technique(bhhh)
		if !_rc {
			estimates store `pfx_short'_m6ai
			local model_list "`model_list' `pfx_short'_m6ai"
		}
	}

	// 导出
	if "`model_list'" != "" {
		if $HAVE_ESTTAB == 1 {
			capture noisily esttab `model_list' using "$TABLEDIR_USED/reg_`prefix'.rtf", ///
				replace rtf se star(* 0.10 ** 0.05 *** 0.01) ///
				b(%9.3f) se(%9.3f) ///
				mtitles("M0-base" "M1-causeOnly" "M2+court" "M3+baseCtrl" "M4-case_amount" "M4-median" "M4-max" "M5-noInter" "M6-amtInter") ///
				addnotes("DV=`dv'", "cluster=`cluster'", "主金额变量=case_amount（大模型抽取）", "低频 activity_type 已合并：N<20 => 其他(稀疏)", "logit 估计设置：iterate(50)+算法回退(nr/bhhh)")
		}
		estimates save "$DATADIR_USED/reg_`prefix'.ster", replace
	}
end

// 全局传参给 program（Stata program 内不直接读取 local）
global CLUSTER_USED "`CLUSTER_ID'"
global HAVE_ESTTAB `HAVE_ESTTAB'
global TABLEDIR_USED "`TABLEDIR'"
global DATADIR_USED "`DATADIR'"
global BASE_ACTIVITY_USED `BASE_ACTIVITY_ID'

// -----------------------------
// 4) 分组回归优先：刑事组 / 民事组
// -----------------------------
run_incremental_block, dv(contract_invalid)       prefix(criminal_contract_invalid) sample("is_criminal==1")
run_incremental_block, dv(contract_invalid)       prefix(civil_contract_invalid)    sample("is_criminal==0")
if `HAS_REGEX_DV' run_incremental_block, dv(contract_invalid_regex) prefix(criminal_contract_invalid_regex) sample("is_criminal==1")
if `HAS_REGEX_DV' run_incremental_block, dv(contract_invalid_regex) prefix(civil_contract_invalid_regex)    sample("is_criminal==0")

// -----------------------------
// 5) 全样本主回归 + 稳健性回归
// -----------------------------
run_incremental_block, dv(contract_invalid)       prefix(main_contract_invalid)
if `HAS_REGEX_DV' run_incremental_block, dv(contract_invalid_regex) prefix(robust_contract_invalid_regex)

di as txt "完成：增量控制回归、交互项模型、稳健性与分组回归已输出。"
di as txt "输出目录：`TABLEDIR' 与 `DATADIR'"
log close
