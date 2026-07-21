"""
Run once to seed a few example shelters into Firestore so the dashboard has
something real to show. Replace with your actual verified shelter list
before going live.

    python seed_shelters.py
"""
from app.services import firebase_service

SAMPLE_SHELTERS = [
    dict(name="Nallakunta Community Hall", address="Nallakunta, Hyderabad",
         lat=17.4035, lon=78.4965, capacity=120, occupied=64),
    dict(name="Govt High School, Adikmet", address="Adikmet, Hyderabad",
         lat=17.4058, lon=78.5010, capacity=200, occupied=180),
    dict(name="Kavadiguda Function Hall", address="Kavadiguda, Hyderabad",
         lat=17.4102, lon=78.4890, capacity=80, occupied=12),
]

if __name__ == "__main__":
    for row in SAMPLE_SHELTERS:
        firebase_service.add_shelter(row)
    print(f"Seeded {len(SAMPLE_SHELTERS)} shelters into Firestore.")
