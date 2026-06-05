import sys
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analyzer import analyze_document
from src.contract_analyzer import analyze_contract
from src.document_classifier import detect_document_type
from src.document_io import extract_text
from src.legal_rules import load_contract_sources, load_legal_sources
from src.reporting import build_json_report, build_markdown_report


DOCUMENT_TYPE_LABELS = {
    "자동 감지 (권장)": "auto",
    "개인정보 수집·이용 동의": "collection",
    "개인정보 제3자 제공 동의": "third_party",
    "수집·이용 및 제3자 제공 복합 문서": "combined",
    "약관형 계약서": "standard_terms_contract",
}


st.set_page_config(
    page_title="법률 문서 검토 보조",
    page_icon="📄",
    layout="wide",
)

sources = load_legal_sources()

st.title("법률 문서 검토 보조")
st.warning(
    "이 서비스는 위법 여부를 판정하거나 법률 자문을 제공하지 않습니다. "
    "공식 법령에 연결된 문구 탐지와 추가 검토 신호만 제공합니다."
)
document_label = st.selectbox("문서 유형", DOCUMENT_TYPE_LABELS)
document_type = DOCUMENT_TYPE_LABELS[document_label]
active_sources = (
    load_contract_sources()
    if document_type == "standard_terms_contract"
    else sources
)
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
uploaded_file = st.file_uploader(
    "문서 업로드",
    type=["txt", "pdf", "docx", "png", "jpg", "jpeg"],
    help="파일은 분석 과정에서만 메모리에 읽으며 애플리케이션 코드가 별도로 저장하지 않습니다.",
)
manual_text = st.text_area(
    "또는 문서 내용을 붙여넣으세요",
    height=300,
    placeholder="개인정보 동의서 또는 약관형 계약서 내용을 입력하세요.",
)

if st.button("문서 분석", type="primary", use_container_width=True):
    try:
        document_text = manual_text
        if uploaded_file is not None:
            if uploaded_file.size > 10 * 1024 * 1024:
                raise ValueError("업로드 파일은 10MB 이하여야 합니다.")
            document_text = extract_text(uploaded_file.name, uploaded_file.getvalue())
        analyzed_type = document_type
        detection = None
        if analyzed_type == "auto":
            detection = detect_document_type(document_text)
            analyzed_type = detection["document_type"]
        if analyzed_type == "standard_terms_contract":
            result = analyze_contract(document_text)
        else:
            result = analyze_document(document_text, analyzed_type)
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
        metric_label = (
            "계약 핵심정보 탐지율"
            if analyzed_type == "standard_terms_contract"
            else "법정 고지사항 구체값 탐지율"
        )
        st.metric(metric_label, f"{result['completeness']}%")
        st.caption(
            "탐지율은 문구와 값의 자동 추출 결과이며 적법성이나 내용의 충분성을 의미하지 않습니다."
        )

        if result.get("scope_warning"):
            st.warning(result["scope_warning"])

        st.markdown("### 구조화 추출")
        for field in result.get("extracted_fields", []):
            value = field["value"] or "찾지 못함"
            st.write(
                f"**{field['label']}**: {value} "
                f"({field['status']}, 신뢰도 {field['confidence']}%)"
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

        report_col1, report_col2 = st.columns(2)
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

st.divider()
st.subheader("적용 법률 근거")
if document_type == "standard_terms_contract":
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
    st.markdown(
        f"- [{sources['metadata']['law_name']}]"
        f"({sources['rules'][0]['official_url']})"
    )
    st.markdown(
        f"- [{contract_sources['metadata']['law_name']}]"
        f"({contract_sources['metadata']['official_url']})"
    )
