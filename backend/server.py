"""
API server for the frontend dashboard. Reads/writes the same CSVs the CLI
(main.py) does - no DB. Long-running jobs (research, personalize) happen in
background threads so the request that triggers one can return immediately;
progress is tracked in an in-memory per-stage state dict polled via
/api/pipeline-status. Research and personalize run independently of each
other - one slot per stage, not one shared lock - so a long research run
never blocks personalizing contacts whose companies were already researched.

Run from backend/:
    uvicorn server:app --reload --port 8000
"""

import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dashboard_stats import get_dashboard_stats
from data_loader import compute_company_key, compute_contact_key, load_contacts, load_leads_with_research_status, load_text
from paths import CAMPAIGN_AGENDA_PATH, CONTACTS_INPUT_PATH, RESEARCH_OUTPUT_PATH
from pipelines.email import drafts_store
from pipelines.email.pipeline import run_personalize
from pipelines.research.pipeline import run_research
from tools.doc_extract import extract_text

load_dotenv()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Background job state - one independent slot per stage
# ---------------------------------------------------------------------------


@dataclass
class _State:
    status: str = "idle"  # idle | running | done | error
    total_items: Optional[int] = None
    completed_items: Optional[int] = None
    current_item: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_message: Optional[str] = None


class RunInProgress(Exception):
    pass


OnProgress = Callable[[int, int, str], None]

_states: dict[str, _State] = {}
_states_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_status_list() -> list[dict]:
    with _states_lock:
        return [{"stage": stage, **asdict(s)} for stage, s in _states.items() if s.status != "idle"]


def _start_job(stage: str, work: Callable[[OnProgress], None]) -> None:
    with _states_lock:
        current = _states.get(stage)
        if current is not None and current.status == "running":
            raise RunInProgress()
        _states[stage] = _State(status="running", started_at=_now_iso())

    def on_progress(completed: int, total: int, current_item: str) -> None:
        with _states_lock:
            s = _states[stage]
            s.total_items = total
            s.completed_items = completed
            s.current_item = current_item

    def target() -> None:
        try:
            work(on_progress)
            with _states_lock:
                s = _states[stage]
                s.status = "done"
                s.finished_at = _now_iso()
                if s.total_items is not None:
                    s.completed_items = s.total_items
        except Exception as e:
            with _states_lock:
                s = _states[stage]
                s.status = "error"
                s.error_message = str(e)
                s.finished_at = _now_iso()

    threading.Thread(target=target, daemon=True).start()


def start_run(company_keys: Optional[list[str]]) -> None:
    _start_job("research", lambda on_progress: run_research(company_keys, on_progress=on_progress))


def start_personalize(contact_keys: Optional[list[str]], agenda_text: str) -> None:
    _start_job(
        "personalize",
        lambda on_progress: run_personalize(contact_keys, agenda_text, on_progress=on_progress),
    )


# ---------------------------------------------------------------------------
# Data access helpers
# ---------------------------------------------------------------------------


def _load_table() -> pd.DataFrame:
    """Contacts (with a stable lead_id and contact_key) left-joined with
    whatever research exists so far."""
    return load_leads_with_research_status(CONTACTS_INPUT_PATH, RESEARCH_OUTPUT_PATH)


def _clean(value):
    return None if pd.isna(value) else value


