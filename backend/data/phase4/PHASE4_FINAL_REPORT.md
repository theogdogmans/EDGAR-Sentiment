# Phase 4 — Final Full-Data Analysis

Generated: 2026-08-22T04:24:01.533028+00:00

## A. Dataset checkpoint

- Integrity: `ok` (backup `ok`)
- Backup: `C:\Users\joshp\edgar-sentiment\backend\data\final\edgar_phase3_final.db` (3058.71 MB)
- Analyses: **9697**
- Filings attempted (quality_log): **9787**
- Unique registrants (CIKs with filings): **499**
- S&P 500 ticker rows: **502**

## B. Coverage

- Sentiment scored: {'attempted': 9787, 'scored': 9697, 'revenue_ok': 7442, 'ni_ok': 8656, 'mda_extractions_ok': 9697, 'quality_log_rows': 9787, 'coverage': {'companies': 502, 'with_filings': 499, 'filings': 9787, 'analyzed': 9697, 'ready': 497}, 'revenue_block': {'filings_revenue_unavailable': 2255, 'reason_counts': {'unavailable': 278, 'sector_not_comparable_revenue': 1816, 'no_valid_prior_period': 55, 'no_fact_for_accession': 97, 'no_fact_near_report_date': 4, 'no_fact_in_duration_band': 5}, 'companies_touched_financials_real_estate': 106, 'non_comparable_sectors': ['Financials', 'Real Estate']}, 'top_failure_reasons': {'ok': 7105, 'rev:sector_not_comparable_revenue': 1797, 'ni:no_fact_for_accession': 515, 'rev:no_fact_for_accession': 97, 'ni:tag_absent': 60, 'rev:no_valid_prior_period': 55, 'already_failed_final: ValueError: Could not extract MD&A text from this filing': 46, 'stage=mda_extraction': 27, 'ni:no_valid_prior_period': 21, 'sector_not_comparable_revenue': 19, 'already_failed_final: ConnectError: [Errno 8] nodename nor servname provided, or not known': 17, 'ni:no_fact_in_duration_band': 8, 'no_fact_for_accession': 6, 'no_valid_prior_period': 5, 'rev:no_fact_in_duration_band': 5, 'rev:no_fact_near_report_date': 4}}
- Top failure reasons: see JSON

## C. Ranking eligibility (10-Q NI)

- n_ge_3: **462**
- n_ge_6: **452**
- n_ge_8: **440**
- n_ge_10: **428**
- n_ge_12: **420**

## D. FDR results (10-Q NI, ranking-eligible n≥6)

- Eligible: **452**
- Raw p < .05: **99**
- FDR q < .05: **33**
- FDR q < .01: **15**

### FDR survivors (q < .05)

