import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"
OUTPUT_PATH = MODEL_DIR / "model_manifest.json"
METRICS_FILES = {
    "document_type_classifier": "document_type_metrics.json",
    "clause_risk_classifier": "clause_risk_metrics.json",
    "field_extractor": "field_extractor_metrics.json",
    "field_span_extractor": "field_span_extractor_metrics.json",
}
TRANSFORMER_DIR = MODEL_DIR / "transformer_ner"
TRANSFORMER_METRICS_PATH = MODEL_DIR / "transformer_ner_metrics.json"


def build_manifest() -> dict:
    models = []
    for model_path in sorted(MODEL_DIR.glob("*.joblib")):
        metrics_path = model_path.with_name(
            METRICS_FILES.get(
                model_path.stem,
                f"{model_path.stem}_metrics.json",
            )
        )
        metrics = (
            json.loads(metrics_path.read_text(encoding="utf-8"))
            if metrics_path.exists()
            else {}
        )
        models.append(
            {
                "name": model_path.stem,
                "file": model_path.name,
                "sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                "size_bytes": model_path.stat().st_size,
                "trained_at_utc": metrics.get("trained_at_utc"),
                "dataset_size": metrics.get("dataset_size"),
                "model_type": metrics.get("model_type"),
            }
        )
    if TRANSFORMER_DIR.is_dir():
        metrics = (
            json.loads(TRANSFORMER_METRICS_PATH.read_text(encoding="utf-8"))
            if TRANSFORMER_METRICS_PATH.exists()
            else {}
        )
        files = []
        for path in sorted(
            item for item in TRANSFORMER_DIR.rglob("*") if item.is_file()
        ):
            files.append(
                {
                    "path": path.relative_to(TRANSFORMER_DIR).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "size_bytes": path.stat().st_size,
                }
            )
        models.append(
            {
                "name": "transformer_ner",
                "directory": TRANSFORMER_DIR.name,
                "files": files,
                "size_bytes": sum(item["size_bytes"] for item in files),
                "trained_at_utc": metrics.get("trained_at_utc"),
                "dataset_size": metrics.get("dataset_size"),
                "model_type": metrics.get("model_type"),
                "base_model": metrics.get("base_model"),
            }
        )
    trained_dates = [
        model["trained_at_utc"] for model in models if model["trained_at_utc"]
    ]
    manifest = {
        "schema_version": "1.0",
        "generated_from_latest_training_utc": max(trained_dates, default=None),
        "models": models,
    }
    OUTPUT_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(build_manifest(), ensure_ascii=False, indent=2))
