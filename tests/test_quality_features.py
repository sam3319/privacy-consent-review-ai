import json
from datetime import date

from src.analyzer import detect_sensitive_data, redact_personal_data
from src.document_io import estimate_text_quality
from src.employment_calculator import calculate_wage_estimate
from src.legal_retrieval import assess_legal_version, search_legal_basis
from src.review_feedback import apply_field_corrections, build_feedback_json


def test_wage_estimate_calculates_premiums():
    result = calculate_wage_estimate(
        hourly_wage=12_000,
        regular_hours=40,
        overtime_hours=5,
        night_hours=2,
        holiday_hours=4,
    )

    assert result["regular_pay"] == 480_000
    assert result["overtime_pay"] == 90_000
    assert result["night_premium"] == 12_000
    assert result["holiday_pay"] == 72_000
    assert result["weekly_total"] == 654_000


def test_wage_estimate_warns_about_excessive_hours():
    result = calculate_wage_estimate(12_000, 40, overtime_hours=13)
    assert len(result["warnings"]) == 2


def test_wage_estimate_handles_holiday_over_eight_and_monthly_conversion():
    result = calculate_wage_estimate(
        monthly_ordinary_wage=2_508_000,
        monthly_standard_hours=209,
        regular_hours=40,
        holiday_hours=10,
        weekly_paid_holiday_hours=8,
    )

    assert result["inputs"]["hourly_wage"] == 12_000
    assert result["holiday_pay"] == 192_000
    assert result["paid_holiday_pay"] == 96_000


def test_legal_retrieval_returns_official_basis():
    results = search_legal_basis("임차인이 계약갱신요구권을 포기한다")

    assert results
    assert results[0]["id"] == "HLA_RENEWAL_REQUEST_WAIVER"
    assert results[0]["official_url"].startswith("https://")


def test_legal_version_check_flags_older_document():
    result = assess_legal_version(
        date(2024, 1, 1),
        {
            "effective_date": "2025-10-23",
            "verified_date": "2026-06-09",
        },
    )
    assert result["status"] == "과거 기준 확인 필요"


def test_field_corrections_are_audited_and_redacted():
    result = {
        "document_type": "employment_contract",
        "extracted_fields": [
            {
                "key": "wage",
                "label": "임금",
                "value": "월 200만원",
                "status": "확인",
                "confidence": 90,
            }
        ],
    }
    corrected = apply_field_corrections(result, {"wage": "월 300만원"})
    feedback = json.loads(
        build_feedback_json(
            result,
            {"wage": "월 300만원"},
            "연락처 010-1234-5678",
        )
    )

    assert corrected["extracted_fields"][0]["status"] == "사용자 수정"
    assert corrected["correction_audit"][0]["before"] == "월 200만원"
    assert "010-1234-5678" not in feedback["redacted_source_text"]


def test_security_masking_and_quality_estimate():
    text = (
        "성명: 홍길동\n주소: 서울특별시 예시구 101호\n"
        "계좌 123-456-789012\n연락처 010-1234-5678"
    )
    redacted = redact_personal_data(text)

    assert "홍길동" not in redacted
    assert "서울특별시 예시구 101호" not in redacted
    assert "123-456-789012" not in redacted
    assert {"성명 후보", "상세 주소 후보", "계좌번호 후보"} <= set(
        detect_sensitive_data(text)
    )
    assert estimate_text_quality("정상적인 한글 계약서 문장 123")["score"] >= 70
