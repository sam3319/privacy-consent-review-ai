import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_training_data import OUTPUT_PATH, build_dataset


MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "document_type_classifier.joblib"
METRICS_PATH = MODEL_DIR / "document_type_metrics.json"
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
                    max_features=12000,
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
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
    cv_scores = cross_val_score(
        pipeline,
        train_texts,
        train_labels,
        cv=cross_validation,
        scoring="f1_macro",
    )
    pipeline.fit(train_texts, train_labels)
    predictions = pipeline.predict(test_texts)
    report = classification_report(
        test_labels,
        predictions,
        output_dict=True,
        zero_division=0,
    )
    metrics = {
        "model_type": "TF-IDF character n-gram + Logistic Regression",
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
        "cross_validation_macro_f1_mean": round(float(cv_scores.mean()), 4),
        "cross_validation_macro_f1_std": round(float(cv_scores.std()), 4),
        "classification_report": report,
        "limitations": [
            "학습 데이터는 개인정보를 포함하지 않는 합성 템플릿 데이터이다.",
            "실제 문서의 다양한 표현과 OCR 오류에 대한 외부 검증이 필요하다.",
            "모델 예측은 법적 판단이 아니라 규칙 엔진 선택을 보조한다.",
        ],
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    METRICS_PATH.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return metrics


if __name__ == "__main__":
    result = train_and_save()
    print(json.dumps(result, ensure_ascii=False, indent=2))
