from __future__ import annotations

from pathlib import Path
import runpy

import pandas as pd
import numpy as np


ROOT = Path.cwd()
ROUND12 = ROOT / "newstudy" / "result" / "round-12-20260518-top-journal-deepening"
OUT = ROUND12 / "tables" / "wald_transaction_tests.csv"


def main() -> None:
    ns = runpy.run_path(str(ROOT / "newstudy" / "code" / "round-12-20260518-top-journal-deepening" / "round12_top_journal_analysis.py"))
    prep_data = ns["prep_data"]
    run_models = ns["run_models"]

    full = pd.read_csv(ROOT / "newstudy" / "result" / "round-11-20260517-dsv4-reanalysis" / "paper_analysis_dataset.csv")
    civil = pd.read_csv(ROOT / "newstudy" / "result" / "round-11-20260517-dsv4-reanalysis" / "civil_main_sample.csv")
    _, civil, _ = prep_data(full, civil)
    results = run_models(civil)
    res = results["results"]["m06_policy_by_transaction"]

    param_names = list(res.params.index)
    interaction_terms = [name for name in param_names if name.startswith("post2021:C(transaction_code")]

    rows = []
    if interaction_terms:
        R = []
        for term in interaction_terms:
            row = [0.0] * len(param_names)
            row[param_names.index(term)] = 1.0
            R.append(row)
        test = res.f_test(R)
        rows.append(
            {
                "test_name": "joint_interaction_terms_zero",
                "hypothesis": "all post2021:transaction_code interaction terms equal 0",
                "statistic": float(np.asarray(test.fvalue).squeeze()),
                "df_num": float(np.asarray(test.df_num).squeeze()),
                "df_denom": float(np.asarray(test.df_denom).squeeze()),
                "p_value": float(np.asarray(test.pvalue).squeeze()),
                "note": "Wald test on heterogeneity in transaction effects",
            }
        )

    def interaction_name(group: str) -> str | None:
        if group == "Lending":
            return None
        suffix = f"[T.{group}]"
        matches = [name for name in interaction_terms if name.endswith(suffix)]
        return matches[0] if matches else None

    def effect_vector(group: str) -> dict[str, float]:
        terms = {"post2021": 1.0}
        term = interaction_name(group)
        if term:
            terms[term] = 1.0
        return terms

    pair_specs = [
        ("Mining", "Trading"),
        ("Mining", "Investment"),
        ("Trading", "Investment"),
        ("ICO", "Mining"),
        ("ICO", "Trading"),
        ("TechService", "Lending"),
    ]

    def build_row(diff_terms: dict[str, float]) -> list[float]:
        row = [0.0] * len(param_names)
        for term, coef in diff_terms.items():
            row[param_names.index(term)] = coef
        return row

    for g1, g2 in pair_specs:
        diff = effect_vector(g1)
        for term, coef in effect_vector(g2).items():
            diff[term] = diff.get(term, 0.0) - coef
        row = build_row(diff)
        test = res.f_test([row])
        rows.append(
            {
                "test_name": f"{g1}_vs_{g2}",
                "hypothesis": f"post2021 effect {g1} equals {g2}",
                "statistic": float(np.asarray(test.fvalue).squeeze()),
                "df_num": float(np.asarray(test.df_num).squeeze()),
                "df_denom": float(np.asarray(test.df_denom).squeeze()),
                "p_value": float(np.asarray(test.pvalue).squeeze()),
                "note": "pairwise Wald comparison of implied treatment effects",
            }
        )

    pd.DataFrame(rows).to_csv(OUT, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
