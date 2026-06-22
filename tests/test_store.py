import time
from agent.store import ReviewStore


def test_put_and_get():
    s = ReviewStore()
    s.put("r1", {"data": "hello"}, code_hash="h1")
    assert s.get("r1") == {"data": "hello"}


def test_get_missing():
    s = ReviewStore()
    assert s.get("nope") is None


def test_get_by_hash():
    s = ReviewStore()
    s.put("r1", {"data": "hello"}, code_hash="h1")
    assert s.get_by_hash("h1") == "r1"


def test_get_by_hash_missing():
    s = ReviewStore()
    assert s.get_by_hash("nope") is None


def test_ttl_eviction():
    s = ReviewStore(ttl=0)
    s.put("r1", {"data": "hello"}, code_hash="h1")
    time.sleep(0.01)
    assert s.get("r1") is None
    assert len(s) == 0


def test_max_size_eviction():
    s = ReviewStore(max_size=2)
    s.put("r1", {"a": 1})
    s.put("r2", {"b": 2})
    s.put("r3", {"c": 3})
    assert len(s) == 2
    assert s.get("r1") is None


def test_len():
    s = ReviewStore()
    assert len(s) == 0
    s.put("r1", {"a": 1})
    s.put("r2", {"a": 2})
    assert len(s) == 2


def test_hash_index_cleaned_on_eviction():
    s = ReviewStore(max_size=1)
    s.put("r1", {"a": 1}, code_hash="h1")
    s.put("r2", {"b": 2}, code_hash="h2")
    assert s.get_by_hash("h1") is None
    assert s.get_by_hash("h2") == "r2"
