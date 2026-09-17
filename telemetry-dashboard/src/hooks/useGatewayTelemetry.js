import { useState, useEffect, useCallback, useRef } from 'react';

const MOCK_EVENTS = [
  { type: 'cache_hit', latency: 12, tokens_saved: 150, model: 'fast_model' },
  { type: 'cache_miss', latency: 245, tokens_saved: 0, model: 'heavy_model' },
  { type: 'cache_hit', latency: 8, tokens_saved: 200, model: 'fast_model' },
  { type: 'cache_miss', latency: 180, tokens_saved: 0, model: 'fast_model' },
  { type: 'cache_hit', latency: 15, tokens_saved: 120, model: 'fast_model' },
  { type: 'cache_miss', latency: 320, tokens_saved: 0, model: 'heavy_model' },
  { type: 'cache_hit', latency: 5, tokens_saved: 300, model: 'fast_model' },
  { type: 'cache_miss', latency: 275, tokens_saved: 0, model: 'heavy_model' },
];

export function useGatewayTelemetry(wsUrl = 'ws://localhost:8080/telemetry') {
  const [events, setEvents] = useState([]);
  const [latencyHistory, setLatencyHistory] = useState([]);
  const [tokensHistory, setTokensHistory] = useState([]);
  const [cacheStats, setCacheStats] = useState({ hits: 0, misses: 0 });
  const [activeNode, setActiveNode] = useState(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const mockIndexRef = useRef(0);

  const processEvent = useCallback((event) => {
    const timestamp = new Date().toLocaleTimeString();
    const enrichedEvent = { ...event, timestamp, id: Date.now() + Math.random() };

    setEvents(prev => [enrichedEvent, ...prev].slice(0, 50));

    setLatencyHistory(prev => [
      ...prev,
      { time: timestamp, latency: event.latency, type: event.type }
    ].slice(-30));

    setTokensHistory(prev => [
      ...prev,
      { time: timestamp, saved: event.tokens_saved, model: event.model }
    ].slice(-20));

    setCacheStats(prev => ({
      hits: prev.hits + (event.type === 'cache_hit' ? 1 : 0),
      misses: prev.misses + (event.type === 'cache_miss' ? 1 : 0),
    }));

    // Animate nodes based on event
    if (event.type === 'cache_hit') {
      setActiveNode('redis');
    } else {
      setActiveNode('upstream');
    }
    setTimeout(() => setActiveNode(null), 1000);
  }, []);

  useEffect(() => {
    // Try WebSocket connection
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onmessage = (msg) => {
        try {
          const event = JSON.parse(msg.data);
          processEvent(event);
        } catch (e) { /* ignore parse errors */ }
      };
      ws.onclose = () => setConnected(false);
      ws.onerror = () => {
        setConnected(false);
        ws.close();
      };
    } catch (e) {
      setConnected(false);
    }

    // Fallback: generate mock data
    const mockInterval = setInterval(() => {
      const event = { ...MOCK_EVENTS[mockIndexRef.current % MOCK_EVENTS.length] };
      event.latency += Math.random() * 30 - 15; // Add jitter
      event.tokens_saved += Math.floor(Math.random() * 50);
      mockIndexRef.current++;
      processEvent(event);
    }, 2000);

    return () => {
      clearInterval(mockInterval);
      if (wsRef.current) wsRef.current.close();
    };
  }, [wsUrl, processEvent]);

  return { events, latencyHistory, tokensHistory, cacheStats, activeNode, connected };
}
