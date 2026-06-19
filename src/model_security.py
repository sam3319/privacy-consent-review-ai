import hashlib
import json
from functools import lru_cache
from pathlib import Path

import joblib


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = ROOT / "models" / "model_manifest.json"
OPTIONAL_MODEL_NAMES = {"transformer_ner"}


class ModelIntegrityError(ValueError):
    pass


def verify_model_file(
    model_path: Path,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict:
    model_path = model_path.resolve()
    manifest_path = manifest_path.resolve()
    if not model_path.exists():
        raise FileNotFoundError(f"모델 파일이 없습니다: {model_path.name}")
    if not manifest_path.exists():
        raise ModelIntegrityError("모델 매니페스트가 없습니다.")
    return _verify_cached(
        str(model_path),
        model_path.stat().st_mtime_ns,
        model_path.stat().st_size,
        str(manifest_path),
        manifest_path.stat().st_mtime_ns,
    )


@lru_cache(maxsize=32)
def _verify_cached(
    model_path_text: str,
    model_mtime_ns: int,
    model_size: int,
    manifest_path_text: str,
    manifest_mtime_ns: int,
) -> dict:
    del model_mtime_ns, manifest_mtime_ns
    model_path = Path(model_path_text)
    manifest = json.loads(
        Path(manifest_path_text).read_text(encoding="utf-8")
    )
    if manifest.get("schema_version") != "1.0":
        raise ModelIntegrityError("지원하지 않는 모델 매니페스트 버전입니다.")
    entry = next(
        (
            item
            for item in manifest.get("models", [])
            if item.get("file") == model_path.name
        ),
        None,
    )
    if entry is None:
        raise ModelIntegrityError(
            f"모델이 매니페스트에 등록되지 않았습니다: {model_path.name}"
        )
    if entry.get("size_bytes") != model_size:
        raise ModelIntegrityError(
            f"모델 파일 크기가 매니페스트와 다릅니다: {model_path.name}"
        )
    actual_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if entry.get("sha256") != actual_hash:
        raise ModelIntegrityError(
            f"모델 SHA-256이 매니페스트와 다릅니다: {model_path.name}"
        )
    return entry


def load_verified_joblib(
    model_path: Path,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
):
    verify_model_file(model_path, manifest_path)
    return joblib.load(model_path)


def verify_model_directory(
    model_path: Path,
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict:
    model_path = model_path.resolve()
    manifest_path = manifest_path.resolve()
    if not model_path.is_dir():
        raise FileNotFoundError(f"모델 디렉터리가 없습니다: {model_path.name}")
    if not manifest_path.exists():
        raise ModelIntegrityError("모델 매니페스트가 없습니다.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "1.0":
        raise ModelIntegrityError("지원하지 않는 모델 매니페스트 버전입니다.")
    entry = next(
        (
            item
            for item in manifest.get("models", [])
            if item.get("directory") == model_path.name
        ),
        None,
    )
    if entry is None:
        raise ModelIntegrityError(
            f"모델 디렉터리가 매니페스트에 등록되지 않았습니다: {model_path.name}"
        )
    expected_files = {
        item["path"]: item for item in entry.get("files", [])
    }
    actual_files = {
        path.relative_to(model_path).as_posix(): path
        for path in model_path.rglob("*")
        if path.is_file()
    }
    missing_files = sorted(set(expected_files) - set(actual_files))
    if missing_files:
        raise ModelIntegrityError(
            f"모델 디렉터리 필수 파일이 없습니다: {', '.join(missing_files)}"
        )
    for relative_path, expected in expected_files.items():
        path = actual_files[relative_path]
        if path.stat().st_size != expected.get("size_bytes"):
            raise ModelIntegrityError(
                f"모델 파일 크기가 다릅니다: {relative_path}"
            )
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected.get("sha256"):
            raise ModelIntegrityError(
                f"모델 SHA-256이 다릅니다: {relative_path}"
            )
    extra_files = sorted(set(actual_files) - set(expected_files))
    return {**entry, "extra_files": extra_files}


def model_integrity_status(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> dict:
    if not manifest_path.exists():
        return {
            "valid": False,
            "models": [],
            "errors": ["모델 매니페스트가 없습니다."],
            "warnings": [],
        }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    statuses = []
    errors = []
    warnings = []
    for entry in manifest.get("models", []):
        is_optional = entry.get("name") in OPTIONAL_MODEL_NAMES
        is_directory = bool(entry.get("directory"))
        model_path = manifest_path.parent / (
            entry["directory"] if is_directory else entry["file"]
        )
        try:
            verified = (
                verify_model_directory(model_path, manifest_path)
                if is_directory
                else verify_model_file(model_path, manifest_path)
            )
        except (FileNotFoundError, ModelIntegrityError) as error:
            statuses.append(
                {
                    "name": entry.get("name", model_path.name),
                    "file": model_path.name,
                    "valid": False,
                    "optional": is_optional,
                    "error": str(error),
                }
            )
            if is_optional:
                warnings.append(
                    f"선택 모델 {entry.get('name', model_path.name)}을 사용할 수 "
                    f"없어 fallback 모델을 사용합니다: {error}"
                )
            else:
                errors.append(str(error))
        else:
            extra_files = verified.get("extra_files", [])
            if extra_files:
                warnings.append(
                    f"{model_path.name} 디렉터리에 매니페스트 미등록 파일 "
                    f"{len(extra_files)}개가 있습니다."
                )
            statuses.append(
                {
                    "name": verified["name"],
                    "file": verified.get("file", verified.get("directory")),
                    "valid": True,
                    "optional": is_optional,
                    **(
                        {"sha256": verified["sha256"]}
                        if verified.get("sha256")
                        else {"file_count": len(verified.get("files", []))}
                    ),
                    **({"extra_files": extra_files} if extra_files else {}),
                }
            )
    return {
        "valid": bool(statuses) and not errors,
        "models": statuses,
        "errors": errors,
        "warnings": warnings,
    }
