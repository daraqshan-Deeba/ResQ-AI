"""Knowledge corpus: Supabase Storage files + pgvector semantic search."""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services import embedding_service, supabase_service, supabase_storage_service

logger = logging.getLogger("resq.knowledge")


def knowledge_available() -> bool:
    return supabase_service.supabase_available


def ingest_asset(
    *,
    title: str,
    content_text: str,
    asset_type: str,
    area: Optional[str] = None,
    storage_path: Optional[str] = None,
    storage_url: Optional[str] = None,
    mime_type: Optional[str] = None,
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    """Persist a knowledge asset and optional embedding for vector search."""
    if not supabase_service.supabase_available:
        raise RuntimeError("Supabase is unavailable")

    embed_source = "\n".join(
        part for part in [title.strip(), area.strip() if area else "", content_text.strip()] if part
    )
    embedding = embedding_service.embed_text(embed_source)

    payload: dict[str, Any] = {
        "title": title,
        "content_text": content_text,
        "asset_type": asset_type,
        "area": area,
        "storage_path": storage_path,
        "storage_url": storage_url,
        "mime_type": mime_type,
        "source_type": source_type,
        "source_id": source_id,
        "metadata": metadata or {},
    }
    if embedding is not None:
        payload["embedding"] = embedding

    response = supabase_service.client.table("knowledge_assets").insert(payload).execute()
    if not response.data:
        raise RuntimeError("Supabase insert returned no data for knowledge asset")

    row = response.data[0]
    return _format_asset(row, similarity=None)


def search_knowledge(
    query: str,
    *,
    limit: int = 5,
    area: Optional[str] = None,
    threshold: float = 0.55,
) -> list[dict]:
    """Semantic search over ingested images/documents/reports."""
    if not supabase_service.supabase_available or supabase_service.client is None:
        return []

    embedding = embedding_service.embed_text(query)
    if embedding is None:
        logger.info("Vector search skipped — embedding model unavailable.")
        return _keyword_fallback(query, limit=limit, area=area)

    try:
        response = supabase_service.client.rpc(
            "match_knowledge_assets",
            {
                "query_embedding": embedding,
                "match_threshold": threshold,
                "match_count": limit,
                "filter_area": area,
            },
        ).execute()
        rows = response.data or []
        return [_format_asset(row, similarity=row.get("similarity")) for row in rows]
    except Exception as exc:
        logger.warning("match_knowledge_assets RPC failed (%s); using keyword fallback.", exc)
        return _keyword_fallback(query, limit=limit, area=area)


def _keyword_fallback(
    query: str,
    *,
    limit: int,
    area: Optional[str],
) -> list[dict]:
    try:
        request = (
            supabase_service.client.table("knowledge_assets")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if area:
            request = request.ilike("area", f"%{area}%")
        needle = query.strip().lower()
        rows = request.execute().data or []
        if needle:
            rows = [
                row
                for row in rows
                if needle in (row.get("title") or "").lower()
                or needle in (row.get("content_text") or "").lower()
            ]
        return [_format_asset(row, similarity=None) for row in rows[:limit]]
    except Exception as exc:
        logger.warning("keyword fallback search failed: %s", exc)
        return []


def upload_and_ingest(
    data: bytes,
    filename: str,
    *,
    title: str,
    description: str,
    area: Optional[str] = None,
    asset_type: str = "document",
    content_type: Optional[str] = None,
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
) -> dict:
    """Upload to object storage, extract text when possible, and index for search."""
    uploaded = supabase_storage_service.upload_bytes(
        data,
        filename,
        folder="knowledge",
        content_type=content_type,
    )
    extracted = supabase_storage_service.extract_text_content(
        data, uploaded["mime_type"], filename
    )
    content_text = "\n\n".join(part for part in [description.strip(), extracted] if part)
    if not content_text:
        content_text = description.strip() or title

    asset = ingest_asset(
        title=title,
        content_text=content_text,
        asset_type=asset_type,
        area=area,
        storage_path=uploaded["storage_path"],
        storage_url=uploaded["storage_url"],
        mime_type=uploaded["mime_type"],
        source_type=source_type,
        source_id=source_id,
        metadata={"filename": filename, "size_bytes": uploaded["size_bytes"]},
    )
    asset["embedding_indexed"] = embedding_service.embedding_available()
    return asset


def _format_asset(row: dict, similarity: Optional[float]) -> dict:
    return {
        "id": str(row["id"]),
        "title": row.get("title", ""),
        "content_text": row.get("content_text", ""),
        "asset_type": row.get("asset_type", "document"),
        "storage_url": row.get("storage_url"),
        "mime_type": row.get("mime_type"),
        "area": row.get("area"),
        "source_type": row.get("source_type"),
        "source_id": str(row["source_id"]) if row.get("source_id") else None,
        "similarity": similarity,
        "created_at": row.get("created_at"),
    }