| ticker | company | sector | n | r | 95% CI | p | q | ρ | Spearman p | agree |
|---|---|---|---:|---:|---|---:|---:|---:|---:|---|
| JBHT | J.B. Hunt | Industrials | 15 | 0.9462 | [0.8421, 0.9823] | 0.0000 | 0.0000 | 0.9036 | 0.0000 | 14 / 15 |
| ODFL | Old Dominion | Industrials | 14 | 0.9514 | [0.8497, 0.9848] | 0.0000 | 0.0000 | 0.8637 | 0.0001 | 6 / 10 |
| MCO | Moody's Corporation | Financials | 15 | 0.9242 | [0.7824, 0.9749] | 0.0000 | 0.0001 | 0.9107 | 0.0000 | 13 / 13 |
| MTD | Mettler Toledo | Health Care | 15 | 0.9082 | [0.7403, 0.9694] | 0.0000 | 0.0003 | 0.8750 | 0.0000 | 11 / 11 |
| TXN | Texas Instruments | Information Technology | 15 | 0.8972 | [0.7123, 0.9656] | 0.0000 | 0.0005 | 0.8321 | 0.0001 | 8 / 10 |
| MS | Morgan Stanley | Financials | 15 | 0.8896 | [0.6933, 0.9630] | 0.0000 | 0.0007 | 0.9071 | 0.0000 | 9 / 10 |
| BBY | Best Buy | Consumer Discretionary | 15 | 0.8716 | [0.6492, 0.9567] | 0.0000 | 0.0015 | 0.8679 | 0.0000 | 7 / 7 |
| EXPD | Expeditors International | Industrials | 15 | 0.8649 | [0.6332, 0.9543] | 0.0000 | 0.0016 | 0.7607 | 0.0010 | 5 / 8 |
| FAST | Fastenal | Industrials | 15 | 0.8656 | [0.6347, 0.9546] | 0.0000 | 0.0016 | 0.8393 | 0.0001 | 10 / 11 |
| STLD | Steel Dynamics | Materials | 10 | 0.9408 | [0.7633, 0.9862] | 0.0001 | 0.0023 | 0.8545 | 0.0016 | 7 / 8 |
| SCHW | Charles Schwab Corporation | Financials | 15 | 0.8467 | [0.5905, 0.9478] | 0.0001 | 0.0028 | 0.8071 | 0.0003 | 9 / 11 |
| CSX | CSX Corporation | Industrials | 15 | 0.8213 | [0.5334, 0.9386] | 0.0002 | 0.0066 | 0.7857 | 0.0005 | 7 / 8 |
| SHW | Sherwin-Williams | Materials | 15 | 0.8160 | [0.5219, 0.9367] | 0.0002 | 0.0072 | 0.8964 | 0.0000 | 10 / 10 |
| ETN | Eaton Corporation | Industrials | 15 | 0.8069 | [0.5023, 0.9334] | 0.0003 | 0.0089 | 0.8286 | 0.0001 | 10 / 14 |
| NVR | NVR, Inc. | Consumer Discretionary | 15 | 0.8048 | [0.4978, 0.9326] | 0.0003 | 0.0089 | 0.8643 | 0.0000 | 12 / 13 |
| URI | United Rentals | Industrials | 14 | 0.8169 | [0.5055, 0.9401] | 0.0004 | 0.0102 | 0.8681 | 0.0001 | 8 / 8 |
| DE | Deere & Company | Industrials | 15 | 0.7907 | [0.4680, 0.9273] | 0.0004 | 0.0116 | 0.8536 | 0.0001 | 9 / 9 |
| DHR | Danaher Corporation | Health Care | 15 | 0.7896 | [0.4657, 0.9269] | 0.0005 | 0.0116 | 0.7250 | 0.0022 | 10 / 12 |
| AAPL | Apple Inc. | Information Technology | 15 | 0.7661 | [0.4177, 0.9181] | 0.0009 | 0.0194 | 0.8536 | 0.0001 | 6 / 8 |
| ADI | Analog Devices | Information Technology | 15 | 0.7652 | [0.4161, 0.9177] | 0.0009 | 0.0194 | 0.7750 | 0.0007 | 8 / 8 |
| CASY | Casey's | Consumer Staples | 15 | 0.7645 | [0.4145, 0.9174] | 0.0009 | 0.0194 | 0.7071 | 0.0032 | 11 / 13 |
| BLDR | Builders FirstSource | Industrials | 15 | 0.7544 | [0.3946, 0.9136] | 0.0012 | 0.0237 | 0.7536 | 0.0012 | 13 / 13 |
| MLM | Martin Marietta Materials | Materials | 15 | -0.7498 | [-0.9118, -0.3857] | 0.0013 | 0.0253 | -0.2000 | 0.4748 | 5 / 7 |
| GRMN | Garmin | Consumer Discretionary | 14 | 0.7599 | [0.3843, 0.9197] | 0.0016 | 0.0298 | 0.7363 | 0.0027 | 4 / 4 |
| NKE | Nike, Inc. | Consumer Discretionary | 15 | 0.7390 | [0.3648, 0.9076] | 0.0016 | 0.0298 | 0.7500 | 0.0013 | 8 / 11 |
| PKG | Packaging Corporation of America | Materials | 15 | 0.7267 | [0.3417, 0.9029] | 0.0021 | 0.0359 | 0.7536 | 0.0012 | 8 / 9 |
| SNA | Snap-on | Industrials | 15 | 0.7278 | [0.3438, 0.9033] | 0.0021 | 0.0359 | 0.8036 | 0.0003 | 8 / 8 |
| CFG | Citizens Financial Group | Financials | 15 | 0.7177 | [0.3249, 0.8993] | 0.0026 | 0.0418 | 0.6286 | 0.0121 | 2 / 2 |
| DG | Dollar General | Consumer Staples | 15 | 0.7117 | [0.3139, 0.8970] | 0.0029 | 0.0455 | 0.4464 | 0.0953 | 4 / 5 |
| PHM | PulteGroup | Consumer Discretionary | 15 | 0.7066 | [0.3047, 0.8949] | 0.0032 | 0.0476 | 0.5643 | 0.0284 | 12 / 12 |
| WST | West Pharmaceutical Services | Health Care | 15 | 0.7061 | [0.3036, 0.8947] | 0.0033 | 0.0476 | 0.7464 | 0.0014 | 14 / 14 |
| CHRW | C.H. Robinson | Industrials | 15 | 0.7039 | [0.2997, 0.8939] | 0.0034 | 0.0480 | 0.6786 | 0.0054 | 8 / 15 |
| EVRG | Evergy | Utilities | 14 | 0.7226 | [0.3115, 0.9059] | 0.0035 | 0.0480 | 0.6396 | 0.0138 | 8 / 12 |

