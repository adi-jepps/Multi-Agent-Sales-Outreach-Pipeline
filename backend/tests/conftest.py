"""
Shared fixtures. Tests never touch the real data/research output/ files -
everything runs against a tiny synthetic dataset written into pytest's
tmp_path, with every module's path constants monkeypatched to point there.

The synthetic dataset is deliberately small but exercises both branches of
the stable-key fallback logic:
  - Acme Council: has a Website (company key = website), two contacts, one
    with an Email (contact key = email hash) and one without (contact key =
    company+name hash) - the more common real-world "no email on file" case.
  - Beta Health Trust: no Website (company key falls back to Company Name),
    one contact, and no Annual Revenue on file (tests the dashboard's
    partial-fill-rate reporting).
"""

import pandas as pd
import pytest

CONTACTS_COLUMNS = [
    "First Name", "Last Name", "Title", "Seniority", "Departments",
    "Company Name", "Email", "Email Status", "Email Confidence",
    "Person Linkedin Url", "Website", "Company Linkedin Url",
    "City", "State", "Country",
    "Company City", "Company State", "Company Country",
    "# Employees", "Industry", "Keywords",
]


def _contacts_rows():
    return [
        {
            "First Name": "Alice", "Last Name": "Anderson", "Title": "Facilities Manager",
            "Seniority": "Manager", "Departments": "Operations",
            "Company Name": "Acme Council", "Email": "alice@acme-council.gov.uk",
            "Email Status": "Verified", "Email Confidence": 90,
            "Person Linkedin Url": "https://linkedin.com/in/alice",
            "Website": "https://acme-council.gov.uk",
            "Company Linkedin Url": "https://linkedin.com/company/acme-council",
            "City": "Anytown", "State": "Anyshire", "Country": "United Kingdom",
            "Company City": "Anytown", "Company State": "Anyshire", "Company Country": "United Kingdom",
            "# Employees": 500, "Industry": "government administration", "Keywords": "council",
        },
        {
            "First Name": "Bob", "Last Name": "Brown", "Title": "Estates Officer",
            "Seniority": "Entry", "Departments": "Operations",
            "Company Name": "Acme Council", "Email": None,
            "Email Status": None, "Email Confidence": None,
            "Person Linkedin Url": None,
            "Website": "https://acme-council.gov.uk",
            "Company Linkedin Url": "https://linkedin.com/company/acme-council",
            "City": "Anytown", "State": "Anyshire", "Country": "United Kingdom",
            "Company City": "Anytown", "Company State": "Anyshire", "Company Country": "United Kingdom",
            "# Employees": 500, "Industry": "government administration", "Keywords": "council",
        },
        {
            "First Name": "Carol", "Last Name": "Carter", "Title": "Head of Facilities",
            "Seniority": "Head", "Departments": "Operations",
            "Company Name": "Beta Health Trust", "Email": "carol@betahealth.org",
            "Email Status": "Verified", "Email Confidence": 95,
            "Person Linkedin Url": "https://linkedin.com/in/carol",
            "Website": None,
            "Company Linkedin Url": None,
            "City": "Otherville", "State": "Othershire", "Country": "United Kingdom",
            "Company City": "Otherville", "Company State": "Othershire", "Company Country": "United Kingdom",
            "# Employees": 3000, "Industry": "hospital & health care", "Keywords": "health",
        },
    ]


@pytest.fixture
def contacts_df():
    return pd.DataFrame(_contacts_rows(), columns=CONTACTS_COLUMNS)


@pytest.fixture
def contacts_csv(tmp_path, contacts_df):
    path = tmp_path / "relevant-columns.csv"
    contacts_df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def final_market_leads_csv(tmp_path, contacts_df):
    df = contacts_df.copy()
    df["Annual Revenue"] = [50_000_000, 50_000_000, None]  # Beta Health Trust: no revenue on file
    path = tmp_path / "final-market-leads.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture
def workspace(tmp_path, monkeypatch, contacts_df):
    """
    Points every module's path constants at an isolated tmp workspace, so
    tests never read/write the real data/research output/ files. Each
    consumer module gets its own copy of these constants patched (via
    `from paths import X`), not just paths.py itself, since Python binds the
    name at import time.
    """
    contacts_path = tmp_path / "relevant-columns.csv"
    contacts_df.to_csv(contacts_path, index=False)

    final_export_path = tmp_path / "final-market-leads.csv"
    full_df = contacts_df.copy()
    full_df["Annual Revenue"] = [50_000_000, 50_000_000, None]
    full_df.to_csv(final_export_path, index=False)

    research_output_path = tmp_path / "company_research.csv"
    contacts_output_path = tmp_path / "contacts_with_research.csv"
    email_drafts_path = tmp_path / "email_drafts.csv"
    campaign_agenda_path = tmp_path / "campaign_agenda.txt"

    import paths

    monkeypatch.setattr(paths, "CONTACTS_INPUT_PATH", str(contacts_path))
    monkeypatch.setattr(paths, "RESEARCH_OUTPUT_PATH", str(research_output_path))
    monkeypatch.setattr(paths, "CONTACTS_OUTPUT_PATH", str(contacts_output_path))
    monkeypatch.setattr(paths, "EMAIL_DRAFTS_PATH", str(email_drafts_path))
    monkeypatch.setattr(paths, "CAMPAIGN_AGENDA_PATH", str(campaign_agenda_path))

    import dashboard_stats

    monkeypatch.setattr(dashboard_stats, "CONTACTS_INPUT_PATH", str(contacts_path))
    monkeypatch.setattr(dashboard_stats, "RESEARCH_OUTPUT_PATH", str(research_output_path))
    monkeypatch.setattr(dashboard_stats, "FULL_EXPORT_PATH", str(final_export_path))

    import pipelines.research.pipeline as research_pipeline

    monkeypatch.setattr(research_pipeline, "CONTACTS_INPUT_PATH", str(contacts_path))
    monkeypatch.setattr(research_pipeline, "CONTACTS_OUTPUT_PATH", str(contacts_output_path))
    monkeypatch.setattr(research_pipeline, "RESEARCH_OUTPUT_PATH", str(research_output_path))

    import pipelines.email.pipeline as email_pipeline

    monkeypatch.setattr(email_pipeline, "CONTACTS_INPUT_PATH", str(contacts_path))
    monkeypatch.setattr(email_pipeline, "RESEARCH_OUTPUT_PATH", str(research_output_path))
    monkeypatch.setattr(email_pipeline, "CAMPAIGN_AGENDA_PATH", str(campaign_agenda_path))

    import pipelines.email.drafts_store as drafts_store

    monkeypatch.setattr(drafts_store, "EMAIL_DRAFTS_PATH", str(email_drafts_path))

    import server

    monkeypatch.setattr(server, "CONTACTS_INPUT_PATH", str(contacts_path))
    monkeypatch.setattr(server, "RESEARCH_OUTPUT_PATH", str(research_output_path))
    monkeypatch.setattr(server, "CAMPAIGN_AGENDA_PATH", str(campaign_agenda_path))

    return {
        "contacts_path": str(contacts_path),
        "final_export_path": str(final_export_path),
        "research_output_path": str(research_output_path),
        "contacts_output_path": str(contacts_output_path),
        "email_drafts_path": str(email_drafts_path),
        "campaign_agenda_path": str(campaign_agenda_path),
    }
