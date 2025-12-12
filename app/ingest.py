from pathlib import Path
from textwrap import wrap
from typing import List

from .db import get_conn
from .embeddings import get_embedding

# Folder that holds the raw docs - use absolute path
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Path to models.sql in the same folder as this file
MODELS_SQL_PATH = Path(__file__).resolve().parent / "models.sql"


def simple_chunk(text: str, max_chars: int = 800) -> List[str]:
    """
    Very simple chunker: split on blank lines into paragraphs,
    then hard-wrap long paragraphs.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []

    for p in paragraphs:
        if len(p) <= max_chars:
            chunks.append(p)
        else:
            chunks.extend(wrap(p, max_chars))
    return chunks


def list_source_files() -> List[Path]:
    """Return all .txt/.md files in the data/ directory."""
    exts = {".txt", ".md"}
    return [p for p in DATA_DIR.glob("*") if p.suffix.lower() in exts]


def ensure_schema() -> None:
    """Run models.sql to ensure tables + pgvector index exist."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            with MODELS_SQL_PATH.open("r", encoding="utf-8") as f:
                sql = f.read()
            cur.execute(sql)
    finally:
        conn.close()


def to_vector_literal(vec: List[float]) -> str:
    """
    Convert a Python list[float] into pgvector literal:
    [0.123456,0.234567,...]
    """
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def index_folder() -> None:
    """
    Ingest all supported files from data/, chunk them, embed,
    and insert into Postgres.
    """
    files = list_source_files()
    if not files:
        print("No .txt/.md files found in data/. Add some docs first.")
        return

    ensure_schema()

    conn = get_conn()
    try:
        cur = conn.cursor()
        try:
            for path in files:
                print(f"Indexing {path.name}...")

                text = path.read_text(encoding="utf-8")
                chunks = simple_chunk(text)

                # Insert document row
                cur.execute(
                    "INSERT INTO documents (title, source_path) VALUES (%s, %s) RETURNING id;",
                    (path.name, str(path)),
                )
                doc_id = cur.fetchone()[0]

                for idx, chunk in enumerate(chunks):
                    emb = get_embedding(chunk)
                    emb_literal = to_vector_literal(emb)
                    
                    cur.execute(
                        """
                        INSERT INTO chunks (document_id, chunk_index, content, embedding)
                        VALUES (%s, %s, %s, %s::vector);
                        """,
                        (doc_id, idx, chunk, emb_literal),
                    )

            print(f"Indexing complete: {len(chunks)} chunks from {path.name}")
        finally:
            cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    index_folder()