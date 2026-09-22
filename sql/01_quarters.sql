-- 01_quarters.sql  |  raw SEC XBRL facts -> one clean row per company x line x fiscal quarter
--
-- Four traps handled here, each found by profiling before any modelling:
--   1. `fy` is the FILING year, not the period year. Each 10-K repeats prior
--      years as comparatives, so the same fact appears under several fy values.
--      Periods are identified by start/end dates, and duplicates collapsed.
--   2. Q4 is never reported as a quarter. It is derived: full year minus the
--      nine-month year-to-date figure.
--   3. 53-week years exist (HD FY2024, LOW FY2022). Quarter length in days is
--      kept on every row so a 14-week Q4 is visible, never silently compared.
--   4. The companies tag the same line differently. Mapped explicitly below.

CREATE OR REPLACE TABLE facts AS
SELECT * FROM read_csv('data/raw/sec_hd_low_income_statement.csv', header=true);

-- Line mapping. D&A uses the income-statement tag, not the cash-flow tag
-- (DepreciationDepletionAndAmortization), which includes D&A buried in cost of sales.
CREATE OR REPLACE TABLE line_map AS SELECT * FROM (VALUES
  ('RevenueFromContractWithCustomerExcludingAssessedTax', 'revenue'),
  ('CostOfRevenue',                                      'cost_of_sales'),
  ('CostOfGoodsAndServicesSold',                         'cost_of_sales'),
  ('GrossProfit',                                        'gross_profit'),
  ('SellingGeneralAndAdministrativeExpense',             'sga'),
  ('DepreciationAndAmortization',                        'da'),
  ('OperatingIncomeLoss',                                'operating_income'),
  ('NetIncomeLoss',                                      'net_income')
) AS t(concept, line);

-- One value per company x line x exact period; latest filing wins (restatements).
CREATE OR REPLACE TABLE periods AS
SELECT ticker, line, start, "end", days, val
FROM (
  SELECT f.ticker, m.line, f.start, f."end", f.days, f.val,
         ROW_NUMBER() OVER (PARTITION BY f.ticker, m.line, f.start, f."end"
                            ORDER BY f.filed DESC) AS rn
  FROM facts f JOIN line_map m USING (concept)
) WHERE rn = 1;

-- Fiscal years: the full-year periods. Named by the calendar year they start in,
-- matching company usage (HD "fiscal 2025" = Feb 3 2025 - Feb 1 2026).
CREATE OR REPLACE TABLE fiscal_years AS
SELECT DISTINCT ticker, start AS fy_start, "end" AS fy_end, days AS fy_days,
       YEAR(start) AS fiscal_year
FROM periods WHERE line = 'revenue' AND days BETWEEN 360 AND 375;

-- Reported quarters Q1-Q3 (13-week periods), placed inside their fiscal year.
CREATE OR REPLACE TABLE q_reported AS
SELECT p.ticker, y.fiscal_year, p.line, p.start, p."end", p.days, p.val,
       ROW_NUMBER() OVER (PARTITION BY p.ticker, y.fiscal_year, p.line ORDER BY p.start) AS fq
FROM periods p
JOIN fiscal_years y ON y.ticker = p.ticker AND p.start >= y.fy_start AND p."end" <= y.fy_end
WHERE p.days BETWEEN 80 AND 100;

-- Also place quarters of the CURRENT fiscal year, which has no full-year period yet.
-- Its start is the day after the prior fiscal year's end.
CREATE OR REPLACE TABLE q_current AS
SELECT p.ticker, y.fiscal_year + 1 AS fiscal_year, p.line, p.start, p."end", p.days, p.val,
       ROW_NUMBER() OVER (PARTITION BY p.ticker, p.line ORDER BY p.start) AS fq
FROM periods p
JOIN (SELECT ticker, MAX(fiscal_year) AS fiscal_year, MAX(fy_end) AS fy_end
      FROM fiscal_years GROUP BY 1) y
  ON y.ticker = p.ticker AND p.start > y.fy_end
WHERE p.days BETWEEN 80 AND 100;

-- Q4 derived = full year - nine-month YTD.
CREATE OR REPLACE TABLE q4_derived AS
SELECT y.ticker, y.fiscal_year, fy.line,
       ytd."end" + 1 AS start, y.fy_end AS "end",
       y.fy_end - ytd."end" AS days,
       fy.val - ytd.val AS val, 4 AS fq
FROM fiscal_years y
JOIN periods fy  ON fy.ticker = y.ticker AND fy.start = y.fy_start AND fy."end" = y.fy_end
JOIN periods ytd ON ytd.ticker = y.ticker AND ytd.line = fy.line
                AND ytd.start = y.fy_start AND ytd.days BETWEEN 260 AND 280;

CREATE OR REPLACE TABLE quarters AS
SELECT ticker, fiscal_year, fq, line, start, "end", days, val FROM q_reported
UNION ALL SELECT ticker, fiscal_year, fq, line, start, "end", days, val FROM q_current
UNION ALL SELECT ticker, fiscal_year, fq, line, start, "end", days, val FROM q4_derived;

-- Wide P&L, with operating expenses DERIVED as gross profit - operating income
-- so the definition is identical for both companies (Lowe's reports no opex total).
CREATE OR REPLACE TABLE pnl AS
SELECT ticker, fiscal_year, fq,
       MIN(start) AS q_start, MAX("end") AS q_end, MAX(days) AS days,
       SUM(CASE WHEN line='revenue'          THEN val END) AS revenue,
       SUM(CASE WHEN line='cost_of_sales'    THEN val END) AS cost_of_sales,
       SUM(CASE WHEN line='gross_profit'     THEN val END) AS gross_profit,
       SUM(CASE WHEN line='sga'              THEN val END) AS sga,
       SUM(CASE WHEN line='da'               THEN val END) AS da,
       SUM(CASE WHEN line='operating_income' THEN val END) AS operating_income,
       SUM(CASE WHEN line='net_income'       THEN val END) AS net_income
FROM quarters GROUP BY 1,2,3;

CREATE OR REPLACE TABLE pnl AS
SELECT *, gross_profit - operating_income AS opex FROM pnl;
