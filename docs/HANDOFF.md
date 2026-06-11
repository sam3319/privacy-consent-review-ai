# 개발 인수인계 기록

최종 업데이트: 2026-06-09

## 프로젝트 목적

대한민국 공식 법령을 근거로 개인정보 동의서와 약관형 계약서를 분석하는
Streamlit 기반 검토 보조 도구입니다.

이 프로젝트는 위법, 무효 또는 법률상 책임을 자동 판정하지 않습니다.
결과 표현은 `확인`, `누락 가능성`, `구체성 검토`, `검토 필요`로 제한합니다.

## 현재 구현 상태

### 머신러닝 모델

- 문서 유형 분류 모델: 문자 n-gram TF-IDF + Logistic Regression
- 조항 위험 유형 분류 모델: 문자 n-gram TF-IDF + Logistic Regression
- 계약 필드 분류 모델: 문자 n-gram TF-IDF + Logistic Regression
- 필드 값 span 모델: 공백 토큰 특징 + Logistic Regression BIO 태거
- 선택형 Transformer NER: `LEGAL_NER_MODEL_PATH`가 설정된 경우 우선 사용
- 선택형 문장 임베딩 검색: `LEGAL_EMBEDDING_MODEL_PATH`가 설정된 경우 우선 사용
- 학습 데이터: 합성 템플릿 문서 320건, 합성 조항 420건, 합성 필드 문장 1,120건
- 모델 산출물: `models/*.joblib`
- 평가 지표: `models/*_metrics.json`
- 학습 재현: `ai_model_training.ipynb`, `scripts/train_*.py`
- 적용 방식: 규칙 추출을 우선하고 누락 필드만 ML 후보로 보완하며, 공식 법령
  규칙 엔진의 검토 결과와 함께 표시하는 하이브리드 분석
- 필드 모델 확률: 3겹 교차검증 sigmoid 보정
- 낮은 신뢰도 필드: `사용자 확인 필요`로 표시하고 탐지율 확정값에서 제외
- 모델 장애: 문서 유형은 규칙 엔진으로 폴백하고 조항·필드 ML은 생략
- 모델 버전: `models/model_manifest.json`에 학습시각·크기·SHA-256 기록
- 모델 로드 보안: 파일명·크기·SHA-256 일치 후에만 `joblib.load` 실행
- 변조·매니페스트 누락: 모델 역직렬화를 차단하고 규칙 엔진으로 폴백

합성 템플릿 데이터의 내부 평가 점수가 실제 문서 성능을 의미하지 않으므로
전문가 라벨 실제 문서에 대한 외부 검증이 필요합니다.

### 문서 입력

- TXT, PDF, DOCX, PNG, JPG, JPEG 지원
- 이미지와 스캔 PDF는 Tesseract `kor+eng` OCR 사용
- 스캔 PDF OCR은 최대 20페이지
- 파일 크기 최대 10MB
- 직접 텍스트 입력 지원
- 업로드 파일 페이지별 텍스트·OCR 품질 점수 표시
- 이미지 원본과 OCR 텍스트 나란히 표시
- 페이지별 OCR 문구 수정 후 전체 문서에 재반영

### 자동 문서 유형 감지

- 개인정보 수집·이용 동의
- 개인정보 제3자 제공 동의
- 수집·이용 및 제3자 제공 복합 문서
- 약관형 계약서
- 주택 임대차(전세·월세) 계약서
- 근로계약서

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

### 공통 계약 구조 분석

- 제1조, 제2조 등 조항 단위 분리
- 갑, 을, 소비자, 사업자, 임대인, 임차인, 사용자, 근로자 관점 선택
- 관점별 권리, 의무, 금액, 기간, 해지·종료 문구 요약
- 시작일·종료일 역전 검사
- 총액과 계약금·중도금·잔금 합계 불일치 검사
- 자동 갱신, 묵시적 갱신 및 해지 통보기간 추출

### 주택 임대차 분석

