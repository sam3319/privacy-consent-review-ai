from streamlit.testing.v1 import AppTest


def test_app_loads():
    app = AppTest.from_file("app/app.py").run(timeout=30)

    assert not app.exception
    assert app.title[0].value == "법률 문서 검토 보조"


def test_app_analyzes_manual_text():
    app = AppTest.from_file("app/app.py").run(timeout=30)
    app.text_area[0].set_value(
        """
        개인정보 수집·이용 목적: 회원 가입
        수집 개인정보 항목: 이름, 이메일
        보유 및 이용 기간: 탈퇴 시까지
        동의를 거부할 권리가 있으며 거부 시 가입이 제한됩니다.
        """
    )
    app.button[0].click().run(timeout=30)

    assert not app.exception
    assert app.subheader[0].value == "분석 결과"
    assert app.metric[0].value == "100%"


def test_app_analyzes_standard_terms_contract():
    app = AppTest.from_file("app/app.py").run(timeout=30)
    app.selectbox[0].set_value("약관형 계약서")
    app.text_area[0].set_value(
        """
        서비스 이용 약관
        계약 당사자: 갑 주식회사 예시, 을 고객
        계약 목적: 온라인 서비스 제공
        계약 기간: 가입일부터 해지일까지
        계약 대금: 월 10,000원
        계약 해지: 을은 계약을 해지할 수 없다.
        손해배상: 갑은 어떠한 책임도 지지 않는다.
        분쟁 해결: 갑의 본점 소재지 법원을 전속 관할로 한다.
        """
    )
    app.button[0].click().run(timeout=30)

    assert not app.exception
    assert app.metric[0].label == "계약 핵심정보 탐지율"
    assert any(
        "해제·해지 권리 제한" in expander.label
        for expander in app.expander
    )
