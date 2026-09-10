"""Smoke-test Supabase connection using service role key from .env."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.services import supabase_service


def main() -> None:
    if not settings.is_supabase_available:
        print("Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        return

    if not supabase_service.supabase_available:
        print(f"Supabase client failed: {supabase_service.supabase_error_detail}")
        return

    try:
        response = supabase_service.client.table("shelters").select("id").limit(1).execute()
        _ = response.data
    except Exception as exc:
        print("Connected to Supabase, but tables are missing.")
        print("Run backend/supabase/schema.sql in the Supabase SQL editor first.")
        print(f"Detail: {exc}")
        return

    shelters = supabase_service.list_shelters()
    reports = supabase_service.list_reports()
    hospitals = supabase_service.list_hospitals()

    vector_ready = False
    storage_ready = False
    try:
        supabase_service.client.table("knowledge_assets").select("id").limit(1).execute()
        vector_ready = True
    except Exception:
        print("Vector tables missing — run backend/supabase/schema_vectors.sql")

    try:
        buckets = supabase_service.client.storage.list_buckets()
        storage_ready = any(b.name == "resq-assets" for b in buckets)
        if not storage_ready:
            print("Storage bucket 'resq-assets' missing — run schema_vectors.sql")
    except Exception as exc:
        print(f"Could not list storage buckets: {exc}")

    print(
        f"Supabase OK — shelters: {len(shelters)}, hospitals: {len(hospitals)}, "
        f"reports: {len(reports)}, vectors: {'yes' if vector_ready else 'no'}, "
        f"storage: {'yes' if storage_ready else 'no'}"
    )


if __name__ == "__main__":
    main()
