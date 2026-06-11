from src.housing_verification import (
    calculate_deposit_risk,
    cross_check_housing_documents,
    parse_money,
)


def test_parse_money_supports_korean_units():
    assert parse_money("1억 5,000만원") == 150_000_000
    assert parse_money("15,000만원") == 150_000_000
    assert parse_money("100,000,000원") == 100_000_000


def test_cross_check_housing_documents_matches_owner_and_address():
    result = cross_check_housing_documents(
        """
        임대인: 홍길동
        임대 목적물: 서울특별시 예시구 예시로 100, 101호
        """,
        {
            "registry": """
                소유자: 홍길동
                소재지: 서울특별시 예시구 예시로 100, 101호
                채권최고액: 80,000,000원
            """,
            "building_ledger": """
                도로명 주소: 서울특별시 예시구 예시로 100, 101호
                주용도: 공동주택
            """,
        },
    )

    statuses = {check["id"]: check["status"] for check in result["checks"]}
    assert statuses["owner_match"] == "확인"
    assert statuses["registry_address_match"] == "확인"
    assert statuses["building_address_match"] == "확인"
    assert statuses["building_use"] == "확인"


def test_cross_check_flags_owner_mismatch():
    result = cross_check_housing_documents(
        "임대인: 홍길동\n임대 목적물: 서울특별시 예시구 101호",
        {"registry": "소유자: 김소유\n소재지: 서울특별시 예시구 101호"},
    )

    owner = next(check for check in result["checks"] if check["id"] == "owner_match")
    assert owner["status"] == "검토 필요"


def test_deposit_risk_uses_prior_claims_and_deposits():
    result = calculate_deposit_risk(
        property_value=300_000_000,
        tenant_deposit=100_000_000,
        senior_claims=120_000_000,
        senior_deposits=30_000_000,
    )

    assert result is not None
    assert result["prior_total"] == 150_000_000
    assert result["burden_ratio"] == 83.3
    assert result["risk_level"] == "중간"


def test_deposit_risk_requires_value_and_deposit():
    assert calculate_deposit_risk(0, 100_000_000) is None
