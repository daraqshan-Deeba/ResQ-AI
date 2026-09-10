import io
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def enable_supabase(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr("app.services.supabase_service.supabase_available", True)
    monkeypatch.setattr("app.services.supabase_service.client", mock_client)
    return mock_client


class TestKnowledgeSearch:
    def test_search_requires_query(self, client):
        res = client.get("/api/knowledge/search")
        assert res.status_code == 400

    def test_search_unavailable_without_supabase(self, client):
        res = client.get("/api/knowledge/search?q=flooding")
        assert res.status_code == 503

    def test_search_returns_results(self, client, enable_supabase):
        enable_supabase.rpc.return_value.execute.return_value.data = [
            {
                "id": "asset-1",
                "title": "Flood photo",
                "content_text": "Road flooded near station",
                "asset_type": "image",
                "storage_url": "https://example.com/photo.jpg",
                "mime_type": "image/jpeg",
                "area": "Tarnaka",
                "source_type": "community_report",
                "source_id": "report-1",
                "similarity": 0.91,
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]

        with patch(
            "app.services.embedding_service.embed_text",
            return_value=[0.1] * 384,
        ):
            res = client.get("/api/knowledge/search?q=flooded%20road&area=Tarnaka")

        assert res.status_code == 200
        body = res.get_json()
        assert body["query"] == "flooded road"
        assert len(body["results"]) == 1
        assert body["results"][0]["title"] == "Flood photo"


class TestKnowledgeUpload:
    def test_upload_requires_supabase(self, client):
        res = client.post(
            "/api/knowledge/upload",
            data={"title": "Guide", "description": "Flood safety"},
        )
        assert res.status_code == 503

    def test_upload_rejects_missing_file(self, client, enable_supabase):
        res = client.post(
            "/api/knowledge/upload",
            data={"title": "Guide", "description": "Flood safety"},
        )
        assert res.status_code == 400

    def test_upload_indexes_document(self, client, enable_supabase):
        enable_supabase.storage.from_.return_value.upload.return_value = None
        enable_supabase.table.return_value.insert.return_value.execute.return_value.data = [
            {
                "id": "asset-99",
                "title": "Evacuation checklist",
                "content_text": "Keep documents dry",
                "asset_type": "document",
                "storage_url": "https://example.com/doc.txt",
                "mime_type": "text/plain",
                "area": "Hyderabad",
                "source_type": "manual_upload",
                "source_id": None,
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]

        with patch(
            "app.services.embedding_service.embed_text",
            return_value=[0.2] * 384,
        ), patch(
            "app.services.embedding_service.embedding_available",
            return_value=True,
        ):
            res = client.post(
                "/api/knowledge/upload",
                data={
                    "title": "Evacuation checklist",
                    "description": "Keep documents dry",
                    "area": "Hyderabad",
                    "file": (io.BytesIO(b"Keep documents dry"), "checklist.txt"),
                },
            )

        assert res.status_code == 201
        body = res.get_json()
        assert body["id"] == "asset-99"
        assert body["embedding_indexed"] is True
