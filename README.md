# EGG — Sales Prospecting Platform

An internal tool that automates the two most time-consuming steps of B2B outbound sales — company research and personalized outreach email drafting — using multi-agent LLM pipelines (CrewAI), with a human review/approval gate before anything leaves the building. **Nothing in this system sends email.** Approving a draft marks it `approved`; from there, an optional, explicit "Create draft in Outlook" action can push it into a real Outlook mailbox, addressed to the real contact, as an actual (unsent) draft via Microsoft Graph — the app only ever holds `Mail.ReadWrite` access and never calls Graph's send endpoint, so it is structurally incapable of sending, not just well-behaved by convention. A human still has to open Outlook, review it, and hit Send themselves.

For architecture, design decisions, and the full API surface, see [`PROJECT.md`](PROJECT.md). This file is the practical "get it running" guide.

## Prerequisites

- Python 3.13 (or compatible)
- Node.js + npm (the frontend also has `bun.lock`/`bunfig.toml` if you prefer Bun — either works)
- An [OpenAI API key](https://platform.openai.com/) (used for both CrewAI pipelines)
- A [SerpAPI key](https://serpapi.com/) (used by the research pipeline's web-search tool)

## 1. Backend setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```
OPENAI_API_KEY=your_openai_key_here
SERPAPI_API_KEY=your_serpapi_key_here
```

## 2. Data prep

The pipeline reads `backend/data/relevant-columns.csv` — a trimmed-down export (First Name, Title, Company Name, Website, Industry, etc.) of a raw Apollo lead export.

`relevant-fields.py` (repo root) is the script that produces it from `data/final-market-leads.csv`:

```bash
python relevant-fields.py
```

It writes `relevant-columns.csv` to wherever you run it from — move (or symlink) the output to `backend/data/relevant-columns.csv` before starting the backend. If you're just running the existing pipeline against data that's already there, you can skip this step — `backend/data/relevant-columns.csv` is already checked in.

## 3. Run the backend

```bash
cd backend
venv\Scripts\python.exe -m uvicorn server:app --reload --port 8000
```

The API is now live at `http://localhost:8000`. Interactive docs (FastAPI's Swagger UI) are at `http://localhost:8000/docs`.

## 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Vite will print the local dev URL (typically `http://localhost:8080`). The frontend talks to the backend at `http://localhost:8000` by default — override with a `VITE_API_BASE_URL` env var in `frontend/.env` if your backend runs elsewhere. If the frontend runs anywhere other than `localhost:8080`/`localhost:3000` (e.g. a LAN IP), add it to `FRONTEND_ORIGINS` in `backend/.env` — see [Environment variables](#environment-variables).

Open the printed URL — you'll land on the dashboard with pipeline stats and market-overview charts, and three action cards: **Run company research**, **Personalize each email**, **Pending approvals**.

## 5. CLI usage (optional)

The research pipeline also runs standalone from the command line, without the API server:

```bash
cd backend
venv\Scripts\python.exe main.py --limit 5   # test on the first 5 companies
venv\Scripts\python.exe main.py             # run the full list
```

## 6. Outlook draft setup (optional)

Skip this unless you want the "Create draft in Outlook" button on the Pending Approvals page to actually work — everything else in the app runs fine without it.

**One-time Azure app registration** (only you can do this — I can't create Azure resources or grant consent on your behalf):

1. In the [Azure Portal](https://portal.azure.com/), under the tenant that owns your mailbox domain, go to **Azure Active Directory → App registrations → New registration**.
2. Name it something like "EGG Sales Draft Creator". Leave the redirect URI blank.
3. Under **Authentication**, set the platform to **Mobile and desktop applications**, and set **Allow public client flows** to **Yes**. (No client secret is needed — this app never stores one.)
4. Under **API permissions → Add a permission → Microsoft Graph → Delegated permissions**, add `Mail.ReadWrite`. `offline_access` and `User.Read` are included by default. Grant admin consent if your tenant requires it for this scope.
5. From the app's **Overview** page, note the **Application (client) ID** and **Directory (tenant) ID**.

**Configure and authorize:**

```bash
# backend/.env
MS_GRAPH_CLIENT_ID=<the client ID from step 5>
MS_GRAPH_TENANT_ID=<the tenant ID from step 5>
MS_GRAPH_MAILBOX=ajeppu@egglighting.com   # documentation only, see below
```

```bash
cd backend
venv\Scripts\python.exe scripts\authorize_outlook.py
```

This prints a URL and a short code — open the URL on any device, enter the code, and sign in **as the mailbox you want drafts created in** (not necessarily your own account). It's a one-time step: the resulting refresh token is cached to `backend/.msal_token_cache.bin` (gitignored — treat it like a credential), and the backend silently refreshes it from then on. Re-run this script only if that file is deleted or the token fully expires.

Calls always target `/me/messages`, so the mailbox that ends up receiving drafts is whichever account completed the sign-in above — `MS_GRAPH_MAILBOX` is just a label for your own reference, not something the code reads.

**The "To" address on every pushed draft is the real contact's actual email address** (from the same contact data the pipeline already has) — there's no test-recipient override. A contact with no email on file can't be pushed (the button returns a 400). Since it's still only ever an unsent draft, this doesn't cross into "sending" — but it does mean a real customer's address ends up on something a human in the mailbox could accidentally hit Send on, so treat pushing to Outlook as a real, reviewed action, not a routine one.

## Running tests

```bash
cd backend
pip install -r requirements-dev.txt   # adds pytest on top of requirements.txt
venv\Scripts\python.exe -m pytest -v
```

Tests never touch the real `data/`/`research output/` files or call the OpenAI/SerpAPI APIs — each test runs against a tiny synthetic dataset in a temp directory, with CrewAI calls mocked out. Covers the data layer (stable key derivation, atomic writes, upsert semantics), the drafts store (protected-approved rows, optimistic-concurrency conflicts), both pipelines (per-item error isolation, approved-contact skipping), and the API surface (status codes, response shapes, 404/409 handling). No frontend test suite yet.

## Project structure

```
Sales-internal/
├── PROJECT.md              # architecture, design decisions, API reference
├── README.md                # you are here
├── relevant-fields.py         # trims a raw Apollo export down to the fields the pipeline uses
├── backend/
│   ├── server.py               # FastAPI app
│   ├── main.py                  # CLI entry point (research only)
│   ├── data_loader.py            # CSV I/O, stable identity keys, atomic writes
│   ├── dashboard_stats.py         # aggregated stats for the dashboard charts
│   ├── outlook_client.py           # MSAL auth + Graph API draft creation (never sends)
│   ├── paths.py                     # file-path constants shared across the backend
│   ├── pipelines/
│   │   ├── research/                 # CrewAI research crew + pipeline logic
│   │   └── email/                     # CrewAI email-personalization crew + pipeline logic
│   ├── models/                         # shared Pydantic schemas
│   ├── tools/                           # CrewAI tools (web scraping, search, PDF/DOCX extraction)
│   ├── scripts/
│   │   └── authorize_outlook.py           # one-time Outlook device-code sign-in
│   ├── tests/                               # pytest suite (data layer, both pipelines, API surface)
│   ├── data/                                 # input CSVs
│   ├── research output/                       # generated CSVs (research results, email drafts, campaign agenda)
│   └── venv/
└── frontend/
    └── src/
        ├── routes/           # index (dashboard), run-research, research, emails
        ├── components/         # shared UI + dashboard-charts
        └── lib/                  # typed API client
```

## Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | `backend/.env` | LLM calls for both CrewAI pipelines (gpt-4.1) |
| `SERPAPI_API_KEY` | `backend/.env` | Web search tool used during company research |
| `FRONTEND_ORIGINS` | `backend/.env` (optional) | Comma-separated list of origins allowed to call the API (CORS). Defaults to the frontend's local dev origins |
| `MS_GRAPH_CLIENT_ID` | `backend/.env` (optional) | Azure app registration client ID — see [Outlook draft setup](#6-outlook-draft-setup-optional) |
| `MS_GRAPH_TENANT_ID` | `backend/.env` (optional) | Azure app registration tenant ID |
| `MS_GRAPH_MAILBOX` | `backend/.env` (optional) | Documentation only — the actual mailbox is whichever account authorized via `scripts/authorize_outlook.py` |
| `VITE_API_BASE_URL` | `frontend/.env` (optional) | Overrides the default `http://localhost:8000` backend URL |

## Known limitations

- No email-sending capability, by design — Outlook drafts can be created (optional, see above) but the app never calls a send endpoint anywhere.
- CSV-based storage, not a database — fine for this dataset's size, see `PROJECT.md` for why that's safe here.
- No authentication — CORS is restricted to known local dev origins (see `FRONTEND_ORIGINS`), but there's no auth on the API itself, so it's still intended for local/trusted use only.
- Backend has a pytest suite (see [Running tests](#running-tests)); no frontend test suite yet.
