import argparse
import hashlib
import subprocess
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT.parent / "privacy-consent-review-ai-colab.zip"
ARCHIVE_ROOT = "privacy-consent-review-ai"
FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
REQUIRED_PATHS = {
    "app/app.py",
    "requirements.txt",
    "models/model_manifest.json",
    "privacy_consent_review_demo.ipynb",
}
EXCLUDED_PREFIXES = (
    ".git/",
    ".venv/",
    ".pytest_cache/",
    "__pycache__/",
    "uploads/",
    "data/evaluation/private/",
)
EXCLUDED_NAMES = {".env", "evaluation.json"}


def tracked_files(root: Path = ROOT) -> list[Path]:
    if (root / ".git").exists():
        completed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        relative_paths = {
            Path(item.decode("utf-8"))
            for item in completed.stdout.split(b"\0")
            if item
        }
    else:
        relative_paths = {
            path.relative_to(root)
            for path in root.rglob("*")
            if path.is_file()
        }

    files = [
        path
        for path in relative_paths
        if (root / path).is_file() and not _is_excluded(path)
    ]
    return sorted(files, key=lambda path: path.as_posix())


def build_archive(output: Path, root: Path = ROOT) -> dict:
    output = output.resolve()
    temporary = output.with_suffix(output.suffix + ".tmp")
    files = [
        path
        for path in tracked_files(root)
        if (root / path).resolve() not in {output, temporary}
    ]
    archived_paths = {path.as_posix() for path in files}
    missing = sorted(REQUIRED_PATHS - archived_paths)
    if missing:
        raise ValueError(f"Required release files are missing: {', '.join(missing)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    if temporary.exists():
        temporary.unlink()

    try:
        with ZipFile(
            temporary,
            "w",
            compression=ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for relative_path in files:
                archive_path = PurePosixPath(ARCHIVE_ROOT) / relative_path.as_posix()
                info = ZipInfo(str(archive_path), FIXED_TIMESTAMP)
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                info.create_system = 3
                archive.writestr(
                    info,
                    (root / relative_path).read_bytes(),
                    compress_type=ZIP_DEFLATED,
                    compresslevel=9,
                )
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()

    return {
        "output": str(output),
        "file_count": len(files),
        "size_bytes": output.stat().st_size,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


def _is_excluded(path: Path) -> bool:
    normalized = path.as_posix()
    return (
        path.name in EXCLUDED_NAMES
        or path.suffix in {".pyc", ".pyo"}
        or "__pycache__" in path.parts
        or any(
            normalized == prefix.rstrip("/") or normalized.startswith(prefix)
            for prefix in EXCLUDED_PREFIXES
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    result = build_archive(arguments.output)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
