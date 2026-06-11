import argparse
import json
import re
from pathlib import Path


SENSITIVE_PATTERNS = {
    "resident_registration_number": r"\b\d{6}-?[1-4]\d{6}\b",
    "phone_number": r"\b01[016789][-\s]?\d{3,4}[-\s]?\d{4}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "bank_account_candidate": r"\b\d{2,6}[-\s]\d{2,6}[-\s]\d{2,8}\b",
}


def validate(path: Path) -> list[dict]:
    issues = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        serialized = json.dumps(row, ensure_ascii=False)
        for name, pattern in SENSITIVE_PATTERNS.items():
            if re.search(pattern, serialized):
                issues.append({"line": line_number, "type": name})
    return issues


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    arguments = parser.parse_args()
    issues = validate(arguments.dataset)
    print(json.dumps({"issues": issues}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if issues else 0)


if __name__ == "__main__":
    main()
