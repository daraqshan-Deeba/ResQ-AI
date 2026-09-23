"""Unit tests for Supabase in-process TTL cache."""

from app.services import supabase_cache, supabase_service


def test_cache_get_set_and_ttl(monkeypatch):
    supabase_cache.clear()
    monkeypatch.setattr(supabase_cache.settings, "supabase_cache_enabled", True)
    monkeypatch.setattr(supabase_cache.settings, "supabase_cache_ttl_hospitals", 300)

    assert supabase_cache.get(supabase_cache.KEY_HOSPITALS) is None
    supabase_cache.set(supabase_cache.KEY_HOSPITALS, [{"id": "1"}])
    assert supabase_cache.get(supabase_cache.KEY_HOSPITALS) == [{"id": "1"}]

    supabase_cache.invalidate(supabase_cache.KEY_HOSPITALS)
    assert supabase_cache.get(supabase_cache.KEY_HOSPITALS) is None


def test_cache_disabled(monkeypatch):
    supabase_cache.clear()
    monkeypatch.setattr(supabase_cache.settings, "supabase_cache_enabled", False)
    supabase_cache.set(supabase_cache.KEY_SHELTERS, [{"id": "s1"}])
    assert supabase_cache.get(supabase_cache.KEY_SHELTERS) is None


def test_list_hospitals_uses_cache(monkeypatch):
    supabase_cache.clear()
    monkeypatch.setattr(supabase_cache.settings, "supabase_cache_enabled", True)
    monkeypatch.setattr(supabase_service, "supabase_available", True)

    calls = {"n": 0}

    class FakeTable:
        def select(self, *_args, **_kwargs):
            return self

        def range(self, *_args, **_kwargs):
            return self

        def execute(self):
            calls["n"] += 1
            return type(
                "R",
                (),
                {
                    "data": [
                        {
                            "id": "h1",
                            "name": "City Hospital",
                            "lat": 17.3,
                            "lon": 78.4,
                        }
                    ]
                },
            )()

    monkeypatch.setattr(supabase_service, "_table", lambda _name: FakeTable())

    first = supabase_service.list_hospitals()
    second = supabase_service.list_hospitals()
    assert first == second
    assert calls["n"] == 1
    assert len(first) == 1
    assert first[0]["name"] == "City Hospital"


def test_add_hospital_invalidates_cache(monkeypatch):
    supabase_cache.clear()
    monkeypatch.setattr(supabase_cache.settings, "supabase_cache_enabled", True)
    monkeypatch.setattr(supabase_service, "supabase_available", True)
    supabase_cache.set(supabase_cache.KEY_HOSPITALS, [{"id": "old"}])

    class FakeTable:
        def insert(self, _payload):
            return self

        def execute(self):
            return type("R", (), {"data": [{"id": "new-id"}]})()

    monkeypatch.setattr(supabase_service, "_table", lambda _name: FakeTable())
    hospital_id = supabase_service.add_hospital(
        {"name": "New", "lat": 17.0, "lon": 78.0}
    )
    assert hospital_id == "new-id"
    assert supabase_cache.get(supabase_cache.KEY_HOSPITALS) is None
