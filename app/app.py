import json
import sys
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
root_path = str(ROOT)
if root_path in sys.path:
    sys.path.remove(root_path)
sys.path.insert(0, root_path)

from src.analyzer import analyze_document, detect_sensitive_data
from src.contract_analyzer import analyze_contract
from src.document_classifier import detect_document_type_hybrid
from src.document_io import extract_text, extract_text_with_details
from src.employment_calculator import calculate_wage_estimate
from src.legal_retrieval import assess_legal_version, search_legal_basis
from src.model_security import model_integrity_status
from src.legal_rules import (
    load_contract_sources,
    load_legal_sources,
)
from src.reporting import build_json_report, build_markdown_report
from src.review_feedback import apply_field_corrections, build_feedback_json
from src.special_contract_analyzer import (
    analyze_employment_contract,
    analyze_housing_contract,
    load_special_sources,
)


DOCUMENT_TYPE_LABELS = {
    "자동 감지 (권장)": "auto",
    "개인정보 수집·이용 동의": "collection",
    "개인정보 제3자 제공 동의": "third_party",
    "수집·이용 및 제3자 제공 복합 문서": "combined",
    "약관형 계약서": "standard_terms_contract",
    "주택 임대차(전세·월세) 계약서": "housing_lease",
    "근로계약서": "employment_contract",
}

DIRECT_FIELD_LABELS = {
    "standard_terms_contract": [
        ("parties", "계약 당사자"),
        ("subject", "계약 목적·대상"),
        ("term", "계약 기간"),
        ("payment", "대금·보수·지급 조건"),
    ],
    "housing_lease": [
        ("parties", "임대인·임차인"),
        ("property", "임대 목적물"),
        ("deposit", "보증금"),
        ("monthly_rent", "월 차임·월세"),
        ("term", "임대차 기간"),
    ],
    "employment_contract": [
        ("parties", "사용자·근로자"),
        ("workplace", "근무 장소"),
        ("duties", "업무 내용"),
        ("work_hours", "소정근로시간"),
        ("wage", "임금 구성·금액"),
    ],
}


st.set_page_config(
    page_title="법률 문서 검토 보조",
    page_icon="📄",
    layout="wide",
)

sources = load_legal_sources()
integrity_status = model_integrity_status()

st.title("법률 문서 검토 보조")
st.warning(
    "이 서비스는 위법 여부를 판정하거나 법률 자문을 제공하지 않습니다. "
    "공식 법령에 연결된 문구 탐지와 추가 검토 신호만 제공합니다."
)
if integrity_status["valid"]:
    st.caption(
        f"모델 무결성 확인: {len(integrity_status['models'])}개 모델 SHA-256 일치"
    )
else:
    st.error(
        "모델 무결성 검증에 실패했습니다. 해당 ML 기능은 규칙 엔진으로 "
        "폴백되거나 생략됩니다."
    )
    with st.expander("모델 무결성 오류"):
        for error in integrity_status["errors"]:
            st.write(f"- {error}")
document_label = st.selectbox("문서 유형", DOCUMENT_TYPE_LABELS)
document_type = DOCUMENT_TYPE_LABELS[document_label]
document_date = st.date_input(
    "문서 작성일 (선택)",
    value=None,
    help="작성 당시 법률과 현재 분석 기준의 시행일 차이를 확인합니다.",
)
source_loaders = {
    "standard_terms_contract": load_contract_sources,
    "housing_lease": lambda: load_special_sources("housing_legal_sources.json"),
    "employment_contract": lambda: load_special_sources(
        "employment_legal_sources.json"
    ),
}
active_sources = source_loaders.get(document_type, lambda: sources)()
metadata = active_sources["metadata"]
if document_type == "auto":
    st.caption(
        "문서 내용을 기준으로 개인정보 동의서 또는 약관형 계약서를 자동 감지합니다."
    )
else:
    st.caption(
        f"법률 기준: {metadata['law_name']} | 시행일 {metadata['effective_date']} | "
        f"근거 확인일 {metadata['verified_date']} | {metadata['official_source']}"
    )
