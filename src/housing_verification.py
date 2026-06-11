import re
from typing import Mapping

from src.analyzer import redact_personal_data


MONEY_UNIT_MULTIPLIERS = {
    "억원": 100_000_000,
    "억": 100_000_000,
    "만원": 10_000,
    "만": 10_000,
    "원": 1,
}


def parse_money(value: str) -> int | None:
    if not value:
        return None
    matches = re.findall(r"([\d,.]+)\s*(억원|억|만원|만|원)", value)
    if matches:
        return round(
            sum(
                float(number.replace(",", "")) * MONEY_UNIT_MULTIPLIERS[unit]
                for number, unit in matches
            )
        )
    match = re.search(r"([\d,.]+)", value)
    if not match:
        return None
    return round(float(match.group(1).replace(",", "")))


def extract_housing_reference(text: str) -> dict:
    return {
        "owner": _first_group(
            text,
            [
                r"(?:소유자|소유권자|성명)\s*[:：]?\s*([^\n,]+)",
                r"임대인(?:\s*성명)?\s*(?:[:：]\s*|\s+)([^\n,]+)",
            ],
        ),
        "address": _first_group(
            text,
            [
                r"(?:소재지|건물\s*주소|도로명\s*주소|임대\s*목적물)\s*[:：]?\s*([^\n]+)",
                r"주소\s*[:：]?\s*([^\n]+)",
            ],
        ),
        "building_use": _first_group(
            text,
            [r"(?:주용도|건축물\s*용도|용도)\s*[:：]?\s*([^\n,]+)"],
        ),
        "senior_claim_amount": _extract_largest_money(
            text,
            [
                r"(?:채권최고액|근저당권|담보권|선순위\s*채권).{0,30}?([\d,.]+\s*(?:억원|억|만원|만|원))",
            ],
        ),
    }


def cross_check_housing_documents(
    contract_text: str,
    supporting_documents: Mapping[str, str] | None = None,
) -> dict:
    documents = supporting_documents or {}
    contract = extract_housing_reference(contract_text)
    registry = extract_housing_reference(documents.get("registry", ""))
    building = extract_housing_reference(documents.get("building_ledger", ""))

    checks = [
        _comparison_check(
            "owner_match",
            "임대인과 등기 소유자",
            contract["owner"],
            registry["owner"],
            "계약서 임대인과 등기사항증명서 소유자",
        ),
        _comparison_check(
            "registry_address_match",
            "계약 목적물과 등기 소재지",
            contract["address"],
            registry["address"],
            "계약서 목적물과 등기사항증명서 소재지",
        ),
        _comparison_check(
            "building_address_match",
            "계약 목적물과 건축물대장 주소",
            contract["address"],
            building["address"],
            "계약서 목적물과 건축물대장 주소",
        ),
    ]

    use = building["building_use"]
    if use:
        residential = bool(re.search(r"주택|아파트|다세대|다가구|연립|오피스텔", use))
        checks.append(
            {
                "id": "building_use",
                "label": "건축물 용도",
                "status": "확인" if residential else "검토 필요",
                "message": (
                    f"건축물대장 용도에서 주거 관련 표현을 확인했습니다: {use}"
                    if residential
                    else f"건축물대장 용도가 주거용인지 추가 확인이 필요합니다: {use}"
                ),
                "contract_value": "",
                "reference_value": redact_personal_data(use),
            }
        )
    else:
        checks.append(
            {
                "id": "building_use",
                "label": "건축물 용도",
                "status": "자료 부족",
                "message": "건축물대장에서 용도 값을 찾지 못했습니다.",
                "contract_value": "",
                "reference_value": "",
            }
        )

    return {
        "checks": checks,
        "registry": registry,
        "building_ledger": building,
        "summary": {
            status: sum(check["status"] == status for check in checks)
            for status in ("확인", "검토 필요", "자료 부족")
        },
        "disclaimer": (
            "문자열 기반 교차확인이며 서류의 진위, 최신 상태, 권리 순위 또는 "
            "법적 효력을 판정하지 않습니다."
        ),
    }


