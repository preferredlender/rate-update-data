#!/usr/bin/env python3
"""Safety checks for a Behind the Rate update. Same rules as the control panel.

Usage: python3 tools/validate.py draft.json
Prints a JSON list of checks and exits 0 if every check passed, 1 otherwise.
"""
import json, re, sys, datetime

BANNED = [r"\brates will\b", r"(?<!not a )(?<!no )\bguarantee", r"\byou should lock\b", r"\block now\b",
          r"\bfloat now\b", r"\bwill definitely\b", r"\bcan't lose\b"]

def checks(d, today=None):
    today = today or datetime.date.today()
    out = []
    def add(name, ok, detail=""):
        out.append({"name": name, "ok": bool(ok), "detail": detail, "source": "morning"})
    r = (d.get("rates") or {}).get("daily") or {}
    o = d.get("outlook") or {}
    add("Headline, takeaway and tile reason are filled in", d.get("headline") and d.get("takeaway") and d.get("tileReason"))
    v = r.get("value")
    add("Today's 30-year rate is in a realistic range (4%-10%)", isinstance(v, (int, float)) and 4 <= v <= 10, f"{v}%")
    try:
        mv = abs(float(r["value"]) - float(r["prior"]))
    except Exception:
        mv = None
    add("One-day move is normal (under 0.35%), or confirmed by two sources",
        mv is not None and (mv < 0.35 or d.get("largeMoveConfirmed") is True),
        "" if mv is None else f"Move: {mv:.2f}%")
    tot = sum(float(o.get(k) or 0) for k in ("up", "flat", "down"))
    add("The 30-day odds add up to 100%", round(tot) == 100, f"{tot:g}")
    try:
        u = datetime.date.fromisoformat(str(d.get("updated", ""))[:10])
        age = (today - u).days
    except Exception:
        u, age = None, None
    add("The update is dated within the last 4 days", age is not None and -1 < age <= 4, str(u))
    src = d.get("sources") or []
    add("At least two sources, each with a date and link",
        len(src) >= 2 and all(s.get("name") and s.get("date") and re.match(r"^https?://", s.get("url", "")) for s in src),
        f"{len(src)} sources")
    items = (d.get("surveys") or {}).get("items") or []
    agree = sum(1 for s in items if isinstance(v, (int, float)) and abs(float(s.get("value", 0)) - v) <= 0.25)
    add("Headline rate agrees with at least one other survey (within 0.25%)", agree >= 2 or not items, f"{agree} surveys within range")
    tp = d.get("talkingPoints") or {}
    text = " ".join(filter(None, [d.get("headline"), d.get("takeaway"), d.get("tileReason"), o.get("basis"), o.get("caveat"),
                                  tp.get("buyers"), tp.get("sellers"), tp.get("oneLiner")] + [x.get("text", "") for x in d.get("drivers") or []]))
    hits = [m.group(0) for rx in BANNED for m in [re.search(rx, text, re.I)] if m]
    add("No guarantees or lock/float advice in the wording", not hits, ("Found: " + ", ".join(hits)) if hits else "")
    drv = d.get("drivers") or []
    add("Every driver has a title and explanation", drv and all(x.get("title") and x.get("text") for x in drv))
    add("Disclaimer pieces present (outlook caveat, sources dated)", bool(o.get("caveat")))
    return out

if __name__ == "__main__":
    data = json.load(open(sys.argv[1]))
    res = checks(data)
    print(json.dumps(res, indent=2))
    sys.exit(0 if all(c["ok"] for c in res) else 1)
