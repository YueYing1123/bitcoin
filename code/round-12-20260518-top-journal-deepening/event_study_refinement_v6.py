from __future__ import annotations

from pathlib import Path
import runpy

import pandas as pd


ROOT = Path.cwd()
ROUND_DIR = ROOT / "newstudy" / "result" / "round-12-20260518-top-journal-deepening"
TABLE_DIR = ROUND_DIR / "tables"


def main() -> None:
    ns = runpy.run_path(str(ROOT / "newstudy" / "code" / "round-12-20260518-top-journal-deepening" / "round12_top_journal_analysis.py"))
    prep_data = ns["prep_data"]
    fit_lpm = ns["fit_lpm"]

    full = pd.read_csv(ROOT / "newstudy" / "result" / "round-11-20260517-dsv4-reanalysis" / "paper_analysis_dataset.csv")
    civil = pd.read_csv(ROOT / "newstudy" / "result" / "round-11-20260517-dsv4-reanalysis" / "civil_main_sample.csv")
    _, civil, _ = prep_data(full, civil)

    controls_full = "amount_log + amount_llm_regex_conflict_flag + C(court_level_code) + C(cause_code) + C(transaction_code, Treatment(reference='Lending')) + C(region_macro_code)"

    years = sorted(int(x) for x in civil["year"].dropna().unique())

    # Full-window descriptive event study relative to 2020.
    event_data = civil.copy()
    event_terms = []
    for y in years:
        if y == 2020:
            continue
        col = f"year_{y}"
        event_data[col] = event_data["year"].eq(y).astype(int)
        event_terms.append(col)
    event_formula = f"contract_invalid ~ {' + '.join(event_terms)} + {controls_full}"
    event_res, _, event_all = fit_lpm(
        event_formula,
        event_data,
        "event_study_2020_base",
        "事件研究；2020年为省略基准年。",
    )
    event_all = event_all[event_all["term"].astype(str).str.startswith("year_") | event_all["term"].eq("base_2020")].copy()
    event_all["year"] = event_all["term"].map(lambda t: 2020 if t == "base_2020" else int(str(t).split("_")[1]))
    event_all = event_all.sort_values("year")
    event_all.to_csv(TABLE_DIR / "event_study_2020_base.csv", index=False, encoding="utf-8-sig")

    pre_terms_full = [f"year_{y} = 0" for y in years if y < 2020]
    pretest_full = event_res.f_test(", ".join(pre_terms_full))

    # Short-window event study from 2017 onward.
    short_years = [y for y in years if 2017 <= y <= 2024]
    short_data = civil.loc[civil["year"].between(2017, 2024)].copy()
    short_terms = []
    for y in short_years:
        if y == 2020:
            continue
        col = f"year_{y}"
        short_data[col] = short_data["year"].eq(y).astype(int)
        short_terms.append(col)
    short_formula = f"contract_invalid ~ {' + '.join(short_terms)} + {controls_full}"
    short_res, _, short_all = fit_lpm(
        short_formula,
        short_data,
        "event_study_2017_2024",
        "事件研究；2017年起的缩短窗口，2020年为省略基准年。",
    )
    short_all = short_all[short_all["term"].astype(str).str.startswith("year_") | short_all["term"].eq("base_2020")].copy()
    short_all["year"] = short_all["term"].map(lambda t: 2020 if t == "base_2020" else int(str(t).split("_")[1]))
    short_all = short_all.sort_values("year")
    short_all.to_csv(TABLE_DIR / "event_study_2017_2024.csv", index=False, encoding="utf-8-sig")

    pre_terms_short = [f"year_{y} = 0" for y in short_years if y < 2020]
    pretest_short = short_res.f_test(", ".join(pre_terms_short))

    summary = pd.DataFrame(
        [
            {
                "spec": "full_window_2014_2024",
                "pre_years": "2014-2019",
                "f_stat": float(pretest_full.fvalue),
                "p_value": float(pretest_full.pvalue),
                "df_denom": float(pretest_full.df_denom),
                "df_num": float(pretest_full.df_num),
                "nobs": int(event_res.nobs),
                "note": "2020 omitted base year; joint pretrend F-test.",
            },
            {
                "spec": "short_window_2017_2024",
                "pre_years": "2017-2019",
                "f_stat": float(pretest_short.fvalue),
                "p_value": float(pretest_short.pvalue),
                "df_denom": float(pretest_short.df_denom),
                "df_num": float(pretest_short.df_num),
                "nobs": int(short_res.nobs),
                "note": "2020 omitted base year; joint pretrend F-test.",
            },
        ]
    )
    summary.to_csv(TABLE_DIR / "event_study_pretrend_tests.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
