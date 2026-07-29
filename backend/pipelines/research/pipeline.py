"""
The actual "research these companies" work, shared by the CLI (main.py) and
the API server (server.py) so there's exactly one implementation of the
CrewAI loop and the upsert-into-CSV logic.
"""

import time
from typing import Callable, Optional

import pandas as pd

from data_loader import get_unique_companies, load_contacts, merge_research_into_contacts, save_csv
from paths import CONTACTS_INPUT_PATH, CONTACTS_OUTPUT_PATH, RESEARCH_OUTPUT_PATH
from pipelines.research.crew import ResearchCrew

OnProgress = Callable[[int, int, str], None]


def research_companies(unique_companies: pd.DataFrame, on_progress: Optional[OnProgress] = None) -> pd.DataFrame:
    """Run the research crew once per row, collecting results."""
    crew = ResearchCrew().crew()
    results = []
    total = len(unique_companies)

    for i, row in unique_companies.iterrows():
        company_name = row["Company Name"]
        if on_progress:
            on_progress(i, total, company_name)

        inputs = {
            "company_name": company_name,
            "website": row["Website"] if pd.notna(row["Website"]) else "not provided",
            "linkedin": row["Company Linkedin Url"]
            if pd.notna(row["Company Linkedin Url"])
            else "not provided",
        }

        try:
            output = crew.kickoff(inputs=inputs)
            research = output.pydantic  # CompanyResearch instance
            results.append(
                {
                    "__company_key": row["__company_key"],
                    "values_alignment": research.values_alignment,
                    "recent_relevant_news": research.recent_relevant_news,
                    "facility_notes": research.facility_notes,
                }
            )
        except Exception as e:
            results.append(
                {
                    "__company_key": row["__company_key"],
                    "values_alignment": "error",
                    "recent_relevant_news": "error",
                    "facility_notes": f"error: {e}",
                }
            )

        time.sleep(1)  # basic rate-limit courtesy

    return pd.DataFrame(results)


def run_research(company_keys: Optional[list[str]] = None, on_progress: Optional[OnProgress] = None) -> None:
    """
    Research either every company (company_keys=None) or just the given
    subset, then upsert the results into RESEARCH_OUTPUT_PATH (preserving
    previously-researched companies not in this run) and regenerate
    CONTACTS_OUTPUT_PATH from the full contact list.
    """
    contacts_df = load_contacts(CONTACTS_INPUT_PATH)
    unique_companies = get_unique_companies(contacts_df)

    if company_keys is None:
        target = unique_companies
    else:
        target = unique_companies[unique_companies["__company_key"].isin(company_keys)].reset_index(drop=True)

    new_research_df = research_companies(target, on_progress=on_progress)

    try:
        existing = pd.read_csv(RESEARCH_OUTPUT_PATH)
    except FileNotFoundError:
        existing = pd.DataFrame(columns=["__company_key", "values_alignment", "recent_relevant_news", "facility_notes"])

    kept = existing[~existing["__company_key"].isin(new_research_df["__company_key"])]
    merged_research = pd.concat([kept, new_research_df], ignore_index=True)

    save_csv(merged_research, RESEARCH_OUTPUT_PATH)
    enriched = merge_research_into_contacts(contacts_df, merged_research)
    save_csv(enriched, CONTACTS_OUTPUT_PATH)
