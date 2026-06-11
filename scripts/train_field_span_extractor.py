import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_field_training_data import OUTPUT_PATH, build_dataset


MODEL_PATH = ROOT / "models" / "field_span_extractor.joblib"
METRICS_PATH = ROOT / "models" / "field_span_extractor_metrics.json"
RANDOM_SEED = 42


def token_features(tokens: list[str], index: int, field_label: str) -> dict:
    token = tokens[index]
    return {
        "field_label": field_label,
        "token": token,
        "prefix1": token[:1],
        "prefix2": token[:2],
        "suffix1": token[-1:],
        "suffix2": token[-2:],
        "has_digit": any(character.isdigit() for character in token),
        "has_colon": ":" in token or "：" in token,
        "position": index,
        "previous": tokens[index - 1] if index else "<START>",
        "next": tokens[index + 1] if index + 1 < len(tokens) else "<END>",
    }


def tokenize_labeled(row: dict) -> tuple[list[dict], list[str]]:
    text = row["text"]
    value = row.get("value", "")
    value_start = text.find(value) if value else -1
    value_end = value_start + len(value) if value_start >= 0 else -1
    matches = list(re.finditer(r"\S+", text))
    tokens = [match.group(0) for match in matches]
    features = [
        token_features(tokens, index, row["label"])
        for index in range(len(tokens))
    ]
    labels = []
    value_token_seen = False
    for match in matches:
        overlaps = value_start >= 0 and match.end() > value_start and match.start() < value_end
        if not overlaps:
            labels.append("O")
        elif not value_token_seen:
            labels.append("B-VALUE")
            value_token_seen = True
        else:
            labels.append("I-VALUE")
    return features, labels


def load_rows() -> list[dict]:
    build_dataset(OUTPUT_PATH)
    with OUTPUT_PATH.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def train_and_save() -> dict:
    rows = [row for row in load_rows() if row["label"] != "other"]
    train_rows, test_rows = train_test_split(
        rows,
        test_size=0.25,
        random_state=RANDOM_SEED,
        stratify=[row["label"] for row in rows],
    )
    train_features, train_labels = _flatten(train_rows)
    test_features, test_labels = _flatten(test_rows)
    vectorizer = DictVectorizer(sparse=True)
    train_matrix = vectorizer.fit_transform(train_features)
    test_matrix = vectorizer.transform(test_features)
    classifier = LogisticRegression(
        max_iter=2500,
        class_weight="balanced",
        random_state=RANDOM_SEED,
    )
    classifier.fit(train_matrix, train_labels)
    predictions = classifier.predict(test_matrix)
    metrics = {
        "model_type": "token feature Logistic Regression BIO tagger",
        "task": "contract field value span extraction",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "random_seed": RANDOM_SEED,
        "dataset_size": len(rows),
        "token_count": len(train_labels) + len(test_labels),
        "class_distribution": dict(Counter(train_labels + test_labels)),
        "holdout_macro_f1": round(
            f1_score(test_labels, predictions, average="macro"),
            4,
        ),
        "classification_report": classification_report(
            test_labels,
            predictions,
            output_dict=True,
            zero_division=0,
        ),
        "limitations": [
            "공백 토큰 기반 BIO 모델로 형태소 단위 한국어 NER보다 단순하다.",
            "합성 문장으로 학습되어 실제 문서와 OCR 오류에 대한 외부 평가가 필요하다.",
            "필드 문장 분류 모델이 선택한 문장 안에서 값 범위만 보조 추출한다.",
        ],
    }
    joblib.dump(
        {"vectorizer": vectorizer, "classifier": classifier},
        MODEL_PATH,
    )
    METRICS_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metrics


def _flatten(rows: list[dict]) -> tuple[list[dict], list[str]]:
    features = []
    labels = []
    for row in rows:
        row_features, row_labels = tokenize_labeled(row)
        features.extend(row_features)
        labels.extend(row_labels)
    return features, labels


if __name__ == "__main__":
    print(json.dumps(train_and_save(), ensure_ascii=False, indent=2))
