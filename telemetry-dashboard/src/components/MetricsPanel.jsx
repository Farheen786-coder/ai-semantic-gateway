import React from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, PieChart, Pie, Cell,
} from 'recharts';

const tooltipStyle = {
  background: '#FFFFFF',
  border: '1px solid #E5E7EB',
  borderRadius: 6,
  color: '#111111',
  fontSize: 12,
  fontFamily: "'JetBrains Mono', monospace",
};

const COLORS = ['#16A34A', '#DC2626'];

export function MetricsPanel({ latencyHistory, tokensHistory, cacheStats }) {
  const pieData = [
    { name: 'Hits', value: cacheStats.hits || 0 },
    { name: 'Misses', value: cacheStats.misses || 0 },
  ];

  const sectionStyle = {
    background: '#FFFFFF',
    padding: 20,
  };

  const headerStyle = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 16, paddingBottom: 12,
    borderBottom: '1px solid #E5E7EB',
  };

  const titleStyle = {
    fontSize: 13, fontWeight: 600, color: '#111111',
    textTransform: 'uppercase', letterSpacing: '0.05em',
  };

  const badgeStyle = {
    fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
    color: '#555555', padding: '2px 6px',
    border: '1px solid #E5E7EB', borderRadius: 3, background: '#F3F4F6',
  };

  return (
    <div style={{
      display: 'grid', gridTemplateColumns: '1fr 1fr 1fr',
      border: '1px solid #E5E7EB', borderRadius: 6,
      overflow: 'hidden', marginBottom: 24,
    }}>
      {/* Latency Chart */}
      <div style={{ ...sectionStyle, borderRight: '1px solid #E5E7EB' }}>
        <div style={headerStyle}>
          <span style={titleStyle}>Avg Latency</span>
          <span style={badgeStyle}>ms</span>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={latencyHistory}>
            <CartesianGrid stroke="#E5E7EB" strokeDasharray="none" vertical={false} />
            <XAxis dataKey="time" stroke="#555555" fontSize={10}
              fontFamily="JetBrains Mono, monospace" tickLine={false} axisLine={{ stroke: '#E5E7EB' }} />
            <YAxis stroke="#555555" fontSize={10}
              fontFamily="JetBrains Mono, monospace" tickLine={false} axisLine={{ stroke: '#E5E7EB' }} />
            <Tooltip contentStyle={tooltipStyle} />
            <Line type="monotone" dataKey="latency" stroke="#2563EB" strokeWidth={1.5}
              dot={false} activeDot={{ r: 3, fill: '#2563EB', stroke: '#FFFFFF', strokeWidth: 2 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Tokens Saved Chart */}
      <div style={{ ...sectionStyle, borderRight: '1px solid #E5E7EB' }}>
        <div style={headerStyle}>
          <span style={titleStyle}>Tokens Saved</span>
          <span style={badgeStyle}>count</span>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={tokensHistory}>
            <CartesianGrid stroke="#E5E7EB" strokeDasharray="none" vertical={false} />
            <XAxis dataKey="time" stroke="#555555" fontSize={10}
              fontFamily="JetBrains Mono, monospace" tickLine={false} axisLine={{ stroke: '#E5E7EB' }} />
            <YAxis stroke="#555555" fontSize={10}
              fontFamily="JetBrains Mono, monospace" tickLine={false} axisLine={{ stroke: '#E5E7EB' }} />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey="saved" fill="#16A34A" radius={[3, 3, 0, 0]} maxBarSize={24} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Cache Hit Rate */}
      <div style={sectionStyle}>
        <div style={headerStyle}>
          <span style={titleStyle}>Cache Hit Rate</span>
          <span style={badgeStyle}>ratio</span>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={65}
              paddingAngle={2} dataKey="value" stroke="#FFFFFF" strokeWidth={2}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              fontSize={11} fontFamily="JetBrains Mono, monospace">
              {pieData.map((_, index) => (
                <Cell key={index} fill={COLORS[index]} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
