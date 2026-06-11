import json
import re
from dataclasses import asdict
from pathlib import Path

from src.analyzer import Finding, first_evidence, normalize_text, redact_personal_data
from src.contract_structure import (
    extract_renewal_terms,
    extract_date_ranges,
    find_internal_consistency_issues,
    split_contract_sections,
    summarize_by_perspective,
)
from src.ml_classifier import predict_clause_risks
from src.field_extraction import augment_fields_with_ml
from src.housing_verification import (
    calculate_deposit_risk,
    cross_check_housing_documents,
    parse_money,
)


ROOT = Path(__file__).resolve().parents[1]

HOUSING_FIELDS = [
    ("parties", "임대인·임차인", [r"임대인", r"임차인"]),
    ("property", "임대 목적물", [r"소재지", r"임대\s*(?:목적물|주택)", r"주소"]),
    ("deposit", "보증금", [r"보증금"]),
    ("monthly_rent", "월 차임·월세", [r"월\s*(?:차임|세)", r"차임"]),
    ("term", "임대차 기간", [r"임대차\s*기간", r"계약\s*기간"]),
    ("payment_date", "차임 지급일", [r"(?:차임|월세)\s*지급일", r"매월.{0,10}지급"]),
    ("management_fee", "관리비", [r"관리비"]),
    ("repairs", "수선·하자 책임", [r"수선", r"하자", r"수리\s*비용"]),
    ("deposit_return", "보증금 반환", [r"보증금\s*반환"]),
    ("special_terms", "특약사항", [r"특약\s*사항", r"특약"]),
]

EMPLOYMENT_FIELDS = [
    ("parties", "사용자·근로자", [r"사용자", r"근로자", r"사업주"]),
    ("workplace", "근무 장소", [r"근무\s*장소", r"취업\s*장소"]),
    ("duties", "업무 내용", [r"업무\s*(?:내용|종류)", r"담당\s*업무"]),
    ("term", "근로계약 기간", [r"근로계약\s*기간", r"계약\s*기간"]),
    ("work_hours", "소정근로시간", [r"소정\s*근로\s*시간", r"근무\s*시간"]),
    ("break_time", "휴게시간", [r"휴게\s*시간"]),
    ("work_days", "근무일", [r"근무일", r"근로일"]),
    ("holidays", "휴일", [r"주휴일", r"유급\s*휴일", r"휴일"]),
    ("wage", "임금 구성·금액", [r"임금", r"기본급", r"시급", r"월급"]),
    ("pay_date", "임금 지급일·방법", [r"임금\s*지급", r"급여\s*지급", r"지급일"]),
    ("annual_leave", "연차 유급휴가", [r"연차", r"유급\s*휴가"]),
]


def load_special_sources(filename: str) -> dict:
    with (ROOT / "data" / filename).open(encoding="utf-8") as source_file:
        return json.load(source_file)


def _extract_special_fields(
    text: str,
    configurations: list[tuple],
    document_group: str,
) -> list[dict]:
    fields = []
    for key, label, patterns in configurations:
        expression = "|".join(patterns)
        match = re.search(
            rf"(?im)^\s*(?:{expression})\s*[:：]?\s*(.+?)\s*$",
            text,
        )
        value = match.group(1).strip(" -·ㆍ") if match else ""
        fields.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "status": "확인" if value else "누락 가능성",
                "confidence": 90 if value else 95,
                "message": (
                    "표제와 구체적인 값이 탐지되었습니다. 실제 사실과의 일치 여부는 "
                    "별도 확인이 필요합니다."
                    if value
                    else "표제와 구체적인 값을 자동 분석에서 찾지 못했습니다."
                ),
            }
        )
    return augment_fields_with_ml(fields, text, document_group)


def analyze_housing_contract(
    text: str,
    perspective: str = "임차인",
    supporting_documents: dict[str, str] | None = None,
    financial_inputs: dict[str, int | float] | None = None,
) -> dict:
    sources = load_special_sources("housing_legal_sources.json")
    result = _analyze_special_contract(
        text=text,
        document_type="housing_lease",
        perspective=perspective,
        sources=sources,
        extracted_fields=_extract_special_fields(text, HOUSING_FIELDS, "housing"),
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
    result["housing_verification"] = cross_check_housing_documents(
        text, supporting_documents
    )
    amounts = financial_inputs or {}
    registry_claim = result["housing_verification"]["registry"].get(
        "senior_claim_amount"
    )
    deposit_field = next(
        (
            field["value"]
            for field in result["extracted_fields"]
            if field["key"] == "deposit"
        ),
        "",
    )
    result["deposit_risk"] = calculate_deposit_risk(
        property_value=amounts.get("property_value", 0),
        tenant_deposit=amounts.get("tenant_deposit") or parse_money(deposit_field) or 0,
        senior_claims=amounts.get("senior_claims") or registry_claim or 0,
        senior_deposits=amounts.get("senior_deposits", 0),
    )
    return result


def analyze_employment_contract(text: str, perspective: str = "근로자") -> dict:
    sources = load_special_sources("employment_legal_sources.json")
    result = _analyze_special_contract(
        text=text,
        document_type="employment_contract",
        perspective=perspective,
        sources=sources,
        extracted_fields=_extract_special_fields(
            text, EMPLOYMENT_FIELDS, "employment"
        ),
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
        "ml_clause_predictions": predict_clause_risks(redacted_text),
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
