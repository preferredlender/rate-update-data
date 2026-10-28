#!/usr/bin/env python3
"""Adds one month's value to local-market.json or economy.json.

Usage:
  python3 tools/append_monthly.py local-market.json oc.active 2026-10 4610
  python3 tools/append_monthly.py economy.json cpi 2026-10 3.55

Series keys:
  local-market.json  <geo>.<metric>, geo = oc | la | sd | us, metric = active | dom | price | pending | cuts
  economy.json       cpi | core | pce | unrate | jobs

The month must be the next month after the last one stored (no gaps, no rewriting history).
A value that jumps implausibly from the prior month is refused. Prints OK or the reason; exit 1 on refusal.
"""
import datetime, json, sys

LIMITS = {  # (min, max, max relative change vs prior month) ; None = no relative check
    "active": (0, 5_000_000, 0.45), "dom": (5, 200, 0.6), "price": (50_000, 10_000_000, 0.15),
    "pending": (0, 5_000_000, 0.6), "cuts": (0, 5_000_000, 0.8),
    "cpi": (-3, 15, None), "core": (-3, 15, None), "pce": (-3, 15, None), "unrate": (1, 20, None), "jobs": (-2000, 2000, None),
}

def month_index(start, ym):
    sy, sm = map(int, start.split("-")); y, m = map(int, ym.split("-"))
    return (y - sy) * 12 + (m - sm)

def main():
    path, key, ym, raw = sys.argv[1:5]
    datetime.date.fromisoformat(ym + "-01")
    d = json.load(open(path))
    if "." in key:
        geo, metric = key.split(".")
        arr = d["series"][geo][metric]
    else:
        metric = key
        arr = d["series"][metric]
    value = float(raw)
    if metric in ("active", "dom", "price", "pending", "cuts", "jobs"):
        value = int(round(value))
    want = month_index(d["start"], ym)
    if want != len(arr):
        print(f"REFUSED: {key} has data through month #{len(arr)} after {d['start']}; {ym} is #{want + 1}. Months must be added in order.")
        sys.exit(1)
    lo, hi, rel = LIMITS[metric]
    if not (lo <= value <= hi):
        print(f"REFUSED: {key} {ym} = {value} is outside {lo}..{hi}"); sys.exit(1)
    prev = next((v for v in reversed(arr) if v is not None), None)
    if rel and prev and abs(value - prev) / prev > rel:
        print(f"REFUSED: {key} {ym} = {value} moved more than {int(rel * 100)}% from {prev}"); sys.exit(1)
    arr.append(value)
    d["updated"] = datetime.date.today().isoformat()
    json.dump(d, open(path, "w"), indent=1)
    print(f"OK: {key} {ym} = {value}")

if __name__ == "__main__":
    main()
