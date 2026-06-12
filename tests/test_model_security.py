import hashlib
import json
from pathlib import Path

import pytest

from src.ml_classifier import DEFAULT_MODEL_PATH
from src.model_security import (
    ModelIntegrityError,
    load_verified_joblib,
    model_integrity_status,
    verify_model_directory,
    verify_model_file,
)


def test_project_models_match_manifest():
    status = model_integrity_status()

    assert status["valid"]
    assert len(status["models"]) == 5
    assert all(item["valid"] for item in status["models"])


def test_verified_loader_loads_registered_model():
    entry = verify_model_file(DEFAULT_MODEL_PATH)
    model = load_verified_joblib(DEFAULT_MODEL_PATH)

    assert entry["name"] == "document_type_classifier"
    assert hasattr(model, "predict_proba")


def test_tampered_model_is_rejected_before_loading(tmp_path):
    model_path = tmp_path / "example.joblib"
    model_path.write_bytes(b"not-a-valid-model")
    original_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "model_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "models": [
                    {
                        "name": "example",
                        "file": model_path.name,
                        "size_bytes": model_path.stat().st_size,
                        "sha256": original_hash,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    model_path.write_bytes(b"tampered-model-data")

    with pytest.raises(ModelIntegrityError):
        load_verified_joblib(model_path, manifest_path)


def test_tampered_model_directory_is_rejected(tmp_path):
    model_path = tmp_path / "transformer_ner"
    model_path.mkdir()
    config_path = model_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    manifest_path = tmp_path / "model_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "models": [
                    {
                        "name": "transformer_ner",
                        "directory": model_path.name,
                        "files": [
                            {
                                "path": config_path.name,
                                "size_bytes": config_path.stat().st_size,
                                "sha256": hashlib.sha256(
                                    config_path.read_bytes()
                                ).hexdigest(),
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config_path.write_text('{"tampered": true}', encoding="utf-8")

    with pytest.raises(ModelIntegrityError):
        verify_model_directory(model_path, manifest_path)
