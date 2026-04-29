import { useState } from 'react';
import { Icon, StatusChip, TRAZA_CONFIG } from '../components/Icon';

const DATA_MENSUAL = [
  { mes: 'Oct', total: 387, aprobados: 351, corregidos: 48, rechazados: 36, efectividad: 90.7 },
  { mes: 'Nov', total: 402, aprobados: 369, corregidos: 52, rechazados: 33, efectividad: 91.8 },
  { mes: 'Dic', total: 318, aprobados: 295, corregidos: 41, rechazados: 23, efectividad: 92.8 },
  { mes: 'Ene', total: 445, aprobados: 412, corregidos: 58, rechazados: 33, efectividad: 92.6 },
  { mes: 'Feb', total: 389, aprobados: 354, corregidos: 49, rechazados: 35, efectividad: 91.0 },
  { mes: 'Mar', total: 421, aprobados: 388, corregidos: 63, rechazados: 33, efectividad: 92.2 },
  { mes: 'Abr', total: 400, aprobados: 368, corregidos: 71, rechazados: 32, efectividad: 92.0 },
];

const TRAZAS_DIST = [
  { traza: 'Original OK',            count: 195, pct: 48.8, config: TRAZA_CONFIG['Original OK'] },
  { traza: 'Corregido Medidor',      count: 52,  pct: 13.0, config: TRAZA_CONFIG['Corregido Medidor'] },
  { traza: 'Corregido Orden',        count: 19,  pct: 4.8,  config: TRAZA_CONFIG['Corregido Orden'] },
  { traza: 'Sin Orden Asociada',     count: 48,  pct: 12.0, config: TRAZA_CONFIG['Sin Orden Asociada'] },
  { traza: 'Repetido X Sumi',        count: 31,  pct: 7.8,  config: TRAZA_CONFIG['Repetido X Sumi'] },
  { traza: 'Error Sumi Nro Med',     count: 25,  pct: 6.3,  config: TRAZA_CONFIG['Error Sumi Nro Med'] },
  { traza: 'Otro Origen',            count: 18,  pct: 4.5,  config: TRAZA_CONFIG['Otro Origen'] },
  { traza: 'Informado-No Ejecutado', count: 12,  pct: 3.0,  config: TRAZA_CONFIG['Informado-No Ejecutado'] },
];

const COD_EPEC_TABLE = [
  { cod: '1001', desc: 'Cambio de Medidor — BT Estándar', count: 112, ok: 108, corr: 4,  pct_ok: 96.4 },
  { cod: '1002', desc: 'Cambio de Medidor — MT',           count: 38,  ok: 35,  corr: 3,  pct_ok: 92.1 },
  { cod: '1003', desc: 'Cambio de Medidor — GD Bidirec.', count: 87,  ok: 79,  corr: 8,  pct_ok: 90.8 },
  { cod: '1004', desc: 'Reparación de Medidor',            count: 54,  ok: 50,  corr: 4,  pct_ok: 92.6 },
  { cod: '1005', desc: 'Retiro de Medidor',                count: 29,  ok: 27,  corr: 2,  pct_ok: 93.1 },
  { cod: '2001', desc: 'Relevamiento — Sin Cambio',        count: 42,  ok: 38,  corr: 4,  pct_ok: 90.5 },
  { cod: '2002', desc: 'Relevamiento — Con Cambio',        count: 18,  ok: 16,  corr: 2,  pct_ok: 88.9 },
  { cod: '3001', desc: 'Inspección — Detección Anomalía', count: 14,  ok: 12,  corr: 2,  pct_ok: 85.7 },
  { cod: '3002', desc: 'Inspección — Sin Anomalía',        count: 6,   ok: 6,   corr: 0,  pct_ok: 100  },
];

