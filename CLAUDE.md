# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Python/Flask port of a C# SMDR (Station Message Detail Recording) telephony logger. Two services share a single SQLite database:

- **TCP SMDR server** (`server/tcpsmdrserver.py`, port 3000) — accepts CSV call records from a PBX and persists them.
- **Flask web app** (`app/main.py`, port 5000) — search UI, statistics dashboard, and JSON APIs over the same database.

Code, log output, and most prose comments are in Italian. Preserve that language when editing existing strings/comments unless the user asks otherwise.

## Running the app

```bash
# Both services in one process (Flask in main thread, TCP server in background thread)
python run.py

# Or run them separately
python -m app.main                  # Flask only
python server/tcpsmdrserver.py      # TCP server only

# Docker — two containers sharing the smdr-data named volume
docker-compose up -d
docker-compose logs -f smdr-webapp
docker-compose logs -f smdr-tcpserver
```

`init_database()` runs at Flask startup, so the DB and `data/` directory are created on first launch. The TCP server also writes monthly raw CSV dumps to `data/reports/YYYY.MM.csv` (mirrors the C# `OutputSMDR` behaviour).

## "Tests"

There is no test framework. The `test_*.py` and `check_db.py` scripts at repo root are manual integration tools you run against a live server:

```bash
python test_e2e.py            # opens TCP socket to localhost:3000, sends a 30-field record, checks DB
python test_record_client.py  # sends sample records in various shapes
python check_db.py            # prints DB stats and recent rows
python server/read.py 10      # show last 10 calls
python server/read.py stats   # show aggregate statistics
```

Don't add test framework scaffolding (pytest, etc.) without being asked.

## Architecture

### Shared data layer — `database.py`

Both services import from `database.py`. It owns the schema, all queries, and timezone/settings logic. Notable points:

- `smdr_calls` is a wide table (~30 columns) mirroring the original C# record fields. `raw_data` stores the original CSV line.
- `app_settings` holds runtime config as key/value rows. Two keys matter:
  - `timezone` (default `Europe/Rome`) — IANA name resolved via `zoneinfo.ZoneInfo`.
  - `timestamp_mode` (`utc` or `local`, default `utc`) — describes how the PBX-sent timestamps stored in `call_start` should be interpreted.
- `localize_timestamp()` is the single place that turns a stored naive timestamp into a tz-aware ISO string for the API. Flask routes wrap call dicts with `_localize_call` / `_localize_calls` before returning JSON. **Don't bypass this** — raw `call_start` strings are timezone-naive and will display incorrectly in the UI.
- `_build_where_clause()` centralises filter parsing for stats queries; reuse it instead of building ad-hoc WHEREs.

### TCP server — faithful C# port

`server/tcpsmdrserver.py` is intentionally a line-by-line port of the original C# `SMDR_Server.cs`. Method names (`HandleClientComm`, `ListenForClients`, `isSMDRRecord`, `createBasicSMDRRecordFromString`, `OutputSMDR`) and behaviours are kept on purpose — comments cite the original C# they correspond to. When changing this file, preserve the C# parity unless the change is explicitly to diverge.

Key invariant from the C#: `isSMDRRecord()` returns true only for **exactly 30 comma-separated fields on a single line**. The Python version adds a permissive fallback that still parses lines with ≥6 fields (logged as "tentativo parsing permissivo"). `DEBUG_GUIDE.md` documents why this matters — PBXes that split records across multiple TCP packets/lines will silently fail the strict check.

Date parsing in `createBasicSMDRRecordFromString` tries `%d/%m/%Y %H:%M:%S` first (the PBX format), then ISO and US fallbacks. If all parses fail it falls back to `datetime.now()` rather than dropping the record.

### Flask app

`app/main.py` is a single-file Flask app. Auth is session-based against env vars `SMDR_USERNAME` / `SMDR_PASSWORD` (defaults `admin` / `smdr2024`) loaded via `python-dotenv` from `.env`. Use `@login_required` for HTML pages and `@api_login_required` for JSON endpoints (the latter returns 401 instead of redirecting). `/api/health` is intentionally unauthenticated.

The README says "nessuna autenticazione" — that's stale; auth is in place. Don't trust the README on this point.

`app/templates/index.html` is the single-page UI; `login.html` is the login form. The frontend reads `tz_info` (returned by `/api/settings` and embedded in `/statistics` responses) to render times correctly.

### Configuration

- `.env` (gitignored) supplies `SMDR_USERNAME`, `SMDR_PASSWORD`, `SMDR_SECRET_KEY`. Don't commit it; don't hardcode secrets in `app/main.py`.
- Timezone and timestamp_mode are runtime settings in `app_settings`, changeable via `POST /api/settings` — not env vars.
- `requirements.txt` lists `Flask-Login` but the code uses plain Flask sessions. If you're tempted to "clean up" the dep, check first whether the user wants to actually migrate to Flask-Login.
