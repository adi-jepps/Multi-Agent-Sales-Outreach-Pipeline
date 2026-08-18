# Multi Agent Sales Outreach Platform

An internal tool that automates the two most time-consuming steps of B2B outbound sales — company research and personalized outreach email drafting — using multi-agent LLM pipelines (CrewAI), with a human review/approval gate before anything leaves the building. **Nothing in this system sends email** — approving a draft only marks it `approved`; a rep still sends it manually.

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

Vite will print the local dev URL (typically `http://localhost:3000`). The frontend talks to the backend at `http://localhost:8000` by default — override with a `VITE_API_BASE_URL` env var in `frontend/.env` if your backend runs elsewhere.

Open the printed URL — you'll land on the dashboard with pipeline stats and market-overview charts, and three action cards: **Run company research**, **Personalize each email**, **Pending approvals**.

## 5. CLI usage (optional)

The research pipeline also runs standalone from the command line, without the API server:

```bash
cd backend
venv\Scripts\python.exe main.py --limit 5   # test on the first 5 companies
venv\Scripts\python.exe main.py             # run the full list
```

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
│   ├── paths.py                    # file-path constants shared across the backend
│   ├── pipelines/
│   │   ├── research/                # CrewAI research crew + pipeline logic
│   │   └── email/                    # CrewAI email-personalization crew + pipeline logic
│   ├── models/                        # shared Pydantic schemas
│   ├── tools/                          # CrewAI tools (web scraping, search, PDF/DOCX extraction)
│   ├── data/                            # input CSVs
│   ├── research output/                  # generated CSVs (research results, email drafts, campaign agenda)
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
| `VITE_API_BASE_URL` | `frontend/.env` (optional) | Overrides the default `http://localhost:8000` backend URL |


