import re
from dataclasses import asdict

from src.analyzer import Finding, first_evidence, normalize_text, redact_personal_data
from src.contract_structure import (
    extract_renewal_terms,
    find_internal_consistency_issues,
    split_contract_sections,
    summarize_by_perspective,
)
from src.field_extraction import extract_contract_fields
from src.legal_rules import load_contract_sources


def analyze_contract(text: str, perspective: str = "을") -> dict:
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("분석할 계약서 내용이 없습니다.")

    sources = load_contract_sources()
    extracted_fields = extract_contract_fields(text)
    for field in extracted_fields:
        field["value"] = redact_personal_data(field["value"])
    findings: list[Finding] = []

    for signal in sources["review_signals"]:
        evidence = redact_personal_data(
            first_evidence(normalized, signal["trigger_patterns"])
        )
        if not evidence:
            continue
        confidence = 90 if len(evidence) >= 20 else 75
        findings.append(
            Finding(
                rule_id=signal["id"],
                status="검토 필요",
                title=signal["title"],
                article=signal["article"],
                message=signal["message"],
                evidence=evidence,
                official_url=signal["official_url"],
                severity=signal["severity"],
                confidence=confidence,
            )
        )

    for issue in find_internal_consistency_issues(text):
        findings.append(
            Finding(
                rule_id=issue["id"],
                status="검토 필요",
                title=issue["title"],
                article="문서 내부 일관성",
                message=issue["message"],
                evidence=redact_personal_data(issue["evidence"]),
                official_url=sources["metadata"]["official_url"],
                severity=issue["severity"],
                confidence=95,
            )
        )

    present_fields = sum(field["status"] == "확인" for field in extracted_fields)
    completeness = round(present_fields / len(extracted_fields) * 100)
    risk_counts = {
        level: sum(finding.severity == level for finding in findings)
        for level in ("높음", "중간", "낮음")
    }

    return {
        "document_type": "standard_terms_contract",
        "completeness": completeness,
        "extracted_fields": extracted_fields,
        "findings": [asdict(finding) for finding in findings],
        "risk_counts": risk_counts,
        "sections": split_contract_sections(redact_personal_data(text)),
        "perspective": perspective,
        "perspective_summary": summarize_by_perspective(
            redact_personal_data(text), perspective
        ),
        "renewal_terms": extract_renewal_terms(redact_personal_data(text)),
        "redacted_preview": redact_personal_data(text),
        "legal_metadata": sources["metadata"],
        "scope_warning": (
            "약관법은 명칭과 관계없이 한쪽 당사자가 여러 상대방과 계약하기 위해 "
            "미리 마련한 내용에 적용될 수 있습니다. 개별 협상 계약, 근로·임대차·금융 등 "
            "특별법이 적용되는 계약은 이 분석만으로 판단할 수 없습니다."
        ),
        "disclaimer": (
            "탐지 결과는 약관 문언의 검토 후보를 제시할 뿐 불공정성, 무효 여부, "
            "손해배상 책임 또는 분쟁 결과를 판정하지 않습니다."
        ),
    }
