import json

from scripts.evaluate_anonymized_dataset import evaluate
from scripts.validate_anonymized_dataset import validate


def test_evaluation_framework_measures_document_and_fields():
    result = evaluate(
        [
            {
                "id": "housing-1",
                "document_type": "housing_lease",
                "text": (
                    "주택 임대차 계약서\n"
                    "임대인·임차인: 임대인 A, 임차인 B\n"
                    "보증금: 100,000,000원\n"
                    "임대차 기간: 2026년 7월 1일부터 2028년 6월 30일까지"
                ),
                "fields": {"deposit": "100,000,000원"},
            }
        ]
    )
    assert result["dataset_size"] == 1
    assert result["document_type_accuracy"] == 1.0
    assert result["document_type_errors"] == []
    assert result["field_evaluation"]["exact_match_rate"] == 1.0
    assert result["field_evaluation"]["by_field"]["deposit"] == {
        "expected": 1,
        "predicted": 1,
        "exact_match": 1,
        "exact_match_rate": 1.0,
    }
    assert result["field_evaluation"]["errors"] == []


def test_evaluation_framework_reports_field_errors():
    result = evaluate(
        [
            {
                "id": "housing-2",
                "document_type": "housing_lease",
                "text": "housing lease without a deposit value",
                "fields": {"deposit": "100000000"},
            }
        ]
    )

    assert result["field_evaluation"]["exact_match_rate"] == 0.0
    assert result["field_evaluation"]["by_field"]["deposit"]["predicted"] == 0
    assert result["field_evaluation"]["errors"] == [
        {
            "id": "housing-2",
            "document_type": "housing_lease",
            "field": "deposit",
            "expected": "100000000",
            "predicted": "",
            "error_type": "missing",
        }
    ]


def test_anonymization_validator_detects_sensitive_values(tmp_path):
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "document_type": "employment_contract",
                "text": "연락처 010-1234-5678",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert validate(dataset)[0]["type"] == "phone_number"
