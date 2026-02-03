import hashlib
import json

from ghai.settings import CACHE_DIR


def get_cache_key(*args: str) -> str:
    content = "".join(args)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_cached(cache_key: str) -> dict | None:
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    return None


def set_cached(cache_key: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{cache_key}.json"
    cache_file.write_text(json.dumps(data))


def clear_cache() -> None:
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
