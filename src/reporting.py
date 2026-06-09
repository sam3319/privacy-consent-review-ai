import json
from datetime import datetime, timezone


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
        lines.append(
            f"- **{field['label']}**: {value} "
            f"[{field['status']}, 신뢰도 {field['confidence']}%]"
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
        if key != "redacted_preview"
    }
    return json.dumps(report, ensure_ascii=False, indent=2)
