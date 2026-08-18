import pandas as pd
import pytest
from fastapi.testclient import TestClient

import pipelines.email.drafts_store as drafts_store
import server
from data_loader import load_leads_with_research_status


@pytest.fixture(autouse=True)
def _reset_job_state():
    """server._states is a module-level global that would otherwise leak
    between tests - e.g. a 'running' state left over from one test causing
    an unexpected 409 in the next."""
    server._states.clear()
    yield
    server._states.clear()


@pytest.fixture
def client():
    return TestClient(server.app)


def test_get_filters_returns_industries_and_fixed_statuses(workspace, client):
    resp = client.get("/api/filters")
    assert resp.status_code == 200
    body = resp.json()
    assert body["industries"] == ["government administration", "hospital & health care"]
    assert body["research_statuses"] == ["researched", "pending", "error"]


def test_get_leads_table_returns_all_contacts(workspace, client):
    resp = client.get("/api/leads/table")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 3
    assert {r["contact_name"] for r in rows} == {"Alice Anderson", "Bob Brown", "Carol Carter"}
    assert all(r["research_status"] == "pending" for r in rows)


def test_get_leads_table_filters_by_industry(workspace, client):
    resp = client.get("/api/leads/table", params={"industry": "hospital & health care"})
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["contact_name"] == "Carol Carter"


def test_get_companies_groups_by_company_and_includes_lead_ids(workspace, client):
    resp = client.get("/api/companies")
    companies = resp.json()
    assert len(companies) == 2
    acme = next(c for c in companies if c["company_name"] == "Acme Council")
    assert acme["contact_count"] == 2
    assert sorted(acme["lead_ids"]) == [0, 1]


def test_get_lead_detail_404_for_unknown_id(workspace, client):
    resp = client.get("/api/leads/999")
    assert resp.status_code == 404


def test_get_lead_detail_returns_null_research_when_pending(workspace, client):
    resp = client.get("/api/leads/0")
    assert resp.status_code == 200
    assert resp.json()["research"] is None


def test_post_research_run_returns_202(workspace, client, monkeypatch):
    monkeypatch.setattr(server, "start_run", lambda company_keys: None)
    resp = client.post("/api/research/run", json={"lead_ids": None})
    assert resp.status_code == 202
    assert resp.json() == {"status": "started"}


def test_post_research_run_returns_409_while_already_running(workspace, client):
    server._states["research"] = server._State(status="running")
    resp = client.post("/api/research/run", json={"lead_ids": None})
    assert resp.status_code == 409


def test_post_emails_run_returns_409_while_already_running(workspace, client):
    server._states["personalize"] = server._State(status="running")
    resp = client.post("/api/emails/run", json={"lead_ids": None, "agenda_text": "Q3"})
    assert resp.status_code == 409


def test_pipeline_status_reflects_running_stage(workspace, client):
    server._states["research"] = server._State(
        status="running", total_items=5, completed_items=2, current_item="Acme Council"
    )
    resp = client.get("/api/pipeline-status")
    assert resp.json() == [
        {
            "stage": "research",
            "status": "running",
            "total_items": 5,
            "completed_items": 2,
            "current_item": "Acme Council",
            "started_at": None,
            "finished_at": None,
            "error_message": None,
        }
    ]


def test_pipeline_status_empty_when_idle(workspace, client):
    resp = client.get("/api/pipeline-status")
    assert resp.json() == []


