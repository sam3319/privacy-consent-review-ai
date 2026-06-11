import json
from copy import deepcopy
from datetime import datetime, timezone

from src.analyzer import redact_personal_data


def apply_field_corrections(result: dict, corrections: dict[str, str]) -> dict:
    corrected = deepcopy(result)
    audit = []
    for field in corrected.get("extracted_fields", []):
        if field["key"] not in corrections:
            continue
        new_value = corrections[field["key"]].strip()
        old_value = field.get("value", "")
        if new_value == old_value:
            continue
        field["value"] = redact_personal_data(new_value)
        field["status"] = "사용자 수정"
        field["confidence"] = 100
        field["extraction_method"] = "user_corrected"
        field["message"] = "사용자가 자동 추출값을 직접 수정했습니다."
        audit.append(
            {
                "field_key": field["key"],
                "label": field["label"],
                "before": redact_personal_data(old_value),
                "after": redact_personal_data(new_value),
            }
        )
    corrected["correction_audit"] = audit
    return corrected


def build_feedback_json(
    result: dict,
    corrections: dict[str, str],
    source_text: str = "",
) -> str:
    payload = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "document_type": result["document_type"],
        "redacted_source_text": redact_personal_data(source_text),
        "corrections": apply_field_corrections(result, corrections).get(
            "correction_audit", []
        ),
        "privacy_notice": (
            "외부 평가 데이터로 사용하기 전에 주소·이름·계좌번호 등 추가 식별정보를 "
            "수동으로 제거해야 합니다."
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
