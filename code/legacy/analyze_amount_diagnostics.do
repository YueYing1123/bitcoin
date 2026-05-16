version 19
clear all
set more off
set linesize 255

// ============================================================
//  Diagnose: 金额变量为何在回归中被 omitted
//  重点检查：total_amount_cny 是否几乎全缺失/全为0/在回归样本中无变异
//
//  Run:
//    cd "D:\BaiduSyncdisk\Doctor\论文\数字货币\数据构建"
//    do analyze_amount_diagnostics.do
// ============================================================

local ROOT "`c(pwd)'"
local OUTDIR "`ROOT'/analyze/diagnostics"
cap mkdir "`ROOT'/analyze"
cap mkdir "`OUTDIR'"

log close _all
log using "`OUTDIR'/amount_diagnostics.log", replace text

di as txt "============================================================"
di as txt "金额变量诊断启动"
di as txt "工作目录: `ROOT'"
di as txt "输出目录: `OUTDIR'"
di as txt "============================================================"

// ---------------------------------
// 1) 载入数据（优先 dta，次选 CSV）
// ---------------------------------
local DTA "`ROOT'/analyze/data/final_all_flat.dta"
local CSV "`ROOT'/analyze/data/final_all_flat.csv"

cap confirm file "`DTA'"
if !_rc {
	use "`DTA'", clear
}
else {
	cap confirm file "`CSV'"
	if _rc {
		di as err "找不到扁平化数据：`DTA' 或 `CSV' 均不存在。请先运行 analyze_all.do"
		error 601
	}
	import delimited using "`CSV'", clear varnames(1) encoding(UTF-8) stringcols(_all)
}
compress

// ---------------------------------
// 2) 确保核心变量存在 & 清洗
// ---------------------------------
foreach v in total_amount_cny contract_validity judgment_date {
	cap confirm variable `v'
	if _rc {
		di as err "缺少变量 `v'，请检查 docs/fields.yaml 是否包含并成功扁平化"
	}
}

// 统一 "null" 字符串
foreach v of varlist _all {
	capture confirm string variable `v'
	if !_rc replace `v' = "" if lower(trim(`v')) == "null"
}

capture destring total_amount_cny, replace ignore(" ,")

// judgment_year（尽量从 judgment_date 推断）
capture confirm variable judgment_year
if _rc {
	gen double judgment_date_d = daily(judgment_date, "YMD")
	format judgment_date_d %td
	gen int judgment_year = year(judgment_date_d)
}

// contract_invalid（若主脚本没生成，则按主逻辑重建）
capture confirm variable contract_invalid
if _rc {
	gen byte contract_invalid = .
	replace contract_invalid = 1 if regexm(trim(contract_validity), "无效|未成立")
	replace contract_invalid = 0 if contract_invalid==. & regexm(trim(contract_validity), "有效")
}

// ln_amount（与主脚本一致）
capture confirm variable ln_amount
if _rc gen double ln_amount = ln(total_amount_cny + 1) if !missing(total_amount_cny)
gen byte ln_amount_miss = missing(ln_amount)

// ---------------------------------
// 3) 总体诊断（是否全缺失/全为0/是否有正值）
// ---------------------------------
quietly count
local N_ALL = r(N)
quietly count if missing(total_amount_cny)
local N_AMT_MISS = r(N)
quietly count if !missing(total_amount_cny)
local N_AMT_NONMISS = r(N)
quietly count if total_amount_cny==0
local N_AMT_ZERO = r(N)
// 注意：Stata 中缺失值在比较运算里会被当成“非常大”，所以必须显式排除 missing
quietly count if total_amount_cny>0 & !missing(total_amount_cny)
local N_AMT_POS = r(N)

di as txt "---- 总体样本量 ----"
di as txt "N_ALL=" `N_ALL'
di as txt "---- 金额变量 ----"
di as txt "total_amount_cny 缺失: " `N_AMT_MISS' " (" %6.2f (100*`N_AMT_MISS'/`N_ALL') "%)"
di as txt "total_amount_cny 非缺失: " `N_AMT_NONMISS'
di as txt "total_amount_cny = 0: " `N_AMT_ZERO'
di as txt "total_amount_cny > 0: " `N_AMT_POS'