// ── Mini bar chart (stacked: rechazados | corregidos | aprobados sin corregir) ──
function MiniBarChart({ data, height = 80 }) {
  const maxVal = Math.max(...data.map((d) => d.total));
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 5, height, paddingTop: 8 }}>
      {data.map((d) => {
        const barH = (d.total / maxVal) * (height - 20);
        return (
          <div key={d.mes} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, flex: 1 }}>
            <div
              style={{
                width: '100%',
                height: barH,
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'flex-end',
                overflow: 'hidden',
                borderRadius: '3px 3px 0 0',
              }}
            >
              <div style={{ background: '#c0392b', height: `${(d.rechazados / d.total) * 100}%`, width: '100%', transition: 'all 0.3s' }} />
              <div style={{ background: '#e6910a', height: `${(d.corregidos / d.total) * 100}%`, width: '100%', transition: 'all 0.3s' }} />
              <div style={{ background: '#1d8348', height: `${((d.aprobados - d.corregidos) / d.total) * 100}%`, width: '100%', transition: 'all 0.3s' }} />
            </div>
            <span style={{ fontSize: 9.5, color: '#8f9c97', fontFamily: "'JetBrains Mono', monospace" }}>{d.mes}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Effectiveness line ──
function EffectivenessLine({ data, height = 60 }) {
  const values = data.map((d) => d.efectividad);
  const min = Math.min(...values) - 2;
  const max = Math.max(...values) + 1;
  const W = 280, H = height;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * (W - 20) + 10;
    const y = H - ((v - min) / (max - min)) * (H - 12) - 4;
    return [x, y];
  });
  const pathD = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0]},${p[1]}`).join(' ');
  const areaD = `${pathD} L${pts[pts.length - 1][0]},${H} L${pts[0][0]},${H} Z`;

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ overflow: 'visible' }}>
      <defs>
        <linearGradient id="greenGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1d8348" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#1d8348" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={areaD} fill="url(#greenGrad)" />
      <path d={pathD} fill="none" stroke="#1d8348" strokeWidth={2} strokeLinejoin="round" />
      {pts.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={3} fill="#1d8348" stroke="white" strokeWidth={1.5} />
      ))}
      {pts.map(([x, y], i) => (
        <text key={i} x={x} y={y - 6} textAnchor="middle" fontSize={9} fill="#155a2e" fontFamily="JetBrains Mono" fontWeight="600">
          {values[i].toFixed(1)}%
        </text>
      ))}
    </svg>
  );
}

// ── Donut con dona center ──
function DonutChart({ data, size = 100 }) {
  const total = data.reduce((sum, d) => sum + d.count, 0);
  let angle = -Math.PI / 2;
  const cx = size / 2, cy = size / 2, r = size * 0.38, inner = size * 0.24;

  const segments = data.map((d) => {
    const a = (d.count / total) * 2 * Math.PI;
    const x1 = cx + r * Math.cos(angle);
    const y1 = cy + r * Math.sin(angle);
    angle += a;
    const x2 = cx + r * Math.cos(angle);
    const y2 = cy + r * Math.sin(angle);
    const ix1 = cx + inner * Math.cos(angle - a);
    const iy1 = cy + inner * Math.sin(angle - a);
    const ix2 = cx + inner * Math.cos(angle);
    const iy2 = cy + inner * Math.sin(angle);
    const largeArc = a > Math.PI ? 1 : 0;
    return {
      ...d,
      path: `M${x1},${y1} A${r},${r} 0 ${largeArc},1 ${x2},${y2} L${ix2},${iy2} A${inner},${inner} 0 ${largeArc},0 ${ix1},${iy1} Z`,
    };
  });

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {segments.map((seg, i) => (
        <path key={i} d={seg.path} fill={seg.config?.bg || '#eaeeec'} stroke="white" strokeWidth={1.5} />
      ))}
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize={14} fontWeight="700" fill="#111614" fontFamily="Plus Jakarta Sans">
        {total}
      </text>
      <text x={cx} y={cy + 10} textAnchor="middle" fontSize={8} fill="#8f9c97" fontFamily="Plus Jakarta Sans">
        partes
      </text>
    </svg>
  );
}

export function DashboardCalidad() {
  const [selectedMes, setSelectedMes] = useState('Abr');
  const mesData = DATA_MENSUAL.find((d) => d.mes === selectedMes) || DATA_MENSUAL[DATA_MENSUAL.length - 1];

  const pcAprobCorr = ((mesData.corregidos / mesData.aprobados) * 100).toFixed(1);
  const pcRechazo = ((mesData.rechazados / mesData.total) * 100).toFixed(1);
  const efectividad = mesData.efectividad.toFixed(1);

  const dS = {
    root: { padding: 20, overflow: 'auto', height: '100%', boxSizing: 'border-box', background: '#f5f7f6' },
    pageHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 },
    pageTitle: { fontSize: 17, fontWeight: 700, color: '#111614' },
    pageSub: { fontSize: 12, color: '#8f9c97', marginTop: 2 },
    monthRow: { display: 'flex', gap: 4 },
    monthBtn: { padding: '4px 10px', border: '1px solid #eaeeec', borderRadius: 3, fontSize: 11.5, fontWeight: 500, cursor: 'pointer', color: '#6b7772', background: 'white', transition: 'all 0.1s' },
    monthBtnActive: { background: '#124e2f', color: 'white', borderColor: '#124e2f', fontWeight: 700 },
    grid3: { display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginBottom: 14 },
    grid2: { display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14, marginBottom: 14 },
    card: { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    cardHeader: { padding: '10px 16px', borderBottom: '1px solid #eaeeec', background: '#fafcfb', display: 'flex', alignItems: 'center', gap: 8 },
    cardTitle: { fontSize: 11.5, fontWeight: 700, color: '#2f3733', flex: 1 },
    cardBody: { padding: 16 },
    kpiCard: { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    kpiLabel: { fontSize: 10.5, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 },
    kpiValue: { fontSize: 28, fontWeight: 700, lineHeight: 1, marginBottom: 4 },
    kpiSub: { fontSize: 11, color: '#6b7772' },
    kpiDelta: { display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10.5, fontWeight: 600, padding: '2px 6px', borderRadius: 3, marginLeft: 8 },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: 11.5 },
    th: { padding: '7px 12px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10.5, letterSpacing: '0.04em', whiteSpace: 'nowrap' },
    td: { padding: '6px 12px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', whiteSpace: 'nowrap', verticalAlign: 'middle' },
    mono: { fontFamily: "'JetBrains Mono', monospace" },
    progWrap: { height: 5, background: '#eaeeec', borderRadius: 3, overflow: 'hidden', width: '100%' },
    progFill: { height: '100%', borderRadius: 3 },
    trazaBar: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7 },
    trazaLabel: { fontSize: 11, color: '#4a5550', width: 160, flexShrink: 0 },
    trazaBarWrap: { flex: 1, height: 7, background: '#eaeeec', borderRadius: 4, overflow: 'hidden' },
    trazaBarFill: { height: '100%', borderRadius: 4, transition: 'width 0.4s ease' },
    trazaCount: { fontSize: 10.5, fontFamily: "'JetBrains Mono', monospace", color: '#6b7772', width: 32, textAlign: 'right', flexShrink: 0 },
    trazaPct: { fontSize: 10.5, fontFamily: "'JetBrains Mono', monospace", color: '#6b7772', width: 36, textAlign: 'right', flexShrink: 0 },
  };

  const kpis = [
    { label: 'Efectividad %',          value: `${efectividad}%`,    color: '#155a2e', sub: `${mesData.aprobados} / ${mesData.total} partes aprobados`, delta: '+0.2pp', deltaOk: true },
    { label: '% Aprobados Corregidos', value: `${pcAprobCorr}%`,    color: '#7a4a00', sub: `${mesData.corregidos} requirieron corrección`,            delta: '+1.1pp', deltaOk: false },
    { label: '% Rechazo',              value: `${pcRechazo}%`,      color: '#7a1c1c', sub: `${mesData.rechazados} partes rechazados`,                delta: '-0.3pp', deltaOk: true },
  ];

  return (
    <div style={dS.root}>
      <div style={dS.pageHeader}>
        <div>
          <div style={dS.pageTitle}>Calidad de Datos</div>
          <div style={dS.pageSub}>Módulo C — Dashboard BI · Overview</div>
        </div>
        <div style={dS.monthRow}>
          {DATA_MENSUAL.map((d) => (
            <button
              key={d.mes}
              style={{ ...dS.monthBtn, ...(selectedMes === d.mes ? dS.monthBtnActive : {}) }}
              onClick={() => setSelectedMes(d.mes)}
            >
              {d.mes}
            </button>
          ))}
        </div>
      </div>

      <div style={dS.grid3}>
        {kpis.map((k) => (
          <div key={k.label} style={dS.kpiCard}>
            <div style={dS.kpiLabel}>{k.label}</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 0 }}>
              <span style={{ ...dS.kpiValue, color: k.color }}>{k.value}</span>
              <span style={{ ...dS.kpiDelta, background: k.deltaOk ? '#d4edda' : '#fff3cd', color: k.deltaOk ? '#155a2e' : '#7a4a00' }}>
                <Icon name="trending-up" size={10} /> {k.delta}
              </span>
            </div>
            <div style={dS.kpiSub}>{k.sub}</div>
          </div>
        ))}
      </div>

      <div style={dS.grid2}>
        <div style={dS.card}>
          <div style={dS.cardHeader}>
            <Icon name="bar-chart" size={14} color="#6b7772" />
            <span style={dS.cardTitle}>Evolución mensual — Partes por Estado</span>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              {[['#1d8348', 'Aprobados'], ['#e6910a', 'Corregidos'], ['#c0392b', 'Rechazados']].map(([c, l]) => (
                <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: c }} />
                  <span style={{ fontSize: 10, color: '#8f9c97' }}>{l}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ ...dS.cardBody, paddingTop: 8 }}>
            <MiniBarChart data={DATA_MENSUAL} height={120} />
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 10.5, fontWeight: 600, color: '#8f9c97', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Efectividad %
              </div>
              <EffectivenessLine data={DATA_MENSUAL} height={56} />
            </div>
          </div>
        </div>

        <div style={dS.card}>
          <div style={dS.cardHeader}>
            <Icon name="layers" size={14} color="#6b7772" />
            <span style={dS.cardTitle}>Distribución de Trazas — {selectedMes}</span>
          </div>
          <div style={{ ...dS.cardBody, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <DonutChart data={TRAZAS_DIST} size={90} />
              <div style={{ flex: 1 }}>
                {TRAZAS_DIST.slice(0, 3).map((t) => (
                  <div key={t.traza} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5 }}>
                    <div style={{ width: 8, height: 8, borderRadius: 2, background: t.config?.bg || '#eaeeec', border: `1px solid ${t.config?.color || '#8f9c97'}`, flexShrink: 0 }} />
                    <span style={{ fontSize: 10.5, color: '#4a5550', flex: 1 }}>{t.traza}</span>
                    <span style={{ fontSize: 10.5, fontFamily: "'JetBrains Mono', monospace", color: '#6b7772', fontWeight: 600 }}>
                      {t.pct}%
                    </span>
                  </div>
                ))}
                <div style={{ fontSize: 10, color: '#b5bfbb', marginTop: 4 }}>+ {TRAZAS_DIST.length - 3} más…</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ ...dS.card, marginBottom: 14 }}>
        <div style={dS.cardHeader}>
          <Icon name="activity" size={14} color="#6b7772" />
          <span style={dS.cardTitle}>Descomposición por Traza Calidad</span>
          <span style={{ fontSize: 10.5, color: '#8f9c97' }}>
            {selectedMes} 2025 · Total {TRAZAS_DIST.reduce((s, t) => s + t.count, 0)} partes
          </span>
        </div>
        <div style={dS.cardBody}>
          {TRAZAS_DIST.map((t) => (
            <div key={t.traza} style={dS.trazaBar}>
              <span style={dS.trazaLabel}>
                <StatusChip label={t.traza} config={t.config} size="xs" />
              </span>
              <div style={dS.trazaBarWrap}>
                <div
                  style={{
                    ...dS.trazaBarFill,
                    width: `${t.pct * 2}%`,
                    background: t.config?.color || '#8f9c97',
                    opacity: 0.6,
                  }}
                />
              </div>
              <span style={dS.trazaCount}>{t.count}</span>
              <span style={dS.trazaPct}>{t.pct}%</span>
            </div>
          ))}
        </div>
      </div>

      <div style={dS.card}>
        <div style={dS.cardHeader}>
          <Icon name="tag" size={14} color="#6b7772" />
          <span style={dS.cardTitle}>Calidad por Código EPEC</span>
          <span style={{ fontSize: 10.5, color: '#8f9c97' }}>Todos los contratistas · {selectedMes} 2025</span>
        </div>
        <table style={dS.table}>
          <thead>
            <tr>
              {['Cód. EPEC', 'Descripción', 'Total', 'Aprobados', 'Corregidos', '% OK', 'Calidad'].map((h) => (
                <th key={h} style={dS.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COD_EPEC_TABLE.map((row, i) => (
              <tr key={row.cod} style={{ background: i % 2 === 0 ? 'white' : '#fafcfb' }}>
                <td style={{ ...dS.td, ...dS.mono, color: '#124e2f', fontWeight: 700 }}>{row.cod}</td>
                <td style={{ ...dS.td, color: '#4a5550', fontSize: 11.5 }}>{row.desc}</td>
                <td style={{ ...dS.td, ...dS.mono, textAlign: 'right' }}>{row.count}</td>
                <td style={{ ...dS.td, ...dS.mono, textAlign: 'right', color: '#155a2e', fontWeight: 600 }}>{row.ok}</td>
                <td style={{ ...dS.td, ...dS.mono, textAlign: 'right', color: row.corr > 5 ? '#7a4a00' : '#4a5550' }}>
                  {row.corr}
                </td>
                <td
                  style={{
                    ...dS.td,
                    ...dS.mono,
                    textAlign: 'right',
                    fontWeight: 700,
                    color: row.pct_ok >= 95 ? '#155a2e' : row.pct_ok >= 90 ? '#7a4a00' : '#7a1c1c',
                  }}
                >
                  {row.pct_ok.toFixed(1)}%
                </td>
                <td style={{ ...dS.td, minWidth: 90 }}>
                  <div style={dS.progWrap}>
                    <div
                      style={{
                        ...dS.progFill,
                        width: `${row.pct_ok}%`,
                        background: row.pct_ok >= 95 ? '#1d8348' : row.pct_ok >= 90 ? '#e6910a' : '#c0392b',
                      }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
