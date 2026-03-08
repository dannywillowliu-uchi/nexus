def __getattr__(name: str):
	if name == "supabase_client":
		from nexus.db.client import supabase_client
		return supabase_client
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["supabase_client"]
