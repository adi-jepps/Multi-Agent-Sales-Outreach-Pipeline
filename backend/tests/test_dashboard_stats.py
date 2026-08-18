import pandas as pd
import pytest

import dashboard_stats


def test_bucket_counts_includes_zero_for_empty_buckets():
    series = pd.Series([10, 10, 3000])
    result = dashboard_stats._bucket_counts(
        series, dashboard_stats.EMPLOYEE_BUCKETS, dashboard_stats.EMPLOYEE_LABELS
    )

    by_label = {row["bucket"]: row["count"] for row in result}
    assert by_label["<50"] == 2
    assert by_label["1,000-4,999"] == 1
    assert by_label["50-249"] == 0  # empty buckets are still present, not omitted


def test_bucket_counts_ignores_nan_values():
    series = pd.Series([10, None, None])
    result = dashboard_stats._bucket_counts(
        series, dashboard_stats.EMPLOYEE_BUCKETS, dashboard_stats.EMPLOYEE_LABELS
    )
    assert sum(row["count"] for row in result) == 1


def test_get_dashboard_stats_company_size_and_industry_are_deduped_per_company(workspace):
    stats = dashboard_stats.get_dashboard_stats()

    # 3 contacts, 2 companies (Alice + Bob share Acme Council) - company-level
    # charts must count 2, not 3, or Acme would be over-weighted.
    assert sum(row["count"] for row in stats["company_size"]) == 2
    assert sum(row["count"] for row in stats["industry"]) == 2
    assert {row["label"] for row in stats["industry"]} == {
        "government administration",
        "hospital & health care",
    }


def test_get_dashboard_stats_titles_are_counted_per_contact_not_deduped(workspace):
    stats = dashboard_stats.get_dashboard_stats()

    # Titles are a person attribute - all 3 contacts should show up, even
    # though two of them share a company.
    assert sum(row["count"] for row in stats["titles"]) == 3
    assert {row["label"] for row in stats["titles"]} == {
        "Facilities Manager",
        "Estates Officer",
        "Head of Facilities",
    }


def test_get_dashboard_stats_revenue_reports_partial_fill_rate(workspace):
    stats = dashboard_stats.get_dashboard_stats()

    # Acme Council has Annual Revenue on file, Beta Health Trust doesn't.
    assert stats["revenue"]["total_companies"] == 2
    assert stats["revenue"]["companies_with_data"] == 1
    bucket_total = sum(row["count"] for row in stats["revenue"]["buckets"])
    assert bucket_total == 1


def test_get_dashboard_stats_research_pipeline_all_pending_with_no_research_file(workspace):
    stats = dashboard_stats.get_dashboard_stats()

    research = stats["pipeline"]["research"]
    assert research["total"] == 2  # 2 companies
    assert research["pending"] == 2
    assert research["researched"] == 0
    assert research["error"] == 0


def test_get_dashboard_stats_email_pipeline_empty_when_no_drafts(workspace):
    stats = dashboard_stats.get_dashboard_stats()

    emails = stats["pipeline"]["emails"]
    assert emails == {"pending": 0, "approved": 0, "rejected": 0, "total": 0}
