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

이름, 상세 주소, 연락처, 주민등록번호, 계좌번호, 서명 이미지는 제거해야 합니다.
