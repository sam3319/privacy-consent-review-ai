import sys
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analyzer import analyze_document
from src.document_io import extract_text
from src.legal_rules import load_legal_sources


DOCUMENT_TYPE_LABELS = {
    "개인정보 수집·이용 동의": "collection",
    "개인정보 제3자 제공 동의": "third_party",
    "수집·이용 및 제3자 제공 복합 문서": "combined",
}


st.set_page_config(
    page_title="개인정보 동의서 검토 보조",
    page_icon="📄",
    layout="wide",
)

sources = load_legal_sources()
metadata = sources["metadata"]

st.title("개인정보 동의서 검토 보조")
st.warning(
    "이 서비스는 위법 여부를 판정하거나 법률 자문을 제공하지 않습니다. "
    "법정 고지사항으로 보이는 문구의 존재 여부와 추가 검토 신호를 제공합니다."
)
st.caption(
    f"법률 기준: {metadata['law_name']} | 시행일 {metadata['effective_date']} | "
    f"근거 확인일 {metadata['verified_date']} | {metadata['official_source']}"
)

document_label = st.selectbox("문서 유형", DOCUMENT_TYPE_LABELS)
uploaded_file = st.file_uploader(
    "문서 업로드",
    type=["txt", "pdf", "docx"],
    help="파일은 분석 과정에서만 메모리에 읽으며 애플리케이션 코드가 별도로 저장하지 않습니다.",
)
manual_text = st.text_area(
    "또는 문서 내용을 붙여넣으세요",
    height=300,
    placeholder="개인정보 수집·이용 동의서 내용을 입력하세요.",
)

if st.button("문서 분석", type="primary", use_container_width=True):
    try:
        document_text = manual_text
        if uploaded_file is not None:
            document_text = extract_text(uploaded_file.name, uploaded_file.getvalue())
        result = analyze_document(
            document_text,
            DOCUMENT_TYPE_LABELS[document_label],
        )
    except ValueError as error:
        st.error(str(error))
    except Exception:
        st.error("문서를 읽는 중 오류가 발생했습니다. 파일 형식과 문서 상태를 확인하세요.")
    else:
        st.subheader("분석 결과")
        st.metric("법정 고지사항 문구 탐지율", f"{result['completeness']}%")
        st.caption("탐지율은 문구 존재 여부만 나타내며 적법성이나 내용의 충분성을 의미하지 않습니다.")

        for finding in result["findings"]:
            if finding["status"] in {"누락 가능성", "검토 필요"}:
                icon = "⚠️"
            else:
                icon = "✅"
            with st.expander(
                f"{icon} [{finding['status']}] {finding['title']}",
                expanded=finding["status"] in {"누락 가능성", "검토 필요"},
            ):
                st.write(finding["message"])
                st.write(f"**법적 근거:** {finding['article']}")
                if finding["evidence"]:
                    st.write(f"**탐지 문구:** {finding['evidence']}")
                st.link_button("국가법령정보센터에서 근거 확인", finding["official_url"])

        with st.expander("개인정보 마스킹 미리보기"):
            st.text(result["redacted_preview"])
        st.info(result["disclaimer"])

st.divider()
st.subheader("적용 법률 근거")
for rule in sources["rules"]:
    st.markdown(
        f"- [{rule['article']} {rule['title']}]({rule['official_url']})"
    )

