from pathlib import Path

from src.ml_classifier import (
    DEFAULT_CLAUSE_MODEL_PATH,
    DEFAULT_MODEL_PATH,
    load_model_metrics,
    predict_clause_risks,
    predict_document_type,
)


def test_trained_model_artifact_exists():
    assert DEFAULT_MODEL_PATH.exists()
    assert DEFAULT_MODEL_PATH.stat().st_size > 1000


def test_model_predicts_each_document_group():
    cases = {
        "samples/complete_collection_consent.txt": "privacy_consent",
        "samples/risky_standard_terms_contract.txt": "standard_terms_contract",
        "samples/risky_housing_lease.txt": "housing_lease",
        "samples/risky_employment_contract.txt": "employment_contract",
    }
    for filename, expected in cases.items():
        text = Path(filename).read_text(encoding="utf-8")
        assert predict_document_type(text)["document_type"] == expected


def test_model_metrics_are_recorded_with_limitations():
    metrics = load_model_metrics()

    assert metrics["dataset_size"] == 320
    assert metrics["holdout_macro_f1"] >= 0.8
    assert metrics["limitations"]


def test_clause_model_artifact_and_predictions():
    assert DEFAULT_CLAUSE_MODEL_PATH.exists()
    predictions = predict_clause_risks(
        """
        갑은 어떠한 손해에 대해서도 일체의 책임을 지지 않는다.
        을은 계약을 해지할 수 없다.
        """
    )

    labels = {prediction["risk_type"] for prediction in predictions}
    assert "liability_exemption" in labels
    assert "termination_restriction" in labels
