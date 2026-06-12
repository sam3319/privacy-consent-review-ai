import json

from src.field_extraction import extract_contract_fields
from src.ml_classifier import (
    DEFAULT_FIELD_METRICS_PATH,
    DEFAULT_FIELD_MODEL_PATH,
    DEFAULT_FIELD_SPAN_MODEL_PATH,
    predict_field_value_span,
    predict_field_candidates,
)
from src.special_contract_analyzer import (
    analyze_employment_contract,
    analyze_housing_contract,
)


def field_by_key(result: dict, key: str) -> dict:
    return next(field for field in result["extracted_fields"] if field["key"] == key)


def test_field_model_artifact_and_metrics_exist():
    assert DEFAULT_FIELD_MODEL_PATH.exists()
    assert DEFAULT_FIELD_MODEL_PATH.stat().st_size > 1000
    assert DEFAULT_FIELD_METRICS_PATH.exists()
    assert DEFAULT_FIELD_SPAN_MODEL_PATH.exists()
    metrics = json.loads(DEFAULT_FIELD_METRICS_PATH.read_text(encoding="utf-8"))
    assert metrics["dataset_size"] == 1120
    assert metrics["limitations"]


def test_field_span_model_extracts_value_tokens():
    result = predict_field_value_span(
        "임차보증금은 1억 5,000만원으로 정한다.",
        "housing.deposit",
    )

    assert result is not None
    assert "1억" in result["value"]
    assert result["span_method"] in {"transformer_ner", "bio_token_model"}


def test_field_model_classifies_natural_housing_line():
    predictions = predict_field_candidates(
        "임차보증금은 1억 5,000만원으로 정한다.",
        "housing",
        {"deposit"},
    )

    assert predictions[0]["key"] == "deposit"
    assert "1억 5,000만원" in predictions[0]["value"]
    assert predictions[0]["span_end"] > predictions[0]["span_start"]


def test_housing_analysis_uses_ml_when_rule_label_is_absent():
    result = analyze_housing_contract(
        """
        주택 임대차 계약서
        임차보증금은 1억 5,000만원으로 정한다.
        임대할 주택은 서울특별시 예시구 101호이다.
        """
    )

    deposit = field_by_key(result, "deposit")
    assert deposit["status"] in {"확인", "사용자 확인 필요"}
    assert deposit["extraction_method"] == "ml_fallback"


def test_employment_analysis_uses_ml_for_natural_wage_sentence():
    result = analyze_employment_contract(
        """
        근로계약서
        근로자에게 월 기본급 3,000,000원을 지급한다.
        직원은 서울 본사에서 근무한다.
        """
    )

    wage = field_by_key(result, "wage")
    assert wage["status"] == "사용자 확인 필요"
    assert wage["extraction_method"] == "ml_fallback"


def test_contract_rule_extraction_remains_preferred():
    fields = extract_contract_fields(
        """
        계약 당사자: 갑 예시회사, 을 김고객
        계약 목적: 온라인 정보 제공
        """
    )
    parties = next(field for field in fields if field["key"] == "parties")

    assert parties["value"] == "갑 예시회사, 을 김고객"
    assert parties.get("extraction_method") != "ml_fallback"
