import argparse
import asyncio
import json
import time
import socket
import random
from aiohttp import web


class MockLLMServer:
    def __init__(self, port: int, server_type: str):
        self.port = port
        self.server_type = server_type  # 'fast' or 'heavy'
        self.active_requests = 0
        self.total_requests = 0
        self.start_time = time.time()

    async def handle_completions(self, request: web.Request) -> web.Response:
        self.active_requests += 1
        self.total_requests += 1
        try:
            body = await request.json()
            prompt = body.get("prompt", "")
            
            # Simulate latency based on type and prompt length
            char_count = len(prompt)
            if self.server_type == "fast":
                delay = max(0.05, (char_count / 100) * 0.01)  # 10ms per 100 chars
            else:
                delay = max(0.1, (char_count / 100) * 0.05)   # 50ms per 100 chars
            
            # Cap delay at 3 seconds
            delay = min(delay, 3.0)
            await asyncio.sleep(delay)

            # Generate mock response
            response_text = self._generate_response(prompt)
            
            result = {
                "id": f"mock-{self.server_type}-{self.total_requests}",
                "object": "text_completion",
                "created": int(time.time()),
                "model": f"mock-{self.server_type}-v1",
                "choices": [{
                    "text": response_text,
                    "index": 0,
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": len(response_text.split()),
                    "total_tokens": len(prompt.split()) + len(response_text.split())
                },
                "server_info": {
                    "port": self.port,
                    "type": self.server_type,
                    "latency_ms": round(delay * 1000, 2)
                }
            }
            return web.json_response(result)
        except json.JSONDecodeError:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
        finally:
            self.active_requests -= 1

    async def handle_health(self, request: web.Request) -> web.Response:
        uptime = time.time() - self.start_time
        return web.json_response({
            "status": "healthy",
            "port": self.port,
            "type": self.server_type,
            "active_requests": self.active_requests,
            "total_requests": self.total_requests,
            "uptime_seconds": round(uptime, 2)
        })

    def _generate_response(self, prompt: str) -> str:
        responses = {
            "fast": [
                f"Quick analysis of your query ({len(prompt)} chars): The key concept relates to efficient data processing and optimization strategies.",
                f"Fast response: Based on the input, I recommend implementing a caching layer with TTL-based invalidation for optimal performance.",
                f"Brief summary: Your prompt covers {len(prompt.split())} tokens. The main theme involves system architecture and scalability patterns."
            ],
            "heavy": [
                f"Detailed analysis of your {len(prompt)}-character query: After thorough examination, the prompt raises several interconnected topics. First, regarding the primary subject matter, there are multiple dimensions to consider including performance optimization, scalability patterns, and architectural best practices. The recommended approach involves implementing a multi-layered caching strategy combined with intelligent load balancing. Furthermore, the system should incorporate circuit breaker patterns for resilience and observability hooks for monitoring. In conclusion, a phased implementation approach would yield the best results while minimizing risk.",
                f"Comprehensive response: The analysis of your {len(prompt.split())}-token prompt reveals complex interdependencies between the discussed concepts. A thorough treatment requires examining the theoretical foundations, practical implications, and edge cases. The optimal solution architecture should leverage event-driven patterns with asynchronous processing pipelines, semantic caching for repeated queries, and adaptive routing based on real-time server health metrics."
            ]
        }
        options = responses.get(self.server_type, responses["fast"])
        return random.choice(options)

    async def udp_heartbeat(self):
        """Send UDP heartbeat to the C++ proxy every 2 seconds."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        target = ("127.0.0.1", 8081)
        print(f"[{self.server_type.upper()}] Starting UDP heartbeat to {target}")
        while True:
            try:
                payload = json.dumps({
                    "port": self.port,
                    "active_requests": self.active_requests,
                    "type": self.server_type,
                    "timestamp": time.time()
                }).encode()
                sock.sendto(payload, target)
            except Exception as e:
                print(f"[{self.server_type.upper()}] Heartbeat error: {e}")
            await asyncio.sleep(2)

    async def start_background_tasks(self, app: web.Application):
        app['heartbeat'] = asyncio.create_task(self.udp_heartbeat())

    async def cleanup_background_tasks(self, app: web.Application):
        app['heartbeat'].cancel()
        await app['heartbeat']

    def create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_post('/v1/completions', self.handle_completions)
        app.router.add_get('/health', self.handle_health)
        app.on_startup.append(self.start_background_tasks)
        app.on_cleanup.append(self.cleanup_background_tasks)
        return app


def main():
    parser = argparse.ArgumentParser(description='Mock LLM Server')
    parser.add_argument('--port', type=int, required=True, help='Port to run on')
    parser.add_argument('--type', type=str, choices=['fast', 'heavy'], required=True,
                        help='Server type (fast or heavy)')
    args = parser.parse_args()

    server = MockLLMServer(port=args.port, server_type=args.type)
    app = server.create_app()
    
    print(f"\n{'='*50}")
    print(f"  Mock LLM Server ({args.type.upper()})")
    print(f"  Port: {args.port}")
    print(f"  Endpoints:")
    print(f"    POST /v1/completions")
    print(f"    GET  /health")
    print(f"  UDP Heartbeat -> 127.0.0.1:8081")
    print(f"{'='*50}\n")
    
    web.run_app(app, host='0.0.0.0', port=args.port, print=None)


if __name__ == '__main__':
    main()
