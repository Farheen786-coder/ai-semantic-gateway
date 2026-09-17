# Architecture

## System Overview

```mermaid
flowchart LR
    Client["Client\n:443"]
    Proxy["C++ Proxy\n:8080"]
    Control["FastAPI Control\n:8000"]
    Redis["Redis Cache\n:6379"]
    Fast["Fast LLM\n:9001"]
    Heavy["Heavy LLM\n:9002"]
    Dashboard["React Dashboard\n:5173"]

    Client -->|HTTP| Proxy
    Proxy -->|Route| Fast
    Proxy -->|Route| Heavy
    Proxy <-->|"Semantic Check"| Control
    Control <-->|"Vector Search"| Redis
    Fast -->|"UDP :8081"| Proxy
    Heavy -->|"UDP :8081"| Proxy
    Proxy -.->|WebSocket| Dashboard
```

## Request Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant P as C++ Proxy
    participant CP as Control Plane
    participant R as Redis
    participant U as Upstream LLM

    C->>P: POST /v1/completions
    P->>CP: POST /process {prompt}
    CP->>CP: Embed prompt (MiniLM-L6-v2)
    CP->>R: Cosine similarity search
    
    alt Cache Hit (similarity > 0.95)
        R-->>CP: Cached response
        CP-->>P: {response, routing: "none", cache_hit: true}
        P-->>C: Cached response (< 15ms)
    else Cache Miss
        R-->>CP: No match
        CP->>CP: RAG search (top-2 docs)
        CP->>CP: Count tokens
        alt tokens > 500
            CP-->>P: {routing: "heavy_model"}
            P->>U: Forward to :9002
        else tokens ≤ 500
            CP-->>P: {routing: "fast_model"}
            P->>U: Forward to :9001
        end
        U-->>P: LLM Response
        P-->>C: Response
        P->>CP: Cache store
        CP->>R: Store embedding + response
    end
```

## Connection State Machine (C++ Proxy)

```mermaid
stateDiagram-v2
    [*] --> ACCEPT
    ACCEPT --> READ_REQUEST: New TCP connection
    READ_REQUEST --> PARSE_HEADERS: recv() complete
    PARSE_HEADERS --> FORWARD: Headers parsed
    FORWARD --> READ_RESPONSE: Connected to upstream
    READ_RESPONSE --> WRITE_RESPONSE: Upstream responded
    WRITE_RESPONSE --> [*]: send() complete
    READ_REQUEST --> [*]: Timeout / Error
    FORWARD --> [*]: Upstream unreachable
```

## UDP Heartbeat Protocol

```
Every 2 seconds, each upstream sends:
┌─────────────────────────────────────────────┐
│ UDP Datagram → 127.0.0.1:8081              │
│                                             │
│ {                                           │
│   "port": 9001,                             │
│   "active_requests": 3,                     │
│   "type": "fast",                           │
│   "timestamp": 1695000000.0                 │
│ }                                           │
└─────────────────────────────────────────────┘

Proxy uses this for least-connections load balancing.
Stale heartbeats (>10s) mark upstream as unhealthy.
```

## Data Flow Summary

| Layer | Technology | Responsibility |
|-------|-----------|----------------|
| Data Plane | C++20, epoll | Non-blocking TCP proxy, UDP health receiver, connection state machine |
| Control Plane | Python, FastAPI | Semantic embedding, cache lookup, RAG retrieval, model routing |
| Cache | Redis | Vector similarity storage, prompt-response cache |
| Upstream | aiohttp | Mock LLM completion API, latency simulation |
| Frontend | React, Recharts | Real-time WebSocket telemetry visualization |
