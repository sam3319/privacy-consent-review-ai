from pathlib import Path

from src.special_contract_analyzer import (
    analyze_employment_contract,
    analyze_housing_contract,
)


def finding_ids(result: dict) -> set[str]:
    return {finding["rule_id"] for finding in result["findings"]}


def test_housing_contract_flags_renewal_and_rent_increase():
    text = Path("samples/risky_housing_lease.txt").read_text(encoding="utf-8")

    result = analyze_housing_contract(text)
    ids = finding_ids(result)

    assert result["document_type"] == "housing_lease"
    assert "HLA_TERM_UNDER_TWO_YEARS" in ids
    assert "HLA_RENEWAL_REQUEST_WAIVER" in ids
    assert "HLA_RENT_INCREASE" in ids
    assert result["perspective"] == "임차인"


def test_employment_contract_flags_hours_wage_and_penalty():
    text = Path("samples/risky_employment_contract.txt").read_text(encoding="utf-8")

    result = analyze_employment_contract(text)
    ids = finding_ids(result)

    assert result["document_type"] == "employment_contract"
    assert "LSA_PENALTY" in ids
    assert "LSA_EXCESSIVE_HOURS" in ids
    assert "LSA_MINIMUM_WAGE" in ids


def test_employment_contract_reports_required_term_omissions():
    result = analyze_employment_contract(
        """
        근로계약서
        사용자·근로자: 사용자 예시회사, 근로자 김예시
        임금 구성·금액: 시급 12,000원
        """
    )

    ids = finding_ids(result)
    assert "LSA_REQUIRED_WORKPLACE" in ids
    assert "LSA_REQUIRED_WORK_HOURS" in ids
