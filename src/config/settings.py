import os

# Configuration entry points (explicit, no .env modifications by AI)
# Read API key from environment to avoid committing secrets
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# File layout
EPISODES_DIR = "episodes"
EPISODES_CONFIG_PATH = "episodes.json"

