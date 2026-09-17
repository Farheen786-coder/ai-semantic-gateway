from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging
from redis_manager import RedisSemanticCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global semantic cache instance
cache = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global cache
    logger.info("Starting up ai-gateway-control-plane...")
    cache = RedisSemanticCache()
    yield
    logger.info("Shutting down ai-gateway-control-plane...")

app = FastAPI(lifespan=lifespan)

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
    return {"status": "healthy", "service": "ai-gateway-control-plane"}

@app.get("/cache/stats")
def cache_stats():
    return cache.get_stats()

@app.delete("/cache/clear")
def clear_cache():
    cache.clear_cache()
    return {"status": "cleared"}

@app.post("/process", response_model=ProcessResponse)
def process_prompt(req: ProcessRequest):
    # Embed prompt
    embedding = cache.embed_text(req.prompt)
    
    # Check cache
    cached_result = cache.cache_lookup(embedding, threshold=0.95)
    
    if cached_result:
        response_text, score = cached_result
        # Estimate tokens just on prompt for cache hit
        token_estimate = len(req.prompt.split())
        return ProcessResponse(
            response=response_text,
            source="cache",
            routing="none",
            cache_hit=True,
            similarity_score=score,
            rag_context=None,
            token_estimate=token_estimate
        )
    
    # RAG Search
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
    
    # Mock Generation
    mock_response = f"Generated response by {routing_model} based on RAG context and prompt: '{req.prompt}'."
    
    # Store in cache
    cache.cache_store(req.prompt, mock_response, embedding)
    
    return ProcessResponse(
        response=mock_response,
        source="generation",
        routing=routing_model,
        cache_hit=False,
        similarity_score=0.0,
        rag_context=rag_context,
        token_estimate=token_estimate
    )
