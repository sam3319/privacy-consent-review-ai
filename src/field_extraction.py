import re
from dataclasses import asdict, dataclass
from typing import Callable

from src.ml_classifier import predict_field_candidates

@dataclass(frozen=True)
class ExtractedField:
    key: str
    label: str
    value: str
    status: str
    confidence: int
    message: str


def _extract_line_value(text: str, labels: list[str]) -> str:
    label_expression = "|".join(labels)
    pattern = re.compile(
        rf"(?im)^\s*(?:{label_expression})\s*[:：]?\s*(.+?)\s*$"
    )
    match = pattern.search(text)
    return match.group(1).strip(" -·ㆍ") if match else ""


def _extract_matching_passages(text: str, patterns: list[str]) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    matches = []
    for line in lines:
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns):
            matches.append(line)
    return " ".join(dict.fromkeys(matches))


def _has_meaningful_value(value: str, minimum_length: int = 2) -> bool:
    compact = re.sub(r"[\s,·ㆍ/]", "", value)
    return len(compact) >= minimum_length


def _purpose_is_specific(value: str) -> bool:
    if not _has_meaningful_value(value, 2):
        return False
    vague = ("서비스 제공", "업무 처리", "기타 목적", "필요한 목적", "관련 업무")
    return value not in vague and not any(value.endswith(item) for item in ("등", "일체"))


def _items_are_specific(value: str) -> bool:
    if not _has_meaningful_value(value):
        return False
    vague = ("필요한 정보", "관련 정보", "모든 정보", "일체의 정보", "기타 정보")
    return not any(item in value for item in vague)


def _period_is_specific(value: str) -> bool:
    if not _has_meaningful_value(value):
        return False
    markers = (
        r"\d+\s*(일|개월|년)",
        r"(회원\s*)?탈퇴",
        r"목적.{0,5}달성",
        r"계약.{0,5}(종료|해지|만료)",
        r"배송.{0,5}완료",
        r"처리.{0,5}완료",
        r"동의.{0,5}철회",
    )
    return any(re.search(pattern, value) for pattern in markers)


def _recipient_is_specific(value: str) -> bool:
    if not _has_meaningful_value(value):
        return False
    return not any(
        phrase in value
        for phrase in ("제휴사", "협력사", "관계사", "필요한 제3자", "관련 업체")
    )


def _refusal_is_specific(value: str) -> bool:
    has_right = bool(re.search(r"(거부.{0,8}권리|동의.{0,8}거부)", value))
    has_consequence = bool(
        re.search(
            r"(불이익|제한|이용할 수 없|가입할 수 없|영향이 없|불이익은 없)",
            value,
        )
    )
    return has_right and has_consequence


def _build_field(
    key: str,
    label: str,
    value: str,
    validator: Callable[[str], bool],
) -> ExtractedField:
    if not value:
        return ExtractedField(
            key,
            label,
            "",
            "누락 가능성",
            95,
            "표제와 구체적인 값을 자동 분석에서 찾지 못했습니다.",
        )
    if not validator(value):
        return ExtractedField(
            key,
            label,
            value,
            "구체성 검토",
            80,
            "관련 값은 탐지되었지만 범위·대상·기간이 충분히 구체적인지 확인해야 합니다.",
        )
    return ExtractedField(
        key,
        label,
        value,
        "확인",
        90,
        "표제와 구체적인 값이 탐지되었습니다. 실제 사실과의 일치 여부는 별도 확인이 필요합니다.",
    )


