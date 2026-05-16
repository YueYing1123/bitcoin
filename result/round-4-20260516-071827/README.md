# Round 4 Spec Check Results

- Rows: 12,135; unique doc_id: 12,135.
- Contract-validity DV nonmissing: 5,714; invalid/non-fully-valid rate: 47.4%.
- Master amount nonmissing: 12,102; LLM amount nonmissing: 11,684; regex max amount nonmissing: 12,100.
- LLM amount appears in regex candidate list rate: 85.3%; conflict flag rate: 14.7%.
- Region mapped: 12,103 (99.7%).

## Key Coefficients
- Baseline LPM log(master amount): coef=0.0025, p=0.4291, n=5,709.
- Region Big4 LPM: coef=-0.0824, p=1.485e-09, n=5,696.
- Amount alignment OLS log(regex max): coef=0.5664, p=0, n=11,680.

## Outputs
- `descriptive_tables.xlsx`: core descriptive tables.
- `regression_results_full.csv`: all regression terms.
- `regression_key_terms.csv`: main terms for interpretation.
- `region_mapping_audit.csv`: court/case-number region mapping audit.
- `analysis_dataset_derived.csv`: derived variables for subsequent exploration.
- `spec_summary.json`: machine-readable summary.