- 임대인·임차인, 목적물, 보증금, 월세, 기간, 관리비, 수선, 보증금 반환 추출
- 등기사항증명서의 소유자·소재지와 계약서 임대인·목적물 교차확인
- 건축물대장의 주소·주용도와 계약 목적물 교차확인
- 등기 문서의 채권최고액 추출 및 사용자 입력 선순위 금액과 연계
- 주택가액 대비 선순위 채권·선순위 보증금·본인 보증금 총 부담 비율 계산
- 선순위 금액 차감 후 보증금 커버리지와 참고 위험 수준 표시
- 2년 미만 임대차 기간 검토
- 보증금 반환 제한 문구 검토
- 묵시적 갱신 후 임차인 해지권 제한 검토
- 계약갱신요구권 포기·제한 검토
- 5% 초과 차임·보증금 증액률 검토
- 선순위 임대차 및 임대인 체납 정보 확인 제한 신호

법률 기준은 주택임대차보호법 2026-01-02 시행본이며 2026-06-09 확인했습니다.

외부 서류 교차확인은 문자열 기반이며 서류 진위, 최신 상태, 권리 순위와
법적 효력을 판정하지 않습니다. 보증금 계산은 경매 낙찰가율, 우선변제권,
소액임차인, 세금과 집행비용을 반영하지 않는 참고 지표입니다.

### 근로계약 분석

- 사용자·근로자, 근무 장소, 업무, 기간, 근로·휴게시간, 휴일, 임금, 연차 추출
- 근로기준법 제17조 서면 명시 항목 누락 가능성
- 근로계약 불이행 위약금·손해배상 예정 검토
- 임금 지급 방식 검토
- 1일 8시간·주 40시간 초과 가능성 검토
- 휴게시간 자유 이용 제한 검토
- 2026년 시간급 10,320원 미달 가능성 검사

법률 기준은 근로기준법 2025-10-23 시행본과 고용노동부고시
제2025-47호이며 2026-06-09 확인했습니다.

### 결과 및 보안

- 심각도와 탐지 신뢰도 표시
- 원문 근거 문장과 국가법령정보센터 링크 표시
- 주민등록번호, 전화번호, 이메일 마스킹
- Markdown 및 JSON 보고서 다운로드
- 업로드 문서를 애플리케이션 코드에서 별도 저장하지 않음
- 사용자가 추출값 수정 JSON을 적용하고 수정 전·후 이력을 보고서에 기록
- 개인정보를 마스킹한 수정 피드백 JSON 다운로드
- 실제 전문가 평가 데이터는 `data/evaluation/private/`에 두고 Git에서 제외

### 근로시간·수당 참고 계산

- 시간급, 주간 통상·연장·야간·휴일근로 시간 입력
- 5인 이상 사업장 선택 시 연장·야간·휴일 50% 가산 참고 계산
- 휴일근로 8시간 초과 구간은 100% 가산 참고 계산
- 야간시간을 별도 입력해 연장·휴일 가산과 중복 계산
- 월 통상임금과 환산 기준시간을 이용한 시간급 계산
- 사용자가 확인한 주휴 유급시간 입력
- 주 12시간 연장근로 및 주 52시간 초과 입력 경고
- 주휴수당, 통상임금 범위와 근로시간제 예외는 계산에서 제외

### 공식 법률 근거 검색

- 로컬 공식 법률 규칙의 제목·메시지·패턴을 문자 n-gram TF-IDF로 검색
- 문서와 가까운 상위 공식 조문 후보와 URL 표시
- 유사도는 법적 적용 여부나 결론이 아닌 탐색 보조 점수
- 문서 작성일과 법률 시행일·근거 확인일 비교 경고

### 외부 평가 체계

