import threading
import time


class ReviewStore:
    def __init__(self, max_size: int = 200, ttl: int = 3600):
        self._data: dict[str, dict] = {}
        self._timestamps: dict[str, float] = {}
        self._hash_index: dict[str, str] = {}
        self._lock = threading.Lock()
        self._max_size = max_size
        self._ttl = ttl

    def get(self, review_id: str) -> dict | None:
        with self._lock:
            self._evict_expired()
            return self._data.get(review_id)

    def put(self, review_id: str, data: dict, code_hash: str = "") -> None:
        with self._lock:
            self._evict_expired()
            if len(self._data) >= self._max_size:
                oldest = min(self._timestamps, key=self._timestamps.get)
                self._remove(oldest)
            self._data[review_id] = data
            self._timestamps[review_id] = time.time()
            if code_hash:
                self._hash_index[code_hash] = review_id

    def get_by_hash(self, code_hash: str) -> str | None:
        with self._lock:
            self._evict_expired()
            rid = self._hash_index.get(code_hash)
            if rid and rid in self._data:
                return rid
            return None

    def _evict_expired(self):
        now = time.time()
        expired = [k for k, t in self._timestamps.items() if now - t > self._ttl]
        for k in expired:
            self._remove(k)

    def _remove(self, review_id: str):
        self._data.pop(review_id, None)
        self._timestamps.pop(review_id, None)
        to_remove = [h for h, rid in self._hash_index.items() if rid == review_id]
        for h in to_remove:
            del self._hash_index[h]

    def __len__(self):
        with self._lock:
            self._evict_expired()
            return len(self._data)
