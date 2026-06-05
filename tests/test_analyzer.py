import pytest

from src.analyzer import analyze_document, redact_personal_data


COMPLETE_COLLECTION_CONSENT = """
개인정보 수집·이용 동의
수집·이용 목적: 회원 가입 및 본인 확인
수집하는 개인정보 항목: 이름, 이메일
보유 및 이용 기간: 회원 탈퇴 시까지
귀하는 개인정보 수집·이용 동의를 거부할 권리가 있습니다.
동의를 거부하는 경우 회원 가입이 제한됩니다.
"""


def finding(result: dict, rule_id: str) -> dict:
    return next(item for item in result["findings"] if item["rule_id"] == rule_id)


def test_complete_collection_notice_detects_four_required_items():
    result = analyze_document(COMPLETE_COLLECTION_CONSENT, "collection")

    assert result["completeness"] == 100
    for rule_id in (
        "PIPA_15_2_PURPOSE",
        "PIPA_15_2_ITEMS",
        "PIPA_15_2_RETENTION",
        "PIPA_15_2_REFUSAL",
    ):
        assert finding(result, rule_id)["status"] == "확인"


def test_missing_retention_period_is_reported_as_possible_omission():
    text = COMPLETE_COLLECTION_CONSENT.replace(
        "보유 및 이용 기간: 회원 탈퇴 시까지",
        "",
    )

    result = analyze_document(text, "collection")

    assert finding(result, "PIPA_15_2_RETENTION")["status"] == "누락 가능성"


def test_sensitive_information_triggers_separate_consent_review():
    text = COMPLETE_COLLECTION_CONSENT.replace(
        "이름, 이메일",
        "이름, 이메일, 건강정보",
    )

    result = analyze_document(text, "collection")

    assert finding(result, "PIPA_23_SENSITIVE")["status"] == "검토 필요"


def test_third_party_notice_uses_article_17_requirements():
    text = """
    개인정보 제3자 제공 동의
    제공받는 자: 주식회사 예시
    제공받는 자의 이용 목적: 배송
    제공하는 개인정보 항목: 이름, 주소
    제공받는 자의 보유 및 이용 기간: 배송 완료 후 30일
    제3자 제공 동의를 거부할 권리가 있으며 거부 시 배송 서비스 이용이 제한됩니다.
    """

    result = analyze_document(text, "third_party")

    assert result["completeness"] == 100
    assert finding(result, "PIPA_17_2_RECIPIENT")["status"] == "확인"


def test_resident_number_requires_specific_legal_basis_review():
    text = COMPLETE_COLLECTION_CONSENT.replace(
        "이름, 이메일",
        "이름, 주민등록번호",
    )

    result = analyze_document(text, "collection")

    resident_number_finding = finding(
        result,
        "PIPA_24_2_RESIDENT_NUMBER",
    )
    assert resident_number_finding["status"] == "검토 필요"
    assert "동의만으로" in resident_number_finding["message"]


def test_personal_data_preview_redacts_common_identifiers():
    text = "홍길동 900101-1234567 010-1234-5678 user@example.com"

    redacted = redact_personal_data(text)

    assert "900101-1234567" not in redacted
    assert "010-1234-5678" not in redacted
    assert "user@example.com" not in redacted


def test_empty_document_is_rejected():
    with pytest.raises(ValueError):
        analyze_document("  ", "collection")
