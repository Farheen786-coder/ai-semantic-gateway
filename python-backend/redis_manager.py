import numpy as np
import json
import hashlib
import time
import os
from typing import Optional, Tuple
import logging

# Prevent SentenceTransformer from hanging on SSL cert issues
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

logger = logging.getLogger(__name__)

# Mock documents for RAG
MOCK_DOCUMENTS = [
    {"id": "doc1", "title": "API Rate Limiting", "content": "Rate limiting is essential for API gateways. Implement token bucket or sliding window algorithms. Set limits per user, per endpoint, and globally. Monitor 429 response rates."},
    {"id": "doc2", "title": "Load Balancing Strategies", "content": "Round-robin distributes requests equally. Least-connections routes to the server with fewest active requests. Weighted routing accounts for server capacity differences. Health checks ensure availability."},
    {"id": "doc3", "title": "Semantic Caching", "content": "Semantic caching uses vector embeddings to find similar previous queries. Unlike exact-match caching, it can return cached results for paraphrased questions. Cosine similarity thresholds typically range from 0.90 to 0.98."},
    {"id": "doc4", "title": "LLM Token Optimization", "content": "Reduce token usage through prompt compression, response caching, and smart routing. Small models handle simple queries while large models process complex reasoning tasks. Token counting helps estimate costs."},
    {"id": "doc5", "title": "Gateway Security", "content": "API gateways must implement authentication, authorization, input validation, and output sanitization. Use JWT tokens for stateless auth. Apply WAF rules to detect prompt injection attacks."}
]


class RedisSemanticCache:
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self._redis = None
        self._redis_url = redis_url
        self._model = None
        self._doc_embeddings = None
        self._cache = {}  # In-memory fallback cache
        self._stats = {"hits": 0, "misses": 0}
        self._initialize_model()

    def _initialize_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("SentenceTransformer model loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load SentenceTransformer: {e}. Using mock embeddings.")
            self._model = None

        # Pre-compute document embeddings for RAG
        self._doc_embeddings = []
        for doc in MOCK_DOCUMENTS:
            emb = self.embed_text(doc["content"])
            self._doc_embeddings.append((doc, emb))

    def _try_connect_redis(self):
        if self._redis is not None:
            return True
        try:
            import redis
            self._redis = redis.from_url(self._redis_url, decode_responses=True)
            self._redis.ping()
            logger.info("Connected to Redis")
            return True
        except Exception as e:
            logger.warning(f"Redis unavailable, using in-memory fallback: {e}")
            self._redis = None
            return False

    def embed_text(self, text: str) -> np.ndarray:
        if self._model is not None:
            return self._model.encode(text, normalize_embeddings=True)
        # Mock embedding: deterministic hash-based vector
        h = hashlib.sha256(text.encode()).hexdigest()
        np.random.seed(int(h[:8], 16))
        vec = np.random.randn(384).astype(np.float32)
        return vec / np.linalg.norm(vec)

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    def cache_lookup(self, embedding: np.ndarray, threshold: float = 0.95) -> Optional[Tuple[str, float]]:
        best_score = 0.0
        best_response = None

        # Try Redis first
        if self._try_connect_redis() and self._redis:
            try:
                keys = self._redis.keys("prompt_cache:*")
                for key in keys:
                    data = self._redis.hgetall(key)
                    if "embedding" in data and "response" in data:
                        cached_emb = np.array(json.loads(data["embedding"]), dtype=np.float32)
                        score = self.cosine_similarity(embedding, cached_emb)
                        if score > best_score:
                            best_score = score
                            best_response = data["response"]
            except Exception as e:
                logger.warning(f"Redis lookup failed: {e}")

        # Also check in-memory cache
        for key, entry in self._cache.items():
            cached_emb = entry["embedding"]
            score = self.cosine_similarity(embedding, cached_emb)
            if score > best_score:
                best_score = score
                best_response = entry["response"]

        if best_score >= threshold and best_response:
            self._stats["hits"] += 1
            return best_response, best_score

        self._stats["misses"] += 1
        return None

    def cache_store(self, prompt: str, response: str, embedding: np.ndarray):
        cache_key = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        # Store in-memory
        self._cache[cache_key] = {
            "prompt": prompt,
            "response": response,
            "embedding": embedding,
            "timestamp": time.time()
        }

        # Try Redis
        if self._try_connect_redis() and self._redis:
            try:
                self._redis.hset(f"prompt_cache:{cache_key}", mapping={
                    "prompt": prompt,
                    "response": response,
                    "embedding": json.dumps(embedding.tolist()),
                    "timestamp": str(time.time())
                })
            except Exception as e:
                logger.warning(f"Redis store failed: {e}")

    def rag_search(self, embedding: np.ndarray, top_k: int = 2) -> list:
        scored = []
        for doc, doc_emb in self._doc_embeddings:
            score = self.cosine_similarity(embedding, doc_emb)
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(doc, score) for score, doc in scored[:top_k]]

    def get_stats(self) -> dict:
        total = self._stats["hits"] + self._stats["misses"]
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "total": total,
            "hit_rate": self._stats["hits"] / total if total > 0 else 0.0
        }

    def clear_cache(self):
        self._cache.clear()
        if self._try_connect_redis() and self._redis:
            try:
                keys = self._redis.keys("prompt_cache:*")
                if keys:
                    self._redis.delete(*keys)
            except Exception:
                pass
        self._stats = {"hits": 0, "misses": 0}
