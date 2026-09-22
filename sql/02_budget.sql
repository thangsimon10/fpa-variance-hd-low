-- 02_budget.sql
-- FY2026 budget built from FY2025 quarterly actuals + each company's own
-- FY2026 guidance (midpoints). One row per ticker x quarter.
--
-- Method
--   Revenue   guided full-year revenue x FY2025 quarter share of revenue
--   GM %      FY2025 quarter GM % shifted by (guided FY GM % - FY2025 FY GM %)
--             -> keeps each quarter's seasonality, lands on the guided year
--   Op margin same shift logic against guided GAAP operating margin
--   Opex      gross profit - operating income   (same definition as actuals)
--   Net inc.  (operating income - guided net interest / 4) x (1 - guided tax)
--
-- Known limitation, disclosed in the memo: FY2025 quarter shares were set
-- before HD's GMS (closed 4 Sep 2025) and LOW's FBM (closed 9 Oct 2025)
-- deals were in the base, so this phasing puts too little acquired revenue
-- in H1 and too much in H2.

CREATE OR REPLACE TABLE guidance AS
SELECT * FROM (VALUES
  -- ticker, revenue growth, gross margin, GAAP op margin, net interest $, tax rate, source
  ('HD',  0.035,  0.331, 0.125, 2.3e9, 0.243,
   'HD Q4 FY2025 release, 24 Feb 2026: sales growth ~2.5-4.5%, GM ~33.1%, OM 12.4-12.6%, net interest ~$2.3B, tax ~24.3%'),
  ('LOW', NULL,   NULL,  0.113, 1.6e9, 0.245,
   'LOW Q4 FY2025 release, 25 Feb 2026: sales $92.0-94.0B, OM 11.2-11.4%, net interest ~$1.6B, tax ~24.5%; no GM guidance')
) g(ticker, rev_growth, gm_pct, om_pct, net_interest, tax_rate, source);

-- LOW guides revenue in dollars, not growth; GM not guided -> hold FY2025 actual.
CREATE OR REPLACE TABLE fy25 AS
SELECT ticker,
       SUM(revenue)::DOUBLE                         AS rev,
       SUM(gross_profit) / SUM(revenue)::DOUBLE     AS gm_pct,
       SUM(operating_income) / SUM(revenue)::DOUBLE AS om_pct
FROM pnl WHERE fiscal_year = 2025
GROUP BY ticker;

CREATE OR REPLACE TABLE budget_fy AS
SELECT f.ticker,
       CASE WHEN f.ticker = 'LOW' THEN 93.0e9 ELSE f.rev * (1 + g.rev_growth) END AS rev,
       COALESCE(g.gm_pct, f.gm_pct) AS gm_pct,
       g.om_pct, g.net_interest, g.tax_rate,
       f.gm_pct AS gm25, f.om_pct AS om25, f.rev AS rev25
FROM fy25 f JOIN guidance g USING (ticker);

CREATE OR REPLACE TABLE budget AS
WITH q AS (
  SELECT p.ticker, p.fq,
         p.revenue / f.rev                               AS rev_share,
         p.gross_profit / p.revenue::DOUBLE              AS gm25_q,
         p.operating_income / p.revenue::DOUBLE          AS om25_q
  FROM pnl p JOIN fy25 f USING (ticker)
  WHERE p.fiscal_year = 2025
), b AS (
  SELECT q.ticker, 2026 AS fiscal_year, q.fq,
         bf.rev * q.rev_share                         AS revenue,
         q.gm25_q + (bf.gm_pct - bf.gm25)             AS gm_pct,
         q.om25_q + (bf.om_pct - bf.om25)             AS om_pct,
         bf.net_interest / 4                          AS interest,
         bf.tax_rate
  FROM q JOIN budget_fy bf USING (ticker)
)
SELECT ticker, fiscal_year, fq,
       revenue,
       revenue * gm_pct                                   AS gross_profit,
       revenue * gm_pct - revenue * om_pct                AS opex,
       revenue * om_pct                                   AS operating_income,
       (revenue * om_pct - interest) * (1 - tax_rate)     AS net_income
FROM b;

-- Long-format fact table for Power BI: one row per ticker/year/quarter/scenario/line.
CREATE OR REPLACE TABLE fact_pnl AS
WITH actual AS (
  SELECT ticker, fiscal_year, fq, 'Actual' AS scenario,
         revenue::DOUBLE AS revenue, gross_profit::DOUBLE AS gross_profit,
         opex::DOUBLE AS opex, operating_income::DOUBLE AS operating_income,
         net_income::DOUBLE AS net_income
  FROM pnl WHERE fiscal_year IN (2025, 2026)
), bud AS (
  SELECT ticker, fiscal_year, fq, 'Budget', revenue, gross_profit, opex,
         operating_income, net_income FROM budget
), u AS (SELECT * FROM actual UNION ALL SELECT * FROM bud)
UNPIVOT u ON revenue, gross_profit, opex, operating_income, net_income
INTO NAME line VALUE amount;

-- H1 FY2026: actual vs budget. Favourable = more revenue/profit, less opex.
CREATE OR REPLACE VIEW h1_variance AS
WITH a AS (SELECT * FROM pnl WHERE fiscal_year = 2026 AND fq <= 2),
     b AS (SELECT * FROM budget WHERE fq <= 2)
SELECT a.ticker, a.fq, l.line,
       CASE l.line WHEN 'revenue' THEN a.revenue WHEN 'gross_profit' THEN a.gross_profit
                   WHEN 'opex' THEN a.opex WHEN 'operating_income' THEN a.operating_income
                   ELSE a.net_income END::DOUBLE AS actual,
       CASE l.line WHEN 'revenue' THEN b.revenue WHEN 'gross_profit' THEN b.gross_profit
                   WHEN 'opex' THEN b.opex WHEN 'operating_income' THEN b.operating_income
                   ELSE b.net_income END AS budget
FROM a JOIN b USING (ticker, fq)
CROSS JOIN (VALUES ('revenue'),('gross_profit'),('opex'),('operating_income'),('net_income')) l(line);
