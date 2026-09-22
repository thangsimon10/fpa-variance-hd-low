#!/usr/bin/env python3
"""Target layout for the Power BI page, one PNG per company (1600x1000).
The user rebuilds this in app.powerbi.com; the PNG is the reference."""
import duckdb, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

con = duckdb.connect("fpa.duckdb", read_only=True)
SURF, CARD, NAVY, INK, INK2, MUTED, GRID = "#f4f4f1", "#ffffff", "#1F3864", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BUD, ACT, FC, GOOD, BAD = "#c3c2b7", "#1F3864", "#2a78d6", "#1b8a5a", "#e34948"
plt.rcParams.update({"text.parse_math": False, "font.family": "sans-serif", "text.color": INK,
                     "axes.edgecolor": GRID, "xtick.color": MUTED, "ytick.color": MUTED})

NAMES = {"HD": "The Home Depot", "LOW": "Lowe's Companies"}


def panel(fig, x, y, w, h, title=None):
    fig.add_artist(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.006",
                                  transform=fig.transFigure, fc=CARD, ec=GRID, lw=1, zorder=-5))
    if title:
        fig.text(x + 0.012, y + h - 0.028, title, fontsize=11.5, weight="bold", color=INK)


def build(tk):
    q = con.execute("""SELECT fq, line, af_amount/1e6, budget_amount/1e6, fav_amount/1e6
                       FROM variance_q WHERE ticker=? ORDER BY fq""", [tk]).fetchall()
    d = {(fq, l): (a, b, f) for fq, l, a, b, f in q}
    o = {l: (b, h1, h2, out, fav) for l, b, h1, h2, out, fav in con.execute(
        "SELECT line, budget_fy/1e6, actual_h1/1e6, forecast_h2/1e6, outlook_fy/1e6, fav_vs_budget/1e6 FROM outlook_fy WHERE ticker=?", [tk]).fetchall()}
    com = con.execute("SELECT 1").fetchall()  # placeholder to keep connection warm

    fig = plt.figure(figsize=(16, 10), dpi=100, facecolor=SURF)
    fig.text(0.02, 0.955, "FY2026 Budget vs Actual vs Forecast", fontsize=22, weight="bold", color=NAVY)
    fig.text(0.02, 0.922, "$ millions  ·  Q1–Q2 actual, Q3–Q4 forecast  ·  favourable variance shown positive",
             fontsize=11.5, color=INK2)
    # slicer
    for i, t in enumerate(["HD", "LOW"]):
        on = t == tk
        fig.add_artist(FancyBboxPatch((0.80 + i * 0.09, 0.925), 0.08, 0.04,
                       boxstyle="round,pad=0,rounding_size=0.006", transform=fig.transFigure,
                       fc=NAVY if on else CARD, ec=NAVY, lw=1.2))
        fig.text(0.84 + i * 0.09, 0.945, t, ha="center", va="center", fontsize=12,
                 weight="bold", color="white" if on else NAVY)
    fig.text(0.80, 0.978, "Company slicer", fontsize=9.5, color=MUTED)

    # KPI cards
    rev = o["revenue"]
    kpis = [
        ("Revenue", o["revenue"][3], o["revenue"][4], None),
        ("Gross margin %", o["gross_profit"][3] / rev[3], None,
         (o["gross_profit"][3] / rev[3] - o["gross_profit"][0] / rev[0]) * 1e4),
        ("Operating expenses", o["opex"][3], o["opex"][4], None),
        ("Operating income", o["operating_income"][3], o["operating_income"][4], None),
        ("Net income", o["net_income"][3], o["net_income"][4], None),
    ]
    cw = 0.186
    for i, (lab, val, var, bps) in enumerate(kpis):
        x = 0.02 + i * (cw + 0.0075)
        panel(fig, x, 0.765, cw, 0.135)
        fig.text(x + 0.012, 0.872, lab + " · FY outlook", fontsize=10.5, color=INK2)
        big = f"{val*100:.1f}%" if bps is not None else f"${val/1000:,.1f}B"
        fig.text(x + 0.012, 0.822, big, fontsize=24, weight="bold", color=INK)
        if bps is not None:
            s, col = f"{bps:+.0f} bps vs budget", GOOD if bps >= 0 else BAD
        else:
            s, col = f"{'+' if var >= 0 else '−'}${abs(var):,.0f}M vs budget", GOOD if var >= 0 else BAD
        fig.text(x + 0.012, 0.785, s, fontsize=11, weight="bold", color=col)

    # revenue columns
    panel(fig, 0.02, 0.405, 0.465, 0.34, "Revenue by quarter: budget vs actual / forecast")
    ax = fig.add_axes([0.06, 0.445, 0.41, 0.24], facecolor=CARD)
    xs = range(4)
    b = [d[(i + 1, "revenue")][1] for i in xs]
    a = [d[(i + 1, "revenue")][0] for i in xs]
    ax.bar([x - 0.19 for x in xs], b, 0.36, color=BUD, label="Budget")
    for x in xs:
        ax.bar(x + 0.19, a[x], 0.36, color=ACT if x < 2 else FC,
               hatch=None if x < 2 else "//", edgecolor="white", lw=0)
        v = a[x] - b[x]
        ax.text(x + 0.19, a[x] * 1.01, f"{v:+,.0f}", ha="center", fontsize=10,
                color=GOOD if v >= 0 else BAD, weight="bold")
    ax.set_xticks(list(xs), ["Q1 · Act", "Q2 · Act", "Q3 · Fcst", "Q4 · Fcst"], fontsize=10)
    lo = min(b + a) * 0.9
    ax.set_ylim(0, max(b + a) * 1.12)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v/1000:,.0f}B")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0)
    ax.bar([0], [0], color=ACT, label="Actual"); ax.bar([0], [0], color=FC, hatch="//", label="Forecast")
    ax.legend(loc="upper right", frameon=False, fontsize=9.5, ncol=3, bbox_to_anchor=(1, 1.13))

    # op margin line
    panel(fig, 0.495, 0.405, 0.24, 0.34, "Operating margin %")
    ax = fig.add_axes([0.525, 0.445, 0.195, 0.24], facecolor=CARD)
    om_b = [d[(i + 1, "operating_income")][1] / d[(i + 1, "revenue")][1] * 100 for i in xs]
    om_a = [d[(i + 1, "operating_income")][0] / d[(i + 1, "revenue")][0] * 100 for i in xs]
    ax.plot(xs, om_b, color=BUD, lw=2.5, marker="o", label="Budget")
    ax.plot([0, 1], om_a[:2], color=ACT, lw=2.5, marker="o", label="Actual")
    ax.plot([1, 2, 3], om_a[1:], color=FC, lw=2.5, marker="o", ls="--", label="Forecast")
    ax.set_xticks(list(xs), ["Q1", "Q2", "Q3", "Q4"], fontsize=10)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.tick_params(length=0)
    ax.legend(frameon=False, fontsize=9, loc="lower left")

    # OI variance by quarter
    panel(fig, 0.745, 0.405, 0.235, 0.34, "Op income variance ($M)")
    ax = fig.add_axes([0.775, 0.445, 0.19, 0.24], facecolor=CARD)
    fv = [d[(i + 1, "operating_income")][2] for i in xs]
    ax.bar(xs, fv, 0.55, color=[GOOD if v >= 0 else BAD for v in fv])
    ax.axhline(0, color=MUTED, lw=1)
    for x, v in zip(xs, fv):
        ax.text(x, v + (8 if v >= 0 else -8), f"{v:+,.0f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=10, color=INK2)
    ax.set_xticks(list(xs), ["Q1", "Q2", "Q3", "Q4"], fontsize=10)
    m = max(abs(v) for v in fv) * 1.35
    ax.set_ylim(-m, m)
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0); ax.set_yticks([])

    # matrix
    panel(fig, 0.02, 0.03, 0.465, 0.355, "Variance matrix (fav +)")
    lines = [("revenue", "Revenue"), ("gross_profit", "Gross profit"), ("opex", "Operating expenses"),
             ("operating_income", "Operating income"), ("net_income", "Net income")]
    cols = ["Q1", "Q2", "Q3", "Q4", "FY Budget", "FY Outlook", "FY Var"]
    cx = [0.165, 0.205, 0.245, 0.285, 0.35, 0.412, 0.468]
    y0 = 0.325
    for c, x in zip(cols, cx):
        fig.text(x, y0, c, ha="right", fontsize=10, weight="bold", color=INK2)
    for r, (k, lab) in enumerate(lines):
        y = y0 - 0.045 * (r + 1)
        fig.text(0.032, y, lab, fontsize=10.5, color=INK)
        for i in range(4):
            v = d[(i + 1, k)][2]
            fig.text(cx[i], y, f"{v:+,.0f}", ha="right", fontsize=10.5,
                     color=GOOD if v >= 0 else BAD)
        fig.text(cx[4], y, f"{o[k][0]:,.0f}", ha="right", fontsize=10.5)
        fig.text(cx[5], y, f"{o[k][3]:,.0f}", ha="right", fontsize=10.5)
        fig.text(cx[6], y, f"{o[k][4]:+,.0f}", ha="right", fontsize=10.5, weight="bold",
                 color=GOOD if o[k][4] >= 0 else BAD)
    fig.text(0.032, 0.045, "Opex is derived (gross profit − operating income).", fontsize=9, color=MUTED)

    # commentary
    panel(fig, 0.495, 0.03, 0.485, 0.355, "Management explanation")
    rows = con.execute("SELECT 1").fetchall()
    return fig


if __name__ == "__main__":
    import openpyxl
    wb = openpyxl.load_workbook("fpa_model.xlsx")
    ws = wb["commentary"]
    com = [r for r in ws.iter_rows(min_row=2, values_only=True)]
    for tk in ("HD", "LOW"):
        fig = build(tk)
        y = 0.325
        for t, rank, direc, lab, per, var, text in [c for c in com if c[0] == tk]:
            col = GOOD if direc == "Favourable" else BAD
            fig.text(0.507, y, f"{direc} · {lab} · {per} · {var:+,.0f}M", fontsize=10.5, weight="bold", color=col)
            short = text.split(". ")
            body = ". ".join(short[:2]).rstrip(".") + "."
            wrapped = textwrap.wrap(body, 108)[:3]
            for j, line in enumerate(wrapped):
                fig.text(0.507, y - 0.024 * (j + 1), line, fontsize=9.3, color=INK2)
            y -= 0.024 * (len(wrapped) + 1) + 0.014
        fig.savefig(f"figures/dashboard_mockup_{tk}.png", facecolor=SURF)
        plt.close(fig)
    print("ok")
