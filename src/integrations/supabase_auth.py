"""Verify Supabase-issued access tokens against the project's JWKS endpoint."""

from functools import lru_cache

import jwt
from jwt import PyJWKClient

from src.settings import get_settings


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(get_settings().supabase_jwks_url, cache_keys=True)


def verify_access_token(token: str) -> dict:
    settings = get_settings()
    signing_key = _jwks_client().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        audience=settings.supabase_jwt_audience,
        options={"require": ["exp", "sub"]},
    )
