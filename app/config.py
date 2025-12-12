import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/vecmind",
)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
PORT = int(os.getenv("PORT", "8000"))