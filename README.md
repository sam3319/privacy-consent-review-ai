# 법률 문서 검토 보조

대한민국 개인정보 보호법의 공식 조문을 기준으로 개인정보 수집·이용
동의서와 제3자 제공 동의서를 점검하고, 약관의 규제에 관한 법률을 기준으로
약관형 계약서의 검토 신호를 찾는 프로젝트입니다.
주택 임대차(전세·월세) 계약서와 근로계약서의 핵심 항목 및 특별법상
검토 신호도 함께 점검합니다.

이 프로젝트는 위법 여부를 판정하거나 법률 자문을 제공하지 않습니다.
자동 분석 결과는 누락 가능성과 추가 검토 지점을 찾기 위한 보조 정보입니다.

현재 개발 상태와 다음 작업 계획은 `docs/HANDOFF.md`에 기록되어 있습니다.

Google Colab 제출 및 기능 재현용 노트북은
`privacy_consent_review_demo.ipynb`입니다.
AI 모델 학습·평가·저장 과정을 재현하는 노트북은
`ai_model_training.ipynb`입니다.

아직 GitHub에 푸시하지 않은 최신 작업본을 Colab에서 실행하려면 다음 두
파일을 사용합니다.

- `privacy_consent_review_colab.ipynb`
- `privacy-consent-review-ai-colab.zip`

Colab에서 노트북을 연 뒤 첫 번째 실행 셀의 업로드 창에 ZIP을 선택하고
`런타임 > 모두 실행`을 누릅니다. ZIP을 선택하지 않으면 GitHub 저장소를
복제하므로 최신 로컬 변경 사항이 포함되지 않을 수 있습니다.

ZIP은 저장소 루트에서 다음 명령으로 데스크톱에 재생성합니다. Git 추적 파일과
`.gitignore`에 걸리지 않은 작업 파일만 포함하며 비공개 평가 데이터, 가상환경,
Git 메타데이터는 제외합니다. 파일 순서와 ZIP 타임스탬프가 고정되어 같은
작업본에서는 같은 SHA-256이 생성됩니다.

```powershell
.\.venv\Scripts\python.exe scripts\package_colab_release.py
```

## AI 모델

프로젝트는 규칙 엔진과 다섯 머신러닝 모델을 결합합니다.

- 문서 유형 분류: 개인정보 동의서, 약관형 계약서, 주택 임대차, 근로계약
- 계약 조항 위험 유형 분류: 책임 면제, 해지 제한, 위약금, 갱신권 제한,
  근로계약 위약, 장시간 근로 등
- 계약 필드 분류: 당사자, 목적물, 보증금, 임금, 기간 등 28개 항목의
  자연 문장 후보를 분류해 정규식 추출의 누락을 보완
- 필드 값 span 추출: BIO 토큰 분류로 선택된 문장 안의 값 범위를 추출

문서·조항·필드 분류 모델은 문자 n-gram `TF-IDF`와 Logistic Regression으로
구현했습니다. 필드 값 span은 한국어 ELECTRA 기반 Transformer BIO NER를
우선 사용하고, 로딩에 실패하면 토큰 특징 기반 Logistic Regression BIO
태거로 복귀합니다.
학습 데이터는 실제 개인정보를 포함하지 않는 합성 템플릿 데이터이며,
모델 파일과 평가 지표는 `models` 폴더에 저장합니다. 내부 평가 점수는 실제
법률 문서에 대한 일반화 성능을 의미하지 않으며, 공식 법률 근거는 규칙 엔진
결과를 우선합니다.

필드 모델은 3겹 교차검증 기반 sigmoid 확률 보정을 사용합니다. 신뢰도가
낮은 예측은 `사용자 확인 필요`로 표시하며, 모델 파일이 없거나 손상되면
규칙 엔진만으로 분석을 계속합니다.

기본 Transformer NER 모델은 `models/transformer_ner`에 포함되며 별도
환경변수 없이 자동으로 사용합니다. 다른 호환 모델을 사용하려면 로컬 모델
경로를 환경변수로 지정할 수 있습니다. `LEGAL_NER_MINIMUM_SCORE`의 기본값은
`0.5`입니다.

```powershell
$env:LEGAL_NER_MODEL_PATH="로컬 NER 모델 경로"
$env:LEGAL_NER_MINIMUM_SCORE="0.5"
```

