"""
The actual "write these personalized emails" work, mirroring pipeline.py's
shape: a per-row generation loop plus a run_ wrapper that resolves the
target set and upserts results.
"""

import time
from typing import Callable, Optional

import pandas as pd

from data_loader import load_leads_with_research_status, save_text
from paths import CAMPAIGN_AGENDA_PATH, CONTACTS_INPUT_PATH, RESEARCH_OUTPUT_PATH
from pipelines.email.crew import EmailCrew
from pipelines.email.drafts_store import now_iso, read_drafts, upsert_drafts

OnProgress = Callable[[int, int, str], None]


def personalize_contacts(df: pd.DataFrame, agenda_text: str, on_progress: Optional[OnProgress] = None) -> pd.DataFrame:
    """Run the email crew once per contact row, collecting draft results."""
    crew = EmailCrew().crew()
    results = []
    total = len(df)

    for i, (_, row) in enumerate(df.iterrows()):
        contact_name = " ".join(
            part for part in [row.get("First Name"), row.get("Last Name")] if pd.notna(part)
        ) or "there"

        if on_progress:
            on_progress(i, total, contact_name)

        inputs = {
            "campaign_agenda": agenda_text,
            "contact_name": contact_name,
            "contact_title": row["Title"] if pd.notna(row.get("Title")) else "their role",
            "company_name": row["Company Name"],
            "values_alignment": row["values_alignment"] if pd.notna(row.get("values_alignment")) else "none found",
            "recent_relevant_news": row["recent_relevant_news"] if pd.notna(row.get("recent_relevant_news")) else "none found",
            "facility_notes": row["facility_notes"] if pd.notna(row.get("facility_notes")) else "none found",
        }

        try:
            output = crew.kickoff(inputs=inputs)
            draft = output.pydantic  # EmailDraft instance
            results.append(
                {
                    "contact_key": row["contact_key"],
                    "subject": draft.subject,
                    "body": draft.body,
                    "status": "pending",
                    "updated_at": now_iso(),
                }
            )
        except Exception as e:
            results.append(
                {
                    "contact_key": row["contact_key"],
                    "subject": "error",
                    "body": f"error: {e}",
                    "status": "pending",
                    "updated_at": now_iso(),
                }
            )

        time.sleep(1)  # basic rate-limit courtesy

    return pd.DataFrame(results)


def run_personalize(contact_keys: Optional[list[str]], agenda_text: str, on_progress: Optional[OnProgress] = None) -> None:
    """
    Personalize either every researched contact (contact_keys=None) or just
    the given subset, skipping any contact whose current draft is already
    approved (a human decision is never silently overwritten by a
    regenerate), then upsert the results into EMAIL_DRAFTS_PATH.
    """
    save_text(agenda_text, CAMPAIGN_AGENDA_PATH)

    df = load_leads_with_research_status(CONTACTS_INPUT_PATH, RESEARCH_OUTPUT_PATH)
    researched = df[df["research_status"] == "researched"]

    if contact_keys is None:
        target = researched
    else:
        target = researched[researched["contact_key"].isin(contact_keys)]

    existing_drafts = read_drafts()
    approved_keys = (
        set(existing_drafts.loc[existing_drafts["status"] == "approved", "contact_key"])
        if not existing_drafts.empty
        else set()
    )
    target = target[~target["contact_key"].isin(approved_keys)]

    if target.empty:
        raise ValueError(
            "No eligible contacts to personalize (selection is unresearched, already approved, or empty)."
        )

    new_drafts = personalize_contacts(target, agenda_text, on_progress=on_progress)
    upsert_drafts(new_drafts)
