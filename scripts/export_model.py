#!/usr/bin/env python3
"""Export the DuckDB model to fpa_model.xlsx: star-schema Excel Tables that
Power BI (browser) imports directly, plus a Summary sheet built on SUMIFS so
the workbook also works on its own in Excel."""
import duckdb
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment

OUT = "fpa_model.xlsx"
con = duckdb.connect("fpa.duckdb", read_only=True)

F = "Arial"
HDR = Font(name=F, bold=True, color="FFFFFF")
HFILL = PatternFill("solid", fgColor="1F3864")
BODY = Font(name=F)
BLUE = Font(name=F, color="0000FF")
BOLD = Font(name=F, bold=True)
YELLOW = PatternFill("solid", fgColor="FFFF00")
MUSD = '#,##0;(#,##0);-'
PCT = '0.0%;(0.0%);-'

wb = Workbook()


def add_table(name, headers, rows, widths=None, fmts=None):
    ws = wb.create_sheet(name)
    ws.append(headers)
    for r in rows:
        ws.append(list(r))
    for c in ws[1]:
        c.font, c.fill = HDR, HFILL
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = BODY
    if fmts:
        for col, fmt in fmts.items():
            for (c,) in ws.iter_rows(min_row=2, min_col=col, max_col=col):
                c.number_format = fmt
    ref = f"A1:{ws.cell(1, len(headers)).column_letter}{len(rows) + 1}"
    t = Table(displayName=f"tbl_{name}", ref=ref)
    t.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
    ws.add_table(t)
    for i, w in enumerate(widths or [], 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    ws.freeze_panes = "A2"
    return ws


# ---------------------------------------------------------------- fact
fact = con.execute("""
    SELECT ticker,
           'FY' || RIGHT(fiscal_year::VARCHAR, 2) || ' Q' || fq AS period_key,
           fiscal_year, fq, scenario, line, ROUND(amount / 1e6, 1) AS amount_musd
    FROM fact_pnl ORDER BY ticker, fiscal_year, fq, scenario, line""").fetchall()

# ---------------------------------------------------------------- dims
dim_company = [
    ("HD", "The Home Depot", "Sunday nearest 31 Jan", "GMS Inc.", "2025-09-04",
     "0000354950"),
    ("LOW", "Lowe's Companies", "Friday nearest 31 Jan", "Foundation Building Materials",
     "2025-10-09", "0000060667"),
]
dim_line = [
    ("revenue", "Revenue", 1, 1),
    ("gross_profit", "Gross profit", 2, 1),
    ("opex", "Operating expenses", 3, -1),
    ("operating_income", "Operating income", 4, 1),
    ("net_income", "Net income", 5, 1),
]
dim_period = []
for fy in (2025, 2026):
    for q in (1, 2, 3, 4):
        status = "Prior year" if fy == 2025 else ("Actual" if q <= 2 else "Forecast")
        dim_period.append((f"FY{str(fy)[2:]} Q{q}", fy, q, f"Q{q}", fy * 10 + q, status))
dim_scenario = [("Actual", 1), ("Budget", 2), ("Forecast", 3)]

# ---------------------------------------------------------------- commentary
v = {(t, q, l): (af, bud, fav, pct) for t, q, l, af, bud, fav, pct in con.execute(
    "SELECT ticker, fq, line, af_amount/1e6, budget_amount/1e6, fav_amount/1e6, pct_vs_budget FROM variance_q").fetchall()}
o = {(t, l): (b, h1, h2, out, fav) for t, l, b, h1, h2, out, fav in con.execute(
    "SELECT ticker, line, budget_fy/1e6, actual_h1/1e6, forecast_h2/1e6, outlook_fy/1e6, fav_vs_budget/1e6 FROM outlook_fy").fetchall()}


def m(x):
    return f"${abs(x)/1000:,.2f}B"


hd_om = o[("HD", "operating_income")][3] / o[("HD", "revenue")][3]
low_om = o[("LOW", "operating_income")][3] / o[("LOW", "revenue")][3]
low_gm_q2 = v[("LOW", 2, "gross_profit")][0] / v[("LOW", 2, "revenue")][0]
low_gm_q2b = v[("LOW", 2, "gross_profit")][1] / v[("LOW", 2, "revenue")][1]

commentary = [
    ("HD", 1, "Favourable", "Revenue", "FY26 Q2", round(v[("HD", 2, "revenue")][2]),
     f"Q2 revenue beat budget by {m(v[('HD',2,'revenue')][2])} (+{v[('HD',2,'revenue')][3]*100:.1f}%); "
     f"H1 by {m(v[('HD',1,'revenue')][2]+v[('HD',2,'revenue')][2])}. "
     "Mostly phasing, not outperformance: the budget uses FY2025's quarterly shape, and GMS only "
     "joined on 4 Sep 2025, so FY2025's first half had no GMS revenue. Comparable sales were +1.7% in Q2. "
     f"The full-year revenue outlook is {m(o[('HD','revenue')][3])}, on budget, so the H1 beat is expected to reverse in H2."),
    ("HD", 2, "Unfavourable", "Operating expenses", "FY26 H1",
     round(v[("HD", 1, "opex")][2] + v[("HD", 2, "opex")][2]),
     f"Opex ran {m(-(v[('HD',1,'opex')][2]+v[('HD',2,'opex')][2]))} over budget in H1 (+3.5%) while revenue was only +1.7% over. "
     "Opex grew 7.0% year over year against 5.3% revenue growth, which is consistent with carrying GMS's cost base. "
     f"It absorbed the whole gross-profit beat: operating income is {m(-o[('HD','operating_income')][4])} under budget for the year "
     f"and the operating margin outlook is {hd_om*100:.1f}%, against 12.5% budget and 12.4-12.6% guidance. "
     "Action: hold H2 SG&A growth at or below revenue growth to protect the guided margin."),
    ("HD", 3, "Unfavourable", "Revenue", "FY26 Q4", round(v[("HD", 4, "revenue")][2]),
     f"Q4 revenue is forecast {m(-v[('HD',4,'revenue')][2])} below budget. This is the mirror image of the H1 phasing: "
     "the FY2025 Q4 base already includes GMS, so growth falls to the +1% comp driver. Treat H1 and Q4 together, not as separate surprises."),
    ("LOW", 1, "Favourable", "Revenue", "FY26 Q1", round(v[("LOW", 1, "revenue")][2]),
     f"Q1 revenue beat budget by {m(v[('LOW',1,'revenue')][2])} (+{v[('LOW',1,'revenue')][3]*100:.1f}%). "
     "FBM closed on 9 Oct 2025, so it is in FY2026 Q1 but absent from the FY2025 Q1 base the budget was phased on. "
     "Underlying demand is soft: comparable sales were +0.2% in Q2."),
    ("LOW", 2, "Unfavourable", "Revenue", "FY26 Q4", round(v[("LOW", 4, "revenue")][2]),
     f"Q4 revenue is forecast {m(-v[('LOW',4,'revenue')][2])} below budget, the largest variance in the model. "
     "The $93.0B budget needed about +6% H2 growth; with FBM fully in the FY2025 Q4 base and comp guidance cut to flat, "
     f"the forecast H2 growth is +2.9%. Full-year outlook is {m(o[('LOW','revenue')][3])} "
     f"({m(-o[('LOW','revenue')][4])} under budget), close to Lowe's own lowered $92.0B outlook (19 Aug 2026). "
     "Action: rebase the H2 budget to the updated outlook."),
    ("LOW", 3, "Unfavourable", "Gross profit", "FY26 Q2", round(v[("LOW", 2, "gross_profit")][2]),
     f"Q2 gross margin was {low_gm_q2*100:.1f}% against {low_gm_q2b*100:.1f}% budget ({m(-v[('LOW',2,'gross_profit')][2])}). "
     "A lower-margin mix from pro distribution businesses is a plausible driver but is not disclosed separately. "
     f"Carried into H2, gross profit is {m(-o[('LOW','gross_profit')][4])} under budget and the operating margin outlook is "
     f"{low_om*100:.1f}% against 11.3% budget. The 'favourable' opex in H2 is a derived-line effect of lower revenue, not cost savings."),
]

assumptions = [
    ("Budget revenue", "+3.5% on FY2025 (midpoint of 2.5-4.5%)", "$93.0B (midpoint of $92.0-94.0B)",
     "Company FY2026 guidance, 24/25 Feb 2026"),
    ("Budget gross margin", "33.1% (guided)", "33.5% = FY2025 actual (not guided)", "HD guidance; LOW analyst assumption"),
    ("Budget operating margin (GAAP)", "12.5% (midpoint 12.4-12.6%)", "11.3% (midpoint 11.2-11.4%)", "Company guidance"),
    ("Net interest", "$2.3B, 1/4 per quarter", "$1.6B, 1/4 per quarter", "Company guidance"),
    ("Tax rate", "24.3%", "24.5%", "Company guidance"),
    ("Quarterly phasing", "FY2025 quarter shares", "FY2025 quarter shares",
     "Known limitation: acquisitions closed mid-FY2025, so H1 is under-phased"),
    ("Forecast comp driver (Q3-Q4)", "+1.0% (flat to +2.0%, reaffirmed 18 Aug 2026)",
     "0.0% (cut to flat, 19 Aug 2026)", "Q2 FY2026 releases"),
    ("Q3 acquisition stub", "GMS $5,513.7M x 31/365 = $468M", "FBM ~$6.5B x 68/365 = $1,211M",
     "GMS FY2025 release (18 Jun 2025); FBM pro forma revenue per MDM"),
    ("Forecast margins", "Budget quarter margin + H1 gap (conservative)",
     "Budget quarter margin + H1 gap (conservative)", "Analyst assumption"),
    ("Grain", "Quarterly", "Quarterly",
     "Public filings are quarterly; monthly splits would be fabricated"),
]

checks = con.execute("SELECT check_name, ticker, pass FROM checks ORDER BY check_name, ticker").fetchall()

# ---------------------------------------------------------------- sheets
ws0 = wb.active
ws0.title = "Summary"

add_table("fact_pnl", ["ticker", "period_key", "fiscal_year", "fq", "scenario", "line", "amount_musd"],
          fact, [9, 12, 11, 6, 11, 18, 14], {7: MUSD})
add_table("dim_company", ["ticker", "company", "fiscal_year_end", "fy2025_acquisition", "acquisition_close", "sec_cik"],
          dim_company, [9, 20, 24, 30, 18, 13])
add_table("dim_line", ["line", "line_label", "line_sort", "sign"], dim_line, [18, 22, 10, 8])
add_table("dim_period", ["period_key", "fiscal_year", "fq", "quarter", "period_sort", "status"],
          dim_period, [12, 11, 6, 9, 12, 12])
add_table("dim_scenario", ["scenario", "scenario_sort"], dim_scenario, [12, 14])
wc = add_table("commentary", ["ticker", "rank", "direction", "line_label", "period", "variance_musd", "explanation"],
               commentary, [8, 6, 14, 20, 10, 14, 110], {6: MUSD})
for (c,) in wc.iter_rows(min_row=2, min_col=7, max_col=7):
    c.alignment = Alignment(wrap_text=True, vertical="top")
add_table("assumptions", ["driver", "HD", "LOW", "source"], assumptions, [30, 42, 42, 60])
add_table("checks", ["check_name", "ticker", "pass"], checks, [60, 9, 8])

# ---------------------------------------------------------------- Summary (SUMIFS)
ws = ws0
ws["A1"] = "FY2026 budget vs actual vs forecast ($M)"
ws["A1"].font = Font(name=F, bold=True, size=14, color="1F3864")
ws["A2"], ws["B2"] = "Company (HD or LOW)", "HD"
ws["A2"].font = BOLD
ws["B2"].font, ws["B2"].fill = BLUE, YELLOW
ws["B2"].comment = Comment("Input: type HD or LOW. Every number below recalculates.", "model")
dv = DataValidation(type="list", formula1='"HD,LOW"', allow_blank=False)
ws.add_data_validation(dv)
dv.add("B2")
ws["A3"] = "Favourable variance is positive: more revenue/profit, or lower operating expenses."
ws["A3"].font = Font(name=F, italic=True, color="52514E")

n = len(fact) + 1
R = lambda col: f"fact_pnl!${col}$2:${col}${n}"
TK, FY, FQ, SC, LN, AM = R("A"), R("C"), R("D"), R("E"), R("F"), R("G")

hdrs = ["Line", "Budget FY26", "Actual H1", "Forecast H2", "Outlook FY26",
        "Variance (fav +)", "Var %", "FY25 actual", "Outlook YoY %"]
for i, h in enumerate(hdrs, 1):
    c = ws.cell(5, i, h)
    c.font, c.fill = HDR, HFILL
    c.alignment = Alignment(horizontal="center", wrap_text=True)


def sumifs(scn, fy, q_op=None, line_cell=None):
    s = f'SUMIFS({AM},{TK},$B$2,{SC},"{scn}",{FY},{fy},{LN},{line_cell})'
    if q_op:
        s = s[:-1] + f',{FQ},"{q_op}")'
    return s


for r, (line, label, _, sign) in enumerate(dim_line, 6):
    ws.cell(r, 1, label).font = BOLD
    ws.cell(r, 11, line).font = Font(name=F, color="898781")     # hidden key
    ws.cell(r, 12, sign).font = BLUE
    key = f"$K{r}"
    ws.cell(r, 2, "=" + sumifs("Budget", 2026, line_cell=key))
    ws.cell(r, 3, "=" + sumifs("Actual", 2026, "<=2", key))
    ws.cell(r, 4, "=" + sumifs("Forecast", 2026, ">=3", key))
    ws.cell(r, 5, f"=C{r}+D{r}")
    ws.cell(r, 6, f"=(E{r}-B{r})*$L{r}")
    ws.cell(r, 7, f"=IF(B{r}=0,0,F{r}/B{r})")
    ws.cell(r, 8, "=" + sumifs("Actual", 2025, line_cell=key))
    ws.cell(r, 9, f"=IF(H{r}=0,0,E{r}/H{r}-1)")
    for col in (2, 3, 4, 5, 6, 8):
        ws.cell(r, col).number_format = MUSD
        ws.cell(r, col).font = BODY
    for col in (7, 9):
        ws.cell(r, col).number_format = PCT
        ws.cell(r, col).font = BODY

ws["A12"], ws["A13"] = "Gross margin %", "Operating margin %"
for r in (12, 13):
    ws.cell(r, 1).font = BOLD
num = {12: 7, 13: 9}
for r, nr in num.items():
    for col in ("B", "C", "D", "E", "H"):
        ws[f"{col}{r}"] = f"=IF({col}6=0,0,{col}{nr}/{col}6)"
        ws[f"{col}{r}"].number_format = PCT
        ws[f"{col}{r}"].font = BODY
    ws[f"F{r}"] = f"=(E{r}-B{r})*10000"
    ws[f"F{r}"].number_format = '#,##0" bps";(#,##0" bps")'
    ws[f"F{r}"].font = BODY
ws["K5"], ws["L5"] = "line key", "sign"
for c in (ws["K5"], ws["L5"]):
    c.font = Font(name=F, color="898781")
ws["A15"] = ("Sign column (L) is an input: +1 where more is better, -1 for costs. "
             "Source data: SEC XBRL companyfacts; budget and forecast drivers on the 'assumptions' sheet.")
ws["A15"].font = Font(name=F, italic=True, color="52514E")
ws.column_dimensions["A"].width = 22
for col in "BCDEFGHI":
    ws.column_dimensions[col].width = 14
ws.row_dimensions[5].height = 32
ws.freeze_panes = "A6"

import os
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
wb.save(OUT)
print("saved", OUT, "fact rows", len(fact))
