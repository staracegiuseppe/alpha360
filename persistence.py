"""Alpha360 — Persistence (JSON file storage)."""

import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger("alpha360.store")


class DataStore:
    def __init__(self, path: str = "/data/alpha360_store.json"):
        self.path = path
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        try:
            if os.path.exists(self.path):
                with open(self.path, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"[Store] Load error: {e}")
        return {"analyses": {}, "meta": {}}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self._data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"[Store] Save error: {e}")

    def save_analysis(self, symbol: str, data: dict):
        with self._lock:
            self._data.setdefault("analyses", {})[symbol] = data
            self._save()

    def get_analysis(self, symbol: str) -> Optional[dict]:
        return self._data.get("analyses", {}).get(symbol)

    def get_all_analyses(self) -> List[dict]:
        return list(self._data.get("analyses", {}).values())

    def save_meta(self, key: str, value: Any):
        with self._lock:
            self._data.setdefault("meta", {})[key] = value
            self._save()

    def get_meta(self, key: str, default=None) -> Any:
        return self._data.get("meta", {}).get(key, default)

    def clear(self):
        with self._lock:
            self._data = {"analyses": {}, "meta": {}}
            self._save()
