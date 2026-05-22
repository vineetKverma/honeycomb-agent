from dotenv import load_dotenv
import os

load_dotenv()

def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(f"Required environment variable '{name}' is missing or empty. Check your .env file.")
    return value

GEMINI_API_KEY: str = _require("GEMINI_API_KEY")
MONGODB_URI: str = _require("MONGODB_URI")
MONGODB_DB: str = _require("MONGODB_DB")
MONGODB_COLLECTION: str = _require("MONGODB_COLLECTION")
VECTOR_INDEX_NAME: str = _require("VECTOR_INDEX_NAME")
