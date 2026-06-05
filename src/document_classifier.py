import re


DOCUMENT_TYPE_LABELS = {
    "collection": "개인정보 수집·이용 동의",
    "third_party": "개인정보 제3자 제공 동의",
    "combined": "수집·이용 및 제3자 제공 복합 문서",
    "standard_terms_contract": "약관형 계약서",
}


def _count_matches(text: str, patterns: list[str]) -> int:
    return sum(bool(re.search(pattern, text, re.IGNORECASE)) for pattern in patterns)


def detect_document_type(text: str) -> dict:
    if not text.strip():
        raise ValueError("문서 유형을 감지할 내용이 없습니다.")

    collection_score = _count_matches(
        text,
        [
            r"개인정보.{0,10}수집",
            r"수집.{0,10}이용.{0,10}목적",
            r"수집.{0,10}(개인정보)?.{0,5}항목",
            r"보유.{0,8}이용.{0,8}기간",
        ],
    )
    third_party_score = _count_matches(
        text,
        [
            r"제3자.{0,10}제공",
            r"제공.{0,5}받는.{0,5}자",
            r"제공(?:하는)?.{0,8}(개인정보)?.{0,5}항목",
            r"제공.{0,20}보유.{0,8}이용.{0,8}기간",
        ],
    )
    contract_score = _count_matches(
        text,
        [
            r"(계약서|이용\s*약관|서비스\s*약관)",
            r"계약\s*당사자",
            r"계약\s*(목적|대상|기간|대금|해지)",
            r"(손해\s*배상|위약금|위약벌)",
            r"(분쟁\s*해결|재판\s*관할|관할\s*법원)",
        ],
    )

    if collection_score >= 2 and third_party_score >= 2:
        document_type = "combined"
        score = collection_score + third_party_score
        maximum = 8
    elif contract_score >= max(collection_score, third_party_score) and contract_score >= 2:
        document_type = "standard_terms_contract"
        score = contract_score
        maximum = 5
    elif third_party_score > collection_score and third_party_score >= 2:
        document_type = "third_party"
        score = third_party_score
        maximum = 4
    elif collection_score >= 2:
        document_type = "collection"
        score = collection_score
        maximum = 4
    else:
        raise ValueError(
            "문서 유형을 신뢰할 수준으로 감지하지 못했습니다. 문서 유형을 직접 선택하세요."
        )

    confidence = min(95, 60 + round(score / maximum * 35))
    return {
        "document_type": document_type,
        "label": DOCUMENT_TYPE_LABELS[document_type],
        "confidence": confidence,
        "scores": {
            "collection": collection_score,
            "third_party": third_party_score,
            "standard_terms_contract": contract_score,
        },
    }
