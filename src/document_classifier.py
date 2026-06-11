import re


DOCUMENT_TYPE_LABELS = {
    "collection": "개인정보 수집·이용 동의",
    "third_party": "개인정보 제3자 제공 동의",
    "combined": "수집·이용 및 제3자 제공 복합 문서",
    "standard_terms_contract": "약관형 계약서",
    "housing_lease": "주택 임대차(전세·월세) 계약서",
    "employment_contract": "근로계약서",
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
    housing_score = _count_matches(
        text,
        [
            r"(주택|아파트|오피스텔).{0,10}(임대차|전세|월세)",
            r"(임대인|임차인)",
            r"(보증금|차임|월세)",
            r"(임대차\s*기간|임대\s*목적물)",
            r"(전입신고|확정일자|계약갱신요구권)",
        ],
    )
    employment_score = _count_matches(
        text,
        [
            r"근로\s*계약서",
            r"(사용자|사업주).{0,20}근로자",
            r"(소정\s*근로\s*시간|근무\s*시간)",
            r"(임금|기본급|시급|월급).{0,20}(지급|원)",
            r"(근무\s*장소|업무\s*내용|주휴일|연차)",
        ],
    )

    if collection_score >= 2 and third_party_score >= 2:
        document_type = "combined"
        score = collection_score + third_party_score
        maximum = 8
    elif employment_score >= max(
        housing_score, contract_score, collection_score, third_party_score
    ) and employment_score >= 2:
        document_type = "employment_contract"
        score = employment_score
        maximum = 5
    elif housing_score >= max(
        contract_score, collection_score, third_party_score
    ) and housing_score >= 2:
        document_type = "housing_lease"
        score = housing_score
        maximum = 5
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
            "housing_lease": housing_score,
            "employment_contract": employment_score,
        },
    }


def detect_document_type_hybrid(text: str) -> dict:
    from src.ml_classifier import predict_document_type

    try:
        rule_prediction = detect_document_type(text)
    except ValueError:
        rule_prediction = None
    try:
        ml_prediction = predict_document_type(text)
    except (FileNotFoundError, OSError, ValueError):
        if not rule_prediction:
            raise ValueError(
                "문서 유형 모델을 사용할 수 없고 규칙 엔진도 유형을 감지하지 못했습니다."
            )
        rule_type = rule_prediction["document_type"]
        ml_group = (
            "privacy_consent"
            if rule_type in {"collection", "third_party", "combined"}
            else rule_type
        )
        ml_prediction = {
            "document_type": ml_group,
            "label": rule_prediction["label"],
            "probability": 0,
            "confidence": 0,
            "probabilities": [],
            "model_type": "모델 사용 불가 - 규칙 엔진 폴백",
        }
        return {
            "document_type": rule_type,
            "label": rule_prediction["label"],
            "confidence": rule_prediction["confidence"],
            "method": "rule_only_fallback",
            "agreement": True,
            "ml_prediction": ml_prediction,
            "rule_prediction": rule_prediction,
        }

    if ml_prediction["document_type"] == "privacy_consent":
        if rule_prediction and rule_prediction["document_type"] in {
            "collection",
            "third_party",
            "combined",
        }:
            document_type = rule_prediction["document_type"]
            label = rule_prediction["label"]
        else:
            document_type = "collection"
            label = DOCUMENT_TYPE_LABELS[document_type]
    else:
        document_type = ml_prediction["document_type"]
        label = DOCUMENT_TYPE_LABELS[document_type]

    rule_type = rule_prediction["document_type"] if rule_prediction else None
    ml_rule_group = (
        "privacy_consent"
        if rule_type in {"collection", "third_party", "combined"}
        else rule_type
    )
    agreement = ml_rule_group == ml_prediction["document_type"]
    confidence = ml_prediction["confidence"]
    if agreement and rule_prediction:
        confidence = round(
            (ml_prediction["confidence"] + rule_prediction["confidence"]) / 2
        )

    return {
        "document_type": document_type,
        "label": label,
        "confidence": confidence,
        "method": "hybrid_ml_rule",
        "agreement": agreement,
        "ml_prediction": ml_prediction,
        "rule_prediction": rule_prediction,
    }
