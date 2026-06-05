# 개발 인수인계 기록

최종 업데이트: 2026-06-05

## 프로젝트 목적

대한민국 공식 법령을 근거로 개인정보 동의서와 약관형 계약서를 분석하는
Streamlit 기반 검토 보조 도구입니다.

이 프로젝트는 위법, 무효 또는 법률상 책임을 자동 판정하지 않습니다.
결과 표현은 `확인`, `누락 가능성`, `구체성 검토`, `검토 필요`로 제한합니다.

## 현재 구현 상태

### 문서 입력

- TXT, PDF, DOCX, PNG, JPG, JPEG 지원
- 이미지와 스캔 PDF는 Tesseract `kor+eng` OCR 사용
- 스캔 PDF OCR은 최대 20페이지
- 파일 크기 최대 10MB
- 직접 텍스트 입력 지원

### 자동 문서 유형 감지

- 개인정보 수집·이용 동의
- 개인정보 제3자 제공 동의
- 수집·이용 및 제3자 제공 복합 문서
- 약관형 계약서

`자동 감지 (권장)`이 기본값입니다. 문서 유형을 신뢰할 수준으로 감지하지
못하면 사용자가 직접 선택하도록 오류를 표시합니다.

### 개인정보 동의서 분석

- 수집·이용 목적
- 수집 개인정보 항목
- 보유 및 이용 기간
- 동의 거부 권리와 불이익
- 제3자 제공받는 자
- 제공받는 자의 이용 목적
- 제공 개인정보 항목
- 제공받는 자의 보유 및 이용 기간
- 제3자 제공 동의 거부 권리와 불이익
- 민감정보, 고유식별정보, 주민등록번호 검토 신호
- 최소 수집 및 동의 사항 구분 검토 신호

단순 표제 탐지를 넘어 실제 값을 추출하고, 값이 포괄적이면 `구체성 검토`로
표시합니다.

### 약관형 계약서 분석

약관의 규제에 관한 법률상 약관일 가능성이 있는 문서를 대상으로 합니다.
모든 개별 계약에 약관법이 적용된다고 전제하지 않습니다.

구조화 항목:

- 계약 당사자
- 계약 목적·대상
- 계약 기간
- 대금·보수·지급 조건
- 해제·해지
- 손해배상·위약금
- 분쟁 해결·관할

검토 신호:

- 제6조: 일방적 변경 및 예상하기 어려운 조항
- 제7조: 사업자 책임 배제·제한
- 제8조: 위약금·지연손해금
- 제9조: 해제·해지 권리 제한과 불균형
- 제12조: 의사표시 간주
- 제14조: 재판관할·입증책임

### 결과 및 보안

- 심각도와 탐지 신뢰도 표시
- 원문 근거 문장과 국가법령정보센터 링크 표시
- 주민등록번호, 전화번호, 이메일 마스킹
- Markdown 및 JSON 보고서 다운로드
- 업로드 문서를 애플리케이션 코드에서 별도 저장하지 않음

## 법률 근거

개인정보 규칙:

- `data/legal_sources.json`
- 개인정보 보호법 기준 시행일: 2025-10-02
- 근거 확인일: 2026-06-05

계약서 규칙:

- `data/contract_legal_sources.json`
- 약관의 규제에 관한 법률 기준 시행일: 2024-08-07
- 근거 확인일: 2026-06-05

법률 규칙을 추가할 때는 국가법령정보센터, 개인정보보호위원회,
공정거래위원회 등 공식 자료만 직접 근거로 사용합니다.

상세 관리 원칙은 `docs/LEGAL_METHOD.md`를 따릅니다.

## 주요 코드

- `app/app.py`: Streamlit 화면과 분석 흐름
- `src/document_classifier.py`: 문서 유형 자동 감지
- `src/document_io.py`: TXT, PDF, DOCX, 이미지 및 OCR 처리
- `src/field_extraction.py`: 동의서와 계약서 핵심 값 추출
- `src/analyzer.py`: 개인정보 동의서 분석
- `src/contract_analyzer.py`: 약관형 계약서 분석
- `src/legal_rules.py`: 법률 데이터 로딩
- `src/reporting.py`: Markdown 및 JSON 보고서 생성
- `data/legal_sources.json`: 개인정보 보호법 규칙
- `data/contract_legal_sources.json`: 약관법 검토 신호

## 합성 테스트 문서

`samples` 폴더:

- `complete_collection_consent.txt`
- `missing_items_consent.txt`
- `sensitive_information_consent.txt`
- `complete_third_party_consent.txt`
- `resident_number_consent.txt`
- `combined_marketing_consent.txt`
- `balanced_service_contract.txt`
- `risky_standard_terms_contract.txt`

실제 개인정보는 포함하지 않습니다.

`risky_standard_terms_contract.txt` 기대 결과:

- 자동 유형: 약관형 계약서
- 유형 감지 신뢰도: 95%
- 계약 핵심정보 탐지율: 100%
- 검토 신호: 제6조, 제7조, 제8조, 제9조, 제14조

## 검증 상태

마지막 전체 테스트 결과:

```text
29 passed
```

실행 명령:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

구문 검사:

```powershell
.\.venv\Scripts\python.exe -m compileall -q src app tests
```

## 로컬 실행

```powershell
cd C:\Users\USER\Desktop\privacy-consent-review-ai
.\.venv\Scripts\python.exe -m streamlit run app/app.py
```

로컬 OCR 실행에는 Tesseract 한국어 언어팩과 Poppler가 필요합니다.

## GitHub 및 배포

원격 저장소:

```text
https://github.com/sam3319/privacy-consent-review-ai.git
```

브랜치:

```text
main
```

Streamlit Community Cloud 진입 파일:

```text
app/app.py
```

변경 반영:

```powershell
git add .
git commit -m "변경 내용"
git push
```

`requirements.txt`는 Python 패키지, `packages.txt`는 Streamlit Cloud의
Tesseract 한국어 언어팩과 Poppler 설치에 사용됩니다.

## 다음 작업 우선순위

1. 계약서를 제1조, 제2조 등 조항 단위로 분리
2. 사용자 관점 선택: 갑, 을, 소비자, 사업자
3. 관점별 권리, 의무, 금액, 기간, 해지 방법 요약
4. 날짜 모순과 금액 합계·분할 지급 불일치 검사
5. 자동 갱신과 해지 통보기간 구조화
6. 계약 유형별 별도 분석
   - 근로계약서
   - 주택 임대차계약서
   - 용역·프리랜서 계약서
   - 전자상거래 이용약관
7. 계약 유형을 추가하기 전에 해당 특별법과 공식 표준계약서 확인
8. OCR 페이지별 품질과 사용자의 OCR 문구 수정 기능
9. 전문가 검수 데이터셋 구축 후 조항 분류 모델 평가

## 다음 작업 시 주의사항

- 추측으로 법률 규칙을 추가하지 않습니다.
- 모든 규칙에 조문, 시행일, 확인일, 공식 URL을 기록합니다.
- 특별법 적용 계약을 일반 약관법만으로 결론 내리지 않습니다.
- LLM을 추가하더라도 원문 근거 문장과 공식 법률 검색 결과를 함께 제시합니다.
- 자동 생성된 법률 설명을 법적 근거 데이터로 저장하지 않습니다.
- 실제 개인정보가 테스트나 Git 저장소에 포함되지 않도록 합니다.

