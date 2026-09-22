-- 03_forecast.sql
-- Driver-based Q3-Q4 FY2026 forecast, full-year outlook, variance tables, checks.
--
-- Revenue  FY2025 same quarter x (1 + comp driver)  + acquisition stub (Q3 only)
--          comp driver = latest comparable-sales guidance midpoint
--            HD  +1.0%  (flat to +2.0%, reaffirmed 18 Aug 2026)
--            LOW  0.0%  (cut to "flat" on 19 Aug 2026, from flat to +2%)
--          stub = the part of FY2025 Q3 before the deal closed, which the
--          FY2025 base is missing:
--            HD  GMS closed 4 Sep 2025; FY25 Q3 began 4 Aug -> 31 pre-close days
--                GMS FY ended Apr-2025 net sales $5,513.7M (GMS release, 18 Jun 2025)
--            LOW FBM closed 9 Oct 2025; FY25 Q3 began 2 Aug -> 68 pre-close days
--                FBM ~$6.5B pro forma 2024 revenue (as reported by MDM)
--          FY2025 Q4 already has both businesses for the full quarter.
-- Margins  budget quarter margin + the H1 gap (actual - budget) in GM % and OM %.
--          Conservative: part of the H1 gap is acquisition mix that the H2
--          budget already contains. Sensitivity row uses budget margins instead.
-- Below OI guided net interest / 4 and guided tax rate (unchanged in August).

CREATE OR REPLACE TABLE fc_drivers AS
SELECT * FROM (VALUES
  ('HD',  0.010, 5513.7e6, 31, 'GMS'),
  ('LOW', 0.000, 6500.0e6, 68, 'FBM')
) d(ticker, comp, acq_annual_rev, stub_days, acq_name);

CREATE OR REPLACE TABLE h1_gap AS
WITH a AS (SELECT ticker, SUM(revenue)::DOUBLE r, SUM(gross_profit)::DOUBLE gp,
                  SUM(operating_income)::DOUBLE oi
           FROM pnl WHERE fiscal_year = 2026 AND fq <= 2 GROUP BY 1),
     b AS (SELECT ticker, SUM(revenue) r, SUM(gross_profit) gp, SUM(operating_income) oi
           FROM budget WHERE fq <= 2 GROUP BY 1)
SELECT ticker, a.gp/a.r - b.gp/b.r AS gm_gap, a.oi/a.r - b.oi/b.r AS om_gap
FROM a JOIN b USING (ticker);

CREATE OR REPLACE TABLE forecast_h2 AS
WITH base AS (
  SELECT p.ticker, p.fq,
         p.revenue * (1 + d.comp)
           + CASE WHEN p.fq = 3 THEN d.acq_annual_rev * d.stub_days / 365.0 ELSE 0 END AS revenue,
         CASE WHEN p.fq = 3 THEN d.acq_annual_rev * d.stub_days / 365.0 ELSE 0 END      AS acq_stub,
         b.gross_profit / b.revenue      AS gm_bud,
         b.operating_income / b.revenue  AS om_bud,
         bf.net_interest / 4 AS interest, bf.tax_rate
  FROM pnl p
  JOIN fc_drivers d USING (ticker)
  JOIN budget b ON b.ticker = p.ticker AND b.fq = p.fq
  JOIN budget_fy bf ON bf.ticker = p.ticker
  WHERE p.fiscal_year = 2025 AND p.fq IN (3, 4)
)
SELECT base.ticker, base.fq, revenue, acq_stub,
       revenue * (gm_bud + g.gm_gap)                                       AS gross_profit,
       revenue * (gm_bud + g.gm_gap) - revenue * (om_bud + g.om_gap)       AS opex,
       revenue * (om_bud + g.om_gap)                                       AS operating_income,
       (revenue * (om_bud + g.om_gap) - interest) * (1 - tax_rate)         AS net_income,
       -- sensitivity: same revenue, budget margins
       revenue * om_bud                                                    AS oi_at_budget_margin,
       (revenue * om_bud - interest) * (1 - tax_rate)                      AS ni_at_budget_margin
FROM base JOIN h1_gap g USING (ticker);

