from pydantic_settings import BaseSettings


class Settings(BaseSettings):
	app_name: str = "Nexus"
	debug: bool = False

	# Anthropic
	anthropic_api_key: str = ""

	# NCBI
	ncbi_api_key: str = ""

	# Semantic Scholar
	semantic_scholar_api_key: str = ""

	# Neo4j
	neo4j_uri: str = ""
	neo4j_username: str = ""
	neo4j_password: str = ""

	# Supabase
	supabase_url: str = ""
	supabase_anon_key: str = ""
	supabase_service_role_key: str = ""

	# Tamarind Bio
	tamarind_bio_api_key: str = ""

	# BioRender
	biorender_api_key: str = ""

	# Strateos (CloudLab)
	strateos_email: str = ""
	strateos_token: str = ""
	strateos_organization_id: str = ""

	# Vercel
	vercel_token: str = ""

	model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
