"""
Aggregated stats for the landing-page dashboard charts. Reads the full Apollo
export (data/final-market-leads.csv) for company attributes not present in the
trimmed pipeline input (Annual Revenue) - joined onto our own contacts via the
same stable company key used elsewhere, not by row position, since the two
files aren't guaranteed to share row order.

Company-level attributes (size, revenue, industry) are counted once per
company (deduped), so a company with many contacts doesn't get over-weighted.
Contact-level attributes (job title) are counted per contact, since we want to
know which roles we're actually reaching, not just which are most common per
company.
"""

import pandas as pd

import pipelines.email.drafts_store as drafts_store
from data_loader import compute_company_key, load_contacts, load_leads_with_research_status
from paths import CONTACTS_INPUT_PATH, RESEARCH_OUTPUT_PATH

FULL_EXPORT_PATH = "data/final-market-leads.csv"

EMPLOYEE_BUCKETS = [0, 50, 250, 1000, 5000, float("inf")]
EMPLOYEE_LABELS = ["<50", "50-249", "250-999", "1,000-4,999", "5,000+"]

REVENUE_BUCKETS = [0, 1e6, 1e7, 1e8, 1e9, float("inf")]
REVENUE_LABELS = ["<£1M", "£1M-£10M", "£10M-£100M", "£100M-£1B", "£1B+"]

TOP_TITLES = 8


def _bucket_counts(series: pd.Series, bins: list[float], labels: list[str]) -> list[dict]:
    counts = pd.cut(series.dropna(), bins=bins, labels=labels, right=False).value_counts()
    return [{"bucket": label, "count": int(counts.get(label, 0))} for label in labels]


def get_dashboard_stats() -> dict:
    contacts_df = load_contacts(CONTACTS_INPUT_PATH)
    contacts_df["__company_key"] = compute_company_key(contacts_df)
    companies_df = contacts_df.drop_duplicates(subset=["__company_key"])

    leads_df = load_leads_with_research_status(CONTACTS_INPUT_PATH, RESEARCH_OUTPUT_PATH)
    research_by_company = leads_df.drop_duplicates(subset=["__company_key"])
    research_counts = research_by_company["research_status"].value_counts()

    drafts_df = drafts_store.read_drafts()
    email_counts = drafts_df["status"].value_counts() if not drafts_df.empty else pd.Series(dtype="int64")

    full_df = pd.read_csv(FULL_EXPORT_PATH)
    full_df["__company_key"] = compute_company_key(full_df)
    full_companies_df = full_df.drop_duplicates(subset=["__company_key"])

    industry_counts = companies_df["Industry"].value_counts().sort_values(ascending=False)

    title_counts = contacts_df["Title"].value_counts()
    top_titles = title_counts.head(TOP_TITLES)
    other_count = int(title_counts.iloc[TOP_TITLES:].sum())
    titles = [{"label": label, "count": int(count)} for label, count in top_titles.items()]
    if other_count:
        titles.append({"label": "Other", "count": other_count})

    return {
        "pipeline": {
            "research": {
                "researched": int(research_counts.get("researched", 0)),
                "pending": int(research_counts.get("pending", 0)),
                "error": int(research_counts.get("error", 0)),
                "total": int(len(research_by_company)),
            },
            "emails": {
                "pending": int(email_counts.get("pending", 0)),
                "approved": int(email_counts.get("approved", 0)),
                "rejected": int(email_counts.get("rejected", 0)),
                "total": int(len(drafts_df)),
            },
        },
        "company_size": _bucket_counts(companies_df["# Employees"], EMPLOYEE_BUCKETS, EMPLOYEE_LABELS),
        "industry": [
            {"label": label, "count": int(count)} for label, count in industry_counts.items()
        ],
        "titles": titles,
        "revenue": {
            "companies_with_data": int(full_companies_df["Annual Revenue"].notna().sum()),
            "total_companies": int(len(full_companies_df)),
            "buckets": _bucket_counts(full_companies_df["Annual Revenue"], REVENUE_BUCKETS, REVENUE_LABELS),
        },
    }
