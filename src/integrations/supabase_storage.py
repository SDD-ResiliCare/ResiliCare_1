"""Profile-image storage operations stay behind this adapter."""

from functools import lru_cache

from src.settings import get_settings
from supabase import Client, create_client


@lru_cache(maxsize=1)
def storage_client() -> Client:
    settings = get_settings()
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required for server-side storage operations")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


def upload_profile_image(path: str, content: bytes, content_type: str) -> str:
    storage_client().storage.from_("profile-images").upload(
        path,
        content,
        file_options={"content-type": content_type, "upsert": "false"},
    )
    return path
