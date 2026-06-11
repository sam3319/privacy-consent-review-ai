from functools import lru_cache
from datetime import date

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.legal_rules import (
    load_contract_sources,
    load_employment_sources,
    load_housing_sources,
    load_legal_sources,
)


@lru_cache(maxsize=1)
def build_legal_corpus() -> list[dict]:
    corpus = []
    source_groups = [
        load_legal_sources(),
        load_contract_sources(),
        load_housing_sources(),
        load_employment_sources(),
    ]
    for source in source_groups:
        metadata = source["metadata"]
        rules = source.get("rules", source.get("review_signals", []))
        for rule in rules:
            text_parts = [
                metadata["law_name"],
                rule.get("article", ""),
                rule.get("title", ""),
                rule.get("message", ""),
                " ".join(rule.get("patterns", rule.get("trigger_patterns", []))),
            ]
            corpus.append(
                {
                    "id": rule["id"],
                    "law_name": metadata["law_name"],
                    "article": rule.get("article", ""),
                    "title": rule.get("title", ""),
                    "message": rule.get("message", ""),
                    "official_url": rule.get(
                        "official_url",
                        metadata.get("official_url", ""),
                    ),
                    "text": " ".join(part for part in text_parts if part),
                }
            )
    return corpus


def search_legal_basis(
    query: str,
    top_k: int = 3,
    minimum_score: float = 0.08,
) -> list[dict]:
    if not query.strip():
        return []
    corpus = build_legal_corpus()
    embedding_results = _search_with_embeddings(query, corpus, top_k, minimum_score)
    if embedding_results is not None:
        return embedding_results
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 5),
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform([item["text"] for item in corpus] + [query])
    scores = cosine_similarity(matrix[-1], matrix[:-1])[0]
    ranked = scores.argsort()[::-1]
    results = []
    for index in ranked:
        score = float(scores[index])
        if score < minimum_score:
            continue
        item = corpus[int(index)]
        results.append(
            {
                key: value
                for key, value in item.items()
                if key != "text"
            }
            | {"score": round(score * 100, 2)}
        )
        if len(results) >= top_k:
            break
    return results


def assess_legal_version(document_date: date | None, metadata: dict) -> dict | None:
    if document_date is None:
        return None
    effective_date = date.fromisoformat(metadata["effective_date"])
    verified_date = date.fromisoformat(metadata["verified_date"])
    if document_date < effective_date:
        status = "과거 기준 확인 필요"
        message = (
            f"문서 작성일은 {document_date.isoformat()}이고 현재 규칙의 법률 시행일은 "
            f"{effective_date.isoformat()}입니다. 작성 당시 법령을 별도로 확인해야 합니다."
        )
    elif document_date > verified_date:
        status = "최신성 확인 필요"
        message = (
            f"문서 작성일이 근거 확인일 {verified_date.isoformat()} 이후입니다. "
            "법률 개정 여부를 공식 원문에서 다시 확인해야 합니다."
        )
    else:
        status = "현재 규칙 범위"
        message = (
            f"문서 작성일이 현재 규칙 시행일과 근거 확인일 사이에 있습니다. "
            "개별 사실관계와 경과규정은 별도 확인해야 합니다."
        )
    return {
        "status": status,
        "message": message,
        "document_date": document_date.isoformat(),
        "effective_date": effective_date.isoformat(),
        "verified_date": verified_date.isoformat(),
    }


def _search_with_embeddings(
    query: str,
    corpus: list[dict],
    top_k: int,
    minimum_score: float,
) -> list[dict] | None:
    from src.optional_models import load_sentence_embedding_model

    model = load_sentence_embedding_model()
    if model is None:
        return None
    embeddings = model.encode(
        [item["text"] for item in corpus] + [query],
        normalize_embeddings=True,
    )
    scores = embeddings[:-1] @ embeddings[-1]
    results = []
    for index in scores.argsort()[::-1]:
        score = float(scores[index])
        if score < minimum_score:
            continue
        item = corpus[int(index)]
        results.append(
            {key: value for key, value in item.items() if key != "text"}
            | {
                "score": round(score * 100, 2),
                "retrieval_method": "sentence_embedding",
            }
        )
        if len(results) >= top_k:
            break
    return results
