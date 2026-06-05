import json

from src.analyzer import analyze_document
from src.reporting import build_json_report, build_markdown_report


def test_reports_include_sources_and_exclude_preview_text():
    result = analyze_document(
        """
        개인정보 수집·이용 목적: 가입
        수집 개인정보 항목: 이메일 user@example.com
        보유 및 이용 기간: 탈퇴 시까지
        동의를 거부할 권리가 있으며 거부 시 가입이 제한됩니다.
        """,
        "collection",
    )

    markdown = build_markdown_report(result)
    json_report = json.loads(build_json_report(result))

    assert "개인정보 보호법" in markdown
    assert "user@example.com" not in markdown
    assert "redacted_preview" not in json_report
    assert json_report["findings"][0]["official_url"].startswith(
        "https://www.law.go.kr/"
    )