def extract_privacy_fields(text: str, document_type: str) -> list[dict]:
    configurations = []
    if document_type in {"collection", "combined"}:
        configurations.extend(
            [
                (
                    "collection_purpose",
                    "수집·이용 목적",
                    [r"수집\s*[·ㆍ및]?\s*이용\s*목적", r"수집\s*목적"],
                    _purpose_is_specific,
                ),
                (
                    "collection_items",
                    "수집 개인정보 항목",
                    [r"수집(?:하는|하려는)?\s*(?:개인정보\s*)?항목", r"수집\s*항목"],
                    _items_are_specific,
                ),
                (
                    "collection_retention",
                    "보유 및 이용 기간",
                    [r"보유\s*(?:및|·|ㆍ)?\s*이용\s*기간", r"보유\s*기간"],
                    _period_is_specific,
                ),
            ]
        )
        refusal_value = _extract_matching_passages(
            text,
            [
                r"동의.{0,12}거부",
                r"거부.{0,12}(불이익|제한)",
                r"동의하지.{0,12}(불이익|제한|이용)",
            ],
        )
        configurations.append(
            (
                "collection_refusal",
                "수집·이용 동의 거부 권리와 불이익",
                [],
                _refusal_is_specific,
                refusal_value,
            )
        )
    if document_type in {"third_party", "combined"}:
        configurations.extend(
            [
                (
                    "third_party_recipient",
                    "제공받는 자",
                    [r"제공\s*받는\s*자", r"제공\s*대상"],
                    _recipient_is_specific,
                ),
                (
                    "third_party_purpose",
                    "제공받는 자의 이용 목적",
                    [r"제공\s*받는\s*자의?\s*(?:개인정보\s*)?이용\s*목적", r"제공\s*목적"],
                    _purpose_is_specific,
                ),
                (
                    "third_party_items",
                    "제공 개인정보 항목",
                    [r"제공(?:하는)?\s*(?:개인정보\s*)?항목", r"제공\s*항목"],
                    _items_are_specific,
                ),
                (
                    "third_party_retention",
                    "제공받는 자의 보유 및 이용 기간",
                    [r"제공\s*받는\s*자의?\s*보유\s*(?:및|·|ㆍ)?\s*이용\s*기간"],
                    _period_is_specific,
                ),
            ]
        )
        refusal_value = _extract_matching_passages(
            text,
            [
                r"제3자.{0,20}동의.{0,12}거부",
                r"제공.{0,20}거부.{0,12}(불이익|제한)",
                r"동의.{0,12}거부.{0,20}(불이익|제한|이용할 수 없)",
            ],
        )
        configurations.append(
            (
                "third_party_refusal",
                "제3자 제공 동의 거부 권리와 불이익",
                [],
                _refusal_is_specific,
                refusal_value,
            )
        )

    results = []
    for configuration in configurations:
        key, label, patterns, validator, *provided_value = configuration
        value = (
            provided_value[0]
            if provided_value
            else _extract_line_value(text, patterns)
        )
        results.append(
            asdict(
                _build_field(
                    key,
                    label,
                    value,
                    validator,
                )
            )
        )
    return results


CONTRACT_FIELD_CONFIGURATIONS = [
    ("parties", "계약 당사자", [r"계약\s*당사자", r"갑\s*[:：].{1,80}을\s*[:：]"], 4),
    ("subject", "계약 목적·대상", [r"계약\s*(?:목적|대상)", r"용역\s*(?:내용|범위)", r"업무\s*범위"], 4),
    ("term", "계약 기간", [r"계약\s*기간", r"유효\s*기간"], 4),
    ("payment", "대금·보수·지급 조건", [r"(?:계약\s*)?대금", r"보수", r"지급\s*(?:조건|방법|일)"], 2),
    ("termination", "해제·해지", [r"해제\s*[·ㆍ및]?\s*해지", r"계약\s*해지", r"중도\s*해지"], 4),
    ("damages", "손해배상·위약금", [r"손해\s*배상", r"위약금", r"위약벌", r"지연\s*손해금"], 2),
    ("dispute", "분쟁 해결·관할", [r"분쟁\s*해결", r"재판\s*관할", r"관할\s*법원"], 2),
]


def extract_contract_fields(text: str) -> list[dict]:
    fields = []
    for key, label, patterns, minimum_length in CONTRACT_FIELD_CONFIGURATIONS:
        value = _extract_line_value(text, patterns)
        fields.append(
            asdict(
                _build_field(
                    key,
                    label,
                    value,
                    lambda item, length=minimum_length: _has_meaningful_value(
                        item, length
                    ),
                )
            )
        )
    return augment_fields_with_ml(fields, text, "contract")


