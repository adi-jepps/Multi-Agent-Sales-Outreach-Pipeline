"""
CLI entry point for the research step.

Usage:
    python main.py --limit 10

Run with --limit while testing so you're not burning API calls/time across
your whole list before checking output quality.
"""

import argparse

from dotenv import load_dotenv

from data_loader import get_unique_companies, load_contacts, merge_research_into_contacts, save_csv
from paths import CONTACTS_INPUT_PATH, CONTACTS_OUTPUT_PATH, RESEARCH_OUTPUT_PATH
from pipelines.research.pipeline import research_companies

load_dotenv()


def print_progress(completed: int, total: int, current_item: str) -> None:
    print(f"[{completed}/{total}] Researching: {current_item}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=CONTACTS_INPUT_PATH)
    parser.add_argument("--limit", type=int, default=None, help="Only research the first N companies (for testing)")
    parser.add_argument("--research-output", default=RESEARCH_OUTPUT_PATH)
    parser.add_argument("--contacts-output", default=CONTACTS_OUTPUT_PATH)
    args = parser.parse_args()

    contacts_df = load_contacts(args.input)
    unique_companies = get_unique_companies(contacts_df)

    print(f"{len(contacts_df)} total contacts, {len(unique_companies)} unique companies")

    if args.limit:
        unique_companies = unique_companies.head(args.limit)
        print(f"Limiting to first {args.limit} companies for this run")

    research_df = research_companies(unique_companies, on_progress=print_progress)
    save_csv(research_df, args.research_output)
    print(f"Saved {args.research_output}")

    enriched = merge_research_into_contacts(contacts_df, research_df)
    save_csv(enriched, args.contacts_output)
    print(f"Saved {args.contacts_output}")


if __name__ == "__main__":
    main()
