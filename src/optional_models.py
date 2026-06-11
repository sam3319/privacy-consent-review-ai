import os
from functools import lru_cache


@lru_cache(maxsize=1)
def load_transformer_ner():
    model_path = os.getenv("LEGAL_NER_MODEL_PATH", "").strip()
    if not model_path:
        return None
    try:
        from transformers import pipeline
    except ImportError:
        return None
    return pipeline(
        "token-classification",
        model=model_path,
        tokenizer=model_path,
        aggregation_strategy="simple",
    )


def predict_transformer_span(text: str, field_label: str) -> dict | None:
    classifier = load_transformer_ner()
    if classifier is None:
        return None
    expected = field_label.replace(".", "_").upper()
    candidates = [
        item
        for item in classifier(text)
        if str(item.get("entity_group", "")).upper() in {expected, "VALUE"}
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda item: float(item.get("score", 0)))
    return {
        "value": text[int(best["start"]):int(best["end"])],
        "span_start": int(best["start"]),
        "span_end": int(best["end"]),
        "span_method": "transformer_ner",
        "span_probability": round(float(best.get("score", 0)) * 100, 2),
    }


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
