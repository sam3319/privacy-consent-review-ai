import csv
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "field_extraction_training.csv"
RANDOM_SEED = 42

FIELD_EXAMPLES = {
    "contract.parties": (
        ["갑 주식회사 예시와 을 김고객", "사업자 예시회사와 이용자 김예시"],
        ["계약 당사자는 {value}로 한다.", "당사자: {value}", "{value} 사이에 계약을 체결한다."],
    ),
    "contract.subject": (
        ["온라인 정보 제공 서비스", "웹사이트 유지보수 용역", "제품 공급 업무"],
        ["계약 목적은 {value}이다.", "업무 범위: {value}", "{value}를 계약 대상으로 한다."],
    ),
    "contract.term": (
        ["2026년 7월 1일부터 2027년 6월 30일까지", "계약 체결일부터 12개월"],
        ["계약 기간은 {value}로 한다.", "유효 기간: {value}", "{value} 동안 계약은 유효하다."],
    ),
    "contract.payment": (
        ["월 100,000원을 매월 25일 지급", "총 3,000,000원을 검수 후 지급"],
        ["계약 대금은 {value}한다.", "보수 및 지급 조건: {value}", "을에게 {value}한다."],
    ),
    "contract.termination": (
        ["상대방이 의무를 위반하면 서면 통지 후 해지할 수 있다", "30일 전 통지로 종료할 수 있다"],
        ["계약 해지는 {value}.", "해제·해지 조건: {value}", "{value}."],
    ),
    "contract.damages": (
        ["귀책 당사자가 직접 손해를 배상한다", "지체일수마다 대금의 0.1%를 지급한다"],
        ["손해배상은 {value}.", "위약금 조건: {value}", "{value}."],
    ),
    "contract.dispute": (
        ["서울중앙지방법원을 관할 법원으로 한다", "상호 협의 후 민사소송으로 해결한다"],
        ["분쟁 해결은 {value}.", "재판 관할: {value}", "{value}."],
    ),
    "housing.parties": (
        ["임대인 홍길동과 임차인 김예시", "소유자 박임대 및 세입자 이임차"],
        ["계약 당사자는 {value}이다.", "{value} 사이에 임대차계약을 체결한다.", "임대인·임차인: {value}"],
    ),
    "housing.property": (
        ["서울특별시 예시구 예시로 100, 101호", "부산광역시 예시동 200번지 아파트 301호"],
        ["임대할 주택은 {value}이다.", "목적물 소재지: {value}", "{value}를 임대 목적물로 한다."],
    ),
    "housing.deposit": (
        ["100,000,000원", "1억 5,000만원", "오천만원"],
        ["임차보증금은 {value}으로 정한다.", "보증금: {value}", "임차인은 {value}을 보증금으로 지급한다."],
    ),
    "housing.monthly_rent": (
        ["매월 500,000원", "월 75만원", "매월 말일 600,000원"],
        ["차임은 {value}이다.", "월세: {value}", "임차인은 {value}을 지급한다."],
    ),
    "housing.term": (
        ["2026년 7월 1일부터 2028년 6월 30일까지", "입주일부터 2년"],
        ["임대차 기간은 {value}로 한다.", "계약 존속기간: {value}", "{value} 동안 임대한다."],
    ),
    "housing.payment_date": (
        ["매월 25일", "매월 말일", "매달 10일"],
        ["차임 지급일은 {value}이다.", "월세는 {value}에 납부한다.", "지급 기일: {value}"],
    ),
    "housing.management_fee": (
        ["월 100,000원", "매월 15만원", "실비 정산"],
        ["관리비는 {value}이다.", "공용관리비: {value}", "임차인이 {value}의 관리비를 부담한다."],
    ),
    "housing.repairs": (
        ["주요 설비는 임대인이 수선한다", "소모품은 임차인이 교체한다"],
        ["수선 책임은 {value}.", "하자 보수: {value}", "{value}."],
    ),
    "housing.deposit_return": (
        ["목적물을 인도받는 즉시 반환한다", "퇴거와 동시에 정산하여 지급한다"],
        ["보증금 반환은 {value}.", "임대인은 {value}.", "반환 조건: {value}"],
    ),
    "housing.special_terms": (
        ["반려동물 사육은 사전 동의를 받는다", "입주 전 도배를 완료한다"],
        ["특약사항: {value}", "특약으로 {value}.", "{value}는 별도 특약으로 정한다."],
    ),
    "employment.parties": (
        ["사용자 예시회사와 근로자 김예시", "사업주 박대표 및 직원 이근로"],
        ["근로계약 당사자는 {value}이다.", "사용자·근로자: {value}", "{value} 사이에 근로계약을 체결한다."],
    ),
    "employment.workplace": (
        ["서울 본사", "예시구 고객지원센터", "회사 지정 사업장"],
        ["근무 장소는 {value}이다.", "취업 장소: {value}", "{value}에서 근무한다."],
    ),
    "employment.duties": (
        ["고객 상담과 문서 관리", "소프트웨어 개발", "매장 판매 업무"],
        ["담당 업무는 {value}이다.", "업무 내용: {value}", "근로자는 {value}를 수행한다."],
    ),
    "employment.term": (
        ["2026년 7월 1일부터 2027년 6월 30일까지", "기간의 정함이 없음"],
        ["근로계약 기간은 {value}이다.", "고용 기간: {value}", "{value} 동안 근무한다."],
    ),
    "employment.work_hours": (
        ["오전 9시부터 오후 6시까지", "1일 8시간 주 40시간"],
        ["소정근로시간은 {value}이다.", "근무 시간: {value}", "{value} 근무한다."],
    ),
    "employment.break_time": (
        ["12시부터 13시까지", "근로 도중 1시간", "오후 3시부터 3시 30분까지"],
        ["휴게시간은 {value}이다.", "휴식 시간: {value}", "{value} 자유롭게 이용한다."],
    ),
    "employment.work_days": (
        ["월요일부터 금요일", "주 5일", "매주 월·화·수·목·금"],
        ["근무일은 {value}이다.", "소정근로일: {value}", "{value}에 근무한다."],
    ),
    "employment.holidays": (
        ["매주 일요일", "토요일과 일요일", "근로자의 날과 법정 공휴일"],
        ["주휴일은 {value}이다.", "유급 휴일: {value}", "{value}을 휴일로 한다."],
    ),
    "employment.wage": (
        ["시간급 12,000원", "월 기본급 3,000,000원", "연봉 40,000,000원"],
        ["임금은 {value}이다.", "급여 구성·금액: {value}", "{value}을 지급한다."],
    ),
    "employment.pay_date": (
        ["매월 25일 근로자 계좌로 지급", "매월 말일 현금으로 지급"],
        ["임금 지급은 {value}한다.", "급여 지급일·방법: {value}", "{value}한다."],
    ),
    "employment.annual_leave": (
        ["근로기준법에 따라 부여한다", "연 15일을 부여한다"],
        ["연차 유급휴가는 {value}.", "연차휴가: {value}", "{value}."],
    ),
}

