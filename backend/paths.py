"""
Single source of truth for file paths shared between the CLI (main.py) and
the API server (server.py), so their defaults can't drift out of sync again.
"""

CONTACTS_INPUT_PATH = "data/relevant-columns.csv"
RESEARCH_OUTPUT_PATH = "research output/company_research.csv"
CONTACTS_OUTPUT_PATH = "research output/contacts_with_research.csv"
CAMPAIGN_AGENDA_PATH = "research output/campaign_agenda.txt"
EMAIL_DRAFTS_PATH = "research output/email_drafts.csv"
