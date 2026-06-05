import re
from dataclasses import asdict, dataclass
from typing import Iterable

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
    return re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[이메일 마스킹]",
        redacted,
    )


def analyze_document(text: str, document_type: str = "collection") -> dict:
    if document_type not in DOCUMENT_TYPES:
        raise ValueError(f"지원하지 않는 문서 유형입니다: {document_type}")
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("분석할 문서 내용이 없습니다.")

    sources = load_legal_sources()
    findings: list[Finding] = []

    for rule in sources["rules"]:
        if document_type not in rule["applies_to"]:
            continue
        evidence = first_evidence(normalized, rule["patterns"])
        if evidence:
            status = "확인"
            message = "관련 고지 문구가 탐지되었습니다. 실제 내용의 구체성과 정확성은 별도 검토가 필요합니다."
        else:
            status = "누락 가능성"
            message = f"자동 분석에서 다음 법정 고지사항을 찾지 못했습니다: {rule['requirement']}"
        findings.append(
            Finding(
                rule_id=rule["id"],
                status=status,
                title=rule["title"],
                article=rule["article"],
                message=message,
                evidence=evidence,
                official_url=rule["official_url"],
            )
        )

    for signal in sources["review_signals"]:
        trigger = first_evidence(normalized, signal["trigger_patterns"])
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
            )
        )

    required = [finding for finding in findings if finding.rule_id.startswith(("PIPA_15_2", "PIPA_17_2"))]
    confirmed = sum(finding.status == "확인" for finding in required)
    completeness = round(confirmed / len(required) * 100) if required else 0

    return {
        "document_type": document_type,
        "completeness": completeness,
        "findings": [asdict(finding) for finding in findings],
        "redacted_preview": redact_personal_data(text),
        "legal_metadata": sources["metadata"],
        "disclaimer": (
            "이 결과는 문구 탐지 기반의 검토 보조 정보이며 위법 여부나 법률 효과를 판정하지 않습니다. "
            "구체적인 사안은 변호사, 개인정보보호책임자 또는 관계 기관의 검토가 필요합니다."
        ),
    }

