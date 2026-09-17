import React from 'react';
import { useGatewayTelemetry } from './hooks/useGatewayTelemetry';
import { NetworkTopology } from './components/NetworkTopology';
import { MetricsPanel } from './components/MetricsPanel';
import { EventLog } from './components/EventLog';
import './App.css';

function App() {
  const { events, latencyHistory, tokensHistory, cacheStats, activeNode, connected } = useGatewayTelemetry();
  const total = cacheStats.hits + cacheStats.misses;
  const hitRate = total > 0 ? ((cacheStats.hits / total) * 100).toFixed(0) : '0';

  return (
    <div className="app">
      {/* ── Header Navbar ── */}
      <header className="header">
        <div className="header-left">
          <h1>AI Gateway</h1>
          <span className="version-tag">v1.0.0</span>
        </div>
        <div className="header-right">
          <div className="status-indicator">
            <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`} />
            <span>{connected ? '● System Active' : '● Demo Mode'}</span>
          </div>
          <div className="stats-row">
            <span>{total} requests</span>
            <span>{hitRate}% hit rate</span>
          </div>
        </div>
      </header>

      {/* ── Hero Segment ── */}
      <div className="hero">
        <div className="hero-text">
          <h2>Real-time Telemetry &<br/>Observability Dashboard</h2>
          <p>
            Live metrics from the semantic caching layer, RAG pipeline routing,
            and upstream LLM health. Monitoring cache efficiency, token savings,
            and request latency across the distributed gateway infrastructure.
          </p>
        </div>
        <NetworkTopology activeNode={activeNode} />
      </div>

      {/* ── Metrics Grid ── */}
      <MetricsPanel latencyHistory={latencyHistory} tokensHistory={tokensHistory} cacheStats={cacheStats} />

      {/* ── Event Log ── */}
      <EventLog events={events} />
    </div>
  );
}

export default App;
