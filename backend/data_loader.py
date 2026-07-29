"""
Handles all CSV in/out for the research pipeline. Kept separate from main.py
so the merge/dedupe logic can be tested or reused independently of the crew.
"""

import hashlib
import os
import time

import pandas as pd


def _atomic_replace(tmp_path: str, path: str) -> None:
    """
    os.replace occasionally fails with WinError 5 (Access is denied) on
    Windows when antivirus real-time scanning briefly opens a just-written
    file - not a real conflict, just a transient lock. Retry a few times
    with a short backoff before giving up.
    """
    last_error: OSError | None = None
    for attempt in range(5):
        try:
            os.replace(tmp_path, path)
            return
        except OSError as e:
            last_error = e
            time.sleep(0.2 * (attempt + 1))
    raise last_error


def load_contacts(path: str) -> pd.DataFrame:
    """Load the (already deduped, already trimmed) contact list."""
    return pd.read_csv(path)


def compute_company_key(df: pd.DataFrame) -> pd.Series:
    """
    The dedup key used everywhere a contact needs to be tied to a company.

    Uses Website where available, falling back to Company Name for rows
    missing a website - names can be inconsistent across Apollo exports, so
    Website is the more reliable key when present.
    """
    return df["Website"].fillna(df["Company Name"])


def compute_contact_key(df: pd.DataFrame) -> pd.Series:
    """
    A stable, position-independent identity for a contact - unlike a
    positional row index, this survives across requests/processes, so it's
    what durable per-contact records (e.g. email drafts) are keyed on.

    Uses Email (lowercased/stripped) where present and non-empty, since it's
    the most reliable unique identifier Apollo gives us. Falls back to a hash
    of company key + first/last name for contacts missing an email. Always a
    URL-safe hex string.
    """
    email = df["Email"].fillna("").astype(str).str.strip().str.lower()
    fallback_basis = (
        compute_company_key(df).astype(str)
        + "|"
        + df["First Name"].fillna("").astype(str)
        + "|"
        + df["Last Name"].fillna("").astype(str)
    )
    basis = email.where(email != "", fallback_basis)
    return basis.apply(lambda s: hashlib.sha1(s.encode("utf-8")).hexdigest())


def get_unique_companies(contacts_df: pd.DataFrame) -> pd.DataFrame:
    """
    Reduce the contact list down to one row per company, so research runs
    once per company rather than once per contact.
    """
    df = contacts_df.copy()
    df["__company_key"] = compute_company_key(df)

    unique_companies = df.drop_duplicates(subset=["__company_key"])[
        ["Company Name", "Website", "Company Linkedin Url", "__company_key"]
    ].reset_index(drop=True)

    return unique_companies


def merge_research_into_contacts(contacts_df: pd.DataFrame, research_df: pd.DataFrame) -> pd.DataFrame:
    """Join company-level research results back onto every contact at that company."""
    df = contacts_df.copy()
    df["__company_key"] = compute_company_key(df)
    merged = df.merge(research_df, on="__company_key", how="left")
    return merged.drop(columns=["__company_key"])


def _derive_research_status(row: pd.Series) -> str:
    if pd.isna(row.get("values_alignment")):
        return "pending"
    if row["values_alignment"] == "error":
        return "error"
    return "researched"


def load_leads_with_research_status(contacts_path: str, research_path: str) -> pd.DataFrame:
    """
    Contacts joined with whatever company research exists so far, plus a
    positional lead_id (for the read-only Leads/Research pages - NOT safe as
    a durable key, see compute_contact_key), the stable contact_key (safe as
    a durable key), and a derived research_status per row.

    Distinct from merge_research_into_contacts()'s contacts_with_research.csv
    output, which is a plain contacts-plus-research shape with no lead_id/
    contact_key/research_status - don't confuse the two.
    """
    contacts_df = load_contacts(contacts_path).reset_index(drop=False).rename(columns={"index": "lead_id"})
    contacts_df["__company_key"] = compute_company_key(contacts_df)
    contacts_df["contact_key"] = compute_contact_key(contacts_df)

    try:
        research_df = pd.read_csv(research_path)
    except FileNotFoundError:
        research_df = pd.DataFrame(columns=["__company_key", "values_alignment", "recent_relevant_news", "facility_notes"])

    merged = contacts_df.merge(research_df, on="__company_key", how="left")
    merged["research_status"] = merged.apply(_derive_research_status, axis=1)
    return merged


def save_csv(df: pd.DataFrame, path: str) -> None:
    """
    Writes via a temp file + atomic os.replace, so a concurrent reader (e.g.
    the API server) never observes a partially-written CSV mid-run.
    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp_path = f"{path}.tmp"
    df.to_csv(tmp_path, index=False)
    _atomic_replace(tmp_path, path)


def load_text(path: str) -> str:
    """Read a plain-text file, or '' if it doesn't exist yet."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def save_text(text: str, path: str) -> None:
    """Same atomic temp-file + os.replace pattern as save_csv, for plain text."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(text)
    _atomic_replace(tmp_path, path)
