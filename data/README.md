# Selected ABS snapshots

These CSVs contain only ABS series A3349414R, original monthly Victoria liquor retailing turnover in nominal AUD millions. Each row is one calendar month. The series is not seasonally adjusted or adjusted for inflation.

| File | Observations | Period |
|---|---:|---|
| `assignment_vintage.csv` | 488 | April 1982 to November 2022 |
| `extension_vintage.csv` | 516 | April 1982 to March 2025 |

The schema is `month` (ISO date at the month's first day) and `turnover_aud_million` (positive numeric turnover). Missing months, duplicate months, missing values and nonpositive turnover are rejected by the notebook. It verifies the selected-file SHA-256 hashes in `provenance.json` before fitting any model.

The original supplied source files are `IA_data.csv` and `8501011_1.csv`. The original wide assignment file is excluded because it contains unrelated series and student identifier columns. Its malformed metadata quoting and one continuation fragment beyond the selected field are documented in `provenance.json`; all expected selected observations were preserved.

The notebook compares both snapshots over their 488 overlapping months. The recorded audit found identical selected values. For development and final evaluation fitting, it retains assignment history through November 2022; final evaluation actuals come from the extension after that date. Only the dated post-evaluation refit uses the entire extension snapshot. Exact source download dates and historical publication vintages are unknown.

Source reference and attribution: Australian Bureau of Statistics, [Retail Trade, Australia, March 2025](https://www.abs.gov.au/statistics/industry/retail-and-wholesale-trade/retail-trade-australia/mar-2025), table 11, original turnover by state and industry subgroup. The supplied extension is a fixed historical snapshot. The [June 2025 reference period](https://www.abs.gov.au/statistics/industry/retail-and-wholesale-trade/retail-trade-australia/jun-2025) was the last Retail Trade publication, released on 31 July 2025.

The selected ABS aggregate data is attributed to the Australian Bureau of Statistics under its published CC BY 4.0 terms. Extraction adapts the presentation while preserving selected numeric values. The source policy, license and changes are described below; the data terms do not select a license for this project's code or prose.


# ABS data attribution and license

The selected CSVs reproduce aggregate data from the Australian Bureau of Statistics (ABS), **Retail Trade, Australia**, table 11, original Victoria liquor retailing turnover, series **A3349414R**. Copyright is held by the Commonwealth of Australia.

Source reference: [ABS Retail Trade, Australia, March 2025](https://www.abs.gov.au/statistics/industry/retail-and-wholesale-trade/retail-trade-australia/mar-2025).

The ABS [copyright and attribution policy](https://www.abs.gov.au/website-privacy-copyright-and-disclaimer), checked on 10 October 2026, provides its website material under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/), subject to stated exceptions. These packaged observations are the selected aggregate statistical series. ABS logos, the Commonwealth Coat of Arms, branding, trademarks and microdata are not included.

**Source: Australian Bureau of Statistics, Retail Trade, Australia, table 11, series A3349414R; selected monthly Victoria liquor retailing turnover.**

The package adapts source presentation by extracting the single series, converting dates to ISO format, and parsing decimal-comma values in the extension source. Numeric selected values are preserved. Both supplied vintages are retained, with hashes and extraction notes in `data/provenance.json`. Subsequent transformations, forecasts and interpretations are this project's analysis, not ABS findings.
