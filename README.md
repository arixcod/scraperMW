# MandirWiki Multi-Source Scraper v6 — Context-Aware Internet Research

## What this version does
- Generates a Quick JSON first from the websites supplied by the user.
- Runs deterministic context-aware cleanup after reconciliation.
- `gufaTimings` is kept only when there is evidence of a literal cave/gufa with separate visitor timings.
- Non-Aarti access windows are moved out of `aartis` when the schema supports `specialAccessTimings`.
- Restrictions such as photography bans are treated as visitor rules, not facilities.
- Historical/mythological facts are removed from prerequisites.
- Optional ritual/service bookings are not treated as mandatory entry registration.
- Missing-field detection skips contextually inapplicable sections.
- If relevant values are still missing, the UI asks the user whether they want to search the wider internet.
- Wider-internet lookup uses the existing OpenAI API key and the Responses API `web_search` tool.
- Internet lookup is restricted to the exact missing paths and cannot overwrite populated scraper values.
- Unsupported/conflicting facts remain null or empty instead of being guessed.

## Removed from this version
- Google Maps Platform credentials and enrichment.
- Google Routes integration.
- Uber API credentials, fare estimates and deep links.
- Ola API credentials, fare estimates and deep links.
- Google-specific fields such as `googleMapsUrl` in the recommended v3 schema.
- Provider-only `nearbyServices` and `travelUtilities` sections from the recommended v3 schema.

## Credentials
Only the OpenAI API key is required for AI reconciliation and optional web search. The key is entered in the Streamlit sidebar and kept in session state; it is not written to project files.

## Run
```bat
pip install -r requirements.txt
scrapling install
python self_test.py
python -m streamlit run app.py
```

## Recommended flow
1. Select `Use MandirWiki schema v3 (recommended)`.
2. Enter the temple/item name and one or more source websites.
3. Click `Generate Quick JSON`.
4. Review/download the scraper result immediately.
5. If relevant fields remain missing, click `Search Internet for Missing Data` only if you want broader web research.
6. Review the Internet Research fills and source audit before using the final JSON.
