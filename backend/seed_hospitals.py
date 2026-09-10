"""
Seed sample hospitals into Supabase (preferred) or Firebase fallback.

    python seed_hospitals.py
"""

from app.services import database_service, supabase_service

SAMPLE_HOSPITALS = [
    {
        "name": "Gandhi Hospital",
        "address": "Musheerabad, Hyderabad",
        "lat": 17.4240,
        "lon": 78.5020,
        "phone": "+914023330000",
        "facility_type": "Government Hospital",
        "source": "manual_seed",
    },
    {
        "name": "Osmania General Hospital",
        "address": "Afzal Gunj, Hyderabad",
        "lat": 17.3725,
        "lon": 78.4780,
        "phone": "+914023330001",
        "facility_type": "Government Hospital",
        "source": "manual_seed",
    },
    {
        "name": "Yashoda Hospitals, Secunderabad",
        "address": "Alexander Road, Secunderabad",
        "lat": 17.4395,
        "lon": 78.4982,
        "phone": "+914046787878",
        "facility_type": "Private Hospital",
        "source": "manual_seed",
    },
    {
        "name": "KIMS Hospital",
        "address": "Kondapur, Hyderabad",
        "lat": 17.4601,
        "lon": 78.3639,
        "phone": "+914044777777",
        "facility_type": "Private Hospital",
        "source": "manual_seed",
    },
    {
        "name": "Care Hospital, Banjara Hills",
        "address": "Banjara Hills, Hyderabad",
        "lat": 17.4239,
        "lon": 78.4478,
        "phone": "+914023444422",
        "facility_type": "Private Hospital",
        "source": "manual_seed",
    },
]

if __name__ == "__main__":
    if not database_service.hospitals_directory_available():
        raise SystemExit(
            "Database not configured. Set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in .env "
            "(or FIREBASE_* for legacy fallback)."
        )

    backend = "Supabase" if supabase_service.supabase_available else "Firebase"
    for row in SAMPLE_HOSPITALS:
        database_service.add_hospital(row)
    print(f"Seeded {len(SAMPLE_HOSPITALS)} sample hospitals into {backend}.")
