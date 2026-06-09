import csv
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "document_type_training.csv"
RANDOM_SEED = 20260609
SAMPLES_PER_CLASS = 80


VOCABULARY = {
    "privacy_consent": {
        "titles": [
            "개인정보 수집 및 이용 동의서",
            "개인정보 처리 동의 안내",
            "회원가입 개인정보 동의",
            "개인정보 제3자 제공 동의서",
        ],
        "lines": [
            "수집 이용 목적: {purpose}",
            "수집 개인정보 항목: {items}",
            "보유 및 이용 기간: {period}",
            "동의를 거부할 권리가 있으며 거부 시 {restriction}",
            "제공받는 자: {recipient}",
            "제공 목적: {purpose}",
        ],
        "values": {
            "purpose": ["회원 가입", "고객 상담", "배송 처리", "서비스 운영"],
            "items": ["이름, 이메일", "성명, 연락처", "주소, 전화번호", "계정 정보"],
            "period": ["회원 탈퇴 시까지", "3년", "목적 달성 시까지", "배송 완료 후 1년"],
            "restriction": ["가입이 제한됩니다", "서비스 이용이 어렵습니다", "불이익은 없습니다"],
            "recipient": ["배송업체", "결제대행사", "주식회사 예시", "고객지원 수탁사"],
        },
    },
    "standard_terms_contract": {
        "titles": ["서비스 이용 약관", "온라인 서비스 계약서", "용역 계약 약관", "회원 이용계약"],
        "lines": [
            "계약 당사자: 갑 {company}, 을 고객",
            "계약 목적: {service} 제공",
            "계약 기간: 가입일부터 해지일까지",
            "계약 대금: 월 {amount}원",
            "계약 해지: {termination}",
            "손해배상: 귀책사유로 발생한 손해를 배상한다",
            "분쟁 해결: 관할 법원에서 해결한다",
        ],
        "values": {
            "company": ["예시회사", "서비스 주식회사", "온라인 사업자", "교육센터"],
            "service": ["온라인 교육", "정보 콘텐츠", "시설 관리", "회원 서비스"],
            "amount": ["10,000", "30,000", "50,000", "100,000"],
            "termination": ["30일 전 통지한다", "서면 통지 후 가능하다", "약관에 따라 처리한다"],
        },
    },
    "housing_lease": {
        "titles": ["주택 임대차 계약서", "아파트 전세 계약서", "오피스텔 월세 계약서", "부동산 임대차계약"],
        "lines": [
            "임대인: {landlord}",
            "임차인: {tenant}",
            "임대 목적물: {address}",
            "보증금: {deposit}원",
            "월세: {rent}원",
            "임대차 기간: {start}부터 {end}까지",
            "관리비: 월 {management}원",
            "특약사항: 계약갱신과 보증금 반환은 법령에 따른다",
        ],
        "values": {
            "landlord": ["홍길동", "김임대", "주식회사 예시", "박소유"],
            "tenant": ["김예시", "이임차", "최거주", "정세입"],
            "address": ["서울시 예시구 101호", "부산시 표본구 202호", "아파트 303동 404호"],
            "deposit": ["10,000,000", "50,000,000", "100,000,000", "200,000,000"],
            "rent": ["0", "300,000", "500,000", "800,000"],
            "start": ["2026년 1월 1일", "2026년 3월 1일", "2026년 7월 1일"],
            "end": ["2027년 12월 31일", "2028년 2월 29일", "2028년 6월 30일"],
            "management": ["50,000", "100,000", "150,000"],
        },
    },
    "employment_contract": {
        "titles": ["근로계약서", "표준 근로계약서", "기간제 근로계약", "직원 고용 계약서"],
        "lines": [
            "사용자: {company}",
            "근로자: {worker}",
            "근무 장소: {workplace}",
            "업무 내용: {duties}",
            "소정근로시간: 1일 {daily_hours}시간",
            "근무일: 월요일부터 금요일",
            "임금: {wage_type} {wage}원",
            "임금 지급일: 매월 {pay_day}일",
            "휴일과 연차 유급휴가는 근로기준법에 따른다",
        ],
        "values": {
            "company": ["예시 주식회사", "표본상사", "온라인센터", "교육기관"],
            "worker": ["김근로", "이직원", "박예시", "최사원"],
            "workplace": ["서울 본사", "부산 지점", "재택 근무지", "지정 사업장"],
            "duties": ["고객 상담", "소프트웨어 개발", "매장 관리", "교육 운영"],
            "daily_hours": ["6", "7", "8", "9"],
            "wage_type": ["시급", "월급", "기본급"],
            "wage": ["12,000", "2,500,000", "3,000,000", "3,500,000"],
            "pay_day": ["10", "20", "25", "말"],
        },
    },
}


def generate_text(label: str, index: int, rng: random.Random) -> str:
    config = VOCABULARY[label]
    values = {
        key: rng.choice(options)
        for key, options in config["values"].items()
    }
    line_count = rng.randint(max(4, len(config["lines"]) - 2), len(config["lines"]))
    lines = rng.sample(config["lines"], line_count)
    rendered = [rng.choice(config["titles"])]
    rendered.extend(line.format(**values) for line in lines)
    if index % 4 == 0:
        rng.shuffle(rendered[1:])
    return "\n".join(rendered)


def build_dataset(output_path: Path = OUTPUT_PATH) -> Path:
    rng = random.Random(RANDOM_SEED)
    rows = []
    for label in VOCABULARY:
        for index in range(SAMPLES_PER_CLASS):
            rows.append(
                {
                    "text": generate_text(label, index, rng),
                    "label": label,
                    "source": "synthetic_template",
                }
            )
    rng.shuffle(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=["text", "label", "source"])
        writer.writeheader()
        writer.writerows(rows)
    return output_path


if __name__ == "__main__":
    path = build_dataset()
    print(f"Generated training data: {path}")
