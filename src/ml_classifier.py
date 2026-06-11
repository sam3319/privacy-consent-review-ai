import json
import re
from pathlib import Path

from src.model_security import load_verified_joblib


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = ROOT / "models" / "document_type_classifier.joblib"
DEFAULT_METRICS_PATH = ROOT / "models" / "document_type_metrics.json"
DEFAULT_CLAUSE_MODEL_PATH = ROOT / "models" / "clause_risk_classifier.joblib"
DEFAULT_CLAUSE_METRICS_PATH = ROOT / "models" / "clause_risk_metrics.json"
DEFAULT_FIELD_MODEL_PATH = ROOT / "models" / "field_extractor.joblib"
DEFAULT_FIELD_METRICS_PATH = ROOT / "models" / "field_extractor_metrics.json"
DEFAULT_FIELD_SPAN_MODEL_PATH = ROOT / "models" / "field_span_extractor.joblib"
DEFAULT_FIELD_SPAN_METRICS_PATH = (
    ROOT / "models" / "field_span_extractor_metrics.json"
)

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
    return load_verified_joblib(path)


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
    return load_verified_joblib(path)


def predict_clause_risks(
    text: str,
    model=None,
    minimum_probability: float = 0.55,
) -> list[dict]:
    try:
        classifier = model or load_clause_risk_model()
    except (FileNotFoundError, OSError, ValueError):
        return []
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


def load_field_extractor_model(path: Path = DEFAULT_FIELD_MODEL_PATH):
    if not path.exists():
        raise FileNotFoundError(
            "학습된 필드 추출 모델이 없습니다. "
            "`python scripts/train_field_extractor.py`를 실행하세요."
        )
    return load_verified_joblib(path)


def predict_field_candidates(
    text: str,
    document_group: str,
    allowed_keys: set[str],
    model=None,
    minimum_probability: float = 0.25,
) -> list[dict]:
    classifier = model or load_field_extractor_model()
    expected_labels = {f"{document_group}.{key}" for key in allowed_keys}
    candidates = {}
    for line in (item.strip() for item in text.splitlines()):
        if len(line) < 4:
            continue
        probabilities = classifier.predict_proba([line])[0]
        classes = [str(label) for label in classifier.classes_]
        best_index = int(probabilities.argmax())
        label = classes[best_index]
        probability = float(probabilities[best_index])
        if label not in expected_labels or probability < minimum_probability:
            continue
        key = label.split(".", 1)[1]
        current = candidates.get(key)
        if current and current["probability"] >= probability * 100:
            continue
        span = predict_field_value_span(line, label)
        candidates[key] = {
            "key": key,
            "line": line,
            **(span or _field_value_from_line(line)),
            "probability": round(probability * 100, 2),
            "model_type": (
                "TF-IDF character n-gram + calibrated Logistic Regression"
            ),
        }
    return list(candidates.values())


def load_field_span_model(path: Path = DEFAULT_FIELD_SPAN_MODEL_PATH):
    if not path.exists():
        raise FileNotFoundError(
            "학습된 필드 span 모델이 없습니다. "
            "`python scripts/train_field_span_extractor.py`를 실행하세요."
        )
    return load_verified_joblib(path)


def predict_field_value_span(
    line: str,
    field_label: str,
    model=None,
) -> dict | None:
    from src.optional_models import predict_transformer_span

    transformer_result = predict_transformer_span(line, field_label)
    if transformer_result:
        return transformer_result
    try:
        bundle = model or load_field_span_model()
        from scripts.train_field_span_extractor import token_features

        matches = list(re.finditer(r"\S+", line))
        tokens = [match.group(0) for match in matches]
        features = [
            token_features(tokens, index, field_label)
            for index in range(len(tokens))
        ]
        matrix = bundle["vectorizer"].transform(features)
        labels = bundle["classifier"].predict(matrix)
    except (FileNotFoundError, OSError, ValueError):
        return None
    selected = [
        match
        for match, label in zip(matches, labels)
        if str(label) in {"B-VALUE", "I-VALUE"}
    ]
    if not selected:
        return None
    start = selected[0].start()
    end = selected[-1].end()
    return {
        "value": line[start:end].strip(" -·ㆍ"),
        "span_start": start,
        "span_end": end,
        "span_method": "bio_token_model",
    }


def _field_value_from_line(line: str) -> dict:
    if re_match := re.search(r"[:：]\s*(.+)$", line):
        raw_value = re_match.group(1)
        value = raw_value.strip(" -·ㆍ")
        start = line.find(value, re_match.start(1))
        return {"value": value, "span_start": start, "span_end": start + len(value)}
    particle_match = re.search(
        r"(?:은|는)\s+(.+)$",
        line,
    )
    if particle_match:
        raw_value = particle_match.group(1)
        value = raw_value.strip(" -·ㆍ")
        start = line.find(value, particle_match.start(1))
        return {"value": value, "span_start": start, "span_end": start + len(value)}
    value = line.strip(" -·ㆍ")
    start = line.find(value)
    return {"value": value, "span_start": start, "span_end": start + len(value)}