def _row_to_table_dict(row: pd.Series) -> dict:
    contact_name = " ".join(
        part for part in [row.get("First Name"), row.get("Last Name")] if pd.notna(part)
    ) or None

    return {
        "lead_id": int(row["lead_id"]),
        "company_name": _clean(row.get("Company Name")),
        "industry": _clean(row.get("Industry")),
        "website": _clean(row.get("Website")),
        "contact_name": contact_name,
        "title": _clean(row.get("Title")),
        "email": _clean(row.get("Email")),
        "person_linkedin_url": _clean(row.get("Person Linkedin Url")),
        "research_status": row["research_status"],
        "values_alignment": _clean(row.get("values_alignment")),
        "recent_relevant_news": _clean(row.get("recent_relevant_news")),
        "facility_notes": _clean(row.get("facility_notes")),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/filters")
def get_filters():
    df = load_contacts(CONTACTS_INPUT_PATH)
    industries = sorted(i for i in df["Industry"].dropna().unique().tolist())
    return {"industries": industries, "research_statuses": ["researched", "pending", "error"]}


@app.get("/api/leads/table")
def get_leads_table(industry: Optional[str] = None, research_status: Optional[str] = None):
    df = _load_table()
    if industry:
        df = df[df["Industry"] == industry]
    if research_status:
        df = df[df["research_status"] == research_status]
    return [_row_to_table_dict(row) for _, row in df.iterrows()]


@app.get("/api/companies")
def get_companies(research_status: Optional[str] = None):
    df = _load_table()

    grouped = (
        df.groupby("__company_key", as_index=False)
        .agg(
            {
                "Company Name": "first",
                "Website": "first",
                "Industry": "first",
                "research_status": "first",
                "values_alignment": "first",
                "recent_relevant_news": "first",
                "facility_notes": "first",
            }
        )
        .rename(columns={"__company_key": "company_key"})
    )
    grouped["contact_count"] = df.groupby("__company_key").size().values
    lead_ids_by_company = df.groupby("__company_key")["lead_id"].apply(list)
    grouped["lead_ids"] = grouped["company_key"].map(lead_ids_by_company)

    if research_status:
        grouped = grouped[grouped["research_status"] == research_status]

    grouped = grouped.sort_values("Company Name")

    return [
        {
            "company_key": row["company_key"],
            "company_name": _clean(row.get("Company Name")),
            "website": _clean(row.get("Website")),
            "industry": _clean(row.get("Industry")),
            "contact_count": int(row["contact_count"]),
            "lead_ids": [int(x) for x in row["lead_ids"]],
            "research_status": row["research_status"],
            "values_alignment": _clean(row.get("values_alignment")),
            "recent_relevant_news": _clean(row.get("recent_relevant_news")),
            "facility_notes": _clean(row.get("facility_notes")),
        }
        for _, row in grouped.iterrows()
    ]


@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: int):
    df = _load_table()
    matches = df[df["lead_id"] == lead_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"No lead with id {lead_id}")

    row = matches.iloc[0]
    has_research = row["research_status"] != "pending"

    return {
        "lead_id": int(row["lead_id"]),
        "company": {
            "name": _clean(row.get("Company Name")),
            "website": _clean(row.get("Website")),
            "linkedin_url": _clean(row.get("Company Linkedin Url")),
            "industry": _clean(row.get("Industry")),
            "city": _clean(row.get("Company City")),
            "state": _clean(row.get("Company State")),
            "country": _clean(row.get("Company Country")),
        },
        "contact": {
            "full_name": " ".join(
                part for part in [row.get("First Name"), row.get("Last Name")] if pd.notna(part)
            )
            or None,
            "title": _clean(row.get("Title")),
            "email": _clean(row.get("Email")),
            "linkedin_url": _clean(row.get("Person Linkedin Url")),
        },
        "research": {
            "values_alignment": row.get("values_alignment"),
            "recent_relevant_news": row.get("recent_relevant_news"),
            "facility_notes": row.get("facility_notes"),
        }
        if has_research
        else None,
    }


class RunResearchRequest(BaseModel):
    lead_ids: Optional[list[int]] = None


@app.post("/api/research/run", status_code=202)
def post_run_research(body: RunResearchRequest):
    if body.lead_ids is None:
        company_keys = None
    else:
        contacts_df = load_contacts(CONTACTS_INPUT_PATH).reset_index(drop=False).rename(columns={"index": "lead_id"})
        subset = contacts_df[contacts_df["lead_id"].isin(body.lead_ids)]
        company_keys = compute_company_key(subset).unique().tolist()

    try:
        start_run(company_keys)
    except RunInProgress:
        raise HTTPException(status_code=409, detail="A research run is already in progress")

    return {"status": "started"}


