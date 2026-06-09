from streamlit.testing.v1 import AppTest


def test_app_loads():
    app = AppTest.from_file("app/app.py").run(timeout=30)

    assert not app.exception
    assert app.title[0].value == "법률 문서 검토 보조"


def test_app_analyzes_manual_text():
    app = AppTest.from_file("app/app.py").run(timeout=30)
    app.selectbox[0].set_value("개인정보 수집·이용 동의")
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


def test_app_auto_detects_contract():
    app = AppTest.from_file("app/app.py").run(timeout=30)
    app.text_area[0].set_value(
        """
        서비스 이용 약관
        계약 당사자: 갑 주식회사 예시, 을 고객
        계약 목적: 온라인 정보 제공
        계약 기간: 가입일부터 해지일까지
        계약 대금: 월 50,000원
        계약 해지: 을은 계약을 해지할 수 없다.
        손해배상: 갑은 어떠한 책임도 지지 않는다.
        재판 관할: 갑의 본점 소재지 법원을 전속 관할로 한다.
        """
    )
    app.button[0].click().run(timeout=30)

    assert not app.exception
    assert app.success[0].value.startswith("자동 감지 문서 유형: 약관형 계약서")
    assert app.metric[0].label == "계약 핵심정보 탐지율"
    assert any("TF-IDF" in caption.value for caption in app.caption)


def test_app_analyzes_housing_lease():
    app = AppTest.from_file("app/app.py").run(timeout=30)
    app.selectbox[0].set_value("주택 임대차(전세·월세) 계약서")
    app.text_area[0].set_value(
        """
        주택 임대차 계약서
        임대인·임차인: 임대인 홍길동, 임차인 김예시
        임대 목적물: 서울특별시 예시구 101호
        보증금: 100,000,000원
        월 차임·월세: 500,000원
        임대차 기간: 2026년 7월 1일부터 2027년 6월 30일까지
        특약사항: 임차인은 계약갱신요구권을 포기한다.
        """
    )
    app.button[0].click().run(timeout=30)

    assert not app.exception
    assert any("계약갱신요구권" in expander.label for expander in app.expander)


def test_app_analyzes_employment_contract():
    app = AppTest.from_file("app/app.py").run(timeout=30)
    app.selectbox[0].set_value("근로계약서")
    app.text_area[0].set_value(
        """
        근로계약서
        사용자·근로자: 사용자 예시회사, 근로자 김예시
        근무 장소: 서울
        업무 내용: 고객 지원
        소정근로시간: 1일 9시간, 주 45시간
        임금 구성·금액: 시급 10,000원
        임금 지급일·방법: 매월 25일 계좌 지급
        """
    )
    app.button[0].click().run(timeout=30)

    assert not app.exception
    labels = [expander.label for expander in app.expander]
    assert any("법정근로시간" in label for label in labels)
    assert any("최저임금" in label for label in labels)
