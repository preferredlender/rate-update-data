# rate-update-data

Data for the Daily Rate Update on thepreferredlender.com.

- `rate-data.json` — the current update (rewritten each weekday morning)
- `archive/` — dated copies of the last 30 days, plus `index.json`
- `market-detail.json` — rate gap tracker and jumbo vs. conforming history (updated each morning by `tools/market_detail.py`; FRED data)
- `settings.json` — Stuart's on/off switches for page sections (the morning task never overwrites this file)

Public commentary only. Nothing private is stored here.
