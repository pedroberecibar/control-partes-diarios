import { useState } from 'react';
import { Icon, StatusChip, TRAZA_CONFIG } from '../components/Icon';

// 8 semanas de datos históricos por traza
const SEMANAS = ['W1','W2','W3','W4','W5','W6','W7','W8'];

const SERIES = [
  {
    traza: 'Original OK',
    values: [42, 45, 48, 44, 51, 47, 50, 55],
    color: '#1d8348',
    dash: '',
  },
  {
    traza: 'Corregido Medidor',
    values: [14, 12, 15, 11, 13, 16, 14, 12],
    color: '#e6910a',
    dash: '4,2',
  },
  {
    traza: 'Sin Orden Asociada',
    values: [9, 11, 8, 10, 7, 9, 11, 8],
    color: '#c0392b',
    dash: '',
  },
  {
    traza: 'Repetido X Sumi',
    values: [7, 6, 8, 7, 9, 6, 7, 8],
    color: '#9b2335',
    dash: '2,2',
  },
  {
    traza: 'Error Sumi Nro Med',
    values: [5, 7, 6, 8, 5, 7, 6, 5],
    color: '#e67e22',
    dash: '4,2',
  },
  {
    traza: 'Corregido Orden',
    values: [6, 5, 7, 6, 8, 5, 6, 7],
    color: '#f39c12',
    dash: '3,3',
  },
];

function MultiLineChart({ series, width = 580, height = 220 }) {
  const allVals = series.flatMap((s) => s.values);
  const minV = 0;
  const maxV = Math.max(...allVals) + 8;
  const PAD = { top: 16, right: 20, bottom: 28, left: 32 };
  const W = width - PAD.left - PAD.right;
  const H = height - PAD.top - PAD.bottom;
  const weeks = series[0].values.length;

  function tx(i) { return PAD.left + (i / (weeks - 1)) * W; }
  function ty(v) { return PAD.top + H - ((v - minV) / (maxV - minV)) * H; }

  const yTicks = [0, 20, 40, 60];

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block', overflow: 'visible' }}>
      {/* grid lines */}
      {yTicks.map((v) => (
        <g key={v}>
          <line x1={PAD.left} y1={ty(v)} x2={PAD.left + W} y2={ty(v)} stroke="#eaeeec" strokeWidth={1} />
          <text x={PAD.left - 5} y={ty(v) + 3.5} textAnchor="end" fontSize={9} fill="#b5bfbb" fontFamily="JetBrains Mono">{v}</text>
        </g>
      ))}

      {/* x axis labels */}
      {SEMANAS.map((w, i) => (
        <text key={w} x={tx(i)} y={height - 4} textAnchor="middle" fontSize={9.5} fill="#8f9c97" fontFamily="JetBrains Mono">{w}</text>
      ))}

      {/* series */}
      {series.map((s) => {
        const pts = s.values.map((v, i) => [tx(i), ty(v)]);
        const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
        return (
          <g key={s.traza}>
            <path d={d} fill="none" stroke={s.color} strokeWidth={2} strokeDasharray={s.dash} strokeLinejoin="round" />
            {pts.map(([x, y], i) => (
              <circle key={i} cx={x} cy={y} r={2.5} fill={s.color} stroke="white" strokeWidth={1} />
            ))}
          </g>
        );
      })}
    </svg>
  );
}

function TrendChip({ values }) {
  const last = values[values.length - 1];
  const prev = values[values.length - 2];
  const delta = last - prev;
  if (delta === 0) return <span style={{ fontSize: 10.5, color: '#8f9c97' }}>=</span>;
  const up = delta > 0;
  return (
    <span style={{ fontSize: 10.5, fontWeight: 700, color: up ? '#c0392b' : '#1d8348', display: 'inline-flex', alignItems: 'center', gap: 2 }}>
      <Icon name={up ? 'trending-up' : 'chevron-down'} size={11} color={up ? '#c0392b' : '#1d8348'} />
      {up ? '+' : ''}{delta}
    </span>
  );
}

