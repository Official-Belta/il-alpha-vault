#!/usr/bin/env python3
"""Build dashboard: embed latest metrics.csv into index.html"""
from pathlib import Path

ROOT = Path(__file__).parent
CSV = ROOT.parent.parent / "keeper" / "metrics.csv"
TEMPLATE = ROOT / "index.html"
OUTPUT = ROOT / "dashboard.html"

csv_data = CSV.read_text() if CSV.exists() else ""
template = TEMPLATE.read_text()
html = template.replace("CSVDATA", csv_data)
OUTPUT.write_text(html)

rows = len(csv_data.strip().split("\n")) - 1 if csv_data else 0
print(f"Dashboard built: {OUTPUT} ({rows} data rows)")