HOUSING_FIELD_CONFIGURATIONS = [
    ("parties", "임대인·임차인", [r"임대인", r"임차인"], 4),
    ("property", "임대 목적물", [r"소재지", r"임대\s*(?:목적물|주택)", r"주소"], 4),
    ("deposit", "보증금", [r"보증금"], 2),
    ("monthly_rent", "월 차임·월세", [r"월\s*(?:차임|세)", r"차임"], 2),
    ("term", "임대차 기간", [r"임대차\s*기간", r"계약\s*기간"], 4),
    ("payment_date", "차임 지급일", [r"(?:차임|월세)\s*지급일", r"매월.{0,10}지급"], 2),
    ("management_fee", "관리비", [r"관리비"], 2),
    ("repairs", "수선·하자 책임", [r"수선", r"하자", r"수리\s*비용"], 4),
    ("deposit_return", "보증금 반환", [r"보증금\s*반환"], 4),
    ("special_terms", "특약사항", [r"특약\s*사항", r"특약"], 2),
]


EMPLOYMENT_FIELD_CONFIGURATIONS = [
    ("parties", "사용자·근로자", [r"사용자", r"근로자", r"사업주"], 4),
    ("workplace", "근무 장소", [r"근무\s*장소", r"취업\s*장소"], 2),
    ("duties", "업무 내용", [r"업무\s*(?:내용|종류)", r"담당\s*업무"], 2),
    ("term", "근로계약 기간", [r"근로계약\s*기간", r"계약\s*기간"], 4),
    ("work_hours", "소정근로시간", [r"소정\s*근로\s*시간", r"근무\s*시간"], 2),
    ("break_time", "휴게시간", [r"휴게\s*시간"], 2),
    ("work_days", "근무일", [r"근무일", r"근로일"], 2),
    ("holidays", "휴일", [r"주휴일", r"유급\s*휴일", r"휴일"], 2),
    ("wage", "임금 구성·금액", [r"임금", r"기본급", r"시급", r"월급"], 2),
    ("pay_date", "임금 지급일·방법", [r"임금\s*지급", r"급여\s*지급", r"지급일"], 2),
    ("annual_leave", "연차 유급휴가", [r"연차", r"유급\s*휴가"], 2),
]


def extract_housing_fields(text: str) -> list[dict]:
    return augment_fields_with_ml(
        _extract_configured_fields(text, HOUSING_FIELD_CONFIGURATIONS),
        text,
        "housing",
    )


def extract_employment_fields(text: str) -> list[dict]:
    return augment_fields_with_ml(
        _extract_configured_fields(text, EMPLOYMENT_FIELD_CONFIGURATIONS),
        text,
        "employment",
    )


def _extract_configured_fields(text: str, configurations: list[tuple]) -> list[dict]:
    fields = []
    for key, label, patterns, minimum_length in configurations:
        value = _extract_line_value(text, patterns)
        fields.append(
            asdict(
                _build_field(
                    key,
                    label,
                    value,
                    lambda item, length=minimum_length: _has_meaningful_value(
                        item, length
                    ),
                )
            )
        )
    return fields


def augment_fields_with_ml(
    fields: list[dict],
    text: str,
    document_group: str,
) -> list[dict]:
    missing_keys = {field["key"] for field in fields if not field["value"]}
    if not missing_keys:
        return fields
    try:
        predictions = predict_field_candidates(
            text,
            document_group,
            missing_keys,
        )
    except (FileNotFoundError, OSError, ValueError):
        return fields

    predictions_by_key = {item["key"]: item for item in predictions}
    for field in fields:
        prediction = predictions_by_key.get(field["key"])
        if not prediction:
            field["extraction_method"] = "rule"
            continue
        field.update(
            {
                "value": prediction["value"],
                "status": (
                    "확인"
                    if prediction["probability"] >= 55
                    else "사용자 확인 필요"
                ),
                "confidence": round(prediction["probability"]),
                "message": (
                    "정규식으로 찾지 못한 값을 필드 분류 모델이 후보로 탐지했습니다. "
                    + (
                        "원문에서 항목과 값의 대응을 확인해야 합니다."
                        if prediction["probability"] >= 55
                        else "신뢰도가 낮아 사용자 확인 전에는 확정값으로 취급하지 않습니다."
                    )
                ),
                "extraction_method": "ml_fallback",
                "ml_source_line": prediction["line"],
                "source_span": {
                    "start": prediction["span_start"],
                    "end": prediction["span_end"],
                },
            }
        )
    return fields
