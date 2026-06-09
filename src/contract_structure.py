import re
from datetime import date


SECTION_PATTERN = re.compile(
    r"(?m)^\s*(제\s*\d+\s*조(?:의\s*\d+)?(?:\s*\([^)\n]+\))?)\s*"
)


def split_contract_sections(text: str) -> list[dict]:
    matches = list(SECTION_PATTERN.finditer(text))
    if not matches:
        return [
            {
                "number": "전문",
                "title": "전체 문서",
                "text": text.strip(),
            }
        ]

    sections = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        sections.append({"number": "전문", "title": "전문", "text": preamble})

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        heading = re.sub(r"\s+", "", match.group(1))
        title_match = re.search(r"\(([^)]+)\)", match.group(1))
        sections.append(
            {
                "number": heading.split("(")[0],
                "title": title_match.group(1).strip() if title_match else "",
                "text": text[match.end() : end].strip(),
            }
        )
    return sections


def summarize_by_perspective(text: str, perspective: str) -> dict:
    aliases = {
        "갑": ("갑",),
        "을": ("을",),
        "소비자": ("소비자", "고객", "회원", "이용자", "을"),
        "사업자": ("사업자", "회사", "갑"),
        "임대인": ("임대인", "갑"),
        "임차인": ("임차인", "을"),
        "사용자": ("사용자", "사업주", "회사", "갑"),
        "근로자": ("근로자", "직원", "을"),
    }
    subjects = aliases.get(perspective, (perspective,))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    categories = {
        "rights": [],
        "obligations": [],
        "amounts": [],
        "periods": [],
        "termination": [],
    }
    subject_pattern = "|".join(map(re.escape, subjects))
    for line in lines:
        if not re.search(subject_pattern, line):
            continue
        if re.search(r"(권리|청구|요구|할 수 있|선택|동의)", line):
            categories["rights"].append(line)
        if re.search(r"(의무|하여야|해야|지급|부담|준수|금지)", line):
            categories["obligations"].append(line)
        if re.search(r"(\d[\d,]*\s*원|보증금|차임|월세|대금|임금|수당)", line):
            categories["amounts"].append(line)
        if re.search(r"(\d+\s*(일|개월|년)|기간|기한|부터|까지)", line):
            categories["periods"].append(line)
        if re.search(r"(해제|해지|종료|갱신|퇴거|퇴직)", line):
            categories["termination"].append(line)
    return {
        key: list(dict.fromkeys(values))
        for key, values in categories.items()
    }


def extract_renewal_terms(text: str) -> list[str]:
    return _matching_lines(
        text,
        [
            r"자동\s*갱신",
            r"묵시.{0,5}갱신",
            r"갱신.{0,20}(통지|거절|요구)",
            r"(해제|해지|종료).{0,20}\d+\s*(일|개월).{0,10}(전|통지)",
        ],
    )


def find_internal_consistency_issues(text: str) -> list[dict]:
    issues = []
    dates = extract_date_ranges(text)
    for line, start, end in dates:
        if end < start:
            issues.append(
                {
                    "id": "CONTRACT_DATE_ORDER",
                    "title": "계약 기간 날짜 순서 검토",
                    "message": "종료일이 시작일보다 앞선 날짜 범위가 탐지되었습니다.",
                    "evidence": line,
                    "severity": "높음",
                }
            )

    total_match = re.search(r"총\s*(?:액|대금|보수)?\s*[:：]?\s*([\d,]+)\s*원", text)
    installments = re.findall(
        r"(?:계약금|중도금|잔금|분할금)\s*[:：]?\s*([\d,]+)\s*원",
        text,
    )
    if total_match and len(installments) >= 2:
        total = int(total_match.group(1).replace(",", ""))
        installment_total = sum(int(value.replace(",", "")) for value in installments)
        if total != installment_total:
            issues.append(
                {
                    "id": "CONTRACT_PAYMENT_SUM",
                    "title": "총액과 분할 지급액 합계 검토",
                    "message": (
                        f"표시된 총액 {total:,}원과 분할 지급액 합계 "
                        f"{installment_total:,}원이 일치하지 않습니다."
                    ),
                    "evidence": total_match.group(0),
                    "severity": "높음",
                }
            )
    return issues


def _matching_lines(text: str, patterns: list[str]) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return list(
        dict.fromkeys(
            line
            for line in lines
            if any(re.search(pattern, line) for pattern in patterns)
        )
    )


def extract_date_ranges(text: str) -> list[tuple[str, date, date]]:
    results = []
    pattern = re.compile(
        r"(?P<sy>\d{4})[.\-/년]\s*(?P<sm>\d{1,2})[.\-/월]\s*"
        r"(?P<sd>\d{1,2})일?.{0,15}?(?:부터|~|∼|-).{0,15}?"
        r"(?P<ey>\d{4})[.\-/년]\s*(?P<em>\d{1,2})[.\-/월]\s*"
        r"(?P<ed>\d{1,2})일?"
    )
    for line in text.splitlines():
        match = pattern.search(line)
        if not match:
            continue
        try:
            start = date(
                int(match.group("sy")),
                int(match.group("sm")),
                int(match.group("sd")),
            )
            end = date(
                int(match.group("ey")),
                int(match.group("em")),
                int(match.group("ed")),
            )
        except ValueError:
            continue
        results.append((line.strip(), start, end))
    return results