- `data/evaluation/README.md`: 전문가 검수 JSONL 형식과 익명화 원칙
- `scripts/validate_anonymized_dataset.py`: 식별정보 후보 검사
- `scripts/evaluate_anonymized_dataset.py`: 문서 유형 분류표와 필드 exact match 평가
- 실제 문서와 전문가 라벨은 제공되지 않았으므로 외부 성능 수치는 아직 없음

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
- `src/ml_classifier.py`: 문서 유형·위험 조항·계약 필드 ML 예측
- `scripts/train_field_extractor.py`: 계약 필드 분류 모델 학습과 평가
- `scripts/train_field_span_extractor.py`: 필드 값 BIO span 모델 학습과 평가
- `data/field_extraction_training.csv`: 개인정보 없는 합성 필드 학습 문장
- `src/analyzer.py`: 개인정보 동의서 분석
- `src/contract_analyzer.py`: 약관형 계약서 분석
- `src/contract_structure.py`: 조항 분리, 관점별 요약 및 내부 일관성 검사
- `src/special_contract_analyzer.py`: 주택 임대차 및 근로계약 분석
- `src/legal_rules.py`: 법률 데이터 로딩
- `src/reporting.py`: Markdown 및 JSON 보고서 생성
- `src/employment_calculator.py`: 근로시간·예상 수당 참고 계산
- `src/legal_retrieval.py`: 공식 법률 규칙 의미 검색
- `src/review_feedback.py`: 사용자 수정 적용과 익명화 피드백 생성
- `src/optional_models.py`: 선택형 Transformer NER·문장 임베딩 어댑터
- `scripts/deployment_smoke_test.py`: 모델·샘플 분석·배포 파일 사전 점검
- `src/model_security.py`: 모델 매니페스트·SHA-256 검증과 안전 로딩
- `data/legal_sources.json`: 개인정보 보호법 규칙
- `data/contract_legal_sources.json`: 약관법 검토 신호
- `data/housing_legal_sources.json`: 주택임대차보호법 검토 신호
- `data/employment_legal_sources.json`: 근로기준법 및 최저임금 검토 신호

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
- `risky_housing_lease.txt`
- `risky_employment_contract.txt`

실제 개인정보는 포함하지 않습니다.

`risky_standard_terms_contract.txt` 기대 결과:

- 자동 유형: 약관형 계약서
- 유형 감지 신뢰도: 95%
- 계약 핵심정보 탐지율: 100%
- 검토 신호: 제6조, 제7조, 제8조, 제9조, 제14조

## 검증 상태

마지막 전체 테스트 결과:

```text
77 passed
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

## Colab 최신 작업본 실행

데스크톱에 생성된 다음 두 파일을 사용합니다.

- `privacy_consent_review_colab.ipynb`
- `privacy-consent-review-ai-colab.zip`

노트북 첫 셀에서 ZIP을 업로드하면 GitHub에 아직 푸시되지 않은 현재 작업본을
`/content/privacy-consent-review-ai`에 풀고 Python 패키지와 OCR 시스템
패키지를 설치합니다. TXT, PDF, DOCX, PNG, JPG 업로드 분석을 지원합니다.

ZIP 압축본을 별도 폴더에 풀어 배포 점검과 전체 테스트를 실행한 결과:

```text
77 passed
```

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

1. 전문가 검수·익명화 실제 문서 데이터 수집 및 외부 성능 측정
2. 전문가 라벨 데이터로 한국어 Transformer NER를 학습해 선택형 어댑터에 연결
3. 기간제·단시간근로자 추가 명시사항과 업종·사업장 규모별 예외 처리
4. 용역·프리랜서 계약서와 근로자성 검토 보조
5. 전자상거래 이용약관 별도 분석

## 다음 작업 시 주의사항

- 추측으로 법률 규칙을 추가하지 않습니다.
- 모든 규칙에 조문, 시행일, 확인일, 공식 URL을 기록합니다.
- 특별법 적용 계약을 일반 약관법만으로 결론 내리지 않습니다.
- LLM을 추가하더라도 원문 근거 문장과 공식 법률 검색 결과를 함께 제시합니다.
- 자동 생성된 법률 설명을 법적 근거 데이터로 저장하지 않습니다.
- 실제 개인정보가 테스트나 Git 저장소에 포함되지 않도록 합니다.
