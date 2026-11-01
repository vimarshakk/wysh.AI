from app.replay_cache import ReplayCache


def test_replay_cache_evicts_oldest_entry_deterministically():
    cache = ReplayCache(max_entries=2)
    cache.put("one", 1)
    cache.put("two", 2)
    assert cache.get("one") == 1
    cache.put("three", 3)
    assert cache.get("one") == 1
    cache.put("four", 4)
    assert cache.get("two") is None
    assert cache.get("three") is None
    assert cache.get("one") == 1
    assert cache.get("four") == 4
    assert len(cache) == 2
