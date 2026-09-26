import jwt

from app.auth import decode_access_token
from app.core.config import settings


def test_hs256_access_token_decodes(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "unit-test-secret")
    token = jwt.encode({"sub": "user-hs"}, "unit-test-secret", algorithm="HS256")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-hs"


def test_es256_access_token_uses_jwks(monkeypatch):
    class _Key:
        key = "unused"

    class _Jwks:
        def get_signing_key_from_jwt(self, _token):
            return _Key()

    monkeypatch.setattr("app.auth._jwks", lambda: _Jwks())
    monkeypatch.setattr("app.auth.jwt.get_unverified_header", lambda _t: {"alg": "ES256"})
    monkeypatch.setattr(
        "app.auth.jwt.decode",
        lambda *_a, **_k: {"sub": "user-es"},
    )
    payload = decode_access_token("header.payload.sig")
    assert payload is not None
    assert payload["sub"] == "user-es"