문장 임베딩 모델과 Transformer 재학습 도구는 선택 패키지를 추가 설치합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-optional-ml.txt
$env:LEGAL_EMBEDDING_MODEL_PATH="로컬 문장 임베딩 모델 경로"
```

환경변수가 없거나 모델 로딩에 실패하면 BIO span 모델과 TF-IDF 법률 검색으로
자동 폴백합니다.

필드 분류 모델 재학습:

```powershell
.\.venv\Scripts\python.exe scripts\generate_field_training_data.py
.\.venv\Scripts\python.exe scripts\train_field_extractor.py
.\.venv\Scripts\python.exe scripts\train_field_span_extractor.py
.\.venv\Scripts\python.exe scripts\train_transformer_ner.py --epochs 5
.\.venv\Scripts\python.exe scripts\build_model_manifest.py
```

Transformer NER는 `monologg/koelectra-small-v3-discriminator`를 기반으로
합성 필드 문장 1,008건에서 `B-VALUE`, `I-VALUE`, `O`를 학습합니다.
현재 합성 holdout macro F1은 `0.9988`이지만 실제 계약서나 OCR 문서에 대한
일반화 성능을 의미하지 않으므로 익명화 전문가 데이터 평가가 필요합니다.

모델은 로드 전에 `models/model_manifest.json`의 파일명, 크기와 SHA-256을
검증합니다. Transformer 디렉터리도 모든 구성 파일을 검증하며, 재학습 후
매니페스트를 갱신하지 않거나 파일이 변조되면 모델을 로드하지 않고 기존
BIO 모델 또는 규칙 엔진으로 폴백합니다.

## 현재 범위

- 개인정보 수집·이용 동의: 개인정보 보호법 제15조 제2항
- 최소 수집 원칙: 제16조
- 개인정보 제3자 제공 동의: 제17조 제2항
- 동의 사항의 구분: 제22조
- 민감정보 별도 동의 또는 법령 근거 검토: 제23조
- 고유식별정보 별도 동의 또는 법령 근거 검토: 제24조
- 주민등록번호 처리의 구체적 법령 근거 검토: 제24조의2
- 약관형 계약서 검토: 약관의 규제에 관한 법률 제6조, 제7조, 제8조,
  제9조, 제12조 및 제14조
- 주택 임대차 검토: 주택임대차보호법 제3조의7, 제4조, 제6조의2,
  제6조의3 및 제7조
- 근로계약 검토: 근로기준법 제17조, 제20조, 제43조, 제50조 및 제54조
- 2026년 적용 최저임금: 시간급 10,320원

법률 기준은 `data/legal_sources.json`에 조문, 시행일, 근거 URL과 함께
관리합니다. 현재 기준 법률 시행일은 2025년 10월 2일이며 근거 확인일은
2026년 6월 5일입니다.

약관형 계약서 규칙은 `data/contract_legal_sources.json`에서 별도 관리합니다.
기준 약관법 시행일은 2024년 8월 7일입니다. 계약서 분석은 사업자가 여러
상대방과 계약하기 위해 미리 마련한 약관형 문서를 대상으로 하며, 모든 개별
계약에 약관법이 적용된다고 전제하지 않습니다.

## 동작 방식

1. TXT, PDF, DOCX, PNG, JPG 또는 직접 입력한 문서를 읽습니다.
   스캔 PDF와 이미지는 한국어·영어 OCR을 사용하며 최대 20페이지를 처리합니다.
2. 기본 설정에서 개인정보 동의서와 약관형 계약서를 자동 구분합니다.
3. 목적, 항목, 기간, 당사자, 대금, 해지 등 핵심 값을 구조화합니다.
4. 값이 비어 있거나 지나치게 포괄적인 경우 구체성 검토로 표시합니다.
5. 민감정보, 고유식별정보 및 약관법 관련 검토 신호를 표시합니다.
6. 각 결과에 심각도, 탐지 신뢰도, 조문과 국가법령정보센터 링크를 제공합니다.
7. 주민등록번호, 전화번호, 이메일을 결과에서 마스킹합니다.
8. Markdown 및 JSON 보고서를 다운로드할 수 있습니다.
9. 계약서를 조항 단위로 분리하고 선택한 당사자 관점의 권리·의무·금액·기간을 요약합니다.
10. 날짜 역전, 총액과 분할 지급액 불일치, 자동 갱신 및 해지 통보기간을 점검합니다.
11. 주택 임대차에서는 등기사항증명서·건축물대장을 선택적으로 입력해 임대인,
    소재지와 건축물 용도를 문자열 기준으로 교차확인합니다.
12. 주택가액, 선순위 채권·보증금과 임차보증금을 입력하면 총 부담 비율과
    보증금 커버리지를 참고 지표로 계산합니다.
13. 근로시간과 시간급을 입력하면 연장·야간·휴일근로 예상 수당을 계산합니다.
14. 문서 내용과 의미가 가까운 공식 법률 규칙 후보를 검색해 원문 링크를 제공합니다.
15. 추출값 수정 JSON을 적용하고 익명화된 수정 피드백을 다운로드할 수 있습니다.
16. 문서 유형별 주요 추출값을 입력창에서 직접 수정할 수 있습니다.
17. 업로드 문서를 페이지별로 추출해 품질 점수와 수정 가능한 OCR 텍스트를 표시합니다.
18. 문서 작성일과 현재 규칙의 법률 시행일·근거 확인일을 비교합니다.
19. 성명·상세 주소·계좌번호 후보를 추가 마스킹하고 다운로드 전 경고합니다.

문구가 탐지되었다고 해서 해당 동의가 적법하거나 충분하다는 의미는 아닙니다.
반대로 문구를 찾지 못했다는 결과도 실제 법 위반을 확정하지 않습니다.

## 로컬 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app/app.py
```

