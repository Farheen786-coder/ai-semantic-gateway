// k6 Load Test for AI Semantic Gateway
// Run: k6 run docs/load-test.js
// Install: https://k6.io/docs/get-started/installation/

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const cacheHitRate = new Rate('cache_hit_rate');
const processLatency = new Trend('process_latency', true);

export const options = {
  stages: [
    { duration: '10s', target: 10 },   // Ramp up
    { duration: '30s', target: 50 },   // Sustained load
    { duration: '10s', target: 100 },  // Peak
    { duration: '10s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],   // 95% of requests under 500ms
    cache_hit_rate: ['rate>0.3'],       // At least 30% cache hit rate
  },
};

const PROMPTS = [
  'How does load balancing work?',
  'Explain rate limiting strategies',
  'What is semantic caching?',
  'How to optimize LLM token usage?',
  'Describe API gateway security best practices',
  'What is round-robin load balancing?',       // Similar to prompt 1
  'Explain API rate limiting',                  // Similar to prompt 2
  'How does semantic cache work?',              // Similar to prompt 3
  'Token optimization for large language models', // Similar to prompt 4
  'API gateway auth and security',              // Similar to prompt 5
];

export default function () {
  const prompt = PROMPTS[Math.floor(Math.random() * PROMPTS.length)];

  // Test /process endpoint
  const processRes = http.post(
    'http://localhost:8000/process',
    JSON.stringify({ prompt }),
    { headers: { 'Content-Type': 'application/json' } }
  );

  check(processRes, {
    'process returns 200': (r) => r.status === 200,
    'has routing field': (r) => JSON.parse(r.body).routing !== undefined,
  });

  if (processRes.status === 200) {
    const body = JSON.parse(processRes.body);
    cacheHitRate.add(body.cache_hit);
    processLatency.add(processRes.timings.duration);
  }

  // Test /health endpoint
  const healthRes = http.get('http://localhost:8000/health');
  check(healthRes, { 'health returns 200': (r) => r.status === 200 });

  // Test /metrics endpoint
  const metricsRes = http.get('http://localhost:8000/metrics');
  check(metricsRes, {
    'metrics returns 200': (r) => r.status === 200,
    'metrics has prometheus format': (r) => r.body.includes('gateway_requests_total'),
  });

  sleep(0.1);
}

export function handleSummary(data) {
  return {
    'docs/load-test-results.json': JSON.stringify(data, null, 2),
  };
}
