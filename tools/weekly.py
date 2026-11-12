#!/usr/bin/env python3
"""Behind the Rate: Week in Review.

Every number in the weekly edition is computed here from the daily reports in archive/,
so the week can never disagree with what was published day by day. The Friday task writes
only the words (headline, story, drivers, next week, talking points, sources).

  python3 tools/weekly.py build    --date 2026-11-13 [--close 7.25 --close-source "Mortgage News Daily, Nov 13"] [--ten 4.98]
        Creates or refreshes weekly-draft.json for the Mon-Fri week containing --date.
        Numbers are recomputed; words already written for the same week are kept.
        --close / --ten add Friday's own closing values when the morning reports don't have them yet.
  python3 tools/weekly.py validate weekly-draft.json [--write]
        Prints the safety checks as JSON; exit 0 if all passed. --write stores them in the draft.
  python3 tools/weekly.py publish  weekly-draft.json --by "Friday task" [--force]
        Writes weekly-review.json, weekly/<weekEnd>.json and weekly/index.json (keeps 13 weeks).
"""
import argparse, datetime, glob, json, os, re, sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LA = ZoneInfo("America/Los_Angeles")
KEEP_WEEKS = 13
FLAT_BAND = 0.125
COMPUTED = ["kind", "schemaVersion", "weekStart", "weekEnd", "weekLabel", "direction", "closes", "tenCloses",
            "days", "rates", "fedOdds", "callCheck", "fridayClose", "fridayTen"]
