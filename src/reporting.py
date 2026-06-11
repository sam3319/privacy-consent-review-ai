import json
from datetime import datetime, timezone

from src.analyzer import redact_personal_data

def build_markdown_report(result: dict) -> str:
    metadata = result["legal_metadata"]
    lines = [
        "# 문서 자동 검토 보조 보고서",
        "",
        f"- 생성 시각(UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- 문서 유형: {result['document_type']}",
        f"- 문서 핵심정보 탐지율: {result['completeness']}%",
        f"- 법률 기준: {metadata['law_name']}",
        f"- 법률 시행일: {metadata['effective_date']}",
        f"- 근거 확인일: {metadata['verified_date']}",
        "",
        "## 구조화 추출",
        "",
    ]
    for field in result.get("extracted_fields", []):
        value = field["value"] or "(찾지 못함)"
        method = (
            "AI 보완"
            if field.get("extraction_method") == "ml_fallback"
            else "규칙 추출"
        )
        lines.append(
            f"- **{field['label']}**: {value} "
            f"[{field['status']}, 신뢰도 {field['confidence']}%, {method}]"
        )

    if result.get("sections"):
        lines.extend(["", "## 조항 구조", ""])
        for section in result["sections"]:
            heading = " ".join(
                item for item in (section["number"], section["title"]) if item
            )
            lines.extend([f"### {heading}", section["text"] or "(내용 없음)", ""])

    if result.get("perspective_summary"):
        lines.extend(
            ["", f"## {result.get('perspective', '')} 관점 요약", ""]
        )
        labels = {
            "rights": "권리",
            "obligations": "의무",
            "amounts": "금액",
            "periods": "기간",
            "termination": "해지·종료",
        }
        for key, label in labels.items():
            values = result["perspective_summary"].get(key, [])
            lines.append(f"- **{label}**: {' / '.join(values) if values else '(찾지 못함)'}")

    if result.get("renewal_terms"):
        lines.extend(["", "## 갱신·해지 통지 조건", ""])
        lines.extend(f"- {term}" for term in result["renewal_terms"])

    if result.get("housing_verification"):
        verification = result["housing_verification"]
        lines.extend(["", "## 외부 서류 교차확인", ""])
        for check in verification["checks"]:
            lines.append(
                f"- **[{check['status']}] {check['label']}**: {check['message']} "
                f"(계약서: {check['contract_value'] or '찾지 못함'} / "
                f"외부 서류: {check['reference_value'] or '찾지 못함'})"
            )
        lines.extend(["", verification["disclaimer"]])

    if result.get("deposit_risk"):
        risk = result["deposit_risk"]
        lines.extend(
            [
                "",
                "## 보증금 담보여력 참고 계산",
                "",
                f"- 참고 위험 수준: {risk['risk_level']}",
                f"- 총 부담 비율: {risk['burden_ratio']}%",
                f"- 보증금 커버리지: {risk['deposit_coverage']}%",
                f"- 선순위 금액 합계: {risk['prior_total']:,}원",
                f"- 선순위 금액과 본인 보증금 합계: {risk['total_exposure']:,}원",
                f"- 주택가액에서 선순위 금액을 뺀 잔여액: {risk['remaining_value']:,}원",
                f"- 검토 의견: {risk['message']}",
                "",
                risk["disclaimer"],
            ]
        )

    if result.get("wage_estimate"):
        wage = result["wage_estimate"]
        lines.extend(
            [
                "",
                "## 근로시간·예상 수당 참고 계산",
                "",
                f"- 통상 근로분: {wage['regular_pay']:,}원",
                f"- 연장 근로분: {wage['overtime_pay']:,}원",
                f"- 야간 가산분: {wage['night_premium']:,}원",
                f"- 휴일 근로분: {wage['holiday_pay']:,}원",
                f"- 주간 합계: {wage['weekly_total']:,}원",
            ]
        )
        lines.extend(f"- 경고: {warning}" for warning in wage["warnings"])
        lines.extend(["", wage["disclaimer"]])

    if result.get("legal_retrieval"):
        lines.extend(["", "## 관련 공식 법률 근거 검색", ""])
        for match in result["legal_retrieval"]:
            lines.append(
                f"- [{match['law_name']} {match['article']}] "
                f"{match['title']} ({match['score']}%): {match['official_url']}"
            )
        lines.append(
            "유사도는 관련 조문 후보 탐색을 위한 값이며 법적 적용 여부를 의미하지 않습니다."
        )

    if result.get("legal_version_check"):
        check = result["legal_version_check"]
        lines.extend(
            [
                "",
                "## 법률 시행일 비교",
                "",
                f"- 상태: {check['status']}",
                f"- 문서 작성일: {check['document_date']}",
                f"- 적용 규칙 시행일: {check['effective_date']}",
                f"- 근거 확인일: {check['verified_date']}",
                f"- 의견: {check['message']}",
            ]
        )

    if result.get("correction_audit"):
        lines.extend(["", "## 사용자 수정 이력", ""])
        for audit in result["correction_audit"]:
            lines.append(
                f"- **{audit['label']}**: {audit['before'] or '(없음)'} "
                f"-> {audit['after'] or '(빈 값)'}"
            )

    if result.get("document_pages"):
        lines.extend(["", "## 문서 페이지 품질", ""])
        for page in result["document_pages"]:
            quality = page["quality"]
            lines.append(
                f"- {page['page']}페이지: {quality['label']} "
                f"({quality['score']}%, {page['method']})"
            )

    if result.get("sensitive_data_candidates"):
        lines.extend(
            [
                "",
                "## 개인정보 다운로드 점검",
                "",
                "- 원문에서 탐지된 후보: "
                + ", ".join(result["sensitive_data_candidates"]),
                "- 보고서의 추출값과 근거 문장은 마스킹 결과를 기준으로 확인해야 합니다.",
            ]
        )

    if result.get("ml_clause_predictions"):
        lines.extend(["", "## AI 조항 위험 유형 예측", ""])
        lines.append(
            "학습 모델의 보조 예측이며 법적 판단이 아닙니다. "
            "공식 법률 규칙 결과를 우선해 확인해야 합니다."
        )
        lines.append("")
        for prediction in result["ml_clause_predictions"]:
            lines.append(
                f"- **{prediction['label']}** "
                f"({prediction['probability']}%): {prediction['clause']}"
            )

    lines.extend(["", "## 법률 검토 신호", ""])
    if not result["findings"]:
        lines.append("- 현재 규칙으로 탐지된 검토 신호가 없습니다.")
    for finding in result["findings"]:
        lines.extend(
            [
                f"### [{finding['status']}] {finding['title']}",
                f"- 심각도: {finding['severity']}",
                f"- 탐지 신뢰도: {finding['confidence']}%",
                f"- 근거: {finding['article']}",
                f"- 검토 의견: {finding['message']}",
                f"- 탐지 문구: {finding['evidence'] or '(없음)'}",
                f"- 공식 원문: {finding['official_url']}",
                "",
            ]
        )

    lines.extend(["## 주의", "", result["disclaimer"]])
    return "\n".join(lines)


def build_json_report(result: dict) -> str:
    report = {
        key: value
        for key, value in result.items()
        if key not in {"redacted_preview", "document_pages"}
    }
    if result.get("document_pages"):
        report["document_pages"] = [
            {
                **page,
                "text": redact_personal_data(page["text"]),
            }
            for page in result["document_pages"]
        ]
    return json.dumps(report, ensure_ascii=False, indent=2)
