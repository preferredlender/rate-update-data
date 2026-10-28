#!/usr/bin/env python3
"""Maintains market-detail.json (rate gap tracker + jumbo vs. conforming) for Behind the Rate.

Usage (morning run, every trading day):
  python3 tools/market_detail.py --date 2026-10-27 --ten 4.98 --conf 7.21 --jumbo 7.30 --rate-data rate-data.json

  --date   date of the observations (the latest FRED observation date, not today's date)
  --ten    10-year Treasury close for that date (FRED DGS10)
  --conf   Optimal Blue 30-year conforming index for that date (FRED OBMMIC30YF)
  --jumbo  Optimal Blue 30-year jumbo index for that date (FRED OBMMIJUMBO30YF)
  Any of --ten/--conf/--jumbo may be left out if that series has no value for the date.

What it does:
  1. Adds the day to `daily` (fills blanks on an existing day, never changes a value already there),
     keeps the last 400 days.
  2. Recomputes every month from the daily log and the Freddie Mac weekly values in rate-data.json:
     finished months are written once and then left alone; the current month is marked partial
     and refreshed. Freddie Mac monthly = average of that month's weekly values (the same method FRED uses).
  3. Prints the checks as JSON. Exit code 1 if a value is outside a realistic range (nothing is written then).
"""
import argparse, datetime, json, sys
from statistics import mean

PATH = "market-detail.json"
RANGES = {"ten": (0.5, 10), "conf": (2, 12), "jumbo": (2, 12)}

def r3(x): return round(x, 3)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--ten", type=float)
    ap.add_argument("--conf", type=float)
    ap.add_argument("--jumbo", type=float)
    ap.add_argument("--rate-data", default="rate-data.json")
    ap.add_argument("--file", default=PATH)
    a = ap.parse_args()
    datetime.date.fromisoformat(a.date)

    checks = []
    def add(name, ok, detail=""): checks.append({"name": name, "ok": bool(ok), "detail": detail, "source": "market-detail"})

    obs = {k: getattr(a, k) for k in ("ten", "conf", "jumbo") if getattr(a, k) is not None}
    for k, v in obs.items():
        lo, hi = RANGES[k]
        add(f"{k} value in a realistic range ({lo}%-{hi}%)", lo <= v <= hi, f"{v}%")
    if "conf" in obs and "jumbo" in obs:
        add("Jumbo and conforming within 1.5% of each other", abs(obs["jumbo"] - obs["conf"]) < 1.5,
            f"{obs['jumbo'] - obs['conf']:+.3f}%")
    if "ten" in obs and "conf" in obs:
        gap = obs["conf"] - obs["ten"]
        add("Rate gap in a realistic range (0.5%-4%)", 0.5 <= gap <= 4, f"{gap:.2f}%")
    if not all(c["ok"] for c in checks):
        print(json.dumps(checks, indent=2)); sys.exit(1)

    d = json.load(open(a.file))
    rows = {r["date"]: r for r in d["daily"]}
    row = rows.setdefault(a.date, {"date": a.date, "ten": None, "conf": None, "jumbo": None})
    for k, v in obs.items():
        if row.get(k) is None:
            row[k] = v
        elif abs(row[k] - v) > 1e-9:
            add(f"{k} for {a.date} already recorded; kept the original", True, f"kept {row[k]}, ignored {v}")
    cutoff = (datetime.date.fromisoformat(a.date) - datetime.timedelta(days=400)).isoformat()
    d["daily"] = sorted((r for r in rows.values() if r["date"] >= cutoff), key=lambda r: r["date"])

    # Freddie Mac weekly values: what this file already used, plus the trend in rate-data.json
    try:
        pts = json.load(open(a.rate_data)).get("trend", {}).get("points", [])
    except Exception:
        pts = []
    fred = d.setdefault("freddieWeekly", [])
    have = {p["date"] for p in fred}
    for p in pts:
        if p["date"] not in have and isinstance(p.get("value"), (int, float)):
            fred.append({"date": p["date"], "value": p["value"]})
    fred.sort(key=lambda p: p["date"])
    d["freddieWeekly"] = [p for p in fred if p["date"] >= cutoff]

    cur = a.date[:7]
    def month_avg(month, key):
        v = [r[key] for r in d["daily"] if r["date"].startswith(month) and r.get(key) is not None]
        return r3(mean(v)) if v else None
    def freddie_avg(month):
        v = [p["value"] for p in d["freddieWeekly"] if p["date"].startswith(month)]
        return round(mean(v), 2) if v else None

    months = sorted({r["date"][:7] for r in d["daily"]})
    sm = {m["date"]: m for m in d["spreadMonthly"]}
    pm = {m["date"]: m for m in d["productsMonthly"]}
    for m in months:
        partial = m >= cur
        s = sm.get(m)
        if s is None or s.get("partial"):
            rate, ten = freddie_avg(m), month_avg(m, "ten")
            if rate is not None and ten is not None:
                sm[m] = {"date": m, "rate": rate, "ten": round(ten, 2)}
                if partial: sm[m]["partial"] = True
        p = pm.get(m)
        if p is None or p.get("partial"):
            c, j = month_avg(m, "conf"), month_avg(m, "jumbo")
            if c is not None and j is not None:
                pm[m] = {"date": m, "conf": c, "jumbo": j}
                if partial: pm[m]["partial"] = True
    d["spreadMonthly"] = sorted(sm.values(), key=lambda x: x["date"])
    d["productsMonthly"] = sorted(pm.values(), key=lambda x: x["date"])
    d["updated"] = datetime.date.today().isoformat()

    latest = next((r for r in reversed(d["daily"]) if r.get("ten") is not None and r.get("conf") is not None), None)
    if latest:
        add("Today's rate gap computed", True, f"{latest['date']}: {latest['conf'] - latest['ten']:.2f}% (normal {d['normalGap']['avg']}%)")
    json.dump(d, open(a.file, "w"), indent=1)
    print(json.dumps(checks, indent=2))

if __name__ == "__main__":
    main()
