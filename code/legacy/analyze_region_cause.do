version 19
clear all
set more off
set linesize 255

// ============================================================
//  Descriptive: 地域分布 & 案由分布关系
//  Input : analyze/data/final_all_flat.dta (preferred) or .csv
//  Output: analyze/region_cause/ (tables, figures, logs)
//
//  Run:
//    cd "D:\BaiduSyncdisk\Doctor\论文\数字货币\数据构建"
//    do analyze_region_cause.do
// ============================================================

local ROOT "`c(pwd)'"
local OUTDIR "`ROOT'/analyze/region_cause"
local TABLEDIR "`OUTDIR'/tables"
local FIGDIR "`OUTDIR'/figures"
local LOGDIR "`OUTDIR'/logs"

cap mkdir "`ROOT'/analyze"
cap mkdir "`OUTDIR'"
cap mkdir "`TABLEDIR'"
cap mkdir "`FIGDIR'"
cap mkdir "`LOGDIR'"

log close _all
log using "`LOGDIR'/region_cause.log", replace text

di as txt "============================================================"
di as txt "地域分布 × 案由分布：描述性分析"
di as txt "工作目录: `ROOT'"
di as txt "输出目录: `OUTDIR'"
di as txt "============================================================"

// ---------------------------------
// 1) 载入数据
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

// 统一 "null" 字符串为空
foreach v of varlist _all {
	capture confirm string variable `v'
	if !_rc replace `v' = "" if lower(trim(`v')) == "null"
}

// ---------------------------------
// 2) 构造“地域变量” region_final
//    - 优先用字段 region（如果有）
//    - 若缺失：从案号 case_number 提取省份简称（如 浙/京/粤/...）
// ---------------------------------
gen str20 region_final = ""
capture confirm string variable region
if !_rc replace region_final = trim(region) if trim(region)!=""

// 从案号提取省份简称（常见格式：（2020）浙0203... 或 (2018)苏0106...）
gen str1 prov_abbr = ""
capture confirm string variable case_number
if !_rc {
	replace prov_abbr = ustrregexs(1) if ustrregexm(case_number, "[\\)）]([京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼])")
}

gen str20 province = ""
replace province = "北京" if prov_abbr=="京"
replace province = "天津" if prov_abbr=="津"
replace province = "上海" if prov_abbr=="沪"
replace province = "重庆" if prov_abbr=="渝"
replace province = "河北" if prov_abbr=="冀"
replace province = "河南" if prov_abbr=="豫"
replace province = "云南" if prov_abbr=="云"
replace province = "辽宁" if prov_abbr=="辽"
replace province = "黑龙江" if prov_abbr=="黑"
replace province = "湖南" if prov_abbr=="湘"
replace province = "安徽" if prov_abbr=="皖"
replace province = "山东" if prov_abbr=="鲁"
replace province = "新疆" if prov_abbr=="新"
replace province = "江苏" if prov_abbr=="苏"
replace province = "浙江" if prov_abbr=="浙"
replace province = "江西" if prov_abbr=="赣"
replace province = "湖北" if prov_abbr=="鄂"
replace province = "广西" if prov_abbr=="桂"
replace province = "甘肃" if prov_abbr=="甘"
replace province = "山西" if prov_abbr=="晋"
replace province = "内蒙古" if prov_abbr=="蒙"
replace province = "陕西" if prov_abbr=="陕"
replace province = "吉林" if prov_abbr=="吉"
replace province = "福建" if prov_abbr=="闽"
replace province = "贵州" if prov_abbr=="贵"
replace province = "广东" if prov_abbr=="粤"
replace province = "青海" if prov_abbr=="青"
replace province = "西藏" if prov_abbr=="藏"
replace province = "四川" if prov_abbr=="川"
replace province = "宁夏" if prov_abbr=="宁"
replace province = "海南" if prov_abbr=="琼"

