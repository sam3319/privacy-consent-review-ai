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
    field_metrics = {}
    document_type_errors = []
    field_errors = []
    for index, row in enumerate(rows, 1):
        prediction = detect_document_type_hybrid(row["text"])
        expected_type = row["document_type"]
        predicted_type = prediction["document_type"]
        case_id = row.get("id", f"row-{index}")
        expected_types.append(expected_type)
        predicted_types.append(predicted_type)
        if expected_type != predicted_type:
            document_type_errors.append(
                {
                    "id": case_id,
                    "expected": expected_type,
                    "predicted": predicted_type,
                    "confidence": prediction.get("confidence"),
                }
            )
        extractor = FIELD_EXTRACTORS.get(row["document_type"])
        if not extractor:
            continue
        extracted = {field["key"]: field["value"] for field in extractor(row["text"])}
        for key, expected_value in row.get("fields", {}).items():
            predicted_value = extracted.get(key, "")
            normalized_expected = _normalize(expected_value)
            normalized_predicted = _normalize(predicted_value)
            matched = normalized_predicted == normalized_expected
            field_totals["expected"] += 1
            metrics = field_metrics.setdefault(key, Counter())
            metrics["expected"] += 1
            if predicted_value:
                field_totals["predicted"] += 1
                metrics["predicted"] += 1
            if matched:
                field_totals["exact_match"] += 1
                metrics["exact_match"] += 1
            else:
                field_errors.append(
                    {
                        "id": case_id,
                        "document_type": expected_type,
                        "field": key,
                        "expected": expected_value,
                        "predicted": predicted_value,
                        "error_type": (
                            "missing" if not predicted_value else "mismatch"
                        ),
                    }
                )

    document_type_correct = sum(
        expected == predicted
        for expected, predicted in zip(expected_types, predicted_types)
    )

    return {
        "dataset_size": len(rows),
        "document_type_accuracy": round(document_type_correct / len(rows), 4)
        if rows
        else None,
        "document_type_report": classification_report(
            expected_types,
            predicted_types,
            output_dict=True,
            zero_division=0,
        )
        if rows
        else {},
        "document_type_errors": document_type_errors,
        "field_evaluation": {
            "expected": field_totals["expected"],
            "predicted": field_totals["predicted"],
            "exact_match": field_totals["exact_match"],
            "exact_match_rate": _rate(
                field_totals["exact_match"], field_totals["expected"]
            ),
            "by_field": {
                key: {
                    "expected": metrics["expected"],
                    "predicted": metrics["predicted"],
                    "exact_match": metrics["exact_match"],
                    "exact_match_rate": _rate(
                        metrics["exact_match"], metrics["expected"]
                    ),
                }
                for key, metrics in sorted(field_metrics.items())
            },
            "errors": field_errors,
        },
    }


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


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