def calculate_deposit_risk(
    property_value: int | float,
    tenant_deposit: int | float,
    senior_claims: int | float = 0,
    senior_deposits: int | float = 0,
) -> dict | None:
    amounts = {
        "property_value": max(float(property_value or 0), 0),
        "tenant_deposit": max(float(tenant_deposit or 0), 0),
        "senior_claims": max(float(senior_claims or 0), 0),
        "senior_deposits": max(float(senior_deposits or 0), 0),
    }
    if not amounts["property_value"] or not amounts["tenant_deposit"]:
        return None

    prior_total = amounts["senior_claims"] + amounts["senior_deposits"]
    total_exposure = prior_total + amounts["tenant_deposit"]
    remaining_value = amounts["property_value"] - prior_total
    burden_ratio = total_exposure / amounts["property_value"] * 100
    deposit_coverage = remaining_value / amounts["tenant_deposit"] * 100

    if burden_ratio >= 100 or deposit_coverage < 100:
        level = "높음"
        message = "입력한 주택가액에서 선순위 금액을 뺀 잔여액이 보증금보다 적습니다."
    elif burden_ratio >= 80:
        level = "중간"
        message = "선순위 금액과 보증금의 합계가 입력한 주택가액의 80% 이상입니다."
    else:
        level = "낮음"
        message = "입력값 기준 총 부담 비율이 80% 미만입니다."

    return {
        "amounts": {key: round(value) for key, value in amounts.items()},
        "prior_total": round(prior_total),
        "total_exposure": round(total_exposure),
        "remaining_value": round(remaining_value),
        "burden_ratio": round(burden_ratio, 1),
        "deposit_coverage": round(deposit_coverage, 1),
        "risk_level": level,
        "message": message,
        "basis": (
            "주택가액 대비 선순위 채권·선순위 보증금·본인 보증금의 단순 합산 비율"
        ),
        "disclaimer": (
            "법정 배당액이나 실제 회수액 계산이 아닙니다. 경매 낙찰가율, 우선변제권, "
            "소액임차인 여부, 세금, 권리 순위와 비용은 반영하지 않습니다."
        ),
    }


def _comparison_check(
    check_id: str,
    label: str,
    contract_value: str,
    reference_value: str,
    description: str,
) -> dict:
    if not contract_value or not reference_value:
        status = "자료 부족"
        message = f"{description} 중 하나 이상의 값을 찾지 못했습니다."
    elif _values_match(contract_value, reference_value):
        status = "확인"
        message = f"{description}가 문자열 기준으로 일치합니다."
    else:
        status = "검토 필요"
        message = f"{description}가 다르게 탐지되었습니다. 원본 서류를 직접 대조하세요."
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "message": message,
        "contract_value": redact_personal_data(contract_value),
        "reference_value": redact_personal_data(reference_value),
    }


def _values_match(left: str, right: str) -> bool:
    left_normalized = re.sub(r"[^0-9가-힣a-z]", "", left.lower())
    right_normalized = re.sub(r"[^0-9가-힣a-z]", "", right.lower())
    if not left_normalized or not right_normalized:
        return False
    if left_normalized in right_normalized or right_normalized in left_normalized:
        return True
    left_tokens = set(re.findall(r"[0-9가-힣a-z]+", left.lower()))
    right_tokens = set(re.findall(r"[0-9가-힣a-z]+", right.lower()))
    return len(left_tokens & right_tokens) >= min(2, len(left_tokens), len(right_tokens))


def _first_group(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(" -·ㆍ")
    return ""


def _extract_largest_money(text: str, patterns: list[str]) -> int | None:
    values = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            amount = parse_money(match.group(1))
            if amount is not None:
                values.append(amount)
    return max(values) if values else None
