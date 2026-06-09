import json
from pathlib import Path

import joblib


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = ROOT / "models" / "document_type_classifier.joblib"
DEFAULT_METRICS_PATH = ROOT / "models" / "document_type_metrics.json"
DEFAULT_CLAUSE_MODEL_PATH = ROOT / "models" / "clause_risk_classifier.joblib"
DEFAULT_CLAUSE_METRICS_PATH = ROOT / "models" / "clause_risk_metrics.json"

ML_LABELS = {
    "privacy_consent": "개인정보 동의서",
    "standard_terms_contract": "약관형 계약서",
    "housing_lease": "주택 임대차(전세·월세) 계약서",
    "employment_contract": "근로계약서",
}

ML_TO_RULE_TYPE = {
    "privacy_consent": "privacy_consent",
    "standard_terms_contract": "standard_terms_contract",
    "housing_lease": "housing_lease",
    "employment_contract": "employment_contract",
}

CLAUSE_LABELS = {
    "normal": "일반 조항",
    "liability_exemption": "책임 면제·제한",
    "termination_restriction": "해지 권리 제한",
    "excessive_penalty": "과도한 위약금 가능성",
    "housing_renewal_restriction": "임대차 갱신권 제한",
    "employment_penalty": "근로계약 위약 예정",
    "excessive_work_hours": "장시간 근로 가능성",
}


def load_document_type_model(path: Path = DEFAULT_MODEL_PATH):
    if not path.exists():
        raise FileNotFoundError(
            "학습된 문서 유형 분류 모델이 없습니다. "
            "`python scripts/train_document_classifier.py`를 실행하세요."
        )
    return joblib.load(path)


def predict_document_type(text: str, model=None) -> dict:
    if not text.strip():
        raise ValueError("문서 유형을 예측할 내용이 없습니다.")
    classifier = model or load_document_type_model()
    probabilities = classifier.predict_proba([text])[0]
    classes = [str(label) for label in classifier.classes_]
    ranking = sorted(
        (
            {
                "document_type": label,
                "label": ML_LABELS[label],
                "probability": round(float(probability) * 100, 2),
            }
            for label, probability in zip(classes, probabilities)
        ),
        key=lambda item: item["probability"],
        reverse=True,
    )
    prediction = ranking[0]
    return {
        **prediction,
        "confidence": round(prediction["probability"]),
        "probabilities": ranking,
        "model_type": "TF-IDF character n-gram + Logistic Regression",
    }


def load_model_metrics(path: Path = DEFAULT_METRICS_PATH) -> dict:
    with path.open(encoding="utf-8") as metrics_file:
        return json.load(metrics_file)


def load_clause_risk_model(path: Path = DEFAULT_CLAUSE_MODEL_PATH):
    if not path.exists():
        raise FileNotFoundError(
            "학습된 조항 위험 분류 모델이 없습니다. "
            "`python scripts/train_clause_classifier.py`를 실행하세요."
        )
    return joblib.load(path)


def predict_clause_risks(
    text: str,
    model=None,
    minimum_probability: float = 0.55,
) -> list[dict]:
    classifier = model or load_clause_risk_model()
    clauses = [
        line.strip()
        for line in text.splitlines()
        if len(line.strip()) >= 8
    ]
    predictions = []
    for clause in clauses:
        probabilities = classifier.predict_proba([clause])[0]
        classes = [str(label) for label in classifier.classes_]
        best_index = int(probabilities.argmax())
        label = classes[best_index]
        probability = float(probabilities[best_index])
        if label == "normal" or probability < minimum_probability:
            continue
        predictions.append(
            {
                "clause": clause,
                "risk_type": label,
                "label": CLAUSE_LABELS[label],
                "probability": round(probability * 100, 2),
                "model_type": "TF-IDF character n-gram + Logistic Regression",
            }
        )
    return predictions
