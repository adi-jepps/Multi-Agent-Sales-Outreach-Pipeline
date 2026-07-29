"""
Every read/write of email_drafts.csv goes through here, behind one lock -
closes the race between a background personalize run's upsert and a
reviewer's concurrent PATCH request, which two independent read-then-write
call sites would not.
"""

import threading
from datetime import datetime, timezone

import pandas as pd

from data_loader import save_csv
from paths import EMAIL_DRAFTS_PATH

_COLUMNS = ["contact_key", "subject", "body", "status", "updated_at"]
_lock = threading.Lock()


class DraftNotFound(Exception):
    pass


class StaleUpdate(Exception):
    pass


def now_iso() -> str:
    """Public so email_pipeline.py can stamp new drafts with the same clock/format."""
    return datetime.now(timezone.utc).isoformat()


def _read() -> pd.DataFrame:
    try:
        return pd.read_csv(EMAIL_DRAFTS_PATH)
    except FileNotFoundError:
        return pd.DataFrame(columns=_COLUMNS)


def read_drafts() -> pd.DataFrame:
    with _lock:
        return _read()


def upsert_drafts(new_rows: pd.DataFrame, protect_statuses: tuple[str, ...] = ("approved",)) -> None:
    """
    Replace rows for contact_keys present in new_rows, except ones whose
    existing status is in protect_statuses - an approved draft is never
    silently overwritten by a regenerate. (Defense in depth: the primary skip
    already happens in email_pipeline.run_personalize before generation even
    starts, so this is a second guard, not the only one.)
    """
    with _lock:
        existing = _read()
        if not existing.empty:
            protected_keys = set(existing.loc[existing["status"].isin(protect_statuses), "contact_key"])
            new_rows = new_rows[~new_rows["contact_key"].isin(protected_keys)]

        kept = existing[~existing["contact_key"].isin(new_rows["contact_key"])] if not existing.empty else existing
        merged = pd.concat([kept, new_rows], ignore_index=True)
        save_csv(merged, EMAIL_DRAFTS_PATH)


def update_draft(contact_key: str, patch: dict, expected_updated_at: str) -> dict:
    with _lock:
        df = _read()
        mask = df["contact_key"] == contact_key
        if not mask.any():
            raise DraftNotFound(contact_key)

        current_updated_at = df.loc[mask, "updated_at"].iloc[0]
        if expected_updated_at != current_updated_at:
            raise StaleUpdate(contact_key)

        for field in ("subject", "body", "status"):
            value = patch.get(field)
            if value is not None:
                df.loc[mask, field] = value
        df.loc[mask, "updated_at"] = now_iso()

        save_csv(df, EMAIL_DRAFTS_PATH)
        return df.loc[mask].iloc[0].to_dict()
