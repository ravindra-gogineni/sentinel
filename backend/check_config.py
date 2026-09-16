from app.config import get_settings
s = get_settings()
print("Config loaded OK")
print(f"  API key set: {bool(s.assemblyai_api_key and s.assemblyai_api_key != 'your_assemblyai_api_key_here')}")
print(f"  Agent ID: {s.sentinel_agent_id or '(not set - will create on first call)'}")
print(f"  CORS origins: {s.cors_origins_list}")
