from supabase import Client, create_client

from nexus.config import settings


def get_supabase_client() -> Client | None:
	"""Create and return a Supabase client. Returns None if URL is not configured."""
	if not settings.supabase_url:
		return None
	return create_client(settings.supabase_url, settings.supabase_anon_key)


supabase_client = get_supabase_client()