if document_type == "standard_terms_contract":
    st.info(
        "계약서 분석은 사업자가 여러 상대방과 계약하기 위해 미리 마련한 "
        "약관형 계약서를 대상으로 합니다. 개별 협상 계약이나 근로·임대차·금융 "
        "계약은 특별법 검토가 추가로 필요합니다."
    )
elif document_type == "housing_lease":
    st.info(
        "등기사항증명서, 건축물대장, 선순위 보증금과 임대인 체납 여부는 "
        "업로드한 계약서만으로 확인할 수 없습니다."
    )
elif document_type == "employment_contract":
    st.info(
        "근로자성, 사업장 규모, 업종과 근로시간 적용 예외는 계약서 문언만으로 "
        "확정할 수 없습니다."
    )
perspective = st.selectbox(
    "검토 관점",
    ["자동 기본", "갑", "을", "소비자", "사업자", "임대인", "임차인", "사용자", "근로자"],
)
uploaded_file = st.file_uploader(
    "문서 업로드",
    type=["txt", "pdf", "docx", "png", "jpg", "jpeg"],
    help="파일은 분석 과정에서만 메모리에 읽으며 애플리케이션 코드가 별도로 저장하지 않습니다.",
)
if uploaded_file is not None and st.button("업로드 텍스트 추출/OCR"):
    if uploaded_file.size > 10 * 1024 * 1024:
        st.error("업로드 파일은 10MB 이하여야 합니다.")
    else:
        try:
            details = extract_text_with_details(
                uploaded_file.name,
                uploaded_file.getvalue(),
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.session_state["document_pages"] = details["pages"]
            st.session_state["manual_document_text"] = details["text"]

if st.session_state.get("document_pages"):
    with st.expander("페이지별 OCR·텍스트 품질 및 수정"):
        st.caption(
            "품질 점수는 문자 구성 기반 참고값입니다. 수정 후 아래 버튼을 눌러 "
            "문서 내용에 반영하세요."
        )
        page_values = []
        for page in st.session_state["document_pages"]:
            quality = page["quality"]
            st.write(
                f"**{page['page']}페이지**: {quality['label']} "
                f"({quality['score']}%, {page['method']})"
            )
            if (
                uploaded_file is not None
                and Path(uploaded_file.name).suffix.lower()
                in {".png", ".jpg", ".jpeg"}
            ):
                preview_column, text_column = st.columns([1, 1])
                preview_column.image(
                    uploaded_file.getvalue(),
                    caption="업로드 원본",
                    use_container_width=True,
                )
                page_values.append(
                    text_column.text_area(
                        f"{page['page']}페이지 텍스트",
                        value=page["text"],
                        height=260,
                        key=f"page_text_{page['page']}",
                    )
                )
            else:
                page_values.append(
                    st.text_area(
                        f"{page['page']}페이지 텍스트",
                        value=page["text"],
                        height=160,
                        key=f"page_text_{page['page']}",
                    )
                )
        if st.button("페이지 수정 내용을 문서에 반영"):
            st.session_state["manual_document_text"] = "\n".join(page_values)
            st.rerun()

manual_text = st.text_area(
    "문서 내용을 붙여넣거나 OCR 결과를 수정하세요",
    height=300,
    placeholder=(
        "직접 입력하거나, 업로드 문서에서 추출한 텍스트를 수정해 다시 분석할 수 있습니다. "
        "입력값이 있으면 업로드 파일보다 우선합니다."
    ),
    key="manual_document_text",
)
correction_json = st.text_area(
    "추출값 수정 JSON (선택)",
    height=100,
    placeholder='예: {"deposit": "120,000,000원", "property": "서울특별시 예시구 101호"}',
    help="이전 분석 결과의 필드 key와 수정값을 JSON 객체로 입력한 뒤 다시 분석하세요.",
)
direct_corrections = {}
if document_type in DIRECT_FIELD_LABELS:
    with st.expander("추출값 직접 수정"):
        st.caption(
            "값을 입력하면 자동 추출 결과보다 우선합니다. 비워 둔 항목은 자동 추출값을 사용합니다."
        )
        for key, label in DIRECT_FIELD_LABELS[document_type]:
            direct_corrections[key] = st.text_input(
                label,
                key=f"direct_correction_{document_type}_{key}",
            )

supporting_uploads = {}
financial_inputs = {}
employment_inputs = {}
if document_type == "housing_lease":
    with st.expander("외부 서류 교차확인 및 보증금 위험 계산"):
        st.caption(
            "등기사항증명서와 건축물대장은 선택 입력입니다. 서류 진위와 최신 상태는 "
            "판정하지 않으며, 입력한 금액으로 단순 담보여력만 계산합니다."
        )
        registry_file = st.file_uploader(
            "등기사항증명서",
            type=["txt", "pdf", "docx", "png", "jpg", "jpeg"],
            key="registry_document",
        )
        building_file = st.file_uploader(
            "건축물대장",
            type=["txt", "pdf", "docx", "png", "jpg", "jpeg"],
            key="building_ledger_document",
        )
        property_value = st.number_input(
            "주택가액 또는 예상 매매가(원)",
            min_value=0,
            step=10_000_000,
            format="%d",
        )
        tenant_deposit = st.number_input(
            "본인 임차보증금(원, 0이면 계약서에서 추출)",
            min_value=0,
            step=10_000_000,
            format="%d",
        )
        senior_claims = st.number_input(
            "선순위 채권액(원, 0이면 등기 문서의 채권최고액 사용)",
            min_value=0,
            step=10_000_000,
            format="%d",
        )
        senior_deposits = st.number_input(
            "선순위 임차보증금 합계(원)",
            min_value=0,
            step=10_000_000,
            format="%d",
        )
        supporting_uploads = {
            "registry": registry_file,
            "building_ledger": building_file,
        }
        financial_inputs = {
            "property_value": property_value,
            "tenant_deposit": tenant_deposit,
            "senior_claims": senior_claims,
            "senior_deposits": senior_deposits,
        }
elif document_type == "employment_contract":
    with st.expander("근로시간 및 예상 수당 계산"):
        st.caption(
            "주 단위 시간과 시간급을 직접 입력합니다. 계산값은 참고용이며 "
            "통상임금·주휴수당·적용 예외를 확정하지 않습니다."
        )
        hourly_wage = st.number_input(
            "시간급(원)",
            min_value=0,
            step=100,
            format="%d",
        )
        regular_hours = st.number_input(
            "주간 통상 근로시간",
            min_value=0.0,
            step=0.5,
        )
        overtime_hours = st.number_input(
            "주간 연장근로 시간",
            min_value=0.0,
            step=0.5,
        )
        night_hours = st.number_input(
            "주간 야간근로 시간(22:00~06:00)",
            min_value=0.0,
            step=0.5,
        )
        holiday_hours = st.number_input(
            "주간 휴일근로 시간",
            min_value=0.0,
            step=0.5,
        )
        monthly_ordinary_wage = st.number_input(
            "월 통상임금(원, 시간급이 0일 때만 사용)",
            min_value=0,
            step=100_000,
            format="%d",
        )
        monthly_standard_hours = st.number_input(
            "월 통상임금 환산 기준시간",
            min_value=1.0,
            value=209.0,
            step=1.0,
        )
        weekly_paid_holiday_hours = st.number_input(
            "주휴수당 대상 유급시간(해당 시)",
            min_value=0.0,
            step=1.0,
        )
        workplace_has_five_or_more = st.checkbox(
            "상시근로자 5인 이상 사업장",
            value=True,
        )
        employment_inputs = {
            "hourly_wage": hourly_wage,
            "regular_hours": regular_hours,
            "overtime_hours": overtime_hours,
            "night_hours": night_hours,
            "holiday_hours": holiday_hours,
            "monthly_ordinary_wage": monthly_ordinary_wage,
            "monthly_standard_hours": monthly_standard_hours,
            "weekly_paid_holiday_hours": weekly_paid_holiday_hours,
            "workplace_has_five_or_more": workplace_has_five_or_more,
        }

if st.button("문서 분석", type="primary", use_container_width=True):
    try:
        document_text = manual_text.strip()
        if not document_text and uploaded_file is not None:
            if uploaded_file.size > 10 * 1024 * 1024:
                raise ValueError("업로드 파일은 10MB 이하여야 합니다.")
            document_text = extract_text(uploaded_file.name, uploaded_file.getvalue())
        supporting_documents = {}
        for supporting_type, supporting_file in supporting_uploads.items():
            if supporting_file is None:
                continue
            if supporting_file.size > 10 * 1024 * 1024:
                raise ValueError("외부 서류는 각 10MB 이하여야 합니다.")
            supporting_documents[supporting_type] = extract_text(
                supporting_file.name, supporting_file.getvalue()
            )
        analyzed_type = document_type
        detection = None
        if analyzed_type == "auto":
            detection = detect_document_type_hybrid(document_text)
            analyzed_type = detection["document_type"]
        selected_perspective = perspective
        if selected_perspective == "자동 기본":
            selected_perspective = {
                "housing_lease": "임차인",
                "employment_contract": "근로자",
                "standard_terms_contract": "을",
            }.get(analyzed_type, "")
        if analyzed_type == "standard_terms_contract":
            result = analyze_contract(document_text, selected_perspective)
        elif analyzed_type == "housing_lease":
            result = analyze_housing_contract(
                document_text,
                selected_perspective,
                supporting_documents=supporting_documents,
                financial_inputs=financial_inputs,
            )
        elif analyzed_type == "employment_contract":
            result = analyze_employment_contract(document_text, selected_perspective)
        else:
            result = analyze_document(document_text, analyzed_type)
        corrections = json.loads(correction_json) if correction_json.strip() else {}
        if not isinstance(corrections, dict):
            raise ValueError("추출값 수정 JSON은 필드 key와 수정값으로 구성된 객체여야 합니다.")
        corrections.update(
            {
                key: value
                for key, value in direct_corrections.items()
                if value.strip()
            }
        )
        result = apply_field_corrections(result, corrections)
        result["document_pages"] = st.session_state.get("document_pages", [])
        result["sensitive_data_candidates"] = detect_sensitive_data(document_text)
        result["legal_retrieval"] = search_legal_basis(document_text)
        result["legal_version_check"] = assess_legal_version(
            document_date,
            result["legal_metadata"],
        )
        if analyzed_type == "employment_contract":
            result["wage_estimate"] = calculate_wage_estimate(**employment_inputs)
        feedback_json = build_feedback_json(result, corrections, document_text)
    except json.JSONDecodeError as error:
        st.error(f"추출값 수정 JSON 형식을 확인하세요: {error.msg}")
    except ValueError as error:
        st.error(str(error))
    except Exception:
        st.error(
            "문서를 읽는 중 오류가 발생했습니다. 파일 형식, OCR 설치 상태와 문서 상태를 확인하세요."
        )
    else:
        st.subheader("분석 결과")
        if detection:
            st.success(
                f"자동 감지 문서 유형: {detection['label']} "
                f"(신뢰도 {detection['confidence']}%)"
            )
            ml_prediction = detection["ml_prediction"]
            st.caption(
                f"AI 모델: {ml_prediction['model_type']} | "
                f"예측 {ml_prediction['label']} "
                f"({ml_prediction['probability']}%) | "
                f"규칙 엔진과 {'일치' if detection['agreement'] else '불일치'}"
            )
            if not detection["agreement"]:
                st.warning(
                    "AI 모델과 규칙 엔진의 문서 유형 판단이 다릅니다. "
                    "원문과 선택된 문서 유형을 직접 확인하세요."
                )
        metric_label = (
            "계약 핵심정보 탐지율"
            if analyzed_type in {
                "standard_terms_contract",
                "housing_lease",
                "employment_contract",
            }
            else "법정 고지사항 구체값 탐지율"
        )
        st.metric(metric_label, f"{result['completeness']}%")
        st.caption(
            "탐지율은 문구와 값의 자동 추출 결과이며 적법성이나 내용의 충분성을 의미하지 않습니다."
        )

        if result.get("scope_warning"):
            st.warning(result["scope_warning"])
        if result.get("legal_version_check"):
            version_check = result["legal_version_check"]
            if version_check["status"] == "현재 규칙 범위":
                st.info(version_check["message"])
            else:
                st.warning(version_check["message"])
        if result.get("sensitive_data_candidates"):
            st.warning(
                "원문에 개인정보 후보가 남아 있습니다: "
                + ", ".join(result["sensitive_data_candidates"])
                + ". 다운로드 전 마스킹 미리보기를 확인하세요."
            )

        st.markdown("### 구조화 추출")
        for field in result.get("extracted_fields", []):
            value = field["value"] or "찾지 못함"
            method = (
                "AI 보완"
                if field.get("extraction_method") == "ml_fallback"
                else "규칙 추출"
            )
            st.write(
                f"**{field['label']}**: {value} "
                f"({field['status']}, 신뢰도 {field['confidence']}%, {method})"
            )

        if result.get("sections"):
            with st.expander(f"조항 구조 ({len(result['sections'])}개)"):
                for section in result["sections"]:
                    heading = " ".join(
                        item for item in (section["number"], section["title"]) if item
                    )
                    st.markdown(f"**{heading}**")
                    st.write(section["text"] or "(내용 없음)")

        if result.get("perspective_summary"):
            st.markdown(f"### {result['perspective']} 관점 요약")
            summary_labels = {
                "rights": "권리",
                "obligations": "의무",
                "amounts": "금액",
                "periods": "기간",
                "termination": "해지·종료",
            }
            for key, label in summary_labels.items():
                values = result["perspective_summary"].get(key, [])
                st.write(f"**{label}**: " + (" / ".join(values) if values else "찾지 못함"))

        if result.get("renewal_terms"):
            st.markdown("### 갱신·해지 통지 조건")
            for term in result["renewal_terms"]:
                st.write(f"- {term}")

        if result.get("housing_verification"):
            verification = result["housing_verification"]
            st.markdown("### 외부 서류 교차확인")
            for check in verification["checks"]:
                st.write(
                    f"**[{check['status']}] {check['label']}**: {check['message']}"
                )
                if check["contract_value"] or check["reference_value"]:
                    st.caption(
                        f"계약서: {check['contract_value'] or '찾지 못함'} | "
                        f"외부 서류: {check['reference_value'] or '찾지 못함'}"
                    )
            st.caption(verification["disclaimer"])

        if result.get("deposit_risk"):
            risk = result["deposit_risk"]
            st.markdown("### 보증금 담보여력 참고 계산")
            risk_col1, risk_col2, risk_col3 = st.columns(3)
            risk_col1.metric("총 부담 비율", f"{risk['burden_ratio']}%")
            risk_col2.metric("보증금 커버리지", f"{risk['deposit_coverage']}%")
            risk_col3.metric("참고 위험 수준", risk["risk_level"])
            st.write(risk["message"])
            st.caption(risk["disclaimer"])

        if result.get("wage_estimate"):
            wage = result["wage_estimate"]
            st.markdown("### 근로시간·예상 수당 참고 계산")
            wage_col1, wage_col2, wage_col3 = st.columns(3)
            wage_col1.metric("통상 근로분", f"{wage['regular_pay']:,}원")
            wage_col2.metric("연장 근로분", f"{wage['overtime_pay']:,}원")
            wage_col3.metric("주간 합계", f"{wage['weekly_total']:,}원")
            st.write(
                f"야간 가산분 {wage['night_premium']:,}원 | "
                f"휴일 근로분 {wage['holiday_pay']:,}원 | "
                f"주휴수당 {wage['paid_holiday_pay']:,}원"
            )
            for warning in wage["warnings"]:
                st.warning(warning)
            st.caption(wage["disclaimer"])

        if result.get("legal_retrieval"):
            st.markdown("### 관련 공식 법률 근거 검색")
            st.caption(
                "문서와 의미가 가까운 공식 법률 규칙 후보입니다. "
                "유사도는 법적 적용 여부나 결론을 의미하지 않습니다."
            )
            for legal_match in result["legal_retrieval"]:
                st.markdown(
                    f"- [{legal_match['law_name']} {legal_match['article']} "
                    f"{legal_match['title']}]({legal_match['official_url']}) "
                    f"(유사도 {legal_match['score']}%)"
                )

        if result.get("ml_clause_predictions"):
            st.markdown("### AI 조항 위험 유형 예측")
            st.caption(
                "학습 모델의 보조 예측이며 법적 판단이 아닙니다. "
                "공식 법률 규칙 결과를 우선해 확인하세요."
            )
            for prediction in result["ml_clause_predictions"]:
                st.write(
                    f"- **{prediction['label']}** "
                    f"({prediction['probability']}%): "
                    f"{prediction['clause']}"
                )

        for finding in result["findings"]:
            if finding["status"] in {
                "누락 가능성",
                "구체성 검토",
                "검토 필요",
            }:
                icon = "⚠️"
            else:
                icon = "✅"
            with st.expander(
                f"{icon} [{finding['status']}] {finding['title']}",
                expanded=finding["status"] in {"누락 가능성", "검토 필요"},
            ):
                st.write(finding["message"])
                st.write(
                    f"**심각도:** {finding['severity']} | "
                    f"**탐지 신뢰도:** {finding['confidence']}%"
                )
                st.write(f"**법적 근거:** {finding['article']}")
                if finding["evidence"]:
                    st.write(f"**탐지 문구:** {finding['evidence']}")
                st.link_button("국가법령정보센터에서 근거 확인", finding["official_url"])

        with st.expander("개인정보 마스킹 미리보기"):
            st.text(result["redacted_preview"])
        st.info(result["disclaimer"])

        report_col1, report_col2, report_col3 = st.columns(3)
        report_col1.download_button(
            "Markdown 보고서 다운로드",
            build_markdown_report(result),
            file_name="document_review_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
        report_col2.download_button(
            "JSON 결과 다운로드",
            build_json_report(result),
            file_name="document_review_report.json",
            mime="application/json",
            use_container_width=True,
        )
        report_col3.download_button(
            "익명화 수정 피드백 다운로드",
            feedback_json,
            file_name="document_review_feedback.json",
            mime="application/json",
            use_container_width=True,
        )

st.divider()
st.subheader("적용 법률 근거")
if document_type in source_loaders:
    st.markdown(
        f"- [{active_sources['metadata']['law_name']}]"
        f"({active_sources['metadata']['official_url']})"
    )
    for rule in active_sources["review_signals"]:
        st.markdown(
            f"- [{rule['article']} {rule['title']}]({rule['official_url']})"
        )
elif document_type != "auto":
    for rule in sources["rules"]:
        st.markdown(
            f"- [{rule['article']} {rule['title']}]({rule['official_url']})"
        )
else:
    contract_sources = load_contract_sources()
    housing_sources = load_special_sources("housing_legal_sources.json")
    employment_sources = load_special_sources("employment_legal_sources.json")
    st.markdown(
        f"- [{sources['metadata']['law_name']}]"
        f"({sources['rules'][0]['official_url']})"
    )
    st.markdown(
        f"- [{contract_sources['metadata']['law_name']}]"
        f"({contract_sources['metadata']['official_url']})"
    )
    st.markdown(
        f"- [{housing_sources['metadata']['law_name']}]"
        f"({housing_sources['metadata']['official_url']})"
    )
    st.markdown(
        f"- [{employment_sources['metadata']['law_name']}]"
        f"({employment_sources['metadata']['official_url']})"
    )
