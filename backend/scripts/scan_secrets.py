"""Quick local secret-pattern scan (no values printed)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERNS = [
    (r"gsk_[A-Za-z0-9]{20,}", "groq_key"),
    (r"sk-[A-Za-z0-9]{20,}", "openai_style_key"),
    (r"AIza[0-9A-Za-z_-]{30,}", "google_api_key"),
    (r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.", "jwt_token"),
    (r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", "private_key"),
    (r"sb_[a-zA-Z0-9]{20,}", "supabase_secret"),
]
SKIP_DIRS = {".git", "node_modules", ".next", "venv", ".venv", "__pycache__", ".pytest_cache"}
SKIP_FILES = {".env", ".env.example", ".env.local", ".env.local.example"}


def main() -> None:
    findings: list[tuple[str, str]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(p in SKIP_DIRS for p in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.suffix in {".png", ".jpg", ".sst", ".meta", ".joblib", ".zip", ".pyc", ".kml"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat, label in PATTERNS:
            for m in re.finditer(pat, text):
                snippet = m.group(0)
                if "..." in snippet or "your-" in snippet:
                    continue
                findings.append((str(path.relative_to(ROOT)), label))

    print(f"findings={len(findings)}")
    for path, label in findings[:40]:
        print(f"  {label}: {path}")

    for env in ["backend/.env", "frontend/.env.local", ".env"]:
        p = ROOT / env
        if not p.exists():
            print(f"env missing: {env}")
            continue
        nonempty = []
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" not in line or line.strip().startswith("#"):
                continue
            key, value = line.split("=", 1)
            val = value.strip().strip('"').strip("'")
            if val and "..." not in val and "your-" not in val:
                nonempty.append(key.strip())
        print(f"env {env}: non_empty={len(nonempty)} keys={', '.join(nonempty)}")


if __name__ == "__main__":
    main()
