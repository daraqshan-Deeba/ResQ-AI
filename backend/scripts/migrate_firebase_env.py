"""One-time helper: copy firebase-service-account.json into backend/.env, then delete JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
JSON_PATH = ROOT / "firebase-service-account.json"
ENV_PATH = BACKEND_DIR / ".env"


def main() -> None:
    if not JSON_PATH.exists():
        print(f"No file at {JSON_PATH}")
        return

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    pk = data["private_key"].replace("\n", "\\n")
    block = (
        "# ---------- Firebase (FCM push notifications) ----------\n"
        f"FIREBASE_PROJECT_ID={data['project_id']}\n"
        f"FIREBASE_CLIENT_EMAIL={data['client_email']}\n"
        f'FIREBASE_PRIVATE_KEY="{pk}"\n'
        "FIREBASE_ALERT_TOPIC=resq_alerts\n"
        f"NEXT_PUBLIC_FIREBASE_PROJECT_ID={data['project_id']}\n"
        f"NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN={data['project_id']}.firebaseapp.com\n"
    )

    text = ENV_PATH.read_text(encoding="utf-8")
    if "FIREBASE_PROJECT_ID=" in text:
        text = re.sub(
            r"# ---------- Firebase.*?# ---------- Redis",
            block + "\n# ---------- Redis",
            text,
            flags=re.S,
        )
    else:
        text = text.replace("# ---------- Redis", block + "\n# ---------- Redis")

    ENV_PATH.write_text(text, encoding="utf-8")
    JSON_PATH.unlink()
    print("Migrated Firebase credentials to .env and deleted firebase-service-account.json")


if __name__ == "__main__":
    main()
