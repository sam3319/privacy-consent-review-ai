import pytest
from pathlib import Path

from src.document_classifier import detect_document_type


def test_detects_standard_terms_contract():
    result = detect_document_type(
        """
        서비스 이용 약관
        계약 당사자: 갑 주식회사 예시, 을 고객
        계약 목적: 온라인 서비스 제공
        계약 기간: 가입일부터 해지일까지
        계약 대금: 월 10,000원
        계약 해지: 서면 통지 후 해지할 수 있다.
        """
    )

    assert result["document_type"] == "standard_terms_contract"
    assert result["confidence"] >= 80


def test_detects_risky_sample_as_contract():
    text = Path("samples/risky_standard_terms_contract.txt").read_text(
        encoding="utf-8"
    )

    result = detect_document_type(text)

    assert result["document_type"] == "standard_terms_contract"


def test_detects_collection_consent():
    result = detect_document_type(
        """
        개인정보 수집·이용 동의
        수집·이용 목적: 회원 가입
        수집 개인정보 항목: 이름, 이메일
        보유 및 이용 기간: 탈퇴 시까지
        """
    )

    assert result["document_type"] == "collection"


def test_detects_combined_privacy_document():
    result = detect_document_type(
        """
        개인정보 수집·이용 및 제3자 제공 동의
        수집·이용 목적: 회원 가입
        수집 개인정보 항목: 이름
        제공받는 자: 주식회사 예시
        제공하는 개인정보 항목: 이름
        """
    )

    assert result["document_type"] == "combined"


def test_rejects_unknown_document():
    with pytest.raises(ValueError):
        detect_document_type("오늘 회의는 오후 세 시에 시작합니다.")