WORDS = ["headline", "tileReason", "takeaway", "drivers", "nextWeek", "talkingPoints", "sources", "largeMoveConfirmed"]
BANNED = [r"\brates will\b", r"(?<!not a )(?<!no )\bguarantee", r"\byou should lock\b", r"\block now\b",
          r"\bfloat now\b", r"\bwill definitely\b", r"\bcan't lose\b"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def P(*a): return os.path.join(ROOT, *a)
def load(p):
    with open(p) as f: return json.load(f)
def save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f: json.dump(d, f, indent=2); f.write("\n")
def D(s): return datetime.date.fromisoformat(str(s)[:10])
def mdy(d): return f"{MON[d.month-1]} {d.day}"
def label(d): return f"{WD[d.weekday()]}, {mdy(d)}"
def r2(v): return round(float(v) + 0.0, 2)


def week_of(any_day):
    d = D(any_day)
    start = d - datetime.timedelta(days=d.weekday())
    return start, start + datetime.timedelta(days=4)


def week_label(s, e):
    if s.month == e.month: return f"Week of {MON[s.month-1]} {s.day}–{e.day}, {e.year}"
    return f"Week of {mdy(s)} – {mdy(e)}, {e.year}"


def compute(any_day, friday_close=None, friday_ten=None):
    """All numbers for the week, from archive/<date>.json plus optional Friday closes."""
    ws, we = week_of(any_day)
    reports = []
    for p in sorted(glob.glob(P("archive", "????-??-??.json"))):
        day = D(os.path.basename(p)[:10])
        if ws - datetime.timedelta(days=10) <= day <= we:
            reports.append((day, load(p)))
    inweek = [(d, r) for d, r in reports if ws <= d <= we]
    if len(inweek) < 2:
        raise SystemExit(f"Only {len(inweek)} daily report(s) for {week_label(ws, we)}; need at least 2.")

    closes, tens = {}, {}
    for day, r in reports:                                   # later reports win
        dl = (r.get("rates") or {}).get("daily") or {}
        if dl.get("asOf") and isinstance(dl.get("value"), (int, float)):
            closes[dl["asOf"][:10]] = float(dl["value"])
        for p in ((r.get("tenYearDaily") or {}).get("points") or []):
            if not p.get("intraday") and isinstance(p.get("value"), (int, float)):
                tens[p["date"][:10]] = float(p["value"])
    if friday_close: closes[friday_close["date"]] = float(friday_close["value"])
    if friday_ten: tens[friday_ten["date"]] = float(friday_ten["value"])

    def span(series, what):
        before = sorted(k for k in series if D(k) < ws)
        upto = sorted(k for k in series if D(k) <= we)
        if not before or not upto or D(upto[-1]) < ws:
            raise SystemExit(f"Not enough {what} closes to cover {week_label(ws, we)}.")
        s, e = before[-1], upto[-1]
        pts = [{"date": k, "value": r2(series[k])} for k in sorted(series) if s <= k <= e]
        vals = [p["value"] for p in pts]
        return {"start": r2(series[s]), "startDate": s, "end": r2(series[e]), "endDate": e,
                "change": r2(series[e] - series[s]), "high": max(vals), "low": min(vals)}, pts

    thirty, cpts = span(closes, "30-year")
    ten, tpts = span(tens, "10-year")
    thirty["source"] = "Mortgage News Daily 30-year fixed index, daily closes"
    ten["source"] = "10-year Treasury yield, daily closes (from each morning's report)"

    first, last = inweek[0][1], inweek[-1][1]
    wk = (last.get("rates") or {}).get("weekly") or {}
    fo1, fo2 = first.get("fedOdds") or {}, last.get("fedOdds") or {}

    def odds(f, day):
        lo, hi = f.get("afterLow"), f.get("afterHigh")
        return {"low": lo, "high": hi, "date": day.isoformat(), "title": f.get("title", "")}
    fed = {"title": fo2.get("title", ""), "start": odds(fo1, inweek[0][0]), "end": odds(fo2, inweek[-1][0]),
           "sameMeeting": fo1.get("title") == fo2.get("title")}

    o = first.get("outlook") or {}
    base = float(o.get("base", thirty["start"]))
    move = r2(thirty["end"] - base)
    bucket = "higher" if move > FLAT_BAND else "lower" if move < -FLAT_BAND else "same"
    probs = {"higher": o.get("up", 0), "same": o.get("flat", 0), "lower": o.get("down", 0)}
    leading = max(probs, key=lambda k: probs[k])
    made = inweek[0][0]
    call = {"made": made.isoformat(), "base": r2(base), "up": o.get("up"), "flat": o.get("flat"), "down": o.get("down"),
            "flatBand": FLAT_BAND, "end": thirty["end"], "endDate": thirty["endDate"], "move": move,
            "soFar": bucket, "leaning": leading, "gradeOn": (made + datetime.timedelta(days=30)).isoformat()}

    days = []
    for day, r in inweek:
        dl = (r.get("rates") or {}).get("daily") or {}
        days.append({"date": day.isoformat(), "label": label(day), "headline": r.get("headline", ""),
                     "direction": r.get("direction", "flat"), "rate": dl.get("value"), "rateAsOf": dl.get("asOf")})

    ch = thirty["change"]
    return {
        "kind": "weekly", "schemaVersion": 1,
        "weekStart": ws.isoformat(), "weekEnd": we.isoformat(), "weekLabel": week_label(ws, we),
        "direction": "up" if ch > 0.03 else "down" if ch < -0.03 else "flat",
        "closes": cpts, "tenCloses": tpts, "days": days,
        "rates": {"thirty": thirty, "tenYear": ten,
                  "freddie": {"value": wk.get("value"), "prior": wk.get("prior"), "priorLabel": wk.get("priorLabel"),
                              "asOf": wk.get("asOf"), "source": wk.get("source", "Freddie Mac PMMS")}},
        "fedOdds": fed, "callCheck": call,
        "fridayClose": friday_close, "fridayTen": friday_ten,
    }


def now_stamp():
    n = datetime.datetime.now(LA)
    h = n.strftime("%I").lstrip("0")
    return n.isoformat(timespec="seconds"), f"{n.strftime('%A, %B')} {n.day}, {n.year} · {h}:{n.strftime('%M %p')} PT"


def cmd_build(a):
    fc = {"date": week_of(a.date)[1].isoformat(), "value": a.close, "source": a.close_source or ""} if a.close is not None else None
    ft = {"date": week_of(a.date)[1].isoformat(), "value": a.ten} if a.ten is not None else None
    nums = compute(a.date, fc, ft)
    path = P("weekly-draft.json")
    old = load(path) if os.path.exists(path) else {}
    d = {}
    if old.get("weekStart") == nums["weekStart"]:
        d = {k: v for k, v in old.items() if k in WORDS}
    d.update(nums)
    d["updated"], d["updatedLabel"] = now_stamp()
    d.setdefault("headline", ""); d.setdefault("tileReason", ""); d.setdefault("takeaway", "")
    d.setdefault("drivers", []); d.setdefault("nextWeek", []); d.setdefault("sources", [])
    d.setdefault("talkingPoints", {"buyers": "", "sellers": "", "oneLiner": ""})
    d["status"] = "pending"; d["checks"] = []
    save(path, d)
    t = nums["rates"]["thirty"]
    print(f"{nums['weekLabel']}: 30-yr {t['start']:.2f}% ({t['startDate']}) -> {t['end']:.2f}% ({t['endDate']}), "
          f"{'+' if t['change'] >= 0 else ''}{t['change']:.2f}. {len(nums['days'])} daily reports. Wrote weekly-draft.json")


def checks(d, today=None):
    today = today or datetime.datetime.now(LA).date()
    out = []
    def add(name, ok, detail=""): out.append({"name": name, "ok": bool(ok), "detail": detail, "source": "weekly"})
    try:
        nums = compute(d.get("weekStart"), d.get("fridayClose"), d.get("fridayTen"))
        diff = [k for k in COMPUTED if json.dumps(nums.get(k), sort_keys=True) != json.dumps(d.get(k), sort_keys=True)]
        add("Every number matches the daily reports in the archive", not diff, ("Changed: " + ", ".join(diff)) if diff else "")
    except SystemExit as e:
        add("Every number matches the daily reports in the archive", False, str(e))
    t = (d.get("rates") or {}).get("thirty") or {}
    add("The week's 30-year rates are in a realistic range (4%-10%)",
        all(isinstance(t.get(k), (int, float)) and 4 <= t[k] <= 10 for k in ("start", "end")), f"{t.get('start')} -> {t.get('end')}")
    mv = abs(t.get("change") or 0)
    add("The week's move is normal (under 0.75%), or confirmed by two sources", mv < 0.75 or d.get("largeMoveConfirmed") is True, f"Move: {mv:.2f}%")
    fc = d.get("fridayClose")
    add("Friday's close (if added) has a source", not fc or bool(fc.get("source")), "")
    add("Headline, story and tile reason are filled in", d.get("headline") and d.get("takeaway") and d.get("tileReason"))
    add("Headline is under 70 characters", len(d.get("headline", "")) < 70, f"{len(d.get('headline', ''))} characters")
    paras = [p for p in str(d.get("takeaway", "")).split("\n\n") if p.strip()]
    add("The story has 4 to 7 paragraphs", 4 <= len(paras) <= 7, f"{len(paras)} paragraphs")
    dr = d.get("drivers") or []
    add("3 to 5 drivers, each with a title, effect, weight and explanation",
        3 <= len(dr) <= 5 and all(x.get("title") and x.get("text") and x.get("effect") in ("up", "down") and x.get("weight") in (1, 2, 3) for x in dr),
        f"{len(dr)} drivers")
    nw = d.get("nextWeek") or []
    add("Next week's calendar has dated events", len(nw) >= 1 and all(x.get("label") and x.get("event") for x in nw), f"{len(nw)} events")
    tp = d.get("talkingPoints") or {}
    add("Buyers, sellers and one-sentence talking points are filled in", tp.get("buyers") and tp.get("sellers") and tp.get("oneLiner"))
    src = d.get("sources") or []
    add("At least two sources, each with a date and link",
        len(src) >= 2 and all(s.get("name") and s.get("date") and re.match(r"^https?://", s.get("url", "")) for s in src), f"{len(src)} sources")
    try:
        age = (today - D(d.get("updated"))).days
    except Exception:
        age = None
    add("Dated within the last 4 days", age is not None and -1 < age <= 4, str(d.get("updated", ""))[:10])
    txt = " ".join([d.get("headline", ""), d.get("takeaway", ""), d.get("tileReason", "")] + [x.get("text", "") for x in dr] +
                   [tp.get("buyers", ""), tp.get("sellers", ""), tp.get("oneLiner", "")] + [x.get("why", "") for x in nw])
    hits = [m.group(0) for rx in BANNED for m in [re.search(rx, txt, re.I)] if m]
    add("No guarantees or lock/float advice in the wording", not hits, ("Found: " + ", ".join(hits)) if hits else "")
    add("Never sends readers to another lender", not re.search(r"\b(your|a|another) lender\b", txt, re.I), "")
    return out


def cmd_validate(a):
    path = a.file if os.path.isabs(a.file) else P(a.file)
    d = load(path); c = checks(d)
    if a.write:
        d["checks"] = c; save(path, d)
    print(json.dumps(c, indent=2))
    sys.exit(0 if all(x["ok"] for x in c) else 1)


def cmd_publish(a):
    path = a.file if os.path.isabs(a.file) else P(a.file)
    d = load(path); c = checks(d)
    if not all(x["ok"] for x in c) and not a.force:
        print("Not published. Failed: " + "; ".join(x["name"] for x in c if not x["ok"])); sys.exit(1)
    d["checks"] = c; d["status"] = "published"; d["publishedBy"] = a.by
    d["publishedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    save(P("weekly-review.json"), d)
    save(P("weekly", d["weekEnd"] + ".json"), d)
    ip = P("weekly", "index.json")
    idx = load(ip) if os.path.exists(ip) else {"keepWeeks": KEEP_WEEKS, "weeks": []}
    t = d["rates"]["thirty"]
    idx["weeks"] = [w for w in idx.get("weeks", []) if w.get("weekEnd") != d["weekEnd"]]
    idx["weeks"].append({"weekEnd": d["weekEnd"], "weekStart": d["weekStart"], "weekLabel": d["weekLabel"],
                         "headline": d["headline"], "direction": d["direction"], "start": t["start"], "end": t["end"]})
    idx["weeks"].sort(key=lambda w: w["weekEnd"], reverse=True)
    for w in idx["weeks"][KEEP_WEEKS:]:
        try: os.remove(P("weekly", w["weekEnd"] + ".json"))
        except FileNotFoundError: pass
    idx["weeks"] = idx["weeks"][:KEEP_WEEKS]; idx["keepWeeks"] = KEEP_WEEKS
    save(ip, idx)
    save(path, d)
    print(f"Published {d['weekLabel']}: {d['headline']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    b = sp.add_parser("build"); b.add_argument("--date", required=True); b.add_argument("--close", type=float)
    b.add_argument("--close-source"); b.add_argument("--ten", type=float); b.set_defaults(f=cmd_build)
    v = sp.add_parser("validate"); v.add_argument("file"); v.add_argument("--write", action="store_true"); v.set_defaults(f=cmd_validate)
    p = sp.add_parser("publish"); p.add_argument("file"); p.add_argument("--by", default="Friday task")
    p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_publish)
    a = ap.parse_args(); a.f(a)
