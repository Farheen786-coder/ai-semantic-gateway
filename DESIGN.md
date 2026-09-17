# DESIGN.md — Architectural Decision Records

## Why This Architecture?

This document explains the **engineering rationale** behind every major design decision in the AI Semantic Gateway. Each section follows the pattern: **Context → Decision → Consequences**.

---

## 1. Why epoll over io_uring?

**Context:** Linux offers multiple async I/O APIs — `select`, `poll`, `epoll`, and the newer `io_uring`.

**Decision:** We chose `epoll` with edge-triggered mode (`EPOLLET`).

**Rationale:**
- `epoll` is battle-tested in production systems (Nginx, HAProxy, Redis all use it)
- `io_uring` requires kernel 5.1+ and has a steeper learning curve with submission/completion queues
- For a TCP reverse proxy handling HTTP/1.1, `epoll` provides sufficient performance — we're I/O bound, not syscall bound
- `epoll_create1(EPOLL_CLOEXEC)` provides automatic close-on-exec, preventing fd leaks in child processes
- Edge-triggered mode minimizes unnecessary wakeups vs. level-triggered

**Consequences:**
- Cannot use `io_uring`'s zero-copy features for file-backed responses
- Sufficient for 10K+ concurrent connections (C10K problem is solved by epoll)
- Future migration path to `io_uring` exists if we need kernel-level batching

---

## 2. Why split Data Plane (C++) and Control Plane (Python)?

**Context:** We need both high-throughput request proxying AND complex ML-based routing logic.

**Decision:** Separate the system into a C++ data plane and Python control plane.

**Rationale:**
- **C++ data plane**: Raw socket performance for proxying. Zero-copy buffer management. No GIL. Deterministic latency. The proxy handles bytes, not business logic.
- **Python control plane**: SentenceTransformers, NumPy, and scikit-learn have first-class Python support. FastAPI provides automatic OpenAPI docs. Rapid iteration on ML pipeline logic.
- This mirrors production architectures: Envoy (C++) + control plane (Go/Python), Nginx + Lua/Python sidecars.

**Consequences:**
- Two deployment units instead of one (mitigated by docker-compose)
- Inter-process communication overhead (HTTP between planes)
- Independent scaling: proxy scales horizontally, control plane scales based on embedding computation load

---

## 3. Why Cosine Similarity threshold = 0.95?

**Context:** Semantic cache needs a similarity threshold to decide "is this query close enough to a cached one?"

**Decision:** 0.95 cosine similarity threshold.

**Rationale:**
- Tested with `all-MiniLM-L6-v2` embeddings (384-dim normalized vectors)
- At 0.90: too many false positives — "How to deploy Redis?" matches "How to deploy Postgres?"
- At 0.98: too strict — "What is load balancing?" doesn't match "Explain load balancing"
- 0.95 hits the sweet spot: catches paraphrases while rejecting semantically different queries
- Literature reference: semantic search benchmarks (MTEB) show 0.93-0.96 as optimal for paraphrase detection

**Consequences:**
- ~40-60% cache hit rate on typical conversational workloads (estimated)
- Tunable per-deployment via environment variable
- Cold start: first query always misses (acceptable)

---

## 4. Why UDP for upstream health heartbeats?

**Context:** Mock upstream servers need to report their health to the proxy for load balancing decisions.

**Decision:** UDP datagrams on port 8081, every 2 seconds.

**Rationale:**
- **Fire-and-forget**: Health data is ephemeral. If one heartbeat is lost, the next arrives in 2s. TCP's reliability guarantees add unnecessary overhead.
- **No connection state**: UDP doesn't maintain connections. The proxy can receive heartbeats from N upstreams without N open TCP connections.
- **Minimal latency**: No handshake, no Nagle's algorithm, no ACK waiting.
- JSON payload keeps it human-readable for debugging: `{"port": 9001, "active_requests": 3}`

**Consequences:**
- Heartbeats can be lost (acceptable — stale data expires after 10s timeout)
- No encryption (acceptable for internal network; production would use mTLS or WireGuard overlay)
- Simple to add new upstream servers — just start broadcasting

---

## 5. Why token-count routing (>500 → heavy, ≤500 → fast)?

**Context:** Different LLMs have different cost/latency profiles. We need a routing heuristic.

**Decision:** Route based on augmented prompt token count after RAG context injection.

**Rationale:**
- Token count correlates with query complexity: longer prompts with RAG context typically indicate multi-hop reasoning
- 500-token threshold based on: typical RAG-augmented prompts are 200-800 tokens. The median split gives balanced routing.
- Fast models (e.g., GPT-3.5, Mistral-7B) handle <500 tokens efficiently
- Heavy models (e.g., GPT-4, Llama-70B) justify their latency/cost for complex prompts
- Simple, deterministic, explainable — no ML model needed for routing itself

**Consequences:**
- Doesn't account for query intent (a 100-token math problem may need a heavy model)
- Future improvement: classify query type (factual vs. reasoning) alongside token count
- Easy to A/B test different thresholds in production

---

## 6. Why Redis for semantic cache (vs. FAISS, Pinecone, etc.)?

**Context:** We need vector similarity search for the semantic cache layer.

**Decision:** Redis with in-memory fallback.

**Rationale:**
- Redis is already in most production stacks — no new infrastructure dependency
- Redis Stack supports vector similarity search (VSS) natively via RediSearch
- Sub-millisecond lookups for our cache size (<100K entries)
- In-memory fallback ensures the system works without Redis (development/testing)
- FAISS would require a separate process; Pinecone adds external SaaS dependency

**Consequences:**
- Limited to datasets that fit in memory
- No built-in ANN index (brute-force cosine sim at our scale is fine; HNSW needed at >1M entries)
- Graceful degradation: if Redis dies, system continues with in-memory cache (no downtime)

---

## 7. Why React + Recharts (not D3 or Grafana)?

**Context:** Need a telemetry dashboard for real-time gateway observability.

**Decision:** React with Recharts library, custom WebSocket hook.

**Rationale:**
- Recharts wraps D3 with React-friendly declarative API — faster development
- Custom `useGatewayTelemetry` hook gives full control over WebSocket lifecycle
- Grafana would require a separate Grafana server + datasource configuration
- The dashboard is part of the product, not an ops tool — needs custom branding/layout
- Vite provides <1s HMR for rapid frontend iteration

**Consequences:**
- More code to maintain than a Grafana dashboard
- Full design control (implemented engineering-minimalist aesthetic)
- WebSocket reconnection with exponential backoff for resilience
