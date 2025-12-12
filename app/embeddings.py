import hashlib
import logging
from typing import List

from openai import OpenAI, RateLimitError
from .config import OPENAI_API_KEY, EMBEDDING_MODEL, EMBEDDING_DIM

logger = logging.getLogger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def _fallback_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """
    Deterministic local fallback embedding based on hashing.
    Not "real" semantic vectors, but enough to demo pgvector search
    when OpenAI quota is unavailable.
    """
    # Make a long pseudo-random-but-deterministic byte string
    h = hashlib.sha256(text.encode("utf-8")).digest()
    buf = bytearray()
    while len(buf) < dim * 4:
        h = hashlib.sha256(h).digest()
        buf.extend(h)

    # Convert bytes to floats in [0,1)
    vals: List[float] = []
    for i in range(dim):
        chunk = buf[4 * i : 4 * (i + 1)]
        vals.append(int.from_bytes(chunk, "big") / 2**32)
    return vals


def get_embedding(text: str) -> List[float]:
    """
    Try to get a real OpenAI embedding.
    If quota or API fails, fall back to a local hash-based embedding.
    """
    text = text.replace("\n", " ")

    if not OPENAI_API_KEY:
        # No key at all → always fallback
        return _fallback_embedding(text)

    if not client:
        return _fallback_embedding(text)
    
    try:
        resp = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
        )
        return resp.data[0].embedding
    except RateLimitError:
        logger.warning("OpenAI quota exceeded, using fallback embeddings")
        return _fallback_embedding(text)
    except Exception as e:
        logger.warning(f"OpenAI embedding error: {e}, using fallback embeddings")
        return _fallback_embedding(text)