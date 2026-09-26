"""Apply backend/supabase/*.sql to the configured Postgres database."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings

SQL_FILES = (
    Path(__file__).resolve().parents[1] / "supabase" / "schema.sql",
    Path(__file__).resolve().parents[1] / "supabase" / "schema_vectors.sql",
    Path(__file__).resolve().parents[1] / "supabase" / "schema_auth.sql",
    Path(__file__).resolve().parents[1] / "supabase" / "schema_auth_phones.sql",
    Path(__file__).resolve().parents[1] / "supabase" / "schema_auth_emergency_relation.sql",
    Path(__file__).resolve().parents[1] / "supabase" / "schema_relationships.sql",
    Path(__file__).resolve().parents[1] / "supabase" / "schema_community_report_coords.sql",
)


def main() -> None:
    # Direct connection (port 5432) is more reliable for DDL than the pooler.
    db_url = (
        settings.postgres_url_non_pooling.strip()
        or settings.postgres_url.split("?")[0] + "?sslmode=require"
    )
    if not db_url:
        print("POSTGRES_URL or POSTGRES_URL_NON_POOLING is not set in .env")
        sys.exit(1)

    try:
        import psycopg2
    except ImportError:
        print("Install psycopg2-binary: pip install psycopg2-binary")
        sys.exit(1)

    for sql_path in SQL_FILES:
        if not sql_path.exists():
            print(f"Missing {sql_path}")
            sys.exit(1)

    print(f"Connecting to Supabase Postgres…")
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    for sql_path in SQL_FILES:
        print(f"Applying {sql_path.name}…")
        sql = sql_path.read_text(encoding="utf-8")
        try:
            cur.execute(sql)
            print(f"  OK: {sql_path.name}")
        except Exception as exc:
            print(f"  WARN: {sql_path.name} — {exc}")

    cur.close()
    conn.close()
    print("Done. Run: python scripts/verify_supabase.py")


if __name__ == "__main__":
    main()
