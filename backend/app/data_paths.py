"""Canonical paths for bundled datasets and source files."""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
SOURCES_DIR = DATA_DIR / "sources"
KML_DIR = SOURCES_DIR / "kml"
METADATA_DIR = SOURCES_DIR / "metadata"
DOWNLOADS_DIR = DATA_DIR / "downloads"
MODELS_DIR = DATA_DIR / "models"

PHC_KML = KML_DIR / "2d9812bb-6901-4eca-90f9-a91ca50772a0.kml"
GHMC_KML = KML_DIR / "058a954c-e370-4b81-8716-0a2197ea5a01.kml"
HOTOSM_METADATA = METADATA_DIR / "hotosm_ind_health_facilities_osm_metadata.json"
