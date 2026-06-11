import re
from dataclasses import asdict, dataclass
from typing import Iterable

from src.field_extraction import extract_privacy_fields
from src.legal_rules import load_legal_sources


DOCUMENT_TYPES = {"collection", "third_party", "combined"}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    status: str
    title: str
    article: str
    message: str
    evidence: str
    official_url: str
    severity: str = "정보"
    confidence: int = 80


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_passages(text: str) -> list[str]:
    passages = re.split(r"[\n\r]+|(?<=[.!?다])\s+", text)
    return [normalize_text(passage) for passage in passages if passage.strip()]


def first_evidence(text: str, patterns: Iterable[str]) -> str:
    passages = split_passages(text)
    for pattern in patterns:
        compiled = re.compile(pattern, re.IGNORECASE)
        for passage in passages:
            if compiled.search(passage):
                return passage[:300]
    return ""


def matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def redact_personal_data(text: str) -> str:
    redacted = re.sub(
        r"\b\d{6}\s*[-]?\s*[1-4]\d{6}\b",
        "[주민등록번호 마스킹]",
        text,
    )
    redacted = re.sub(
        r"\b01[016789][-\s]?\d{3,4}[-\s]?\d{4}\b",
        "[전화번호 마스킹]",
        redacted,
    )
    redacted = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[이메일 마스킹]",
        redacted,
    )
    redacted = re.sub(
        r"(?<!\d)\d{2,6}[-\s]\d{2,6}[-\s]\d{2,8}(?!\d)",
        "[계좌번호 후보 마스킹]",
        redacted,
    )
    redacted = re.sub(
        r"(?m)^(\s*(?:성명|이름|임대인|임차인|근로자|사용자)\s*[:：]\s*)"
        r"([가-힣]{2,4})(\s*)$",
        r"\1[성명 마스킹]\3",
        redacted,
    )
    return re.sub(
        r"(?m)^(\s*(?:주소|소재지|도로명\s*주소|임대\s*목적물)\s*[:：]\s*)"
        r"(.+)$",
        r"\1[상세 주소 마스킹]",
        redacted,
    )


def detect_sensitive_data(text: str) -> list[str]:
    patterns = {
        "주민등록번호": r"\b\d{6}\s*[-]?\s*[1-4]\d{6}\b",
        "전화번호": r"\b01[016789][-\s]?\d{3,4}[-\s]?\d{4}\b",
        "이메일": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "계좌번호 후보": r"(?<!\d)\d{2,6}[-\s]\d{2,6}[-\s]\d{2,8}(?!\d)",
        "성명 후보": (
            r"(?m)^\s*(?:성명|이름|임대인|임차인|근로자|사용자)"
            r"\s*[:：]\s*[가-힣]{2,4}\s*$"
        ),
        "상세 주소 후보": (
            r"(?m)^\s*(?:주소|소재지|도로명\s*주소|임대\s*목적물)"
            r"\s*[:：]\s*.+$"
        ),
    }
    return [
        label
        for label, pattern in patterns.items()
        if re.search(pattern, text)
    ]


def analyze_document(text: str, document_type: str = "collection") -> dict:
    if document_type not in DOCUMENT_TYPES:
        raise ValueError(f"지원하지 않는 문서 유형입니다: {document_type}")
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("분석할 문서 내용이 없습니다.")

    sources = load_legal_sources()
    findings: list[Finding] = []
    extracted_fields = extract_privacy_fields(text, document_type)
    for field in extracted_fields:
        field["value"] = redact_personal_data(field["value"])
    field_by_key = {field["key"]: field for field in extracted_fields}
    rule_fields = {
        "PIPA_15_2_PURPOSE": "collection_purpose",
        "PIPA_15_2_ITEMS": "collection_items",
        "PIPA_15_2_RETENTION": "collection_retention",
        "PIPA_15_2_REFUSAL": "collection_refusal",
        "PIPA_17_2_RECIPIENT": "third_party_recipient",
        "PIPA_17_2_PURPOSE": "third_party_purpose",
        "PIPA_17_2_ITEMS": "third_party_items",
        "PIPA_17_2_RETENTION": "third_party_retention",
        "PIPA_17_2_REFUSAL": "third_party_refusal",
    }

    for rule in sources["rules"]:
        if document_type not in rule["applies_to"]:
            continue
        evidence = redact_personal_data(
            first_evidence(normalized, rule["patterns"])
        )
        extracted_field = field_by_key.get(rule_fields.get(rule["id"], ""))
        if extracted_field and extracted_field["status"] == "구체성 검토":
            status = "구체성 검토"
            message = (
                "관련 값은 탐지되었지만 대상·범위·기간이 충분히 구체적인지 "
                "확인해야 합니다."
            )
            confidence = extracted_field["confidence"]
        elif extracted_field and extracted_field["status"] == "확인":
            status = "확인"
            message = (
                "관련 고지 문구와 구체적인 값이 탐지되었습니다. "
                "실제 사실과의 일치 및 법적 충분성은 별도 검토가 필요합니다."
            )
            confidence = extracted_field["confidence"]
        elif evidence:
            status = "확인"
            message = (
                "관련 고지 문구가 탐지되었습니다. 실제 내용의 구체성과 "
                "정확성은 별도 검토가 필요합니다."
            )
            confidence = 80
        else:
            status = "누락 가능성"
            message = f"자동 분석에서 다음 법정 고지사항을 찾지 못했습니다: {rule['requirement']}"
            confidence = 90
        findings.append(
            Finding(
                rule_id=rule["id"],
                status=status,
                title=rule["title"],
                article=rule["article"],
                message=message,
                evidence=evidence,
                official_url=rule["official_url"],
                severity="높음" if status == "누락 가능성" else "정보",
                confidence=confidence,
            )
        )

    for signal in sources["review_signals"]:
        trigger = redact_personal_data(
            first_evidence(normalized, signal["trigger_patterns"])
        )
        if not trigger:
            continue
        if matches_any(normalized, signal["satisfaction_patterns"]):
            status = "표현 확인"
            message = (
                "관련 동의 또는 구분 표현이 탐지되었습니다. "
                "법정 요건을 실제로 충족하는지는 원문과 적용 법령을 검토해야 합니다."
            )
        else:
            status = "검토 필요"
            message = signal["message"]
        findings.append(
            Finding(
                rule_id=signal["id"],
                status=status,
                title=signal["title"],
                article=signal["article"],
                message=message,
                evidence=trigger,
                official_url=signal["official_url"],
                severity="높음" if status == "검토 필요" else "정보",
                confidence=85,
            )
        )

    required = [finding for finding in findings if finding.rule_id.startswith(("PIPA_15_2", "PIPA_17_2"))]
    confirmed = sum(finding.status == "확인" for finding in required)
    completeness = round(confirmed / len(required) * 100) if required else 0

    return {
        "document_type": document_type,
        "completeness": completeness,
        "extracted_fields": extracted_fields,
        "findings": [asdict(finding) for finding in findings],
        "redacted_preview": redact_personal_data(text),
        "legal_metadata": sources["metadata"],
        "disclaimer": (
            "이 결과는 문구 탐지 기반의 검토 보조 정보이며 위법 여부나 법률 효과를 판정하지 않습니다. "
            "구체적인 사안은 변호사, 개인정보보호책임자 또는 관계 기관의 검토가 필요합니다."
        ),
    }
