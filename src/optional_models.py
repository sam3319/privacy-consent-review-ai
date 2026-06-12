import os
from functools import lru_cache
from pathlib import Path

from src.model_security import ModelIntegrityError, verify_model_directory


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NER_MODEL_PATH = ROOT / "models" / "transformer_ner"
DEFAULT_NER_MINIMUM_SCORE = 0.5


@lru_cache(maxsize=1)
def load_transformer_ner():
    configured_path = os.getenv("LEGAL_NER_MODEL_PATH", "").strip()
    model_path = Path(configured_path) if configured_path else DEFAULT_NER_MODEL_PATH
    if not model_path.is_dir():
        return None
    try:
        verify_model_directory(model_path)
    except (FileNotFoundError, ModelIntegrityError):
        return None
    try:
        from transformers import pipeline
    except (ImportError, OSError, ValueError):
        return None
    try:
        return pipeline(
            "token-classification",
            model=str(model_path),
            tokenizer=str(model_path),
            aggregation_strategy="simple",
            device=-1,
        )
    except (OSError, ValueError):
        return None


def predict_transformer_span(text: str, field_label: str) -> dict | None:
    classifier = load_transformer_ner()
    if classifier is None:
        return None
    expected = transformer_entity_label(field_label)
    minimum_score = _minimum_ner_score()
    candidates = [
        item
        for item in classifier(text)
        if _entity_group(item) in {expected, "VALUE"}
        and float(item.get("score", 0)) >= minimum_score
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda item: float(item.get("score", 0)))
    start = int(best["start"])
    end = int(best["end"])
    return {
        "value": text[start:end].strip(" -·ㆍ"),
        "span_start": start,
        "span_end": end,
        "span_method": "transformer_ner",
        "span_probability": round(float(best.get("score", 0)) * 100, 2),
    }


def transformer_entity_label(field_label: str) -> str:
    return field_label.replace(".", "_").replace("-", "_").upper()


def _entity_group(item: dict) -> str:
    raw_label = item.get("entity_group") or item.get("entity") or ""
    label = str(raw_label).upper()
    return label[2:] if label.startswith(("B-", "I-")) else label


def _minimum_ner_score() -> float:
    configured = os.getenv("LEGAL_NER_MINIMUM_SCORE", "").strip()
    if not configured:
        return DEFAULT_NER_MINIMUM_SCORE
    try:
        return min(max(float(configured), 0.0), 1.0)
    except ValueError:
        return DEFAULT_NER_MINIMUM_SCORE


@lru_cache(maxsize=1)
def load_sentence_embedding_model():
    model_path = os.getenv("LEGAL_EMBEDDING_MODEL_PATH", "").strip()
    if not model_path:
        return None
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    return SentenceTransformer(model_path)
