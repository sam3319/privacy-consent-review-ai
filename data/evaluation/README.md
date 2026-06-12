# 익명화 외부 평가 데이터

실제 문서를 저장소에 직접 추가하지 않습니다. 전문가 검수가 끝난 익명화
JSONL 파일을 로컬의 `data/evaluation/private/`에 두고 평가합니다.

한 줄 형식:

```json
{"id":"case-001","document_type":"housing_lease","text":"익명화된 문서","fields":{"deposit":"100,000,000원"},"reviewer":"reviewer-id","reviewed_at":"2026-06-09"}
```

지원 문서 유형은 `collection`, `third_party`, `combined`,
`standard_terms_contract`, `housing_lease`, `employment_contract`입니다.

```powershell
python scripts/validate_anonymized_dataset.py data/evaluation/private/cases.jsonl
python scripts/evaluate_anonymized_dataset.py data/evaluation/private/cases.jsonl --output evaluation.json
```

평가 결과에는 다음 항목이 포함됩니다.

- `document_type_accuracy`: 전체 문서 유형 정확도
- `document_type_report`: 문서 유형별 precision, recall, F1
- `document_type_errors`: 문서 유형 오분류 사례
- `field_evaluation.by_field`: 필드별 예측 수와 exact-match 비율
- `field_evaluation.errors`: 누락 또는 값 불일치 사례

오류 사례에는 원문 전체가 아니라 사례 `id`, 기대값, 예측값만 기록됩니다.
`evaluation.json`도 실제 값이 포함될 수 있으므로 저장소에 커밋하지 않습니다.

이름, 상세 주소, 연락처, 주민등록번호, 계좌번호, 서명 이미지는 제거해야 합니다.
