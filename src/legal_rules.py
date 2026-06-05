import json
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGAL_SOURCES_PATH = ROOT / "data" / "legal_sources.json"


@lru_cache(maxsize=1)
def load_legal_sources(path: Path = LEGAL_SOURCES_PATH) -> dict:
    with path.open(encoding="utf-8") as source_file:
        return json.load(source_file)

