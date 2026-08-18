from unittest.mock import MagicMock

import pandas as pd
import pytest

import data_loader
import pipelines.research.pipeline as research_pipeline
from models.schemas import CompanyResearch


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr(research_pipeline.time, "sleep", lambda _: None)


def _mock_crew(monkeypatch, kickoff_side_effect):
    """Patches ResearchCrew so .crew().kickoff(...) follows the given side effects
    (a list of return values / exceptions, one per call, in order)."""
    mock_kickoff = MagicMock(side_effect=kickoff_side_effect)
    mock_crew_instance = MagicMock(kickoff=mock_kickoff)
    mock_research_crew = MagicMock()
    mock_research_crew.return_value.crew.return_value = mock_crew_instance
    monkeypatch.setattr(research_pipeline, "ResearchCrew", mock_research_crew)
    return mock_kickoff


def _crew_output(values_alignment="net zero by 2040", news="none found", facility="none found"):
    output = MagicMock()
    output.pydantic = CompanyResearch(
        values_alignment=values_alignment, recent_relevant_news=news, facility_notes=facility
    )
    return output


def test_research_companies_success_path(monkeypatch, contacts_df):
    unique_companies = data_loader.get_unique_companies(contacts_df)  # 2 companies
    _mock_crew(monkeypatch, [_crew_output(values_alignment="Acme result"), _crew_output(values_alignment="Beta result")])

    result = research_pipeline.research_companies(unique_companies)

    assert len(result) == 2
    assert set(result["values_alignment"]) == {"Acme result", "Beta result"}
    assert (result["__company_key"] == unique_companies["__company_key"]).all()


def test_research_companies_isolates_errors_per_item(monkeypatch, contacts_df):
    unique_companies = data_loader.get_unique_companies(contacts_df)
    _mock_crew(monkeypatch, [RuntimeError("scrape failed"), _crew_output(values_alignment="Beta result")])

    result = research_pipeline.research_companies(unique_companies)

    assert len(result) == 2  # one failure doesn't abort the batch
    failed_row = result.iloc[0]
    assert failed_row["values_alignment"] == "error"
    assert "scrape failed" in failed_row["facility_notes"]
    assert result.iloc[1]["values_alignment"] == "Beta result"


def test_research_companies_reports_progress(monkeypatch, contacts_df):
    unique_companies = data_loader.get_unique_companies(contacts_df)
    _mock_crew(monkeypatch, [_crew_output(), _crew_output()])

    progress_calls = []
    research_pipeline.research_companies(unique_companies, on_progress=lambda c, t, n: progress_calls.append((c, t, n)))

    assert progress_calls == [
        (0, 2, "Acme Council"),
        (1, 2, "Beta Health Trust"),
    ]


def test_run_research_upserts_preserving_untouched_companies(workspace, monkeypatch, contacts_df):
    # Seed an existing research file as if Beta Health Trust was researched previously.
    pd.DataFrame(
        [{"__company_key": "Beta Health Trust", "values_alignment": "previous result",
          "recent_relevant_news": "none found", "facility_notes": "none found"}]
    ).to_csv(workspace["research_output_path"], index=False)

    _mock_crew(monkeypatch, [_crew_output(values_alignment="fresh Acme result")])

    research_pipeline.run_research(company_keys=["https://acme-council.gov.uk"])

    saved = pd.read_csv(workspace["research_output_path"])
    assert len(saved) == 2
    beta_row = saved[saved["__company_key"] == "Beta Health Trust"].iloc[0]
    assert beta_row["values_alignment"] == "previous result"  # untouched, not overwritten
    acme_row = saved[saved["__company_key"] == "https://acme-council.gov.uk"].iloc[0]
    assert acme_row["values_alignment"] == "fresh Acme result"


def test_run_research_with_no_company_keys_researches_everyone(workspace, monkeypatch):
    mock_kickoff = _mock_crew(monkeypatch, [_crew_output(), _crew_output()])

    research_pipeline.run_research(company_keys=None)

    assert mock_kickoff.call_count == 2  # both companies researched