export function DashboardEvolucion() {
  const [selectedSerie, setSelectedSerie] = useState(null);

  const visibleSeries = selectedSerie
    ? SERIES.filter((s) => s.traza === selectedSerie)
    : SERIES;

  const totalLastWeek  = SERIES.reduce((s, r) => s + r.values[r.values.length - 1], 0);
  const totalFirstWeek = SERIES.reduce((s, r) => s + r.values[0], 0);
  const deltaTot  = totalLastWeek - totalFirstWeek;
  const okLastW   = SERIES.find((s) => s.traza === 'Original OK')?.values.slice(-1)[0] || 0;
  const issLastW  = totalLastWeek - okLastW;

  const dS = {
    root:      { padding: 20, overflow: 'auto', height: '100%', boxSizing: 'border-box', background: '#f5f7f6' },
    hdr:       { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 },
    title:     { fontSize: 17, fontWeight: 700, color: '#111614' },
    sub:       { fontSize: 12, color: '#8f9c97', marginTop: 2 },
    kpiRow:    { display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 18 },
    kpiCard:   { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, padding: '14px 16px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    kpiLabel:  { fontSize: 10.5, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 },
    kpiVal:    { fontSize: 22, fontWeight: 700, lineHeight: 1.1 },
    kpiSub:    { fontSize: 11, color: '#8f9c97', marginTop: 3 },
    grid:      { display: 'grid', gridTemplateColumns: '1fr 320px', gap: 14 },
    card:      { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    cardHdr:   { padding: '10px 16px', borderBottom: '1px solid #eaeeec', background: '#fafcfb', display: 'flex', alignItems: 'center', gap: 8 },
    cardTitle: { fontSize: 12, fontWeight: 700, color: '#2f3733', flex: 1 },
    cardBody:  { padding: 16 },
    table:     { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
    th:        { padding: '7px 12px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10.5, letterSpacing: '0.04em', whiteSpace: 'nowrap' },
    td:        { padding: '7px 12px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', whiteSpace: 'nowrap', verticalAlign: 'middle' },
    mono:      { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
    legItem:   { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid #f5f7f6', cursor: 'pointer', borderRadius: 4 },
  };

  const kpis = [
    { label: 'Partes últ. semana', value: totalLastWeek, color: '#111614', sub: 'W8 — semana en curso' },
    { label: 'Original OK (W8)',   value: okLastW,        color: '#155a2e', sub: `${((okLastW/totalLastWeek)*100).toFixed(1)}% del total` },
    { label: 'Con obs. (W8)',      value: issLastW,       color: '#7a4a00', sub: `${((issLastW/totalLastWeek)*100).toFixed(1)}% requieren revisión` },
    { label: 'Δ vs. W1',          value: `${deltaTot > 0 ? '+' : ''}${deltaTot}`, color: deltaTot > 0 ? '#155a2e' : '#7a1c1c', sub: 'variación total de volumen' },
  ];

  return (
    <div style={dS.root}>
      <div style={dS.hdr}>
        <div>
          <div style={dS.title}>Evolución de Observaciones</div>
          <div style={dS.sub}>Módulo C — Dashboard BI · Tendencia semanal por traza de calidad</div>
        </div>
        <button style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 11px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, fontWeight: 600, color: '#2f3733', cursor: 'pointer' }}>
          <Icon name="download" size={13} /> Exportar
        </button>
      </div>

      <div style={dS.kpiRow}>
        {kpis.map((k) => (
          <div key={k.label} style={dS.kpiCard}>
            <div style={dS.kpiLabel}>{k.label}</div>
            <div style={{ ...dS.kpiVal, color: k.color }}>{k.value}</div>
            <div style={dS.kpiSub}>{k.sub}</div>
          </div>
        ))}
      </div>

      <div style={{ ...dS.card, marginBottom: 14 }}>
        <div style={dS.cardHdr}>
          <Icon name="trending-up" size={14} color="#6b7772" />
          <span style={dS.cardTitle}>Partes por Traza — 8 semanas</span>
          {selectedSerie && (
            <button
              style={{ fontSize: 11, color: '#8f9c97', border: 'none', background: 'transparent', cursor: 'pointer' }}
              onClick={() => setSelectedSerie(null)}
            >
              Ver todas
            </button>
          )}
        </div>
        <div style={{ ...dS.cardBody, overflowX: 'auto' }}>
          <MultiLineChart series={visibleSeries} width={680} height={220} />
        </div>
      </div>

      <div style={dS.grid}>
        <div style={dS.card}>
          <div style={dS.cardHdr}>
            <Icon name="activity" size={14} color="#6b7772" />
            <span style={dS.cardTitle}>Detalle por Traza — W1 a W8</span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={dS.table}>
              <thead>
                <tr>
                  <th style={dS.th}>Traza</th>
                  {SEMANAS.map((w) => (<th key={w} style={{ ...dS.th, textAlign: 'right' }}>{w}</th>))}
                  <th style={{ ...dS.th, textAlign: 'right' }}>Total</th>
                  <th style={{ ...dS.th, textAlign: 'center' }}>Δ W7→W8</th>
                </tr>
              </thead>
              <tbody>
                {SERIES.map((s, i) => {
                  const total = s.values.reduce((a, b) => a + b, 0);
                  const tc = TRAZA_CONFIG[s.traza] || {};
                  const isActive = selectedSerie === s.traza;
                  return (
                    <tr
                      key={s.traza}
                      style={{ background: isActive ? '#edf5f0' : i % 2 === 0 ? 'white' : '#fafcfb', cursor: 'pointer' }}
                      onClick={() => setSelectedSerie(isActive ? null : s.traza)}
                    >
                      <td style={dS.td}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ width: 10, height: 3, background: s.color, borderRadius: 2, flexShrink: 0 }} />
                          <StatusChip label={s.traza} config={tc} size="xs" />
                        </div>
                      </td>
                      {s.values.map((v, wi) => (
                        <td key={wi} style={{ ...dS.td, ...dS.mono, textAlign: 'right', color: '#4a5550' }}>{v}</td>
                      ))}
                      <td style={{ ...dS.td, ...dS.mono, textAlign: 'right', fontWeight: 700, color: '#111614' }}>{total}</td>
                      <td style={{ ...dS.td, textAlign: 'center' }}><TrendChip values={s.values} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div style={dS.card}>
          <div style={dS.cardHdr}>
            <Icon name="layers" size={14} color="#6b7772" />
            <span style={dS.cardTitle}>Leyenda — click para filtrar</span>
          </div>
          <div style={{ padding: '8px 16px' }}>
            {SERIES.map((s) => {
              const tc   = TRAZA_CONFIG[s.traza] || {};
              const last = s.values[s.values.length - 1];
              const total = s.values.reduce((a, b) => a + b, 0);
              const isActive = selectedSerie === s.traza;
              return (
                <div
                  key={s.traza}
                  style={{ ...dS.legItem, background: isActive ? '#edf5f0' : 'transparent', padding: '8px 6px', transition: 'background 0.1s' }}
                  onClick={() => setSelectedSerie(isActive ? null : s.traza)}
                  onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = '#f5f7f6'; }}
                  onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = 'transparent'; }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <div style={{ width: 28, height: 3, background: s.color, borderRadius: 2, marginBottom: 2 }} />
                    {s.dash && <div style={{ width: 28, height: 1, borderTop: `2px dashed ${s.color}`, opacity: 0.5 }} />}
                  </div>
                  <div style={{ flex: 1 }}>
                    <StatusChip label={s.traza} config={tc} size="xs" />
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, fontWeight: 700, color: '#2f3733' }}>{last}</div>
                    <div style={{ fontSize: 10, color: '#8f9c97' }}>tot. {total}</div>
                  </div>
                  <TrendChip values={s.values} />
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
