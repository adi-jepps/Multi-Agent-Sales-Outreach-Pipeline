# AI Sales Prospecting Platform

An internal tool that automates the two most time-consuming steps of B2B outbound sales — company research and personalized outreach email drafting — using multi-agent LLM pipelines, and exposes the results through a review dashboard so a human stays in the loop before anything gets sent.

The campaign context in this build (sustainable lighting remanufacturing / ESG outreach) is configuration, not architecture — the agents, tasks, and prompts are swappable via YAML without touching pipeline code.

## Problem it solves

Given a raw list of leads (company + contact exports from Apollo), a rep manually has to: research each company for a genuine reason to reach out, then write an individually-tailored cold email per contact. Both steps are slow, repetitive, and inconsistent in quality. This project automates both steps with LLM agents while keeping a human review/approval gate before any email is considered final.

## Architecture

```
data/relevant-columns.csv (raw leads)
        │
        ▼
┌───────────────────┐        ┌──────────────────────┐
│  Research Pipeline │──CSV──▶│   Email Pipeline      │
│  (CrewAI agent +   │        │   (CrewAI agent,      │
│   web search +     │        │    no tools, pure     │
│   site scraping)   │        │    writing task)       │
└───────────────────┘        └──────────────────────┘
        │                              │
        ▼                              ▼
research output/company_research.csv   research output/email_drafts.csv
        │                              │
        └──────────────┬───────────────┘
                        ▼
              FastAPI backend (server.py)
                        │
                        ▼
        React / TanStack Start dashboard (frontend/)
```

- **Storage**: flat CSVs, not a database — deliberate choice for an internal tool with a small, batch-oriented dataset. All the durability/consistency concerns a DB would normally absorb (atomic writes, dedup keys, concurrency locks, optimistic concurrency) are handled explicitly in the data layer instead (see below).
- **Backend**: FastAPI, serving both the CLI (`main.py`) and the dashboard (`server.py`) off the same pipeline modules — one implementation of the agent loop, two entry points.
- **Frontend**: React 19 + TanStack Start/Router/Query, Tailwind, Radix/shadcn components, Recharts for the dashboard charts.

## The AI pipelines

Both pipelines are built with **CrewAI**, structured identically (`CrewBase` class → one `@agent` → one `@task` → one `@crew`, `Process.sequential`), with agent role/goal/backstory and task prompts defined declaratively in `config/agents.yaml` / `config/tasks.yaml` rather than hardcoded in Python. That separation means prompt iteration doesn't touch pipeline code.

### 1. Research pipeline (`backend/pipelines/research/`)

