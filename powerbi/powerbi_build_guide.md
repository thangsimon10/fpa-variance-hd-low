# Power BI build guide (browser, app.powerbi.com)

Target layout: `dashboard_mockup_HD.png` / `dashboard_mockup_LOW.png`. One report page, company slicer on top.

## Step 1 — Load the data with Power Query Online
The browser's Import button only accepts .pbix/.rdl, and "Upload file" needs work/school OneDrive, so the
workbook is read from the public GitHub repo instead.
1. app.powerbi.com → **Create** → **Excel** → **Link to file**.
2. URL: `https://raw.githubusercontent.com/thangsimon10/fpa-variance-hd-low/main/fpa_model.xlsx`,
   Authentication kind **Anonymous** → **Next**.
3. Tick the eight Excel *Tables* (`tbl_assumptions`, `tbl_checks`, `tbl_commentary`, `tbl_dim_company`,
   `tbl_dim_line`, `tbl_dim_period`, `tbl_dim_scenario`, `tbl_fact_pnl`), not the plain sheet names → **Transform data**.
4. Check the types Power Query applied (amount_musd = decimal, pass = true/false) → **Create a report**.

## Step 2 — Relationships (semantic model → **Open data model** → **Manage relationships**)
| From (many) | To (one) | Direction |
|---|---|---|
| tbl_fact_pnl[ticker] | tbl_dim_company[ticker] | Single |
| tbl_fact_pnl[period_key] | tbl_dim_period[period_key] | Single |
| tbl_fact_pnl[line] | tbl_dim_line[line] | Single |
| tbl_fact_pnl[scenario] | tbl_dim_scenario[scenario] | Single |
| tbl_commentary[ticker] | tbl_dim_company[ticker] | Single |

Sort columns: tbl_dim_line[line_label] → *Sort by column* line_sort; tbl_dim_period[period_key] → period_sort.
Hide from report view: tbl_fact_pnl[amount_musd], all key columns on fact tables.

## Step 3 — Measures
Select `tbl_fact_pnl` → **New measure**, paste each block from `measures.dax` (one measure per paste).
Format: $ measures → Whole number, thousands separator; % measures → Percentage, 1 decimal; bps → Whole number.

## Step 4 — Page (16:9)
Page filter: tbl_dim_period[fiscal_year] = 2026.

| Visual | Fields | Notes |
|---|---|---|
| Slicer (tile) | tbl_dim_company[ticker] | Single select, top-right |
| 5 × Card (new) | Revenue A/F, GM % A/F, Opex A/F, Op Income A/F, Net Income A/F | Reference label: matching Budget measure and variance |
| Clustered column | X: tbl_dim_period[quarter]; Y: Revenue Budget, Revenue A/F | Budget grey #C3C2B7, A/F navy #1F3864; Y axis starts at 0 |
| Line | X: tbl_dim_period[quarter]; Y: OM % Budget, OM % A/F | |
| Column | X: tbl_dim_period[quarter]; Y: Op Income Var (fav +) | Conditional colour: >0 green #1B8A5A, <0 red #E34948 |
| Matrix | Rows: tbl_dim_line[line_label]; Columns: tbl_dim_period[quarter]; Values: Variance (fav +) | Row subtotal = FY; font colour rules same as above |
| Table | tbl_commentary[direction], [period], [line_label], [variance_musd], [explanation] | Word wrap on; sorted by rank |
| Text box | "Q1–Q2 actual · Q3–Q4 forecast · $M · favourable positive" | Under title |

Optional page 2 "Assumptions & checks": tables of `assumptions` and `checks` (every row should read TRUE).

## Step 5 — Check the numbers
With **HD** selected the cards should read: Revenue $170.4B (−$7M), Op income $20.7B (−$568M), Net income $13.9B (−$452M).
With **LOW**: Revenue $91.6B (−$1,357M), Op income $10.1B (−$429M), Net income $6.4B (−$301M).
If a card differs, the relationship to tbl_dim_scenario or tbl_dim_line is usually the cause.
