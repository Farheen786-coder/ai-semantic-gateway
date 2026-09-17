import React from 'react';

const typeConfig = {
  cache_hit: { color: '#16A34A', label: 'CACHE HIT' },
  cache_miss: { color: '#D97706', label: 'CACHE MISS' },
  error: { color: '#DC2626', label: 'ERROR' },
};

export function EventLog({ events }) {
  return (
    <div style={{
      background: '#FFFFFF',
      border: '1px solid #E5E7EB',
      borderRadius: 6,
      overflow: 'hidden',
      marginBottom: 24,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px 20px',
        borderBottom: '1px solid #E5E7EB',
      }}>
        <span style={{
          fontSize: 13, fontWeight: 600, color: '#111111',
          textTransform: 'uppercase', letterSpacing: '0.05em',
        }}>Event Log</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
            color: '#555555', padding: '2px 6px',
            border: '1px solid #E5E7EB', borderRadius: 3, background: '#F3F4F6',
          }}>{events.length} events</span>
          <span style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
            color: '#555555', padding: '2px 6px',
            border: '1px solid #E5E7EB', borderRadius: 3, background: '#F3F4F6',
          }}>↵ scroll</span>
        </div>
      </div>

      <div style={{ maxHeight: 320, overflowY: 'auto' }}>
        {/* Table Header */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '80px 100px 80px 100px 1fr',
          gap: 12,
          padding: '10px 20px',
          borderBottom: '1px solid #E5E7EB',
          background: '#F3F4F6',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10,
          fontWeight: 500,
          color: '#555555',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
          position: 'sticky',
          top: 0,
        }}>
          <span>Time</span>
          <span>Status</span>
          <span>Latency</span>
          <span>Tokens</span>
          <span>Route</span>
        </div>

        {events.length === 0 && (
          <div style={{
            padding: 32, textAlign: 'center',
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 12, color: '#555555',
          }}>
            Waiting for events...
          </div>
        )}

        {events.map((event) => {
          const config = typeConfig[event.type] || { color: '#555555', label: event.type };
          return (
            <div key={event.id} style={{
              display: 'grid',
              gridTemplateColumns: '80px 100px 80px 100px 1fr',
              gap: 12,
              padding: '8px 20px',
              borderBottom: '1px solid #E5E7EB',
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 12,
              color: '#111111',
              animation: 'fadeIn 100ms ease-out',
              transition: 'all 100ms ease-out',
            }}>
              <span style={{ color: '#555555' }}>{event.timestamp}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: config.color, flexShrink: 0,
                }} />
                <span style={{ color: config.color, fontWeight: 500, fontSize: 10 }}>
                  {config.label}
                </span>
              </span>
              <span>{event.latency?.toFixed(0)}ms</span>
              <span>
                {event.tokens_saved > 0
                  ? <span style={{ color: '#16A34A' }}>+{event.tokens_saved}</span>
                  : <span style={{ color: '#555555' }}>—</span>
                }
              </span>
              <span style={{ color: '#2563EB' }}>→ {event.model}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
