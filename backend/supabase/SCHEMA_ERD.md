# ResQ AI — Supabase schema relationships

## Entity relationship diagram

```mermaid
erDiagram
    auth_users ||--o| profiles : "1:1"
    profiles ||--o{ community_reports : "reports"
    profiles ||--o{ sos_events : "SOS"
    profiles ||--o{ emergency_logs : "assessments"
    profiles ||--o{ device_tokens : "FCM tokens"
    community_reports ||--o{ knowledge_assets : "embedded as source"

    hospitals {
        uuid id PK
        text name
        float lat
        float lon
        text source
    }

    shelters {
        uuid id PK
        text name
        int capacity
    }

    profiles {
        uuid id PK_FK
        text email
        text city
    }

    community_reports {
        uuid id PK
        uuid user_id FK
        text area
        text message
    }

    knowledge_assets {
        uuid id PK
        uuid source_id FK
        vector embedding
    }

    sos_events {
        uuid id PK
        uuid user_id FK
        float latitude
        float longitude
    }

    emergency_logs {
        uuid id PK
        uuid user_id FK
        text description
    }

    device_tokens {
        text token PK
        uuid user_id FK
    }
```

## Which tables connect and which do not

| Table | Connected to | Why |
|-------|----------------|-----|
| `profiles` | `auth.users` | One profile per signed-in user |
| `community_reports` | `profiles` (optional `user_id`) | Who filed the report |
| `sos_events` | `profiles` (optional `user_id`) | Who triggered SOS |
| `emergency_logs` | `profiles` (optional `user_id`) | Who ran assessment |
| `device_tokens` | `profiles` (optional `user_id`) | Whose phone receives push |
| `knowledge_assets` | `community_reports` via `source_id` | RAG index of report text |
| `hospitals` | *(none)* | City-wide reference data (3,112 OSM/KML points) |
| `shelters` | *(none)* | City-wide reference data |

Reference tables **should not** FK to users — every user shares the same hospital/shelter directory.

## Apply relationships on an existing project

```powershell
cd backend
python scripts/apply_supabase_schema.py
```

Or paste `schema_relationships.sql` into the Supabase SQL Editor.

**Note:** If `knowledge_assets` contains `source_id` values that are not valid `community_reports.id`, the FK add will fail. Clear orphan rows first:

```sql
update public.knowledge_assets
set source_id = null
where source_id is not null
  and not exists (
    select 1 from public.community_reports cr where cr.id = knowledge_assets.source_id
  );
```

## Populating `user_id` from the app

`user_id` columns are nullable so anonymous and demo data still work. When the frontend sends a Supabase JWT on API calls, the backend can set `user_id` on insert (future enhancement).
