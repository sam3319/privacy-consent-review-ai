import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_field_training_data import OUTPUT_PATH, build_dataset


MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "field_extractor.joblib"
METRICS_PATH = MODEL_DIR / "field_extractor_metrics.json"
RANDOM_SEED = 42


def load_dataset(path: Path = OUTPUT_PATH) -> tuple[list[str], list[str]]:
    if not path.exists():
        build_dataset(path)
    with path.open(encoding="utf-8", newline="") as source_file:
        rows = list(csv.DictReader(source_file))
    return [row["text"] for row in rows], [row["label"] for row in rows]


def build_pipeline() -> Pipeline:
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    min_df=2,
                    sublinear_tf=True,
                    max_features=18000,
                ),
            ),
            (
                "classifier",
                CalibratedClassifierCV(
                    estimator=LogisticRegression(
                        max_iter=2500,
                        class_weight="balanced",
                        random_state=RANDOM_SEED,
                    ),
                    method="sigmoid",
                    cv=3,
                ),
            ),
        ]
    )


def train_and_save() -> dict:
    texts, labels = load_dataset()
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts,
        labels,
        test_size=0.25,
        random_state=RANDOM_SEED,
        stratify=labels,
    )
    pipeline = build_pipeline()
    cross_validation = StratifiedKFold(
        n_splits=5,
        shuffle=True,
        random_state=RANDOM_SEED,
    )
    scores = cross_val_score(
        pipeline,
        train_texts,
        train_labels,
        cv=cross_validation,
        scoring="f1_macro",
    )
    pipeline.fit(train_texts, train_labels)
    predictions = pipeline.predict(test_texts)
    metrics = {
        "model_type": (
            "TF-IDF character n-gram + calibrated Logistic Regression"
        ),
        "task": "document field line classification",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "random_seed": RANDOM_SEED,
        "dataset_size": len(texts),
        "class_distribution": dict(Counter(labels)),
        "holdout_size": len(test_texts),
        "holdout_accuracy": round(accuracy_score(test_labels, predictions), 4),
        "holdout_macro_f1": round(
            f1_score(test_labels, predictions, average="macro"),
            4,
        ),
        "cross_validation_macro_f1_mean": round(float(scores.mean()), 4),
        "cross_validation_macro_f1_std": round(float(scores.std()), 4),
        "classification_report": classification_report(
            test_labels,
            predictions,
            output_dict=True,
            zero_division=0,
        ),
        "limitations": [
            "합성 문장으로 학습되어 실제 계약서 표현과 OCR 오류에 대한 외부 검증이 필요하다.",
            "문장 단위 필드 후보 분류 모델이며 토큰 단위 개체명 인식 모델은 아니다.",
            "정규식 추출 결과를 대체하지 않고 누락된 필드의 후보를 보완한다.",
        ],
        "probability_calibration": {
            "method": "sigmoid",
            "cross_validation_folds": 3,
        },
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    METRICS_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metrics


if __name__ == "__main__":
    print(json.dumps(train_and_save(), ensure_ascii=False, indent=2))
