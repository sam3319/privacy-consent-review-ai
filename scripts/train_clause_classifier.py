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

from scripts.generate_clause_training_data import OUTPUT_PATH, build_dataset


MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "clause_risk_classifier.joblib"
METRICS_PATH = MODEL_DIR / "clause_risk_metrics.json"
RANDOM_SEED = 43


def load_dataset() -> tuple[list[str], list[str]]:
    if not OUTPUT_PATH.exists():
        build_dataset()
    with OUTPUT_PATH.open(encoding="utf-8", newline="") as source_file:
        rows = list(csv.DictReader(source_file))
    return [row["text"] for row in rows], [row["label"] for row in rows]


def train_and_save() -> dict:
    texts, labels = load_dataset()
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts,
        labels,
        test_size=0.25,
        random_state=RANDOM_SEED,
        stratify=labels,
    )
    pipeline = Pipeline(
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
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_SEED)
    cv_scores = cross_val_score(
        pipeline,
        train_texts,
        train_labels,
        cv=cv,
        scoring="f1_macro",
    )
    pipeline.fit(train_texts, train_labels)
    predictions = pipeline.predict(test_texts)
    metrics = {
        "model_type": "TF-IDF character n-gram + Logistic Regression",
        "task": "contract clause risk category classification",
        "trained_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
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
        "classification_report": classification_report(
            test_labels,
            predictions,
            output_dict=True,
            zero_division=0,
        ),
        "limitations": [
            "합성 템플릿 문장으로 학습되어 실제 계약서 외부 검증이 필요하다.",
            "조항 분류는 법적 위험이나 무효를 확정하지 않는다.",
            "법률 근거는 기존 규칙 엔진의 공식 법령 결과를 우선한다.",
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
    print(json.dumps(train_and_save(), ensure_ascii=False, indent=2))
