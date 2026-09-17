# 🚀 AI Semantic Gateway

[![Build & Test](https://github.com/Farheen786-coder/ai-semantic-gateway/actions/workflows/build.yml/badge.svg)](https://github.com/Farheen786-coder/ai-semantic-gateway/actions/workflows/build.yml)
![C++20](https://img.shields.io/badge/C%2B%2B-20-blue)
![Python](https://img.shields.io/badge/Python-3.11+-green)
![React](https://img.shields.io/badge/React-19-61DAFB)
![License](https://img.shields.io/badge/License-MIT-yellow)

A high-performance Agentic AI Gateway with semantic caching, RAG-augmented routing, and real-time telemetry.

> **📐 [Architecture Diagrams](docs/architecture.md)** · **🧠 [Design Decisions](DESIGN.md)** · **📊 [Load Test](docs/load-test.js)**

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Client    │────▶│  C++ Proxy       │────▶│  Upstream LLMs  │
│             │     │  (epoll, TCP     │     │  (Mock Fast/    │
│             │◀────│   port 8080)     │◀────│   Heavy)        │
└─────────────┘     └───────┬──────────┘     └────────┬────────┘
                            │                         │
                    ┌───────▼──────────┐              │
                    │  Python Control  │     UDP Heartbeat
                    │  Plane (FastAPI  │     (port 8081)
                    │   port 8000)     │              │
                    └───────┬──────────┘              │
                            │                         │
                    ┌───────▼──────────┐              │
                    │  Redis           │              │
                    │  (Semantic Cache) │              │
                    │  (port 6379)     │              │
                    └──────────────────┘              │
                                                     │
                    ┌──────────────────┐              │
                    │  React Dashboard │◀─────────────┘
                    │  (Vite, Recharts │  WebSocket Telemetry
                    │   port 5173)     │
                    └──────────────────┘
```

## Components

| Component | Technology | Port | Description |
|-----------|-----------|------|-------------|
| Data Plane | C++20, epoll | 8080 (TCP), 8081 (UDP) | Async reverse proxy with state machine |
| Control Plane | Python, FastAPI | 8000 | Semantic cache + RAG routing |
| Mock Fast LLM | Python, aiohttp | 9001 | Low-latency mock model |
| Mock Heavy LLM | Python, aiohttp | 9002 | High-capability mock model |
| Cache | Redis 7 | 6379 | Vector similarity search |
| Dashboard | React, Vite, Recharts | 5173 | Real-time telemetry UI |

## Quick Start

### Docker (Recommended)
```bash
docker-compose up --build
```

### Manual Setup

#### 1. C++ Proxy (Linux only)
```bash
cd cpp-proxy
cmake .
make
./gateway_proxy
```

#### 2. Python Control Plane
```bash
cd python-backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

#### 3. Mock Servers
```bash
cd mock-servers
pip install -r requirements.txt
python mock_llm.py --port 9001 --type fast &
python mock_llm.py --port 9002 --type heavy &
```

#### 4. Telemetry Dashboard
```bash
cd telemetry-dashboard
npm install
npm run dev
```

## API Endpoints

### Control Plane (port 8000)
- `POST /process` - Process prompt (cache check → RAG → route)
- `GET /health` - Health check
- `GET /cache/stats` - Cache statistics
- `DELETE /cache/clear` - Clear cache

### Mock LLMs (ports 9001, 9002)
- `POST /v1/completions` - Generate completion
- `GET /health` - Server health

## Observability

### Prometheus Metrics
```bash
curl http://localhost:8000/metrics
```
Returns Prometheus-compatible metrics:
- `gateway_requests_total` — Total requests processed
- `gateway_cache_hits_total` / `gateway_cache_misses_total` — Cache performance
- `gateway_cache_hit_rate` — Current hit rate gauge
- `gateway_tokens_saved_total` — Tokens saved via caching
- `gateway_requests_by_route{model="fast_model|heavy_model|cache"}` — Routing distribution
- `gateway_uptime_seconds` — Server uptime

### OpenAPI Documentation
FastAPI auto-generates interactive API docs:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Load Testing
```bash
# Install k6: https://k6.io/docs/get-started/installation/
k6 run docs/load-test.js

# Results saved to docs/load-test-results.json
```

## Testing

```bash
# Test control plane
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"prompt": "How does load balancing work?"}'

# Test mock LLM
curl -X POST http://localhost:9001/v1/completions \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Hello world"}'

# Check Prometheus metrics
curl http://localhost:8000/metrics
```

## License

MIT License - see [LICENSE](LICENSE) for details.
