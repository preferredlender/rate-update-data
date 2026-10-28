#!/usr/bin/env python3
"""Adds a month of Realtor.com county data (via FRED) to local-market.json.

Usage:
  python3 tools/local_market.py new-month.json

new-month.json looks like:
  {"month": "2026-10",
   "oc": {"active": 4700, "dom": 55, "price": 1285000, "reduced": 1800, "newl": 2100},
   "la": {...}, "sd": {...}, "us": {...}}

Values come from the FRED series pages (latest observation):
  active  ACTLISCOU<area>    dom  MEDDAYONMAR<area>    price  MEDLISPRI<area>
  reduced PRIREDCOU<area>    newl NEWLISCOU<area>      area = 6059 (Orange), 6037 (Los Angeles), 6073 (San Diego), US
Checks: the month is the next one after the latest stored, every value is present and positive,
and each moves less than 40% from the month before. Nothing is written if a check fails.
Months already stored are never changed. Prints the checks as JSON; exit code 1 on failure.
"""
import json, sys

PATH = "local-market.json"
KEYS = ("active", "dom", "price", "reduced", "newl")

def next_month(m):
    y, mo = int(m[:4]), int(m[5:7]) + 1
    return f"{y + (mo > 12):04d}-{(mo - 1) % 12 + 1:02d}"

def main():
    new = json.load(open(sys.argv[1]))
    d = json.load(open(PATH))
    checks = []
    def add(name, ok, detail=""): checks.append({"name": name, "ok": bool(ok), "detail": detail, "source": "local-market"})
    m = new.get("month", "")
    if m <= d["latest"]:
        add("Month is newer than what's stored", False, f"{m} vs stored {d['latest']}; nothing to add")
        print(json.dumps(checks, indent=2)); sys.exit(0)
    add("Month follows the latest stored month", m == next_month(d["latest"]), f"{m} after {d['latest']}")
    for a in d["areas"]:
        v = new.get(a["key"]) or {}
        prev = a["monthly"][-1]
        for k in KEYS:
            x = v.get(k)
            ok = isinstance(x, (int, float)) and x > 0
            if ok and prev.get(k):
                ok = abs(x / prev[k] - 1) < 0.40
            add(f"{a['name']}: {k}", ok, f"{x} (prior {prev.get(k)})")
    if not all(c["ok"] for c in checks):
        print(json.dumps(checks, indent=2)); sys.exit(1)
    for a in d["areas"]:
        v = new[a["key"]]
        a["monthly"].append({"m": m, **{k: v[k] for k in KEYS}})
    d["latest"] = m
    import datetime
    d["updated"] = datetime.date.today().isoformat()
    json.dump(d, open(PATH, "w"), indent=1)
    print(json.dumps(checks, indent=2))

if __name__ == "__main__":
    main()