-- Forecast scenario = actuals for closed quarters + forecast for open quarters.
CREATE OR REPLACE TABLE fact_pnl AS
WITH actual AS (
  SELECT ticker, fiscal_year, fq, 'Actual' AS scenario,
         revenue::DOUBLE revenue, gross_profit::DOUBLE gross_profit, opex::DOUBLE opex,
         operating_income::DOUBLE operating_income, net_income::DOUBLE net_income
  FROM pnl WHERE fiscal_year IN (2025, 2026)
), bud AS (
  SELECT ticker, fiscal_year, fq, 'Budget', revenue, gross_profit, opex, operating_income, net_income
  FROM budget
), fc AS (
  SELECT ticker, fiscal_year, fq, 'Forecast', revenue, gross_profit, opex, operating_income, net_income
  FROM actual WHERE fiscal_year = 2026
  UNION ALL
  SELECT ticker, 2026, fq, 'Forecast', revenue, gross_profit, opex, operating_income, net_income
  FROM forecast_h2
), u AS (SELECT * FROM actual UNION ALL SELECT * FROM bud UNION ALL SELECT * FROM fc)
UNPIVOT u ON revenue, gross_profit, opex, operating_income, net_income
INTO NAME line VALUE amount;

-- Quarterly variance: Actual (Q1-Q2) or Forecast (Q3-Q4) vs Budget.
-- sign = +1 when more is better, -1 for costs. fav_amount > 0 is favourable.
CREATE OR REPLACE TABLE variance_q AS
WITH f AS (SELECT * FROM fact_pnl WHERE fiscal_year = 2026 AND scenario = 'Forecast'),
     b AS (SELECT * FROM fact_pnl WHERE fiscal_year = 2026 AND scenario = 'Budget')
SELECT f.ticker, f.fq, f.line,
       CASE WHEN f.fq <= 2 THEN 'Actual' ELSE 'Forecast' END AS basis,
       f.amount AS af_amount, b.amount AS budget_amount,
       (f.amount - b.amount) * CASE WHEN f.line = 'opex' THEN -1 ELSE 1 END AS fav_amount,
       f.amount / b.amount - 1 AS pct_vs_budget
FROM f JOIN b USING (ticker, fq, line);

CREATE OR REPLACE TABLE outlook_fy AS
SELECT ticker, line,
       SUM(budget_amount)                                 AS budget_fy,
       SUM(CASE WHEN fq <= 2 THEN af_amount END)          AS actual_h1,
       SUM(CASE WHEN fq >  2 THEN af_amount END)          AS forecast_h2,
       SUM(af_amount)                                     AS outlook_fy,
       SUM(fav_amount)                                    AS fav_vs_budget
FROM variance_q GROUP BY ticker, line;

-- Validation checks: every row must say pass = true.
CREATE OR REPLACE TABLE checks AS
SELECT 'Budget revenue ties to guided FY revenue' AS check_name, bf.ticker,
       ABS(SUM(b.revenue) - bf.rev) < 1 AS pass
FROM budget b JOIN budget_fy bf USING (ticker) GROUP BY bf.ticker, bf.rev
UNION ALL
SELECT 'Budget op margin = guided op margin', bf.ticker,
       ABS(SUM(b.operating_income)/SUM(b.revenue) - bf.om_pct) < 1e-9
FROM budget b JOIN budget_fy bf USING (ticker) GROUP BY bf.ticker, bf.om_pct
UNION ALL
SELECT 'Opex = gross profit - operating income, all scenarios', ticker,
       BOOL_AND(ABS(gp - ox - oi) < 1)
FROM (PIVOT fact_pnl ON line USING SUM(amount) GROUP BY ticker, fiscal_year, fq, scenario)
     t(ticker, fiscal_year, fq, scenario, gp, ni, oi, ox, rev)
GROUP BY ticker
UNION ALL
SELECT 'Forecast Q1-Q2 equals actual', a.ticker, BOOL_AND(ABS(a.amount - f.amount) < 1)
FROM fact_pnl a JOIN fact_pnl f USING (ticker, fiscal_year, fq, line)
WHERE a.scenario = 'Actual' AND f.scenario = 'Forecast' AND a.fq <= 2
GROUP BY a.ticker
UNION ALL
-- $5M tolerance: filers round each quarter and the YTD figure separately
-- (LOW: Q1+Q2+Q3 = $65,702M vs 9-month YTD $65,701M).
SELECT 'FY2025 quarters sum to 10-K full year (within $5M rounding)', p.ticker,
       ABS(SUM(p.revenue) - MAX(fy.val)) <= 5e6
FROM pnl p JOIN periods fy ON fy.ticker = p.ticker AND fy.line = 'revenue'
JOIN fiscal_years y ON y.ticker = p.ticker AND y.fiscal_year = 2025
     AND fy.start = y.fy_start AND fy."end" = y.fy_end
WHERE p.fiscal_year = 2025 GROUP BY p.ticker
UNION ALL
SELECT 'Every 2026 quarter has budget and forecast for all 5 lines', ticker,
       COUNT(*) = 20
FROM variance_q GROUP BY ticker;
