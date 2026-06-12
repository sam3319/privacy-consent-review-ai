import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.document_classifier import detect_document_type_hybrid
from src.model_security import model_integrity_status
from src.special_contract_analyzer import analyze_housing_contract


def run() -> dict:
    required_files = [
        ROOT / "app" / "app.py",
        ROOT / "packages.txt",
        ROOT / "requirements.txt",
        ROOT / "models" / "model_manifest.json",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_files if not path.exists()]
    sample = (ROOT / "samples" / "risky_housing_lease.txt").read_text(
        encoding="utf-8"
    )
    detection = detect_document_type_hybrid(sample)
    analysis = analyze_housing_contract(sample)
    integrity = model_integrity_status()
    model_size = sum(
        path.stat().st_size
        for path in (ROOT / "models").rglob("*")
        if path.is_file() and path.suffix in {".joblib", ".safetensors"}
    )
    result = {
        "missing_files": missing,
        "document_type": detection["document_type"],
        "finding_count": len(analysis["findings"]),
        "model_size_mb": round(model_size / 1024 / 1024, 2),
        "model_integrity": integrity,
        "ready": (
            not missing
            and integrity["valid"]
            and detection["document_type"] == "housing_lease"
            and bool(analysis["findings"])
        ),
    }
    if not result["ready"]:
        raise SystemExit(json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
