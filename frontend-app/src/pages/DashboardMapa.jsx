import { useState } from 'react';
import { Icon } from '../components/Icon';

const ZONAS = [
  { id: 'no', label: 'Nor-Oeste',  partes: 52,  issues: 5,  col: 0, row: 0 },
  { id: 'n',  label: 'Norte',      partes: 78,  issues: 9,  col: 1, row: 0 },
  { id: 'ne', label: 'Nor-Este',   partes: 45,  issues: 8,  col: 2, row: 0 },
  { id: 'o',  label: 'Oeste',      partes: 71,  issues: 11, col: 0, row: 1 },
  { id: 'c',  label: 'Centro',     partes: 124, issues: 21, col: 1, row: 1 },
  { id: 'e',  label: 'Este',       partes: 63,  issues: 7,  col: 2, row: 1 },
  { id: 'so', label: 'Sur-Oeste',  partes: 41,  issues: 4,  col: 0, row: 2 },
  { id: 's',  label: 'Sur',        partes: 89,  issues: 8,  col: 1, row: 2 },
  { id: 'se', label: 'Sur-Este',   partes: 38,  issues: 6,  col: 2, row: 2 },
];

function pctOk(z) { return (((z.partes - z.issues) / z.partes) * 100).toFixed(1); }

function heatColor(pct) {
  if (pct >= 90) return { bg: '#d4edda', text: '#155a2e', border: '#a8d9c0' };
  if (pct >= 84) return { bg: '#fff3cd', text: '#7a4a00', border: '#fcd975' };
  return { bg: '#fde8e8', text: '#7a1c1c', border: '#f5b7b1' };
}

