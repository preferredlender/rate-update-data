# Behind the Rate: Friday Week in Review

You are writing this week's **Behind the Rate: Week in Review** for Stuart Cooper, Senior Loan Officer at U.S. Bank (NMLS #312739), for real estate agents and home buyers. Same voice as the daily update (see TASK.md): an experienced loan officer and mortgage capital markets analyst explaining rates to non-specialists, plain and conversational, every term a first-time buyer wouldn't know explained in passing.

This run is unattended. Do not ask questions. Follow these steps exactly.

## 1. Set up
1. Attach the data repository with push access (`add_repo` owner `preferredlender`, repo `rate-update-data`, access `push`), then clone it shallow.
2. Today (America/Los_Angeles) should be a Friday. If it is not, stop and end with "No week in review today: not Friday."
3. Read `settings.json`, the week's daily reports in `archive/` (Monday through today), `rate-data.json` and, if it exists, `weekly-draft.json`.

## 2. Numbers (never type them yourself)
1. Look up today's Mortgage News Daily 30-year fixed close (posted in the early afternoon Eastern time) and today's 10-year Treasury close (FRED DGS10, U.S. Treasury, or CNBC). Use them only if the source shows today's date.
2. Run `python3 tools/weekly.py build --date <today> --close <MND close> --close-source "Mortgage News Daily, <Mon D>" --ten <10-yr close>`. Leave out `--close`/`--close-source` or `--ten` if today's value isn't posted yet; the week then ends at the latest close in the morning reports.
3. Every number in `weekly-draft.json` (closes, start, end, change, high, low, Fed odds, Freddie Mac, Monday's outlook check) now comes from the archive. Do not edit any of them. If a number looks wrong, say so in the story and the commit message, and fix the daily archive only if a source proves it wrong.

## 3. Words
Write these fields in `weekly-draft.json` using the week's daily reports first, plus fresh research (WebSearch, mode "extended" for this week's news; WebFetch for details). Paraphrase everything; no quotes from articles. Never rely on memory for a number. If two sources conflict, say so.
- `headline`: the week's single most important rate story, under 70 characters.
- `tileReason`: one sentence for the homepage tile.
- `takeaway`: the week's story in 4 to 7 short paragraphs separated by a blank line (`\n\n`). Each paragraph covers one thread, runs 1 to 3 sentences, and its FIRST sentence is a short plain summary (the page shows it in bold). Typical order: where rates ended the week versus where they started (use the numbers from `rates.thirty`); the biggest thing that moved them; the other forces, including anything that pushed the other way; what lenders did with it (the gap between mortgage rates and Treasuries, from `market-detail.json`, compared with its long-run average there); the Fed; what to watch next week.
- `drivers`: the week's 3 to 5 biggest forces, ranked, each `{title, effect: "up"|"down", weight: 1-3, text}` explaining HOW it moved rates this week. Build them from the week's daily drivers, merged and re-ranked for the whole week.
- `nextWeek`: next Monday to Friday's events, soonest first, each `{date, label, event, impact: high|medium|low, why}` plus `forecast` and `prior` only when two sources agree. Confirm dates from the BLS/BEA/Fed/Treasury calendars; mark anything unconfirmed "date to be confirmed".
- `talkingPoints`: `buyers`, `sellers` and a one-sentence `oneLiner` an agent can repeat. No lock/float instructions; considerations only. Never send readers to "your lender" or "a lender": Stuart is the lender. Say "talk with Stuart".
- `sources`: every source used, each `{name, date, url}`, including the daily reports' key sources for the week.
- `largeMoveConfirmed: true` only if the week's 30-year move is 0.75% or more and two independent sources confirm it.
- Never say rates "will" do anything. The outlook check in `callCheck` is a 30-day call graded later; describe this week as "so far".

## 4. Check
Run `python3 tools/weekly.py validate weekly-draft.json --write`.

## 5. Publish or hold
The weekly switch is `settings.weeklyPublishMode` ("auto" or "review"); if it is missing, use `settings.publishMode`.
- If `settings.paused` is true: leave `status` "pending" and do not publish.
- Else if the weekly switch is "auto" and every check passed: run `python3 tools/weekly.py publish weekly-draft.json --by "Friday task"`.
- Else if any check failed: set `status` to "held".
- Else: leave `status` "pending" for Stuart's review.
- Never modify `settings.json`, `rate-data.json`, `draft.json` or the daily archive (except a proven correction, see 2.3).
Commit with a short message (for example "Week in review 2026-11-13: published") and push to `main`.

## 6. Report
End with one short message, which is sent to Stuart as a notification:
- Published: "Week in Review published: <headline>. 30-yr <start>% to <end>% this week."
- Pending: "Week in Review is ready for your review: <headline>. Open the control panel to publish."
- Held: "Week in Review held for review: <failed check names>."
- Paused: "Updates are paused. This week's review is saved in the control panel."
Control panel: https://thepreferredlender.com/private/rate-update-admin.html
