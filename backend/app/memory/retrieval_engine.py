"""向量检索引擎 — 基于 Pinecone + sentence-transformers 的语义检索。

当文章总数超过 VECTOR_DB_ARTICLE_THRESHOLD 时启用。
低于阈值时使用 MySQL 关键词匹配（memory_service 中判断）。
"""
from __future__ import annotations

import logging

from ..config import (
    PINECONE_API_KEY,
    PINECONE_ENV,
    PINECONE_INDEX_NAME,
    VECTOR_DB_ARTICLE_THRESHOLD,
)

logger = logging.getLogger(__name__)

_embed_model = None
_pinecone_index = None
_initialized: bool = False  # True = 已尝试初始化（无论成功与否）
_available: bool = False     # True = 初始化成功，可用


def _init_pinecone() -> None:
    """Lazy init Pinecone + embedding model。只在首次调用时加载。"""
    global _embed_model, _pinecone_index, _initialized, _available

    if _initialized:
        return

    _initialized = True

    if not PINECONE_API_KEY:
        logger.info("PINECONE_API_KEY not set, vector search disabled")
        return

    try:
        from pinecone import Pinecone
        from sentence_transformers import SentenceTransformer
    except ImportError:
        logger.warning("pinecone-client or sentence-transformers not installed, vector search disabled")
        return

    try:
        # Lightweight multilingual model, supports Chinese
        _embed_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

        pc = Pinecone(api_key=PINECONE_API_KEY)
        if PINECONE_INDEX_NAME not in pc.list_indexes().names():
            from pinecone import ServerlessSpec
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=384,  # MiniLM-L12-v2 embedding dim
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region=PINECONE_ENV),
            )
            logger.info(f"Created Pinecone index: {PINECONE_INDEX_NAME}")

        _pinecone_index = pc.Index(PINECONE_INDEX_NAME)
        _available = True
        logger.info("Pinecone + embedding model initialized")
    except Exception as e:
        logger.error(f"Pinecone init failed: {e}")
        _available = False


def is_vector_search_enabled(article_count: int) -> bool:
    """判断是否该启用向量检索：配置齐全 + 文章数超阈值。"""
    if article_count < VECTOR_DB_ARTICLE_THRESHOLD:
        return False
    _init_pinecone()
    return _available


def index_article(article_id: int, topic: str, content: str) -> bool:
    """将文章向量化并存入 Pinecone。"""
    _init_pinecone()
    if not _available:
        return False

    # 用 topic + 前800字作为索引文本
    text = f"{topic}\n{content[:800]}"

    try:
        embedding = _embed_model.encode(text).tolist()  # type: ignore[union-attr]
        _pinecone_index.upsert(  # type: ignore[union-attr]
            vectors=[{
                "id": str(article_id),
                "values": embedding,
                "metadata": {
                    "topic": topic,
                    "snippet": content[:120].replace("\n", " "),
                },
            }]
        )
        logger.info(f"Indexed article {article_id}: {topic}")
        return True
    except Exception as e:
        logger.error(f"Failed to index article {article_id}: {e}")
        return False


def search_similar_articles(query: str, top_k: int = 5) -> list[dict]:
    """语义检索与 query 最相似的文章。

    Returns: [{"id", "topic", "snippet", "score"}, ...]
    """
    _init_pinecone()
    if not _available:
        return []

    try:
        embedding = _embed_model.encode(query).tolist()  # type: ignore[union-attr]
        results = _pinecone_index.query(  # type: ignore[union-attr]
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
        )
        matches = []
        for m in results.get("matches", []):
            md = m.get("metadata", {})
            matches.append({
                "id": int(m["id"]),
                "topic": md.get("topic", ""),
                "snippet": md.get("snippet", ""),
                "score": round(m.get("score", 0), 4),
            })
        return matches
    except Exception as e:
        logger.error(f"Pinecone query failed: {e}")
        return []


def get_article_count_for_threshold() -> int:
    """返回阈值配置值，供 memory_service 使用。"""
    return VECTOR_DB_ARTICLE_THRESHOLD
