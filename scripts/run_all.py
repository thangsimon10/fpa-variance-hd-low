#!/usr/bin/env python3
"""Rebuild everything from the raw SEC extract. Run from the repo root:
    pip install duckdb openpyxl matplotlib
    python scripts/run_all.py
Creates fpa.duckdb, prints the validation checks, rewrites fpa_model.xlsx."""
import pathlib, subprocess, sys
import duckdb

ROOT = pathlib.Path(__file__).resolve().parent.parent
con = duckdb.connect(str(ROOT / "fpa.duckdb"))
for f in ["01_quarters.sql", "02_budget.sql", "03_forecast.sql"]:
    con.execute((ROOT / "sql" / f).read_text())
    print("ran", f)

checks = con.execute("SELECT check_name, ticker, pass FROM checks ORDER BY 1, 2").fetchall()
for c in checks:
    print(("PASS" if c[2] else "FAIL"), c[1], c[0])
con.close()
if not all(c[2] for c in checks):
    sys.exit("validation failed")

subprocess.run([sys.executable, str(ROOT / "scripts" / "export_model.py")], cwd=ROOT, check=True)
