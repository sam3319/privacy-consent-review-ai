import re
from dataclasses import asdict

from src.analyzer import Finding, first_evidence, normalize_text, redact_personal_data
from src.contract_structure import (
    extract_renewal_terms,
    extract_date_ranges,
    find_internal_consistency_issues,
    split_contract_sections,
    summarize_by_perspective,
)
from src.field_extraction import extract_employment_fields, extract_housing_fields
from src.legal_rules import load_employment_sources, load_housing_sources


def analyze_housing_contract(text: str, perspective: str = "임차인") -> dict:
    sources = load_housing_sources()
    result = _analyze_special_contract(
        text=text,
        document_type="housing_lease",
        perspective=perspective,
        sources=sources,
        extracted_fields=extract_housing_fields(text),
        scope_warning=(
            "등기사항증명서, 건축물대장, 선순위 임차보증금, 국세·지방세 체납, "
            "소유자 일치 여부는 문서 원문만으로 확인할 수 없습니다."
        ),
    )
    ids = {finding["rule_id"] for finding in result["findings"]}
    short_term = next(
        (
            line
            for line, start, end in extract_date_ranges(text)
            if 0 < (end - start).days < 730
        ),
        "",
    )
    if short_term and "HLA_TERM_UNDER_TWO_YEARS" not in ids:
        rule = next(
            signal
            for signal in sources["review_signals"]
            if signal["id"] == "HLA_TERM_UNDER_TWO_YEARS"
        )
        result["findings"].append(
            asdict(
                Finding(
                    rule_id=rule["id"],
                    status="검토 필요",
                    title=rule["title"],
                    article=rule["article"],
                    message=rule["message"],
                    evidence=redact_personal_data(short_term),
                    official_url=rule["official_url"],
                    severity=rule["severity"],
                    confidence=95,
                )
            )
        )
        result["risk_counts"] = _risk_counts(result["findings"])
    return result


def analyze_employment_contract(text: str, perspective: str = "근로자") -> dict:
    sources = load_employment_sources()
    result = _analyze_special_contract(
        text=text,
        document_type="employment_contract",
        perspective=perspective,
        sources=sources,
        extracted_fields=extract_employment_fields(text),
        scope_warning=(
            "근로자성, 사업장 규모, 업종, 수습·단시간근로 및 근로시간 적용 예외는 "
            "계약서 문언만으로 확정할 수 없습니다."
        ),
    )
    findings = result["findings"]
    fields = {field["key"]: field for field in result["extracted_fields"]}
    required = {
        "workplace": "근무 장소",
        "duties": "업무 내용",
        "work_hours": "소정근로시간",
        "holidays": "휴일",
        "wage": "임금 구성·금액",
        "pay_date": "임금 지급일·방법",
        "annual_leave": "연차 유급휴가",
    }
    for key, label in required.items():
        if fields[key]["value"]:
            continue
        findings.append(
            asdict(
                Finding(
                    rule_id=f"LSA_REQUIRED_{key.upper()}",
                    status="누락 가능성",
                    title=f"{label} 서면 명시 확인",
                    article="근로기준법 제17조",
                    message=(
                        f"{label}에 관한 구체적인 값을 찾지 못했습니다. "
                        "근로계약 체결 시 서면 명시·교부 대상인지 확인해야 합니다."
                    ),
                    evidence="",
                    official_url=(
                        "https://www.law.go.kr/lsLinkCommonInfo.do?"
                        "chrClsCd=010202&lsJoLnkSeq=1027161447"
                    ),
                    severity="높음",
                    confidence=90,
                )
            )
        )

    minimum_wage = sources["metadata"]["minimum_wage_2026"]
    hourly_matches = re.findall(
        r"(?:시급|시간급)\s*[:：]?\s*([\d,]+)\s*원", text
    )
    for value in hourly_matches:
        amount = int(value.replace(",", ""))
        if amount >= minimum_wage:
            continue
        rule = next(
            signal
            for signal in sources["review_signals"]
            if signal["id"] == "LSA_MINIMUM_WAGE"
        )
        findings.append(
            asdict(
                Finding(
                    rule_id=rule["id"],
                    status="검토 필요",
                    title=rule["title"],
                    article=rule["article"],
                    message=rule["message"],
                    evidence=f"시간급 {amount:,}원",
                    official_url=rule["official_url"],
                    severity=rule["severity"],
                    confidence=95,
                )
            )
        )
        break
    result["risk_counts"] = _risk_counts(findings)
    return result


def _analyze_special_contract(
    text: str,
    document_type: str,
    perspective: str,
    sources: dict,
    extracted_fields: list[dict],
    scope_warning: str,
) -> dict:
    normalized = normalize_text(text)
    if not normalized:
        raise ValueError("분석할 계약서 내용이 없습니다.")

    redacted_text = redact_personal_data(text)
    for field in extracted_fields:
        field["value"] = redact_personal_data(field["value"])

    findings = []
    for signal in sources["review_signals"]:
        if not signal["trigger_patterns"]:
            continue
        evidence = redact_personal_data(
            first_evidence(normalized, signal["trigger_patterns"])
        )
        if not evidence:
            continue
        findings.append(
            asdict(
                Finding(
                    rule_id=signal["id"],
                    status="검토 필요",
                    title=signal["title"],
                    article=signal["article"],
                    message=signal["message"],
                    evidence=evidence,
                    official_url=signal["official_url"],
                    severity=signal["severity"],
                    confidence=90 if len(evidence) >= 20 else 75,
                )
            )
        )

    for issue in find_internal_consistency_issues(text):
        findings.append(
            asdict(
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
        )

    present_fields = sum(field["status"] == "확인" for field in extracted_fields)
    completeness = round(present_fields / len(extracted_fields) * 100)
    return {
        "document_type": document_type,
        "completeness": completeness,
        "extracted_fields": extracted_fields,
        "findings": findings,
        "risk_counts": _risk_counts(findings),
        "sections": split_contract_sections(redacted_text),
        "perspective": perspective,
        "perspective_summary": summarize_by_perspective(
            redacted_text, perspective
        ),
        "renewal_terms": extract_renewal_terms(redacted_text),
        "redacted_preview": redacted_text,
        "legal_metadata": sources["metadata"],
        "scope_warning": scope_warning,
        "disclaimer": (
            "탐지 결과는 계약 문언의 누락·불일치·검토 후보를 제시할 뿐 "
            "법 위반, 계약 효력, 임금·보증금 반환액 또는 분쟁 결과를 판정하지 않습니다."
        ),
    }


def _risk_counts(findings: list[dict]) -> dict:
    return {
        level: sum(finding["severity"] == level for finding in findings)
        for level in ("높음", "중간", "낮음")
    }
