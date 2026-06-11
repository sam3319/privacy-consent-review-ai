import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from sklearn.metrics import classification_report

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.document_classifier import detect_document_type_hybrid
from src.field_extraction import (
    extract_contract_fields,
    extract_employment_fields,
    extract_housing_fields,
)


FIELD_EXTRACTORS = {
    "standard_terms_contract": extract_contract_fields,
    "housing_lease": extract_housing_fields,
    "employment_contract": extract_employment_fields,
}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not row.get("text") or not row.get("document_type"):
            raise ValueError(f"{number}행에 text 또는 document_type이 없습니다.")
        rows.append(row)
    return rows


def evaluate(rows: list[dict]) -> dict:
    expected_types = []
    predicted_types = []
    field_totals = Counter()
    for row in rows:
        prediction = detect_document_type_hybrid(row["text"])
        expected_types.append(row["document_type"])
        predicted_types.append(prediction["document_type"])
        extractor = FIELD_EXTRACTORS.get(row["document_type"])
        if not extractor:
            continue
        extracted = {field["key"]: field["value"] for field in extractor(row["text"])}
        for key, expected_value in row.get("fields", {}).items():
            field_totals["expected"] += 1
            if extracted.get(key):
                field_totals["predicted"] += 1
            if _normalize(extracted.get(key, "")) == _normalize(expected_value):
                field_totals["exact_match"] += 1

    return {
        "dataset_size": len(rows),
        "document_type_report": classification_report(
            expected_types,
            predicted_types,
            output_dict=True,
            zero_division=0,
        ),
        "field_evaluation": {
            "expected": field_totals["expected"],
            "predicted": field_totals["predicted"],
            "exact_match": field_totals["exact_match"],
            "exact_match_rate": round(
                field_totals["exact_match"] / field_totals["expected"], 4
            )
            if field_totals["expected"]
            else None,
        },
    }


def _normalize(value: str) -> str:
    return "".join(str(value).lower().split())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = evaluate(load_jsonl(arguments.dataset))
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