OTHER_EXAMPLES = [
    "본 계약은 상호 신뢰를 바탕으로 성실히 이행한다.",
    "문서의 제목과 조 번호는 편의를 위한 것이다.",
    "당사자는 개인정보를 안전하게 관리한다.",
    "계약서 두 부를 작성하여 각각 한 부씩 보관한다.",
    "기타 정하지 않은 사항은 상호 협의한다.",
]


def build_dataset(path: Path = OUTPUT_PATH, examples_per_field: int = 36) -> Path:
    randomizer = random.Random(RANDOM_SEED)
    rows = []
    for label, (values, templates) in FIELD_EXAMPLES.items():
        for index in range(examples_per_field):
            value = values[index % len(values)]
            template = templates[(index // len(values)) % len(templates)]
            text = template.format(value=value)
            if index % 4 == 1:
                text = text.replace(":", " : ")
            elif index % 4 == 2:
                text = text.replace(" ", "  ")
            rows.append({"text": text, "label": label, "value": value})

    other_count = max(examples_per_field * 3, len(FIELD_EXAMPLES) * 4)
    for index in range(other_count):
        rows.append(
            {
                "text": OTHER_EXAMPLES[index % len(OTHER_EXAMPLES)],
                "label": "other",
                "value": "",
            }
        )
    randomizer.shuffle(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=["text", "label", "value"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


if __name__ == "__main__":
    print(build_dataset())
