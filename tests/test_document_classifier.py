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


def test_detects_housing_lease():
    result = detect_document_type(
        """
        주택 임대차 계약서
        임대인: 홍길동
        임차인: 김예시
        보증금: 100,000,000원
        월세: 500,000원
        임대차 기간: 2026년 7월 1일부터 2028년 6월 30일까지
        """
    )

    assert result["document_type"] == "housing_lease"


def test_detects_employment_contract():
    result = detect_document_type(
        """
        근로계약서
        사용자: 주식회사 예시
        근로자: 김예시
        소정근로시간: 1일 8시간
        임금: 월 3,000,000원
        근무 장소: 서울
        """
    )

    assert result["document_type"] == "employment_contract"
