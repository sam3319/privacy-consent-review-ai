from streamlit.testing.v1 import AppTest


def test_app_loads():
    app = AppTest.from_file("app/app.py").run(timeout=30)

    assert not app.exception
    assert app.title[0].value == "개인정보 동의서 검토 보조"


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

