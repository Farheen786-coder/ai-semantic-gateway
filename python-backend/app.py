from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
import time
from redis_manager import RedisSemanticCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global semantic cache instance
cache = None

# Prometheus-style metrics counters
metrics = {
    "requests_total": 0,
    "cache_hits_total": 0,
    "cache_misses_total": 0,
    "requests_by_route": {"fast_model": 0, "heavy_model": 0, "none": 0},
    "latency_sum_seconds": 0.0,
    "tokens_saved_total": 0,
    "errors_total": 0,
    "startup_time": 0.0,
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global cache
    logger.info("Starting up ai-gateway-control-plane...")
    metrics["startup_time"] = time.time()
    cache = RedisSemanticCache()
    yield
    logger.info("Shutting down ai-gateway-control-plane...")

app = FastAPI(
    title="AI Gateway Control Plane",
    description="Semantic caching, RAG retrieval, and intelligent model routing for the AI Gateway.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProcessRequest(BaseModel):
    prompt: str

class ProcessResponse(BaseModel):
    response: str
    source: str
    routing: str
    cache_hit: bool
    similarity_score: float
    rag_context: Optional[List[Dict[str, Any]]] = None
    token_estimate: int

@app.get("/health")
def health_check():
    uptime = time.time() - metrics["startup_time"] if metrics["startup_time"] else 0
    return {
        "status": "healthy",
        "service": "ai-gateway-control-plane",
        "version": "1.0.0",
        "uptime_seconds": round(uptime, 2),
    }

@app.get("/cache/stats")
def cache_stats():
    return cache.get_stats()

@app.delete("/cache/clear")
def clear_cache():
    cache.clear_cache()
    return {"status": "cleared"}

@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics():
    """Prometheus-compatible metrics endpoint."""
    uptime = time.time() - metrics["startup_time"] if metrics["startup_time"] else 0
    cache_s = cache.get_stats() if cache else {"hits": 0, "misses": 0, "total": 0, "hit_rate": 0}

    lines = [
        "# HELP gateway_requests_total Total number of requests processed.",
        "# TYPE gateway_requests_total counter",
        f'gateway_requests_total {metrics["requests_total"]}',
        "",
        "# HELP gateway_cache_hits_total Total semantic cache hits.",
        "# TYPE gateway_cache_hits_total counter",
        f'gateway_cache_hits_total {metrics["cache_hits_total"]}',
        "",
        "# HELP gateway_cache_misses_total Total semantic cache misses.",
        "# TYPE gateway_cache_misses_total counter",
        f'gateway_cache_misses_total {metrics["cache_misses_total"]}',
        "",
        "# HELP gateway_cache_hit_rate Current cache hit rate.",
        "# TYPE gateway_cache_hit_rate gauge",
        f'gateway_cache_hit_rate {cache_s["hit_rate"]:.4f}',
        "",
        "# HELP gateway_tokens_saved_total Total tokens saved via cache hits.",
        "# TYPE gateway_tokens_saved_total counter",
        f'gateway_tokens_saved_total {metrics["tokens_saved_total"]}',
        "",
        "# HELP gateway_request_latency_seconds_sum Sum of request latencies.",
        "# TYPE gateway_request_latency_seconds_sum counter",
        f'gateway_request_latency_seconds_sum {metrics["latency_sum_seconds"]:.4f}',
        "",
        "# HELP gateway_requests_by_route Requests routed to each model.",
        "# TYPE gateway_requests_by_route counter",
        f'gateway_requests_by_route{{model="fast_model"}} {metrics["requests_by_route"]["fast_model"]}',
        f'gateway_requests_by_route{{model="heavy_model"}} {metrics["requests_by_route"]["heavy_model"]}',
        f'gateway_requests_by_route{{model="cache"}} {metrics["requests_by_route"]["none"]}',
        "",
        "# HELP gateway_errors_total Total processing errors.",
        "# TYPE gateway_errors_total counter",
        f'gateway_errors_total {metrics["errors_total"]}',
        "",
        "# HELP gateway_uptime_seconds Seconds since server start.",
        "# TYPE gateway_uptime_seconds gauge",
        f"gateway_uptime_seconds {uptime:.2f}",
    ]
    return "\n".join(lines) + "\n"

@app.post("/process", response_model=ProcessResponse)
def process_prompt(req: ProcessRequest):
    start_time = time.time()
    metrics["requests_total"] += 1

    try:
        # Embed prompt
        embedding = cache.embed_text(req.prompt)

        # Check cache
        cached_result = cache.cache_lookup(embedding, threshold=0.95)

        if cached_result:
            response_text, score = cached_result
            token_estimate = len(req.prompt.split())
            metrics["cache_hits_total"] += 1
            metrics["tokens_saved_total"] += token_estimate
            metrics["requests_by_route"]["none"] += 1
            metrics["latency_sum_seconds"] += time.time() - start_time
            return ProcessResponse(
                response=response_text,
                source="cache",
                routing="none",
                cache_hit=True,
                similarity_score=score,
                rag_context=None,
                token_estimate=token_estimate,
            )

        # RAG Search
        metrics["cache_misses_total"] += 1
        rag_results = cache.rag_search(embedding, top_k=2)
        rag_context = []
        context_text = ""
        for doc, score in rag_results:
            rag_context.append({"doc": doc, "score": score})
            context_text += f"{doc['title']}: {doc['content']}\n"

        augmented_prompt = f"Context:\n{context_text}\nPrompt: {req.prompt}"

        # Token estimation
        token_estimate = len(augmented_prompt.split())

        # Routing
        routing_model = "heavy_model" if token_estimate > 500 else "fast_model"
        metrics["requests_by_route"][routing_model] += 1

        # Mock Generation
        mock_response = f"Generated response by {routing_model} based on RAG context and prompt: '{req.prompt}'."

        # Store in cache
        cache.cache_store(req.prompt, mock_response, embedding)

        metrics["latency_sum_seconds"] += time.time() - start_time
        return ProcessResponse(
            response=mock_response,
            source="generation",
            routing=routing_model,
            cache_hit=False,
            similarity_score=0.0,
            rag_context=rag_context,
            token_estimate=token_estimate,
        )
    except Exception as e:
        metrics["errors_total"] += 1
        metrics["latency_sum_seconds"] += time.time() - start_time
        raise e