replace region_final = province if region_final=="" & province!=""
replace region_final = "未知" if region_final==""

di as txt "---- 地域变量覆盖率（region_final）----"
quietly count
di as txt "N=" r(N)
tab region_final, missing

// ---------------------------------
// 3) 构造“案由/纠纷类型” cause_main
//    - 优先 legal_characterization（通常更丰富）
//    - 否则用 case_type_primary
// ---------------------------------
gen str80 cause_main = ""
capture confirm string variable legal_characterization
if !_rc replace cause_main = trim(legal_characterization) if trim(legal_characterization)!=""
capture confirm string variable case_type_primary
if !_rc replace cause_main = trim(case_type_primary) if cause_main=="" & trim(case_type_primary)!=""
replace cause_main = "未知" if cause_main==""

// 生成“案由分组”：取全样本 Top10，其余并为“其他”
preserve
keep cause_main
gen byte one = 1
collapse (sum) N=one, by(cause_main)
gsort -N
gen int rank = _n
tempfile topcauses
keep if rank<=10
save "`topcauses'", replace
restore

gen str80 cause_group = "其他"
merge m:1 cause_main using "`topcauses'", keep(match master) nogen
replace cause_group = cause_main if !missing(N)

// ---------------------------------
// 4) 表格输出（Excel）
// ---------------------------------
di as txt "开始输出表格..."

// 表1：地域分布（Top20）
preserve
gen byte one = 1
collapse (sum) N=one, by(region_final)
gsort -N
gen double share = N/sum(N)
keep in 1/20
export excel using "`TABLEDIR'/tab_region_top20.xlsx", firstrow(variables) replace
restore

// 表2：案由分布（Top20）
preserve
gen byte one = 1
collapse (sum) N=one, by(cause_main)
gsort -N
keep in 1/20
export excel using "`TABLEDIR'/tab_cause_top20.xlsx", firstrow(variables) replace
restore

// 表3：地域 × 案由分组（Top10 地域；行内份额）
preserve
gen byte one = 1
collapse (sum) N=one, by(region_final cause_group)

// 取地域 Top10
bys region_final: egen total_r = total(N)
gsort -total_r
egen byte tag = tag(region_final)
keep if tag
keep region_final total_r
gsort -total_r
keep in 1/10
tempfile topregions
save "`topregions'", replace
restore

preserve
gen byte one = 1
collapse (sum) N=one, by(region_final cause_group)
merge m:1 region_final using "`topregions'", keep(match) nogen
bys region_final: egen total = total(N)
gen double share = N/total
sort region_final -N
export excel using "`TABLEDIR'/tab_region_by_causegroup_top10.xlsx", firstrow(variables) replace
restore

// 卡方检验（地域×案由分组）
preserve
keep if region_final!="未知"
tab region_final cause_group, chi2 row
restore

// ---------------------------------
// 5) 图片输出（PNG）
// ---------------------------------
di as txt "开始输出图片..."

// 图1：地域 Top20（水平条形）
preserve
gen byte one = 1
collapse (sum) N=one, by(region_final)
gsort -N
keep in 1/20
graph hbar N, over(region_final, sort(1) descending label(labsize(small))) ///
	title("地域分布 Top20") ytitle("案件数")
graph export "`FIGDIR'/fig_region_top20.png", replace width(2400)
restore

// 图2：案由 Top20（水平条形）
preserve
gen byte one = 1
collapse (sum) N=one, by(cause_main)
gsort -N
keep in 1/20
graph hbar N, over(cause_main, sort(1) descending label(labsize(vsmall))) ///
	title("案由/法律定性 Top20") ytitle("案件数")
graph export "`FIGDIR'/fig_cause_top20.png", replace width(2400)
restore

// 图3：地域 × 案由分组 热力图（Top10 地域；色阶=地域内份额）
di as txt "开始输出热力图（地域×案由分组）..."
preserve
gen byte one = 1
collapse (sum) N=one, by(region_final cause_group)

