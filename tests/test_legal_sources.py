from datetime import date

from src.legal_rules import load_legal_sources


def test_every_rule_has_official_law_go_kr_source():
    sources = load_legal_sources()
    all_rules = sources["rules"] + sources["review_signals"]

    assert all_rules
    for rule in all_rules:
        assert rule["official_url"].startswith(
            ("https://www.law.go.kr/", "https://law.go.kr/")
        )
        assert rule["article"].startswith("제")


def test_legal_metadata_has_effective_and_verification_dates():
    metadata = load_legal_sources()["metadata"]

    effective_date = date.fromisoformat(metadata["effective_date"])
    verified_date = date.fromisoformat(metadata["verified_date"])
    assert effective_date <= verified_date