로컬 OCR에는 Tesseract 한국어 언어팩과 Poppler가 필요합니다. Streamlit
Community Cloud에서는 루트의 `packages.txt`를 통해 설치됩니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

테스트는 필수 고지사항 탐지, 누락 가능성, 민감정보 검토 신호, 개인정보
마스킹, 문서 읽기, 공식 법령 URL 제약, 임대차 외부 서류 교차확인,
보증금 참고 계산 및 Streamlit 입력 흐름을 검증합니다.

근로수당 계산은 휴일근로 8시간 이내 50%, 8시간 초과 100% 가산과
연장·야간 가산 중복 입력을 지원합니다. 월 통상임금을 기준시간으로 나눈
시간급 환산과 사용자가 확인한 주휴 유급시간도 입력할 수 있습니다.

## 익명화 외부 평가

실제 문서는 저장소에 커밋하지 않습니다. 전문가 검수가 끝난 익명화 JSONL
데이터를 `data/evaluation/private/`에 두고 다음 명령으로 검사·평가합니다.

```powershell
.\.venv\Scripts\python.exe scripts\validate_anonymized_dataset.py data\evaluation\private\cases.jsonl
.\.venv\Scripts\python.exe scripts\evaluate_anonymized_dataset.py data\evaluation\private\cases.jsonl --output evaluation.json
```

형식과 익명화 원칙은 `data/evaluation/README.md`에 기록되어 있습니다.
평가 JSON에는 전체 문서 유형 정확도와 분류표, 오분류 사례, 전체 및 필드별
exact-match 비율, 누락·불일치 필드 사례가 포함됩니다.
모델 버전·학습시각·SHA-256은 `models/model_manifest.json`으로 관리하며,
GitHub Actions가 구문 검사, 노트북 JSON, 매니페스트와 전체 테스트를 검증합니다.

배포 사전 점검:

```powershell
.\.venv\Scripts\python.exe scripts\deployment_smoke_test.py
```

`samples` 폴더에는 실제 개인정보를 포함하지 않는 합성 테스트 문서가 있습니다.

- `complete_collection_consent.txt`: 수집·이용 필수 고지사항 포함
- `missing_items_consent.txt`: 보유 기간과 거부 권리 문구 누락
- `sensitive_information_consent.txt`: 건강·질병 정보 포함
- `complete_third_party_consent.txt`: 제3자 제공 필수 고지사항 포함
- `resident_number_consent.txt`: 주민등록번호 처리 법령 근거 검토 사례
- `combined_marketing_consent.txt`: 필수·선택·제3자 제공 복합 사례
- `balanced_service_contract.txt`: 핵심 조항을 갖춘 합성 서비스 계약서
- `risky_standard_terms_contract.txt`: 책임 면제, 해지 제한, 전속 관할 등의 검토 신호 사례
- `risky_housing_lease.txt`: 갱신요구권 포기와 월세 증액 검토 사례
- `risky_employment_contract.txt`: 장시간, 최저임금 및 위약금 검토 사례

## 법률 업데이트 원칙

- 법률 규칙은 국가법령정보센터 또는 개인정보보호위원회 공식 자료로만 추가합니다.
- 조문 번호, 시행일, 확인일, 공식 URL을 함께 기록합니다.
- 판례나 행정해석을 규칙으로 추가할 때는 사건번호 또는 공식 문서 식별자를 기록합니다.
- 모델이 자체 생성한 법률 설명은 법적 근거로 저장하지 않습니다.
- 법률 변경 시 기존 규칙을 덮어쓰기보다 변경 이력을 남기는 방식으로 확장해야 합니다.

상세 절차는 `docs/LEGAL_METHOD.md`에 정리되어 있습니다.

## 모델 확장 계획

현재 버전은 법률 근거의 추적 가능성을 우선한 결정론적 규칙 기반 기준선입니다.
향후 실제 전문가 라벨이 확보되면 조항 분류 모델을 추가할 수 있지만, 모델의
결과도 반드시 현재 규칙 엔진 및 공식 법령 검색 결과와 함께 제시해야 합니다.