## E–G. Robust / disagreements / sectors

See `phase4_final_report.json` tables.

## I. Case studies

### AAPL
10-Q NI n=15, Pearson r=0.7661, p=0.0009, q=0.0194, Spearman ρ=0.8536, agree=6 / 8. FDR survivor.

### ADI
10-Q NI n=15, Pearson r=0.7652, p=0.0009, q=0.0194, Spearman ρ=0.7750, agree=8 / 8. FDR survivor.

### ABBV
10-Q NI n=15, Pearson r=-0.0317, p=0.9106, q=0.9472, Spearman ρ=0.0143, agree=7 / 15. Still near zero.

### ADSK
10-Q NI n=15, Pearson r=-0.0314, p=0.9116, q=0.9472, Spearman ρ=-0.0071, agree=9 / 10. Still near zero.

### AFL
10-Q NI n=15, Pearson r=-0.4016, p=0.1379, q=0.3994, Spearman ρ=-0.1321, agree=2 / 4. Winsor not applicable at company n; check extreme YoY rows for outlier sensitivity.

### AES
10-Q NI n=15, Pearson r=0.4614, p=0.0834, q=0.2993, Spearman ρ=0.4607, agree=2 / 2.

### AMZN
10-Q NI n=15, Pearson r=-0.6144, p=0.0148, q=0.1046, Spearman ρ=-0.5250, agree=4 / 15. Still negative.

### MSFT
10-Q NI n=15, Pearson r=0.5683, p=0.0271, q=0.1590, Spearman ρ=0.4357, agree=13 / 15. Moderate-positive interpretation needs revision (r=0.5683).

### ADM
10-Q NI n=15, Pearson r=0.3863, p=0.1550, q=0.4194, Spearman ρ=0.7321, agree=10 / 10.

### NVDA
10-Q NI n=15, Pearson r=0.4024, p=0.1370, q=0.3994, Spearman ρ=0.6357, agree=13 / 13. Still unusually high direction agreement.

## J. Final conclusions

Across the full S&P 500 Phase 3 corpus, contemporaneous MD&A tone vs NI YoY associations are mostly weak-to-modest; FDR-surviving companies are a small minority of ranking-eligible names.

Median |Pearson r| among n≥6 eligible companies: **0.3172**

## K. Website recommendations

- **primary_metric:** 10-Q NI should be the primary company metric (form-homogeneous, largest n).
- **display_first:** Show Spearman alongside Pearson; lead with Spearman for robustness, keep Pearson for familiarity + CI.
- **ranking_n:** Prefer n>=8 for public rankings; keep n>=6 as exploratory/limited-sample tier.
- **show_p_values:** Show p-values only with sample size and CI; never alone. Prefer FDR q for multi-company claims.
- **fdr_badge:** Yes — badge FDR-surviving 10-Q NI results (q<0.05), with explicit multiple-comparison disclaimer.
- **hide_10k:** Keep 10-K visible but secondary/collapsed until more annual history accumulates; do not pool as primary.
- **revenue_secondary:** Yes — revenue secondary; exclude/label Financials & Real Estate as non-comparable.
- **homepage_case_studies:**
  - AAPL
  - MSFT
  - AMZN
  - NVDA
  - ADI
- **safest_sector_feature:** Energy
- **disclaimers:**
  - Contemporaneous same-filing association only — not prediction, forecasting, alpha, or trading advice.
  - Tone and accounting YoY can disagree for legitimate accounting reasons (one-time items, base effects).
  - Small n and extreme YoY can inflate Pearson; inspect Spearman, agreement, and outliers.
  - FDR controls false discoveries across many companies; most names will not survive.
  - Production rankings must not imply causal management-tone effects on earnings.

## L. Supabase footprint estimate

- Company rows: 502
- Sector rows: 11
- Chart points: 9697
- JSON payload: 2.74 MB
- Estimated Postgres: **7.93 MB** (<100 MB preferred)
- Largest row: DHI (4.1 KB)
- Below 500 MB: True

## M. Methodological limitations

- Associations are contemporaneous within the same filing; they are not predictive.
- NI YoY base effects (near-zero priors, loss↔profit flips) can dominate Pearson.
- 10-K samples remain short for many registrants; combined pooling mixes form dynamics.
- FDR is applied across ranking-eligible companies; it does not make individual r causal.
- Financials/Real Estate revenue is intentionally non-comparable and excluded from revenue rankings.
- MD&A extraction quality varies; residual extraction failures bias coverage by sector/ticker.
- Sentiment is FinBERT sentence-average tone, not a human reading of emphasis or risk language.
- Multiple thresholds (n=6/8/10/12) change who appears 'strong' — treat rankings as sensitivity analysis.