// 仅保留地域 Top10（复用前面生成的 topregions）
merge m:1 region_final using "`topregions'", keep(match) nogen

// 地域内份额（0-100）
bys region_final: egen total = total(N)
gen double share_pct = 100*N/total

// 编码为数值轴（便于画热力图）
encode region_final, gen(rid)
encode cause_group, gen(cid)

// 优先使用 heatplot（若未安装则尝试安装）
local HAVE_HEATPLOT = 0
cap which heatplot
if _rc {
	capture noisily ssc install heatplot, replace
	cap which heatplot
}
if !_rc local HAVE_HEATPLOT = 1

local USED_HEATPLOT = 0
if `HAVE_HEATPLOT' {
	// heatplot 常见依赖：palettes / colrspace
	capture noisily ssc install palettes, replace
	capture noisily ssc install colrspace, replace

	capture noisily heatplot share_pct rid cid, ///
		xlabel(, valuelabel angle(45) labsize(small)) ///
		ylabel(, valuelabel angle(0) labsize(small)) ///
		title("地域×案由分组 热力图（Top10 地域；色阶=地域内份额%）") ///
		legend(title("份额(%)")) ///
		aspect(0.7)
	if !_rc {
		graph export "`FIGDIR'/fig_region_cause_heatmap_top10.png", replace width(2600)
		local USED_HEATPLOT = 1
	}
}

if `USED_HEATPLOT'==0 {
	// 备用：分箱“方块散点图”模拟热力图（无需额外包）
	xtile bin = share_pct, nq(5)
	label define bin 1 "最低" 2 "较低" 3 "中等" 4 "较高" 5 "最高"
	label values bin bin

	twoway ///
		(scatter rid cid if bin==1, msymbol(square) msize(large) mcolor(gs15)) ///
		(scatter rid cid if bin==2, msymbol(square) msize(large) mcolor(gs12)) ///
		(scatter rid cid if bin==3, msymbol(square) msize(large) mcolor(gs9)) ///
		(scatter rid cid if bin==4, msymbol(square) msize(large) mcolor(gs6)) ///
		(scatter rid cid if bin==5, msymbol(square) msize(large) mcolor(gs3)) ///
		, ///
		xlabel(, valuelabel angle(45) labsize(small)) ///
		ylabel(, valuelabel angle(0) labsize(small)) ///
		xtitle("案由分组") ytitle("地域") ///
		title("地域×案由分组 热力图（Top10 地域；分位数色阶）") ///
		legend(order(1 "最低" 2 "较低" 3 "中等" 4 "较高" 5 "最高") rows(1))
	graph export "`FIGDIR'/fig_region_cause_heatmap_top10.png", replace width(2600)
}
restore

// 图4：地域（Top8）内的案由分组份额（小多图）
preserve
gen byte one = 1
collapse (sum) N=one, by(region_final cause_group)
bys region_final: egen total_r = total(N)
gsort -total_r
egen byte tag = tag(region_final)
keep if tag
keep region_final total_r
gsort -total_r
keep in 1/8
tempfile topregions8
save "`topregions8'", replace
restore

preserve
gen byte one = 1
collapse (sum) N=one, by(region_final cause_group)
merge m:1 region_final using "`topregions8'", keep(match) nogen
bys region_final: egen total = total(N)
gen double share = N/total
graph bar share, over(cause_group, sort(1) descending label(angle(30) labsize(small))) ///
	by(region_final, col(2) note("") title("地域内案由分组份额（Top8 地域）")) ///
	ytitle("份额") ylabel(0(0.2)1, format(%3.1f))
graph export "`FIGDIR'/fig_region_causegroup_share_top8.png", replace width(2600)
restore

di as txt "============================================================"
di as txt "完成：请查看 analyze/region_cause/ 下 tables/figures/logs"
di as txt "============================================================"

log close

