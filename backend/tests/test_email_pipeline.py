from unittest.mock import MagicMock

import pandas as pd
import pytest

import pipelines.email.drafts_store as drafts_store
import pipelines.email.pipeline as email_pipeline
from data_loader import load_leads_with_research_status
from models.schemas import EmailDraft


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr(email_pipeline.time, "sleep", lambda _: None)


def _mock_crew(monkeypatch, kickoff_side_effect):
    mock_kickoff = MagicMock(side_effect=kickoff_side_effect)
    mock_crew_instance = MagicMock(kickoff=mock_kickoff)
    mock_email_crew = MagicMock()
    mock_email_crew.return_value.crew.return_value = mock_crew_instance
    monkeypatch.setattr(email_pipeline, "EmailCrew", mock_email_crew)
    return mock_kickoff


def _crew_output(subject="Hello", body="Body text"):
    output = MagicMock()
    output.pydantic = EmailDraft(subject=subject, body=body)
    return output


def _researched_leads(workspace, contacts_df):
    """Seeds company_research.csv so both companies show as 'researched', then
    returns the joined leads dataframe personalize_contacts expects."""
    pd.DataFrame(
        [
            {"__company_key": "https://acme-council.gov.uk", "values_alignment": "net zero", "recent_relevant_news": "none found", "facility_notes": "none found"},
            {"__company_key": "Beta Health Trust", "values_alignment": "net zero", "recent_relevant_news": "none found", "facility_notes": "none found"},
        ]
    ).to_csv(workspace["research_output_path"], index=False)
    return load_leads_with_research_status(workspace["contacts_path"], workspace["research_output_path"])


def test_personalize_contacts_success_path(workspace, monkeypatch, contacts_df):
    leads = _researched_leads(workspace, contacts_df)
    _mock_crew(monkeypatch, [_crew_output(subject="s1"), _crew_output(subject="s2"), _crew_output(subject="s3")])

    result = email_pipeline.personalize_contacts(leads, agenda_text="Q3 campaign")

    assert len(result) == 3
    assert set(result["subject"]) == {"s1", "s2", "s3"}
    assert (result["status"] == "pending").all()


def test_personalize_contacts_isolates_errors_per_item(workspace, monkeypatch, contacts_df):
    leads = _researched_leads(workspace, contacts_df)
    _mock_crew(monkeypatch, [RuntimeError("LLM timeout"), _crew_output(), _crew_output()])

    result = email_pipeline.personalize_contacts(leads, agenda_text="Q3 campaign")

    assert len(result) == 3
    failed = result.iloc[0]
    assert failed["subject"] == "error"
    assert "LLM timeout" in failed["body"]


def test_run_personalize_persists_agenda_text(workspace, monkeypatch, contacts_df):
    _researched_leads(workspace, contacts_df)
    _mock_crew(monkeypatch, [_crew_output(), _crew_output(), _crew_output()])

    email_pipeline.run_personalize(contact_keys=None, agenda_text="Q3 sustainability push")

    with open(workspace["campaign_agenda_path"], encoding="utf-8") as f:
        assert f.read() == "Q3 sustainability push"


def test_run_personalize_skips_approved_contacts(workspace, monkeypatch, contacts_df):
    leads = _researched_leads(workspace, contacts_df)
    alice_key = leads.loc[leads["First Name"] == "Alice", "contact_key"].iloc[0]

    # Alice already has an approved draft.
    drafts_store.upsert_drafts(
        pd.DataFrame([{"contact_key": alice_key, "subject": "Approved copy", "body": "b", "status": "approved", "updated_at": drafts_store.now_iso()}])
    )

    mock_kickoff = _mock_crew(monkeypatch, [_crew_output(), _crew_output()])

    email_pipeline.run_personalize(contact_keys=None, agenda_text="Q3 campaign")

    # Only Bob and Carol should have been generated for - Alice is protected.
    assert mock_kickoff.call_count == 2
    drafts = drafts_store.read_drafts()
    alice_draft = drafts[drafts["contact_key"] == alice_key].iloc[0]
    assert alice_draft["subject"] == "Approved copy"
    assert alice_draft["status"] == "approved"


def test_run_personalize_raises_when_no_eligible_contacts(workspace):
    # No research done yet - every contact is "pending", none eligible.
    with pytest.raises(ValueError, match="No eligible contacts"):
        email_pipeline.run_personalize(contact_keys=None, agenda_text="Q3 campaign")


def test_run_personalize_filters_to_requested_contact_keys(workspace, monkeypatch, contacts_df):
    leads = _researched_leads(workspace, contacts_df)
    carol_key = leads.loc[leads["First Name"] == "Carol", "contact_key"].iloc[0]

    mock_kickoff = _mock_crew(monkeypatch, [_crew_output()])

    email_pipeline.run_personalize(contact_keys=[carol_key], agenda_text="Q3 campaign")

    assert mock_kickoff.call_count == 1
    drafts = drafts_store.read_drafts()
    assert list(drafts["contact_key"]) == [carol_key]