@app.get("/api/pipeline-status")
def get_pipeline_status():
    return get_status_list()


@app.get("/api/dashboard/stats")
def get_dashboard_stats_endpoint():
    return get_dashboard_stats()


# ---------------------------------------------------------------------------
# Campaign agenda
# ---------------------------------------------------------------------------


@app.get("/api/campaign-agenda")
def get_campaign_agenda():
    return {"text": load_text(CAMPAIGN_AGENDA_PATH)}


@app.post("/api/campaign-agenda/extract")
async def post_extract_campaign_agenda(file: UploadFile = File(...)):
    content = await file.read()
    try:
        text = extract_text(file.filename or "", content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"text": text}


# ---------------------------------------------------------------------------
# Email drafts
# ---------------------------------------------------------------------------


class RunPersonalizeRequest(BaseModel):
    lead_ids: Optional[list[int]] = None
    agenda_text: str


@app.post("/api/emails/run", status_code=202)
def post_run_personalize(body: RunPersonalizeRequest):
    if body.lead_ids is None:
        contact_keys = None
    else:
        contacts_df = load_contacts(CONTACTS_INPUT_PATH).reset_index(drop=False).rename(columns={"index": "lead_id"})
        subset = contacts_df[contacts_df["lead_id"].isin(body.lead_ids)]
        contact_keys = compute_contact_key(subset).unique().tolist()

    try:
        start_personalize(contact_keys, body.agenda_text)
    except RunInProgress:
        raise HTTPException(status_code=409, detail="A personalize run is already in progress")

    return {"status": "started"}


def _draft_row_to_dict(row: pd.Series) -> dict:
    contact_name = " ".join(
        part for part in [row.get("First Name"), row.get("Last Name")] if pd.notna(part)
    ) or None

    return {
        "contact_key": row["contact_key"],
        "company_name": _clean(row.get("Company Name")),
        "contact_name": contact_name,
        "title": _clean(row.get("Title")),
        "subject": row["subject"],
        "body": row["body"],
        "status": row["status"],
        "updated_at": row["updated_at"],
    }


@app.get("/api/emails")
def get_emails(status: Optional[str] = None):
    drafts_df = drafts_store.read_drafts()
    if drafts_df.empty:
        return []

    contacts_df = load_leads_with_research_status(CONTACTS_INPUT_PATH, RESEARCH_OUTPUT_PATH)
    merged = drafts_df.merge(contacts_df, on="contact_key", how="left")

    if status:
        merged = merged[merged["status"] == status]
    merged = merged.sort_values("updated_at", ascending=False)

    return [_draft_row_to_dict(row) for _, row in merged.iterrows()]


class UpdateEmailRequest(BaseModel):
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Optional[str] = None
    expected_updated_at: str


@app.patch("/api/emails/{contact_key}")
def patch_email(contact_key: str, body: UpdateEmailRequest):
    try:
        updated = drafts_store.update_draft(
            contact_key,
            {"subject": body.subject, "body": body.body, "status": body.status},
            body.expected_updated_at,
        )
    except drafts_store.DraftNotFound:
        raise HTTPException(status_code=404, detail=f"No email draft for contact {contact_key}")
    except drafts_store.StaleUpdate:
        raise HTTPException(
            status_code=409, detail="This draft changed since you loaded it - refresh and try again."
        )

    contacts_df = load_leads_with_research_status(CONTACTS_INPUT_PATH, RESEARCH_OUTPUT_PATH)
    contact_matches = contacts_df[contacts_df["contact_key"] == contact_key]
    contact_row = contact_matches.iloc[0] if not contact_matches.empty else pd.Series(dtype=object)

    merged = {**contact_row.to_dict(), **updated}
    return _draft_row_to_dict(pd.Series(merged))