def test_dashboard_stats_endpoint_returns_expected_shape(workspace, client):
    resp = client.get("/api/dashboard/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"pipeline", "company_size", "industry", "titles", "revenue"}


def test_get_campaign_agenda_empty_when_not_set(workspace, client):
    resp = client.get("/api/campaign-agenda")
    assert resp.json() == {"text": ""}


def test_get_emails_empty_when_no_drafts(workspace, client):
    resp = client.get("/api/emails")
    assert resp.status_code == 200
    assert resp.json() == []


def test_patch_email_404_for_unknown_contact(workspace, client):
    resp = client.patch(
        "/api/emails/does-not-exist", json={"status": "approved", "expected_updated_at": "whatever"}
    )
    assert resp.status_code == 404


def test_patch_email_409_on_stale_update(workspace, client):
    drafts_store.upsert_drafts(
        pd.DataFrame(
            [
                {
                    "contact_key": "c1",
                    "subject": "s",
                    "body": "b",
                    "status": "pending",
                    "updated_at": drafts_store.now_iso(),
                }
            ]
        )
    )

    resp = client.patch(
        "/api/emails/c1", json={"status": "approved", "expected_updated_at": "wrong-timestamp"}
    )
    assert resp.status_code == 409


def test_patch_email_success_updates_and_returns_enriched_row(workspace, client):
    leads = load_leads_with_research_status(workspace["contacts_path"], workspace["research_output_path"])
    carol_key = leads.loc[leads["First Name"] == "Carol", "contact_key"].iloc[0]

    drafts_store.upsert_drafts(
        pd.DataFrame(
            [
                {
                    "contact_key": carol_key,
                    "subject": "Original",
                    "body": "b",
                    "status": "pending",
                    "updated_at": drafts_store.now_iso(),
                }
            ]
        )
    )
    original_updated_at = drafts_store.read_drafts().iloc[0]["updated_at"]

    resp = client.patch(
        f"/api/emails/{carol_key}",
        json={"subject": "Edited subject", "status": "approved", "expected_updated_at": original_updated_at},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["subject"] == "Edited subject"
    assert body["status"] == "approved"
    assert body["contact_name"] == "Carol Carter"  # enriched from contacts, not just the draft
    assert body["company_name"] == "Beta Health Trust"


def test_push_to_outlook_404_for_unknown_contact(workspace, client):
    resp = client.post("/api/emails/does-not-exist/push-to-outlook")
    assert resp.status_code == 404


def test_push_to_outlook_400_when_not_approved(workspace, client):
    drafts_store.upsert_drafts(
        pd.DataFrame(
            [{"contact_key": "c1", "subject": "s", "body": "b", "status": "pending", "updated_at": drafts_store.now_iso()}]
        )
    )

    resp = client.post("/api/emails/c1/push-to-outlook")
    assert resp.status_code == 400


def test_push_to_outlook_400_when_contact_has_no_email(workspace, client):
    leads = load_leads_with_research_status(workspace["contacts_path"], workspace["research_output_path"])
    bob_key = leads.loc[leads["First Name"] == "Bob", "contact_key"].iloc[0]
    assert pd.isna(leads.loc[leads["First Name"] == "Bob", "Email"].iloc[0])  # sanity check on fixture data

    drafts_store.upsert_drafts(
        pd.DataFrame(
            [{"contact_key": bob_key, "subject": "s", "body": "b", "status": "approved", "updated_at": drafts_store.now_iso()}]
        )
    )

    resp = client.post(f"/api/emails/{bob_key}/push-to-outlook")
    assert resp.status_code == 400


def test_push_to_outlook_success_records_id_and_returns_enriched_row(workspace, client, monkeypatch):
    leads = load_leads_with_research_status(workspace["contacts_path"], workspace["research_output_path"])
    carol_key = leads.loc[leads["First Name"] == "Carol", "contact_key"].iloc[0]

    drafts_store.upsert_drafts(
        pd.DataFrame(
            [{"contact_key": carol_key, "subject": "s", "body": "b", "status": "approved", "updated_at": drafts_store.now_iso()}]
        )
    )

    captured = {}

    def fake_create_draft(subject, body, to_address):
        captured["subject"], captured["body"], captured["to_address"] = subject, body, to_address
        return {"id": "outlook-msg-id-1", "web_link": "https://outlook.office.com/mail/deeplink"}

    monkeypatch.setattr(server.outlook_client, "create_draft", fake_create_draft)

    resp = client.post(f"/api/emails/{carol_key}/push-to-outlook")

    assert resp.status_code == 200
    assert resp.json()["outlook_draft_id"] == "outlook-msg-id-1"
    assert captured["to_address"] == "carol@betahealth.org"  # the real contact's email
    assert captured["subject"] == "s"


def test_push_to_outlook_503_when_not_authorized(workspace, client, monkeypatch):
    leads = load_leads_with_research_status(workspace["contacts_path"], workspace["research_output_path"])
    carol_key = leads.loc[leads["First Name"] == "Carol", "contact_key"].iloc[0]

    drafts_store.upsert_drafts(
        pd.DataFrame(
            [{"contact_key": carol_key, "subject": "s", "body": "b", "status": "approved", "updated_at": drafts_store.now_iso()}]
        )
    )

    def fake_create_draft(subject, body, to_address):
        raise RuntimeError("Outlook isn't authorized yet - run `python scripts/authorize_outlook.py` once.")

    monkeypatch.setattr(server.outlook_client, "create_draft", fake_create_draft)

    resp = client.post(f"/api/emails/{carol_key}/push-to-outlook")
    assert resp.status_code == 503


def test_push_to_outlook_502_on_graph_api_error(workspace, client, monkeypatch):
    leads = load_leads_with_research_status(workspace["contacts_path"], workspace["research_output_path"])
    carol_key = leads.loc[leads["First Name"] == "Carol", "contact_key"].iloc[0]

    drafts_store.upsert_drafts(
        pd.DataFrame(
            [{"contact_key": carol_key, "subject": "s", "body": "b", "status": "approved", "updated_at": drafts_store.now_iso()}]
        )
    )

    def fake_create_draft(subject, body, to_address):
        raise RuntimeError("Outlook API error (400): bad request")

    monkeypatch.setattr(server.outlook_client, "create_draft", fake_create_draft)

    resp = client.post(f"/api/emails/{carol_key}/push-to-outlook")
    assert resp.status_code == 502
