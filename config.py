import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _clean_env(name, default=None):
	value = os.getenv(name, default)
	if value is None:
		return None
	value = str(value).strip()
	# Support accidentally quoted values copied into .env
	if len(value) >= 2 and (
		(value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
	):
		value = value[1:-1].strip()
	return value


def _clean_env_aliased(*names, default=None):
	"""Return first non-empty env var among names. Used for RAVEN_* with legacy fallback."""
	for n in names:
		v = _clean_env(n)
		if v:
			return v
	return default


# LLM provider credentials
OPENAI_API_KEY = _clean_env("OPENAI_API_KEY")
GOOGLE_API_KEY = _clean_env("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = _clean_env("ANTHROPIC_API_KEY")
OLLAMA_BASE_URL = _clean_env("OLLAMA_BASE_URL")
OPENROUTER_BASE_URL = _clean_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = _clean_env("OPENROUTER_API_KEY")
LLAMA_CPP_BASE_URL = _clean_env("LLAMA_CPP_BASE_URL")
CUSTOM_API_BASE_URL = _clean_env("CUSTOM_API_BASE_URL")
CUSTOM_API_KEY = _clean_env("CUSTOM_API_KEY")
CUSTOM_API_MODEL = _clean_env("CUSTOM_API_MODEL")

# --- Raven-specific (with ROBIN_* legacy alias) ---
RAVEN_DATA_DIR = Path(_clean_env_aliased("RAVEN_DATA_DIR", "ROBIN_DATA_DIR", default=".raven"))
RAVEN_PROXY_URL = _clean_env_aliased("RAVEN_PROXY_URL", "ROBIN_PROXY_URL")
