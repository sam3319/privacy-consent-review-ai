import csv
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "clause_risk_training.csv"
RANDOM_SEED = 20260610
SAMPLES_PER_CLASS = 60

TEMPLATES = {
    "normal": [
        "각 당사자는 귀책사유로 발생한 직접 손해를 배상한다.",
        "계약 해지는 {days}일 전에 서면으로 통지할 수 있다.",
        "임금은 매월 {day}일 근로자 명의 계좌로 지급한다.",
        "임대인은 계약 종료 후 정산하여 보증금을 반환한다.",
        "분쟁은 당사자 협의 후 민사소송법상 관할법원에서 해결한다.",
    ],
    "liability_exemption": [
        "회사는 어떠한 손해에 대해서도 일체의 책임을 지지 않는다.",
        "갑은 모든 사고와 손해배상 책임을 부담하지 않는다.",
        "사업자는 고의 또는 중대한 과실이 있어도 책임이 없다.",
        "고객에게 발생하는 모든 손해에 대해 회사의 책임을 면제한다.",
    ],
    "termination_restriction": [
        "을은 계약기간 중 어떠한 사유로도 계약을 해지할 수 없다.",
        "고객의 중도 해지는 금지되며 회사는 언제든 해지할 수 있다.",
        "이용자는 해지할 수 없고 사업자만 임의로 계약을 종료한다.",
        "회원의 계약 해지 권리를 제한한다.",
    ],
    "excessive_penalty": [
        "을은 중도 해지 시 잔여 대금 전액을 위약금으로 지급한다.",
        "계약 위반 시 총 계약금액의 {rate}%를 위약벌로 납부한다.",
        "해지하는 고객은 이미 지급한 금액을 모두 포기한다.",
        "연체 시 매월 {rate}%의 지연손해금을 부담한다.",
    ],
    "housing_renewal_restriction": [
        "임차인은 계약갱신요구권을 포기한다.",
        "세입자는 어떠한 경우에도 임대차 갱신을 요구할 수 없다.",
        "임차인의 갱신 요구 권리는 인정하지 않는다.",
        "계약 종료 시 임차인은 갱신 없이 즉시 퇴거한다.",
    ],
    "employment_penalty": [
        "근로자가 중도 퇴사하면 위약금 {amount}원을 지급한다.",
        "무단 퇴사 시 근로자는 손해배상액 {amount}원을 납부한다.",
        "계약기간을 채우지 못하면 급여 한 달분을 벌금으로 공제한다.",
        "사직하는 직원은 교육비 전액을 위약금으로 반환한다.",
    ],
    "excessive_work_hours": [
        "소정근로시간은 1일 {hours}시간, 주 {weekly}시간으로 한다.",
        "근로자는 매일 {hours}시간 근무하고 휴일에도 출근한다.",
        "주당 근무시간은 {weekly}시간이며 추가 수당은 없다.",
        "업무상 필요하면 하루 {hours}시간까지 상시 근무한다.",
    ],
}


def build_dataset(output_path: Path = OUTPUT_PATH) -> Path:
    rng = random.Random(RANDOM_SEED)
    rows = []
    for label, templates in TEMPLATES.items():
        for _ in range(SAMPLES_PER_CLASS):
            text = rng.choice(templates).format(
                days=rng.choice([7, 14, 30, 60]),
                day=rng.choice([10, 20, 25]),
                rate=rng.choice([20, 30, 50, 100]),
                amount=f"{rng.choice([50, 100, 200, 300]) * 10000:,}",
                hours=rng.choice([9, 10, 11, 12]),
                weekly=rng.choice([45, 50, 52, 60]),
            )
            rows.append(
                {"text": text, "label": label, "source": "synthetic_template"}
            )
    rng.shuffle(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=["text", "label", "source"])
        writer.writeheader()
        writer.writerows(rows)
    return output_path


if __name__ == "__main__":
    print(f"Generated clause training data: {build_dataset()}")