di as txt "---- total_amount_cny 描述统计（仅 >0）----"
summarize total_amount_cny if total_amount_cny>0, detail
// 修正：排除 missing（否则会出现“no observations”/统计错乱）
summarize total_amount_cny if total_amount_cny>0 & !missing(total_amount_cny), detail

di as txt "---- ln_amount/ln_amount_miss 变异性检查 ----"
summarize ln_amount if !missing(ln_amount)
tab ln_amount_miss, missing

// ---------------------------------
// 4) 按 contract_invalid 分组诊断
// ---------------------------------
di as txt "---- 按 contract_invalid 分组：金额缺失/正值情况 ----"
tab contract_invalid, missing
by contract_invalid, sort: summarize total_amount_cny if total_amount_cny>0 & !missing(total_amount_cny)
by contract_invalid, sort: tab ln_amount_miss, missing

// ---------------------------------
// 5) 模拟回归样本与回归前处理，判断为何 omitted
//    回归样本：keep if !missing(contract_invalid)
//    主脚本处理：ln_amount 缺失 -> 0；并加入 ln_amount_miss 指示
// ---------------------------------
preserve
keep if !missing(contract_invalid)
quietly count
local N_REG0 = r(N)

gen double ln_amount_reg = ln_amount
gen byte ln_amount_miss_reg = missing(ln_amount_reg)
replace ln_amount_reg = 0 if missing(ln_amount_reg)

di as txt "---- 回归样本（仅 contract_invalid 非缺失）----"
di as txt "N_REG0=" `N_REG0'
tab ln_amount_miss_reg, missing
summarize ln_amount_reg
quietly summarize ln_amount_reg
di as txt "ln_amount_reg 的最小/最大: " r(min) " / " r(max)

// 判断是否“常数”
quietly summarize ln_amount_reg
if r(min)==r(max) {
	di as err "诊断结论：ln_amount 在回归样本中为常数（无变异），必然会被 omitted。"
}
quietly tab ln_amount_miss_reg
if r(r)==1 {
	di as err "诊断结论：ln_amount_miss 在回归样本中也为常数（全缺失或全非缺失），会被 omitted。"
}
restore

// 直接用 putexcel 写 summary（避免数据来回切换）
local XLS "`OUTDIR'/amount_diagnostics.xlsx"
cap erase "`XLS'"
putexcel set "`XLS'", replace sheet("summary")
putexcel A1=("总体诊断"), bold
putexcel A2=("N_ALL") B2=(`N_ALL')
putexcel A3=("total_amount_cny_missing") B3=(`N_AMT_MISS')
putexcel A4=("total_amount_cny_nonmissing") B4=(`N_AMT_NONMISS')
putexcel A5=("total_amount_cny_zero") B5=(`N_AMT_ZERO')
putexcel A6=("total_amount_cny_positive") B6=(`N_AMT_POS')

putexcel A8=("回归样本诊断（contract_invalid 非缺失）"), bold
putexcel A9=("N_reg") B9=(`N_REG0')

// 抽取若干“金额非缺失”的样本行，便于检查扁平化是否成功
preserve
keep if !missing(total_amount_cny)
quietly count
if r(N)==0 {
	restore
	di as err "top_amount_cases 跳过：total_amount_cny 全部缺失，无法导出样本行。"
	putexcel A11=("top_amount_cases 跳过：total_amount_cny 全缺失"), bold
}
else {
gsort -total_amount_cny
keep in 1/30
keep doc_id judgment_date contract_validity total_amount_cny activity_type court_level court_name region
export excel using "`XLS'", sheet("top_amount_cases") firstrow(variables) sheetreplace
restore
}

// 画一个金额分布图（仅正值）
capture noisily histogram total_amount_cny if total_amount_cny>0 & !missing(total_amount_cny), bin(50) ///
	title("total_amount_cny 分布（>0）") xtitle("CNY") ytitle("频数")
if !_rc {
	graph export "`OUTDIR'/hist_total_amount_cny.png", replace width(2400)
}

log close
di as txt "完成。请查看：`OUTDIR'/amount_diagnostics.log 与 amount_diagnostics.xlsx"

