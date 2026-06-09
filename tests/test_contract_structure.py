from src.contract_structure import (
    find_internal_consistency_issues,
    split_contract_sections,
    summarize_by_perspective,
)


def test_splits_numbered_contract_sections():
    sections = split_contract_sections(
        """
        서비스 계약서
        제1조(목적)
        본 계약은 서비스 제공을 목적으로 한다.
        제2조 (대금)
        을은 갑에게 월 30,000원을 지급하여야 한다.
        """
    )

    assert [section["number"] for section in sections] == ["전문", "제1조", "제2조"]
    assert sections[1]["title"] == "목적"
    assert "30,000원" in sections[2]["text"]


def test_builds_party_perspective_summary():
    summary = summarize_by_perspective(
        "을은 매월 30,000원을 지급하여야 한다.\n을은 30일 전에 해지할 수 있다.",
        "을",
    )

    assert summary["obligations"]
    assert summary["amounts"]
    assert summary["termination"]


def test_finds_date_and_payment_inconsistencies():
    issues = find_internal_consistency_issues(
        """
        계약 기간: 2026년 12월 31일부터 2026년 1월 1일까지
        총 대금: 1,000,000원
        계약금: 300,000원
        잔금: 600,000원
        """
    )

    assert {issue["id"] for issue in issues} == {
        "CONTRACT_DATE_ORDER",
        "CONTRACT_PAYMENT_SUM",
    }
