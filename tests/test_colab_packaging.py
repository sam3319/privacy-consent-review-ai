import hashlib
from zipfile import ZipFile

from scripts.package_colab_release import ARCHIVE_ROOT, build_archive


def test_colab_archive_is_deterministic_and_excludes_private_data(tmp_path):
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"

    first_result = build_archive(first)
    second_result = build_archive(second)

    assert first_result["sha256"] == second_result["sha256"]
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(
        second.read_bytes()
    ).digest()

    with ZipFile(first) as archive:
        names = archive.namelist()
        assert f"{ARCHIVE_ROOT}/app/app.py" in names
        assert f"{ARCHIVE_ROOT}/models/model_manifest.json" in names
        assert all("/data/evaluation/private/" not in name for name in names)
        assert all("/.git/" not in name for name in names)
        assert all("/.venv/" not in name for name in names)
        assert names == sorted(names)
