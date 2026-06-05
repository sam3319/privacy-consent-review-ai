from src.contract_analyzer import analyze_contract


BALANCED_CONTRACT = """
서비스 이용 계약서
계약 당사자: 갑 주식회사 예시, 을 홍길동
계약 목적: 온라인 교육 서비스 제공
계약 기간: 2026년 1월 1일부터 2026년 12월 31일까지
계약 대금: 월 30,000원, 매월 말일까지 지급
계약 해지: 각 당사자는 30일 전에 서면 통지하여 계약을 해지할 수 있다.
손해배상: 당사자의 귀책사유로 발생한 직접 손해를 배상한다.
분쟁 해결: 당사자 간 협의 후 민사소송법에 따른 관할법원에서 해결한다.
"""


RISKY_CONTRACT = """
서비스 이용 약관
계약 당사자: 갑 주식회사 예시, 을 고객
계약 목적: 온라인 정보 제공
계약 기간: 가입일부터 해지일까지
계약 대금: 월 50,000원
계약 해지: 을은 계약을 해지할 수 없으며 갑은 언제든지 계약을 해지할 수 있다.
손해배상: 갑은 어떠한 손해에 대해서도 일체의 책임을 지지 않는다.
위약금: 을은 해지 시 잔여 대금 전액을 위약금으로 지급한다.
재판 관할: 갑의 본점 소재지 법원을 전속 관할로 한다.
갑은 별도 통지 없이 계약 내용을 일방적으로 변경할 수 있다.
"""


def finding_ids(result: dict) -> set[str]:
    return {finding["rule_id"] for finding in result["findings"]}


def test_contract_extracts_core_information():
    result = analyze_contract(BALANCED_CONTRACT)
    fields = {field["key"]: field for field in result["extracted_fields"]}

    assert result["completeness"] == 100
    assert fields["term"]["value"].startswith("2026년 1월 1일")
    assert fields["payment"]["value"].startswith("월 30,000원")


def test_contract_flags_grounded_terms_review_signals():
    result = analyze_contract(RISKY_CONTRACT)
    ids = finding_ids(result)

    assert "ATCA_6_UNFAIR_GENERAL" in ids
    assert "ATCA_7_EXEMPTION" in ids
    assert "ATCA_8_LIQUIDATED_DAMAGES" in ids
    assert "ATCA_9_TERMINATION" in ids
    assert "ATCA_14_JURISDICTION" in ids


def test_contract_result_does_not_claim_illegality():
    result = analyze_contract(RISKY_CONTRACT)
    combined_messages = " ".join(
        finding["message"] for finding in result["findings"]
    )

    assert "불법" not in combined_messages
    assert "위법" not in combined_messages
    assert "판정하지 않습니다" in result["disclaimer"]

