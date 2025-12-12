import logging
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import EMBEDDING_DIM
from .db import get_conn
from .embeddings import get_embedding
from .ingest import index_folder, to_vector_literal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
VECTOR_DIMENSION = EMBEDDING_DIM  # 1536 for text-embedding-3-small

app = FastAPI(title="VecMind – Semantic Knowledge Search Engine")


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    Returns a value between -1 and 1, where 1 means identical vectors.
    """
    if len(a) != len(b):
        raise ValueError(f"Vectors must have same length: {len(a)} != {len(b)}")
    
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


def parse_vector_from_text(vector_text: str) -> List[float]:
    """
    Parse a pgvector text representation into a Python list of floats.
    Handles formats like '[0.123,0.456,...]' or '[0.123, 0.456, ...]'
    """
    # Remove brackets and split by comma
    vector_text = vector_text.strip()
    if vector_text.startswith('[') and vector_text.endswith(']'):
        vector_text = vector_text[1:-1]
    
    # Split by comma and convert to floats
    values = [float(x.strip()) for x in vector_text.split(',') if x.strip()]
    return values

# Get absolute path to static directory
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


# Serve index.html at root
@app.get("/")
async def read_root():
    return FileResponse(str(STATIC_DIR / "index.html"))


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchResult(BaseModel):
    document_title: str
    source_path: Optional[str]
    chunk_index: int
    content: str
    score: float


@app.get("/debug/count")
def debug_count():
    """Debug helper: returns how many documents and chunks are in the DB."""
    try:
        conn = get_conn()
        with conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents;")
            docs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM chunks;")
            chunks = cur.fetchone()[0]
            
            # Get sample data
            sample_chunk = None
            sample_embedding_literal = None
            if chunks > 0:
                cur.execute("SELECT c.content, c.embedding::text FROM chunks c LIMIT 1;")
                sample_row = cur.fetchone()
                if sample_row:
                    sample_chunk = sample_row[0][:100] if sample_row[0] else None
                    sample_embedding_literal = sample_row[1][:200] if sample_row[1] else None
            
            # Check document-chunk relationships
            cur.execute("""
                SELECT COUNT(*) 
                FROM chunks c 
                LEFT JOIN documents d ON c.document_id = d.id 
                WHERE d.id IS NULL;
            """)
            orphaned_chunks = cur.fetchone()[0]
            
        return {
            "documents": docs,
            "chunks": chunks,
            "orphaned_chunks": orphaned_chunks,
            "sample_chunk_preview": sample_chunk,
            "sample_embedding_preview": sample_embedding_literal
        }
    except Exception as e:
        logger.error(f"Debug count failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database connection failed: {e}")


@app.get("/debug/test-vector")
def test_vector():
    """
    Test vector queries directly to diagnose search issues.
    Tests vector distance queries with and without JOINs.
    """
    try:
        conn = get_conn()
        results = {}
        
        with conn, conn.cursor() as cur:
            # Get a sample vector from database
            cur.execute("SELECT embedding::text FROM chunks LIMIT 1;")
            sample_row = cur.fetchone()
            
            if not sample_row:
                return {"error": "No chunks in database"}
            
            sample_vec_literal = sample_row[0]
            results["sample_vector_preview"] = sample_vec_literal[:200]
            
            # Test 1: Simple vector distance query without JOIN
            test_sql_no_join = f"""
            SELECT 
                c.id,
                c.chunk_index,
                1 - (c.embedding <=> '{sample_vec_literal}'::vector) AS score
            FROM chunks c
            ORDER BY c.embedding <=> '{sample_vec_literal}'::vector
            LIMIT 5;
            """
            
            try:
                cur.execute(test_sql_no_join)
                no_join_rows = cur.fetchall()
                results["test_no_join"] = {
                    "success": True,
                    "row_count": len(no_join_rows),
                    "scores": [float(r[2]) for r in no_join_rows[:3]] if no_join_rows else []
                }
            except Exception as e:
                results["test_no_join"] = {"success": False, "error": str(e)}
            
            # Test 2: Vector distance query with JOIN
            test_sql_with_join = f"""
            SELECT 
                d.title,
                c.chunk_index,
                1 - (c.embedding <=> '{sample_vec_literal}'::vector) AS score
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            ORDER BY c.embedding <=> '{sample_vec_literal}'::vector
            LIMIT 5;
            """
            
            try:
                cur.execute(test_sql_with_join)
                with_join_rows = cur.fetchall()
                results["test_with_join"] = {
                    "success": True,
                    "row_count": len(with_join_rows),
                    "scores": [float(r[2]) for r in with_join_rows[:3]] if with_join_rows else []
                }
            except Exception as e:
                results["test_with_join"] = {"success": False, "error": str(e)}
            
            # Test 3: Check if chunks have valid document references
            cur.execute("""
                SELECT 
                    COUNT(*) as total_chunks,
                    COUNT(DISTINCT c.document_id) as unique_docs,
                    COUNT(CASE WHEN d.id IS NULL THEN 1 END) as orphaned
                FROM chunks c
                LEFT JOIN documents d ON c.document_id = d.id;
            """)
            stats = cur.fetchone()
            results["chunk_stats"] = {
                "total_chunks": stats[0],
                "unique_documents": stats[1],
                "orphaned_chunks": stats[2]
            }
            
            # Test 4: Test with a query embedding
            test_query = "test query"
            try:
                query_emb = get_embedding(test_query)
                query_vec_literal = to_vector_literal(query_emb)
                
                test_sql_query = f"""
                SELECT 
                    d.title,
                    c.chunk_index,
                    1 - (c.embedding <=> '{query_vec_literal}'::vector) AS score
                FROM chunks c
                JOIN documents d ON c.document_id = d.id
                ORDER BY c.embedding <=> '{query_vec_literal}'::vector
                LIMIT 3;
                """
                
                cur.execute(test_sql_query)
                query_rows = cur.fetchall()
                results["test_with_query_embedding"] = {
                    "success": True,
                    "row_count": len(query_rows),
                    "scores": [float(r[2]) for r in query_rows] if query_rows else [],
                    "query_vector_preview": query_vec_literal[:200]
                }
            except Exception as e:
                results["test_with_query_embedding"] = {"success": False, "error": str(e)}
        
        return results
        
    except Exception as e:
        logger.error(f"Test vector failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test vector failed: {e}")


@app.post("/index")
def index_docs():
    """
    Re-index all .md/.txt files in the data/ folder.
    NOTE: requires Postgres + pgvector to be running and DATABASE_URL to be valid.
    """
    try:
        index_folder()
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")


@app.post("/search", response_model=List[SearchResult])
def search(req: SearchRequest):
    """
    Embed the query, run a vector similarity search in Postgres,
    and return the top-k matching chunks.
    
    Automatically falls back to Python-based cosine similarity if pgvector fails.
    """
    start_time = time.time()
    
    # Generate embedding for the query
    try:
        query_emb = get_embedding(req.query)
        vec_literal = to_vector_literal(query_emb)
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {e}")

    # Connect to database
    try:
        conn = get_conn()
    except Exception as e:
        logger.error(f"Database connection failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database connection failed: {e}")

    # Normalize vector format to match PostgreSQL's text output format
    # PostgreSQL removes trailing zeros, so we need to match that format
    try:
        conn_normalize = get_conn()
        with conn_normalize, conn_normalize.cursor() as cur_norm:
            cur_norm.execute(
                f"CREATE TEMP TABLE IF NOT EXISTS temp_query_vec (v vector({VECTOR_DIMENSION}));"
            )
            cur_norm.execute("DELETE FROM temp_query_vec;")
            cur_norm.execute("INSERT INTO temp_query_vec VALUES (%s::vector);", (vec_literal,))
            cur_norm.execute("SELECT v::text FROM temp_query_vec;")
            normalized_vec = cur_norm.fetchone()[0]
            cur_norm.execute("DROP TABLE temp_query_vec;")
            vec_literal = normalized_vec
    except Exception as norm_err:
        logger.warning(f"Could not normalize vector format: {norm_err}")
    
    # Use parameterized query with %s::vector (same approach as insertion)
    sql = """
    SELECT
        d.title,
        d.source_path,
        c.chunk_index,
        c.content,
        1 - (c.embedding <=> %s::vector) AS score
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    ORDER BY c.embedding <=> %s::vector
    LIMIT %s;
    """

    # Execute query with parameterized vector
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, (vec_literal, vec_literal, req.top_k))
            rows = cur.fetchall()
            query_time = time.time() - start_time
            
            if rows:
                logger.info(f"pgvector query successful: {len(rows)} results in {query_time:.3f}s")
            else:
                logger.warning(f"pgvector query returned 0 rows (took {query_time:.3f}s), falling back to Python")
            
            # If no results, fall back to Python similarity search
            if not rows:
                fallback_start_time = time.time()
                logger.info("Falling back to Python-based similarity search")
                try:
                    # Fetch all chunks with their embeddings
                    cur.execute("""
                        SELECT 
                            c.id,
                            c.content,
                            c.chunk_index,
                            c.embedding::text,
                            d.title,
                            d.source_path
                        FROM chunks c
                        JOIN documents d ON c.document_id = d.id
                    """)
                    all_chunks = cur.fetchall()
                    
                    # Compute similarities
                    chunk_scores = []
                    for chunk_id, content, chunk_index, embedding_text, doc_title, doc_path in all_chunks:
                        try:
                            chunk_emb = parse_vector_from_text(embedding_text)
                            sim_score = cosine_similarity(query_emb, chunk_emb)
                            chunk_scores.append({
                                'title': doc_title,
                                'source_path': doc_path,
                                'chunk_index': chunk_index,
                                'content': content,
                                'score': sim_score
                            })
                        except Exception as parse_err:
                            logger.warning(f"Error processing chunk {chunk_id}: {parse_err}")
                            continue
                    
                    # Sort by score and take top-k
                    chunk_scores.sort(key=lambda x: x['score'], reverse=True)
                    top_chunks = chunk_scores[:req.top_k]
                    
                    fallback_time = time.time() - fallback_start_time
                    logger.info(f"Python fallback: {len(chunk_scores)} similarities in {fallback_time:.3f}s, returning {len(top_chunks)} results")
                    
                    # Convert to rows format matching pgvector query structure
                    rows = [
                        (
                            chunk['title'],
                            chunk['source_path'],
                            chunk['chunk_index'],
                            chunk['content'],
                            chunk['score']
                        )
                        for chunk in top_chunks
                    ]
                except Exception as fallback_err:
                    logger.error(f"Python fallback failed: {fallback_err}", exc_info=True)
                    rows = []
                
    except Exception as e:
        logger.error(f"Search query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")

    # Build results
    results = []
    for row in rows:
        try:
            result = SearchResult(
                document_title=str(row[0]) if row[0] else "Unknown",
                source_path=str(row[1]) if row[1] else None,
                chunk_index=int(row[2]),
                content=str(row[3]),
                score=float(row[4]) if row[4] is not None else 0.0,
            )
            results.append(result)
        except (IndexError, ValueError, TypeError) as e:
            logger.warning(f"Error processing row: {e}, row data: {row}")
            continue

    return results


@app.post("/reindex")
def reindex_docs():
    """
    Re-index all .md/.txt files in the data/ folder.
    This clears existing data and re-indexes everything.
    """
    try:
        # Clear existing data
        conn = get_conn()
        try:
            with conn, conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE chunks, documents RESTART IDENTITY CASCADE;")
            conn.close()
        except Exception as e:
            logger.warning(f"Error clearing existing data: {e}")
        
        # Re-index
        index_folder()
        return {"status": "ok", "message": "Re-indexing complete"}
    except Exception as e:
        logger.error(f"Re-indexing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Re-indexing failed: {e}")