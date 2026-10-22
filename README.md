# Tripzy

A trip-planning web app: accounts, friends and friend groups, trips with members, a budget splitter (equal or custom shares, balances, "who owes whom"), and popular place suggestions with optional browser geolocation.

Built with FastAPI, SQLite (SQLAlchemy 2), Jinja2 templates and vanilla JavaScript, following `tripzy_technical_specification.md`.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then set SECRET_KEY to a long random string
uvicorn app.main:app --reload
```

Open http://localhost:8000 and sign up. API docs are at http://localhost:8000/docs.

The database (`tripzy.db`) is created automatically on first start. Delete it to start fresh.

Use `localhost`, not a LAN IP: browsers only allow geolocation on HTTPS or `localhost`.

## Configuration (`.env`)

| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | `development` | Set to `production` to require a strong `SECRET_KEY` and mark cookies `Secure` (HTTPS only). |
| `SECRET_KEY` | dev placeholder | Signs the session cookie. Must be long and random in production. |
| `DATABASE_URL` | `sqlite:///./tripzy.db` | SQLAlchemy database URL. |
| `PLACES_PROVIDER` | `mock` | `mock` = offline demo data (labelled "Demo data" in the UI). `osm` = live OpenStreetMap data via Nominatim + Overpass (no key needed; requires internet; public servers are sometimes busy). |
| `PLACES_API_KEY` | empty | Reserved for a keyed provider. |

The mock provider has curated places for Goa, Mumbai, Pune, Delhi and Jaipur, and generic results for anything else.

## Tests

```bash
pytest -q                 # API, unit and acceptance tests (uses a temporary database)
```

Browser tests (optional) cover the UI flows and the geolocation cases LS-03/LS-04:

```bash
pip install -r requirements-e2e.txt
playwright install chromium
pytest -q tests/e2e
```

When Playwright isn't installed, `tests/e2e` is skipped.

### Saving results to a spreadsheet

```bash
python scripts/export_test_results.py --tester "Your Name"     # add --skip-e2e if Playwright isn't installed
```

This runs the whole suite and writes `reports/tripzy_test_results.xlsx`, which has three sheets:
- **Summary:** pass/fail counts per area.
- **Acceptance (PBL 7):** the 14 spreadsheet cases with Actual Result, Status, Executed Time/By/Date.
- **All tests:** every test with its status and duration.

### Spreadsheet mapping (PBL Assignment 7)

| ID | Test |
|---|---|
| BS-01 | `tests/test_acceptance_cases.py::test_add_expense_valid` |
| BS-02 | `test_negative_expense_rejected` |
| BS-03 | `test_equal_split_all_members` |
| BS-04 | `test_split_selected_members_only` |
| BS-05 | `test_custom_split_reconciles_total` |
| BS-06 | `test_delete_expense_updates_balances` |
| TM-01 | `test_create_trip` |
| TM-02 | `test_owner_adds_trip_member` |
| TM-03 | `test_owner_removes_trip_member` |
| TM-04 | `test_delete_trip_cascades_data` |
| LS-01 | `test_save_location_to_trip` |
| LS-02 | `test_popular_location_suggestions` |
| LS-03 | `tests/e2e/test_browser.py::test_geolocation_granted_uses_location` |
| LS-04 | `tests/e2e/test_browser.py::test_geolocation_denied_shows_message` |

`tests/e2e/test_browser.py::test_trip_members_budget_and_locations_flow` also runs BS, TM and LS cases through the real UI. Record the actual results, date/time and tester in the spreadsheet after you run the cases yourself.

## Project layout

```
app/
  main.py            FastAPI app, session middleware, security headers
  config.py          settings from environment / .env
  database.py        engine (SQLite foreign keys ON), session, init
  models/            SQLAlchemy tables
  schemas/           Pydantic request bodies
  services/          business logic (auth, friends, groups, trips, money, expenses, locations)
  providers/places.py  places adapter: mock + OpenStreetMap
  routers/           JSON API + HTML pages
  templates/, static/  Jinja2 pages, CSS, JS
tests/               pytest suite; tests/e2e = Playwright browser tests
```

## Design decisions

- **Money** is stored as integer paise. Equal splits give the leftover paise, one each, to participants in ascending user-ID order, so shares always add up exactly. The UI explains the rounding.
- **Balances**: net = paid − share. Net positions always sum to zero. Settlements greedily match the largest debtor to the largest creditor.
- **Sessions**: signed HTTP-only cookie (`SameSite=Lax`, `Secure` in production). Every state-changing API call needs an `X-CSRF-Token` header that matches the session. Passwords use Argon2id. Five failed logins in 15 minutes lock that email/IP pair for the rest of the window.
- **Permissions** are checked on the server. Non-members get `404` for a trip (so trip IDs can't be probed). Members who try owner-only actions get `403`.
- **Friend requests**: one row per pair of users. If the other person already sent you a request, sending one back accepts it. A rejected or cancelled request can be sent again.
- **Friend groups** contain accepted friends only. Unfriending someone also removes them from your groups (and you from theirs).
- **Trips**: the owner can't remove themselves (they delete the trip instead). A member who is in any expense can't be removed until those expenses are deleted, so balances stay correct. Deleting a trip cascades to its members, expenses, shares and saved places.
- **Expenses** can be added and deleted by any trip member. Only INR is supported.
- **Geolocation** runs only after the user clicks "Use my location" and reads an explanation. Coordinates are used for that one search and never stored. After a denial the app doesn't prompt again and keeps destination search working.

## Not included

Email verification, password-reset emails, ownership transfer, account deletion, multi-currency, and server-side form handling for browsers without JavaScript.