For each unique company in the lead list:
- Agent (`company_researcher`) is given the company name, website, and LinkedIn URL.
- Tools available: `ScrapeWebsiteTool` (site content) and a custom `web_search_tool` (SerpAPI-backed Google search, used as a fallback for sources that aren't scrapable — e.g. LinkedIn company pages, which frequently block direct scraping).
- Agent is explicitly instructed not to fabricate findings — every field must say `"none found"` rather than invent a plausible-sounding answer, since a fabricated "researched" detail in a cold email is worse than a generic one.
- Output is constrained to a Pydantic schema (`CompanyResearch`: `values_alignment`, `recent_relevant_news`, `facility_notes`) via CrewAI's `output_pydantic`, so the result is a typed object the rest of the system can rely on — no downstream free-text parsing.

Research runs **once per unique company**, not per contact (companies are deduped by a stable key — see below), then fanned back out to every contact at that company.

### 2. Email pipeline (`backend/pipelines/email/`)

For each contact eligible for outreach (researched, not yet approved):
- Agent (`email_copywriter`) receives the campaign agenda (free-text brief, uploaded as PDF/DOCX or typed directly), the contact's name/title/company, and that company's research findings.
- No tools — pure generation task, deliberately kept separate from the research step (single-responsibility agents, easier to prompt-tune independently).
- Instructed to reference the research literally: skip any field marked `"none found"` rather than papering over gaps with generic flattery.
- Output constrained to `EmailDraft` (`subject` <60 chars, `body` <150 words, exactly one call to action) via `output_pydantic`.

Both pipelines share the same reliability pattern: **per-item error isolation** (a failed company/contact gets an `"error"` sentinel value and the loop continues rather than aborting the whole batch) and a fixed pacing delay as basic rate-limit courtesy.

## Backend design details worth calling out

- **Background job orchestration** (`server.py`): research and email-generation runs are long-running (many sequential LLM calls) and are kicked off as daemon threads, not handled inline in the request/response cycle. Progress is tracked in an in-memory state dict per stage and polled via `/api/pipeline-status`. Research and personalize are independent slots (not one shared lock), so a long research run never blocks personalizing contacts whose companies are already done.
- **Stable identity keys** (`data_loader.py`): contacts and companies need a durable identifier that survives across pipeline reruns and API requests — a positional row index doesn't work once rows are added/reordered. `compute_company_key` uses website (falling back to company name); `compute_contact_key` uses a SHA1 hash of the lowercased email (falling back to a hash of company+name for contacts missing one). This is what makes reruns and CSV upserts safe.
- **Upsert-not-overwrite semantics**: rerunning research or email generation on a subset of leads merges into existing output — previously researched companies not in the current run are preserved, not dropped, and an **approved** email draft is never silently regenerated over (checked in two places: filtered out of the target set before generation starts, and re-checked at upsert time as defense in depth).
- **Atomic writes**: every CSV/text write goes through a temp-file + `os.replace` pattern (with retry/backoff for a known transient Windows antivirus file-lock issue), so a concurrent reader — e.g. the dashboard polling while a background job writes — never observes a partially-written file.
- **Optimistic concurrency on edits**: the `PATCH /api/emails/{contact_key}` endpoint requires the client to send the `updated_at` it last read; a mismatch returns 409 rather than silently clobbering a concurrent edit.
- **Thread-safe draft store** (`drafts_store.py`): every read/write to the email drafts CSV goes through one lock, closing a race between a background pipeline upsert and a reviewer's concurrent edit that two independent read-then-write call sites wouldn't.

## API surface (`server.py`)

| Endpoint | Purpose |
|---|---|
| `GET /api/leads/table`, `/api/companies`, `/api/leads/{id}` | Browse leads/companies with research status |
| `POST /api/research/run` | Kick off research (all companies, or a specific selection) |
| `POST /api/emails/run` | Kick off personalization for researched, non-approved contacts |
| `GET /api/pipeline-status` | Poll progress of in-flight research/personalize jobs |
| `GET /api/emails`, `PATCH /api/emails/{contact_key}` | Review, edit, approve/reject drafted emails |
| `POST /api/campaign-agenda/extract` | Upload a PDF/DOCX campaign brief, extract text server-side (PyMuPDF / python-docx) |
| `GET /api/dashboard/stats` | Aggregated pipeline + lead-list stats for the dashboard charts |

## Frontend (`frontend/`)

React 19 + TanStack Start (file-based routing via TanStack Router, server state via TanStack Query), Tailwind v4 + Radix/shadcn UI components, Recharts.

Routes: dashboard (`index.tsx`, pipeline funnel + company-size/industry/title/revenue charts), leads browser + research trigger (`run-research.tsx`), company research browser + campaign setup/personalize trigger (`research.tsx`), email review/approval queue (`emails.tsx`). A `pipeline-status-banner` component polls `/api/pipeline-status` to surface in-flight background jobs across the app.

## Tech stack

**AI/agents**: CrewAI, Pydantic (structured outputs), SerpAPI (search tool), OpenAI (gpt-4.1)
**Backend**: FastAPI, Pandas, uvicorn, PyMuPDF, python-docx
**Frontend**: React 19, TanStack Start/Router/Query, TypeScript, Tailwind CSS v4, Radix UI, Recharts

## Notable engineering decisions (and why)

- **CSV instead of a database**: appropriate for a small, batch-driven internal tool — but only safe because the concurrency/durability problems a DB would solve for free were solved explicitly (locking, atomic replace, upsert semantics, optimistic concurrency).
- **Company-level research, contact-level email**: research is expensive and company-scoped (why re-research the same company for five contacts?); email generation is cheap-ish and inherently per-contact. The pipelines are shaped around that distinction rather than treating every row identically.
- **Structured outputs over free-text parsing**: constraining every agent task to a Pydantic model means the boundary between "LLM output" and "typed data the system trusts" is enforced by the framework, not by regexing a paragraph of prose.
- **Human approval gate**: nothing generated is ever sent automatically — email drafts start `pending` and require explicit `approved` status via the review UI, and approved drafts are protected from being overwritten by a rerun.
