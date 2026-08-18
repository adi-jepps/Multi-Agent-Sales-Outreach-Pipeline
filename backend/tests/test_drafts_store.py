import pandas as pd
import pytest

import pipelines.email.drafts_store as drafts_store


@pytest.fixture(autouse=True)
def _isolated_drafts_file(tmp_path, monkeypatch):
    """Every test in this file gets its own empty email_drafts.csv location."""
    monkeypatch.setattr(drafts_store, "EMAIL_DRAFTS_PATH", str(tmp_path / "email_drafts.csv"))


def _draft(contact_key="c1", status="pending", subject="Hi", body="Body", updated_at=None):
    return {
        "contact_key": contact_key,
        "subject": subject,
        "body": body,
        "status": status,
        "updated_at": updated_at or drafts_store.now_iso(),
    }


def test_read_drafts_empty_when_file_missing():
    df = drafts_store.read_drafts()
    assert df.empty
    assert list(df.columns) == [
        "contact_key", "subject", "body", "status", "updated_at", "outlook_draft_id", "outlook_pushed_at",
    ]


def test_upsert_drafts_inserts_new_rows():
    drafts_store.upsert_drafts(pd.DataFrame([_draft("c1"), _draft("c2")]))

    df = drafts_store.read_drafts()
    assert sorted(df["contact_key"]) == ["c1", "c2"]


def test_upsert_drafts_replaces_pending_rows():
    drafts_store.upsert_drafts(pd.DataFrame([_draft("c1", subject="Original")]))
    drafts_store.upsert_drafts(pd.DataFrame([_draft("c1", subject="Regenerated")]))

    df = drafts_store.read_drafts()
    assert len(df) == 1
    assert df.iloc[0]["subject"] == "Regenerated"


def test_upsert_drafts_protects_approved_rows_by_default():
    drafts_store.upsert_drafts(pd.DataFrame([_draft("c1", status="approved", subject="Approved copy")]))
    # Simulate a regenerate run that would otherwise overwrite c1.
    drafts_store.upsert_drafts(pd.DataFrame([_draft("c1", subject="Should be dropped"), _draft("c2")]))

    df = drafts_store.read_drafts()
    assert len(df) == 2
    c1_row = df[df["contact_key"] == "c1"].iloc[0]
    assert c1_row["subject"] == "Approved copy"
    assert c1_row["status"] == "approved"
    assert "c2" in set(df["contact_key"])


def test_update_draft_applies_patch_and_bumps_updated_at():
    drafts_store.upsert_drafts(pd.DataFrame([_draft("c1", subject="Original")]))
    original = drafts_store.read_drafts().iloc[0]

    updated = drafts_store.update_draft(
        "c1", {"subject": "Edited", "status": "approved"}, expected_updated_at=original["updated_at"]
    )

    assert updated["subject"] == "Edited"
    assert updated["status"] == "approved"
    assert updated["updated_at"] != original["updated_at"]


def test_update_draft_raises_stale_update_on_mismatch():
    drafts_store.upsert_drafts(pd.DataFrame([_draft("c1")]))

    with pytest.raises(drafts_store.StaleUpdate):
        drafts_store.update_draft("c1", {"status": "approved"}, expected_updated_at="not-the-real-timestamp")


def test_update_draft_raises_not_found_for_unknown_key():
    with pytest.raises(drafts_store.DraftNotFound):
        drafts_store.update_draft("nope", {"status": "approved"}, expected_updated_at="whatever")


def test_update_draft_partial_patch_leaves_other_fields_untouched():
    drafts_store.upsert_drafts(pd.DataFrame([_draft("c1", subject="Subject", body="Body")]))
    original = drafts_store.read_drafts().iloc[0]

    updated = drafts_store.update_draft("c1", {"status": "rejected"}, expected_updated_at=original["updated_at"])

    assert updated["subject"] == "Subject"
    assert updated["body"] == "Body"
    assert updated["status"] == "rejected"


def test_record_outlook_push_sets_id_and_timestamp():
    drafts_store.upsert_drafts(pd.DataFrame([_draft("c1", status="approved")]))
    original_updated_at = drafts_store.read_drafts().iloc[0]["updated_at"]

    updated = drafts_store.record_outlook_push("c1", "outlook-message-id-123")

    assert updated["outlook_draft_id"] == "outlook-message-id-123"
    assert updated["outlook_pushed_at"]  # non-empty timestamp
    assert updated["updated_at"] == original_updated_at  # untouched - not a human edit


def test_record_outlook_push_raises_not_found_for_unknown_key():
    with pytest.raises(drafts_store.DraftNotFound):
        drafts_store.record_outlook_push("nope", "outlook-message-id-123")
