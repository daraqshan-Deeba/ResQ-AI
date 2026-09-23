from app.main import app


def test_keepalive_requires_secret(client):
    response = client.get("/api/cron/keepalive")
    assert response.status_code == 401


def test_keepalive_with_secret(client, monkeypatch):
    monkeypatch.setattr("app.blueprints.keepalive.settings.cron_secret", "test-cron-secret")
    monkeypatch.setattr(
        "app.blueprints.keepalive.run_keepalive",
        lambda: {
            "status": "ok",
            "configured": ["supabase"],
            "healthy": ["supabase"],
            "checks": {"supabase": {"ok": True, "configured": True}},
        },
    )

    response = client.get(
        "/api/cron/keepalive",
        headers={"Authorization": "Bearer test-cron-secret"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert "supabase" in payload["checks"]