function ZoneGrid({ zones, selected, onSelect }) {
  const CELL = 108;
  const GAP  = 6;
  const W = 3 * CELL + 2 * GAP;
  const H = 3 * CELL + 2 * GAP;

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: 'block' }}>
      {/* compass */}
      <text x={W / 2} y={14} textAnchor="middle" fontSize={11} fill="#8f9c97" fontFamily="Plus Jakarta Sans" fontWeight="600">N</text>

      {zones.map((z) => {
        const x = z.col * (CELL + GAP);
        const y = z.row * (CELL + GAP) + 18;
        const pct = parseFloat(pctOk(z));
        const c = heatColor(pct);
        const isSelected = selected === z.id;

        return (
          <g key={z.id} style={{ cursor: 'pointer' }} onClick={() => onSelect(isSelected ? null : z.id)}>
            <rect
              x={x} y={y} width={CELL} height={CELL}
              rx={6} ry={6}
              fill={isSelected ? '#124e2f' : c.bg}
              stroke={isSelected ? '#0a3320' : c.border}
              strokeWidth={isSelected ? 2 : 1}
              style={{ transition: 'all 0.15s' }}
            />
            <text x={x + CELL / 2} y={y + 22} textAnchor="middle" fontSize={10} fill={isSelected ? 'rgba(255,255,255,0.7)' : '#8f9c97'} fontFamily="Plus Jakarta Sans" fontWeight="600">
              {z.label}
            </text>
            <text x={x + CELL / 2} y={y + 48} textAnchor="middle" fontSize={22} fill={isSelected ? 'white' : c.text} fontFamily="Plus Jakarta Sans" fontWeight="700">
              {z.partes}
            </text>
            <text x={x + CELL / 2} y={y + 64} textAnchor="middle" fontSize={9.5} fill={isSelected ? 'rgba(255,255,255,0.6)' : '#8f9c97'} fontFamily="Plus Jakarta Sans">
              partes
            </text>
            <text x={x + CELL / 2} y={y + 85} textAnchor="middle" fontSize={13} fill={isSelected ? '#a8d9c0' : c.text} fontFamily="JetBrains Mono" fontWeight="700">
              {pct}%
            </text>
            <text x={x + CELL / 2} y={y + 98} textAnchor="middle" fontSize={9} fill={isSelected ? 'rgba(255,255,255,0.5)' : '#8f9c97'} fontFamily="Plus Jakarta Sans">
              calidad
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function DashboardMapa() {
  const [selected, setSelected] = useState(null);
  const [metric, setMetric]     = useState('partes');

  const selZona  = selected ? ZONAS.find((z) => z.id === selected) : null;
  const totalP   = ZONAS.reduce((s, z) => s + z.partes, 0);
  const totalIss = ZONAS.reduce((s, z) => s + z.issues, 0);
  const avgOk    = (((totalP - totalIss) / totalP) * 100).toFixed(1);
  const topZona  = [...ZONAS].sort((a, b) => b.partes - a.partes)[0];

  const dS = {
    root:       { padding: 20, overflow: 'auto', height: '100%', boxSizing: 'border-box', background: '#f5f7f6' },
    hdr:        { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 },
    title:      { fontSize: 17, fontWeight: 700, color: '#111614' },
    sub:        { fontSize: 12, color: '#8f9c97', marginTop: 2 },
    kpiRow:     { display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 18 },
    kpiCard:    { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, padding: '14px 16px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    kpiLabel:   { fontSize: 10.5, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 },
    kpiVal:     { fontSize: 22, fontWeight: 700, lineHeight: 1.1 },
    kpiSub:     { fontSize: 11, color: '#8f9c97', marginTop: 3 },
    body:       { display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 16, alignItems: 'start' },
    mapCard:    { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, boxShadow: '0 1px 3px rgba(0,0,0,0.05)', overflow: 'hidden' },
    cardHdr:    { padding: '10px 16px', borderBottom: '1px solid #eaeeec', background: '#fafcfb', display: 'flex', alignItems: 'center', gap: 8 },
    cardTitle:  { fontSize: 12, fontWeight: 700, color: '#2f3733', flex: 1 },
    cardBody:   { padding: 16 },
    legend:     { display: 'flex', gap: 14, marginTop: 12 },
    table:      { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
    th:         { padding: '7px 12px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10.5, letterSpacing: '0.04em', whiteSpace: 'nowrap' },
    td:         { padding: '7px 12px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', whiteSpace: 'nowrap', verticalAlign: 'middle' },
    mono:       { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
    progWrap:   { width: 80, height: 5, background: '#eaeeec', borderRadius: 3, overflow: 'hidden', display: 'inline-block' },
    metricBtn:  { padding: '4px 10px', border: '1px solid #eaeeec', borderRadius: 3, fontSize: 11.5, fontWeight: 500, cursor: 'pointer', transition: 'all 0.1s' },
  };

  const kpis = [
    { label: 'Zonas activas',     value: ZONAS.length,    color: '#111614', sub: 'región Córdoba metropolitana' },
    { label: 'Total suministros', value: totalP,          color: '#111614', sub: 'partes procesados este mes'   },
    { label: 'Calidad promedio',  value: `${avgOk}%`,     color: '#155a2e', sub: 'sin observaciones críticas'   },
    { label: 'Zona más activa',   value: topZona.label,   color: '#124e2f', sub: `${topZona.partes} partes · ${pctOk(topZona)}% OK` },
  ];

  const sorted = [...ZONAS].sort((a, b) => metric === 'partes' ? b.partes - a.partes : b.issues - a.issues);

  return (
    <div style={dS.root}>
      <div style={dS.hdr}>
        <div>
          <div style={dS.title}>Mapa de Suministros</div>
          <div style={dS.sub}>Módulo C — Dashboard BI · Distribución geográfica por zona</div>
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

      <div style={dS.body}>
        <div style={dS.mapCard}>
          <div style={dS.cardHdr}>
            <Icon name="map-pin" size={14} color="#6b7772" />
            <span style={dS.cardTitle}>Heatmap de Calidad por Zona</span>
            <span style={{ fontSize: 10.5, color: '#8f9c97' }}>Clic para seleccionar</span>
          </div>
          <div style={{ ...dS.cardBody, paddingBottom: 10 }}>
            <ZoneGrid zones={ZONAS} selected={selected} onSelect={setSelected} />
            <div style={{ ...dS.legend, justifyContent: 'center' }}>
              {[['#d4edda', '#a8d9c0', '#155a2e', '≥90% OK'], ['#fff3cd', '#fcd975', '#7a4a00', '84–89%'], ['#fde8e8', '#f5b7b1', '#7a1c1c', '<84%']].map(([bg, border, text, label]) => (
                <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <div style={{ width: 14, height: 14, background: bg, border: `1px solid ${border}`, borderRadius: 3 }} />
                  <span style={{ fontSize: 10.5, color: '#6b7772' }}>{label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div>
          {selZona && (
            <div style={{ ...dS.mapCard, marginBottom: 14, border: '1px solid #a8d9c0' }}>
              <div style={{ ...dS.cardHdr, background: '#edf5f0', borderColor: '#a8d9c0' }}>
                <Icon name="map-pin" size={14} color="#124e2f" />
                <span style={{ ...dS.cardTitle, color: '#124e2f' }}>Zona seleccionada — {selZona.label}</span>
                <button
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#8f9c97', display: 'flex', alignItems: 'center' }}
                  onClick={() => setSelected(null)}
                >
                  <Icon name="x" size={14} color="#8f9c97" />
                </button>
              </div>
              <div style={{ ...dS.cardBody, display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
                {[
                  ['Partes totales',  selZona.partes,                             '#111614'],
                  ['Observaciones',   selZona.issues,                             '#7a4a00'],
                  ['Calidad',         `${pctOk(selZona)}%`,                       '#155a2e'],
                  ['OK sin obs.',     selZona.partes - selZona.issues,            '#155a2e'],
                  ['Tasa de issues',  `${((selZona.issues / selZona.partes)*100).toFixed(1)}%`, '#7a1c1c'],
                  ['Rank volumen',    `#${ZONAS.slice().sort((a,b)=>b.partes-a.partes).findIndex(z=>z.id===selZona.id)+1} / ${ZONAS.length}`, '#124e2f'],
                ].map(([l, v, c]) => (
                  <div key={l}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>{l}</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: c, fontFamily: "'JetBrains Mono', monospace" }}>{v}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div style={dS.mapCard}>
            <div style={dS.cardHdr}>
              <Icon name="bar-chart" size={14} color="#6b7772" />
              <span style={dS.cardTitle}>Detalle por Zona</span>
              <div style={{ display: 'flex', gap: 4 }}>
                {[['partes', 'Volumen'], ['issues', 'Issues']].map(([m, l]) => (
                  <button
                    key={m}
                    style={{ ...dS.metricBtn, background: metric === m ? '#124e2f' : 'white', color: metric === m ? 'white' : '#6b7772', borderColor: metric === m ? '#124e2f' : '#eaeeec' }}
                    onClick={() => setMetric(m)}
                  >
                    {l}
                  </button>
                ))}
              </div>
            </div>
            <table style={dS.table}>
              <thead>
                <tr>
                  {['Zona', 'Partes', 'Issues', '% Calidad', 'Distribución'].map((h) => (
                    <th key={h} style={dS.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((z, i) => {
                  const pct = parseFloat(pctOk(z));
                  const c   = heatColor(pct);
                  const isS = selected === z.id;
                  return (
                    <tr
                      key={z.id}
                      style={{ background: isS ? '#edf5f0' : i % 2 === 0 ? 'white' : '#fafcfb', cursor: 'pointer' }}
                      onClick={() => setSelected(isS ? null : z.id)}
                    >
                      <td style={{ ...dS.td, fontWeight: 600, color: isS ? '#124e2f' : '#2f3733' }}>{z.label}</td>
                      <td style={{ ...dS.td, ...dS.mono, textAlign: 'right', fontWeight: 700 }}>{z.partes}</td>
                      <td style={{ ...dS.td, ...dS.mono, textAlign: 'right', color: z.issues > 10 ? '#7a1c1c' : '#7a4a00', fontWeight: z.issues > 10 ? 700 : 400 }}>{z.issues}</td>
                      <td style={dS.td}>
                        <span style={{ ...dS.mono, fontWeight: 700, color: c.text }}>{pct}%</span>
                      </td>
                      <td style={dS.td}>
                        <div style={dS.progWrap}>
                          <div style={{ width: `${pct}%`, height: '100%', background: pct >= 90 ? '#1d8348' : pct >= 84 ? '#e6910a' : '#c0392b', borderRadius: 3 }} />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
