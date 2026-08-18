import hashlib
import os

import pandas as pd
import pytest

import data_loader


def test_compute_company_key_prefers_website(contacts_df):
    keys = data_loader.compute_company_key(contacts_df)
    # Alice and Bob are both at Acme Council, which has a Website - same key.
    assert keys.iloc[0] == keys.iloc[1] == "https://acme-council.gov.uk"


def test_compute_company_key_falls_back_to_company_name(contacts_df):
    keys = data_loader.compute_company_key(contacts_df)
    # Carol's company (Beta Health Trust) has no Website.
    assert keys.iloc[2] == "Beta Health Trust"


def test_compute_contact_key_prefers_lowercased_email(contacts_df):
    keys = data_loader.compute_contact_key(contacts_df)
    expected = hashlib.sha1(b"alice@acme-council.gov.uk").hexdigest()
    assert keys.iloc[0] == expected


def test_compute_contact_key_falls_back_when_no_email(contacts_df):
    keys = data_loader.compute_contact_key(contacts_df)
    # Bob has no email - falls back to a hash of company_key|first|last.
    expected = hashlib.sha1(b"https://acme-council.gov.uk|Bob|Brown").hexdigest()
    assert keys.iloc[1] == expected


def test_compute_contact_key_is_unique_per_contact(contacts_df):
    keys = data_loader.compute_contact_key(contacts_df)
    assert keys.nunique() == len(contacts_df)


def test_get_unique_companies_dedupes_by_company_key(contacts_df):
    unique = data_loader.get_unique_companies(contacts_df)
    # Alice and Bob share a company - 3 contacts collapse to 2 companies.
    assert len(unique) == 2
    assert set(unique["__company_key"]) == {"https://acme-council.gov.uk", "Beta Health Trust"}


def test_merge_research_into_contacts_joins_and_drops_key(contacts_df):
    research_df = pd.DataFrame(
        [{"__company_key": "https://acme-council.gov.uk", "values_alignment": "net zero by 2040"}]
    )
    merged = data_loader.merge_research_into_contacts(contacts_df, research_df)

    assert "__company_key" not in merged.columns
    assert merged.loc[merged["First Name"] == "Alice", "values_alignment"].iloc[0] == "net zero by 2040"
    # Carol's company (Beta Health Trust) has no research row - left join gives NaN, not an error.
    assert pd.isna(merged.loc[merged["First Name"] == "Carol", "values_alignment"].iloc[0])


def test_load_leads_with_research_status_all_pending_when_research_file_missing(contacts_csv, tmp_path):
    missing_research_path = str(tmp_path / "does-not-exist.csv")
    df = data_loader.load_leads_with_research_status(contacts_csv, missing_research_path)

    assert (df["research_status"] == "pending").all()
    assert list(df["lead_id"]) == [0, 1, 2]
    assert df["contact_key"].nunique() == 3


def test_load_leads_with_research_status_derives_researched_and_error(contacts_csv, tmp_path):
    research_path = tmp_path / "company_research.csv"
    pd.DataFrame(
        [
            {
                "__company_key": "https://acme-council.gov.uk",
                "values_alignment": "net zero by 2040",
                "recent_relevant_news": "none found",
                "facility_notes": "none found",
            },
            {
                "__company_key": "Beta Health Trust",
                "values_alignment": "error",
                "recent_relevant_news": "error",
                "facility_notes": "error: timed out",
            },
        ]
    ).to_csv(research_path, index=False)

    df = data_loader.load_leads_with_research_status(contacts_csv, str(research_path))

    acme_rows = df[df["Company Name"] == "Acme Council"]
    assert (acme_rows["research_status"] == "researched").all()

    beta_rows = df[df["Company Name"] == "Beta Health Trust"]
    assert (beta_rows["research_status"] == "error").all()


def test_save_csv_writes_atomically_and_creates_parent_dir(tmp_path):
    path = tmp_path / "nested" / "output.csv"
    data_loader.save_csv(pd.DataFrame([{"a": 1}]), str(path))

    assert path.exists()
    assert not (tmp_path / "nested" / "output.csv.tmp").exists()
    assert pd.read_csv(path).to_dict("records") == [{"a": 1}]


def test_load_text_returns_empty_string_when_missing(tmp_path):
    assert data_loader.load_text(str(tmp_path / "missing.txt")) == ""


def test_save_text_then_load_text_roundtrips(tmp_path):
    path = tmp_path / "agenda.txt"
    data_loader.save_text("Q3 campaign: sustainable lighting.", str(path))

    assert data_loader.load_text(str(path)) == "Q3 campaign: sustainable lighting."
    assert not os.path.exists(f"{path}.tmp")


def test_atomic_replace_retries_transient_failures_then_succeeds(tmp_path, monkeypatch):
    tmp_file = tmp_path / "source.tmp"
    dest = tmp_path / "dest.csv"
    tmp_file.write_text("data")

    calls = {"count": 0}
    real_replace = os.replace

    def flaky_replace(src, dst):
        calls["count"] += 1
        if calls["count"] < 3:
            raise OSError("[WinError 5] Access is denied")
        return real_replace(src, dst)

    monkeypatch.setattr(data_loader.os, "replace", flaky_replace)
    monkeypatch.setattr(data_loader.time, "sleep", lambda _: None)  # don't actually wait in tests

    data_loader._atomic_replace(str(tmp_file), str(dest))

    assert calls["count"] == 3
    assert dest.read_text() == "data"


def test_atomic_replace_gives_up_after_max_retries(tmp_path, monkeypatch):
    tmp_file = tmp_path / "source.tmp"
    dest = tmp_path / "dest.csv"
    tmp_file.write_text("data")

    def always_fails(src, dst):
        raise OSError("[WinError 5] Access is denied")

    monkeypatch.setattr(data_loader.os, "replace", always_fails)
    monkeypatch.setattr(data_loader.time, "sleep", lambda _: None)

    with pytest.raises(OSError):
        data_loader._atomic_replace(str(tmp_file), str(dest))
