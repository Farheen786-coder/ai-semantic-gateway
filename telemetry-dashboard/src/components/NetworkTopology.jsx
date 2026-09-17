import React from 'react';

export function NetworkTopology({ activeNode }) {
  const nodes = [
    { id: 'client', label: 'Client', x: 20, y: 50 },
    { id: 'gateway', label: 'Gateway', x: 170, y: 50 },
    { id: 'redis', label: 'Redis Cache', x: 320, y: 20 },
    { id: 'upstream', label: 'Upstream LLM', x: 320, y: 80 },
  ];

  const edges = [
    { from: 'client', to: 'gateway' },
    { from: 'gateway', to: 'redis' },
    { from: 'gateway', to: 'upstream' },
  ];

  const getCenter = (n) => ({ cx: n.x + 55, cy: n.y + 16 });

  const isActive = (id) => activeNode === id;

  return (
    <div style={{
      background: '#FFFFFF',
      border: '1px solid #E5E7EB',
      borderRadius: 6,
      padding: 20,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 16, paddingBottom: 12,
        borderBottom: '1px solid #E5E7EB',
      }}>
        <span style={{
          fontSize: 13, fontWeight: 600, color: '#111111',
          textTransform: 'uppercase', letterSpacing: '0.05em',
        }}>Network Topology</span>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
          color: '#555555', padding: '2px 6px',
          border: '1px solid #E5E7EB', borderRadius: 3, background: '#F3F4F6',
        }}>LIVE</span>
      </div>
      <svg width="100%" viewBox="0 0 440 120" style={{ maxHeight: 130 }}>
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#E5E7EB" />
          </marker>
        </defs>

        {edges.map((edge, i) => {
          const from = nodes.find(n => n.id === edge.from);
          const to = nodes.find(n => n.id === edge.to);
          const fc = getCenter(from);
          const tc = getCenter(to);
          return (
            <line key={i} x1={fc.cx} y1={fc.cy} x2={tc.cx} y2={tc.cy}
              stroke="#E5E7EB" strokeWidth={1.5}
              markerEnd="url(#arrow)" />
          );
        })}

        {nodes.map((node) => {
          const active = isActive(node.id);
          const borderColor = active
            ? (node.id === 'redis' ? '#16A34A' : '#2563EB')
            : '#E5E7EB';
          const bg = active ? '#F3F4F6' : '#FFFFFF';

          return (
            <g key={node.id}>
              <rect x={node.x} y={node.y} width={110} height={32}
                rx={6} fill={bg}
                stroke={borderColor} strokeWidth={active ? 2 : 1}
                style={{ transition: 'all 100ms ease-out' }}
              />
              {active && (
                <circle cx={node.x + 10} cy={node.y + 16} r={3}
                  fill={node.id === 'redis' ? '#16A34A' : '#2563EB'} />
              )}
              <text
                x={node.x + 55} y={node.y + 20}
                textAnchor="middle" fill="#111111"
                fontSize={11} fontWeight={600}
                fontFamily="Inter, system-ui, sans-serif"
              >
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
