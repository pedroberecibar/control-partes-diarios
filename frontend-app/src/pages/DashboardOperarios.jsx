import { useMemo, useState } from 'react';
import { Icon } from '../components/Icon';
import { PARTES_DATA } from '../data/partesMock';

function seededSparkline(name, weeks = 8) {
  const seed = name.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  return Array.from({ length: weeks }, (_, w) => {
    const x = Math.sin((seed + w * 3.7) * 9.1) * 10000;
    const r = x - Math.floor(x);
    return Math.round(74 + r * 24);
  });
}

function MiniSparkline({ values, width = 88, height = 28 }) {
  const min = Math.min(...values) - 2;
  const max = Math.max(...values) + 2;
  const pts = values.map((v, i) => [
    (i / (values.length - 1)) * (width - 4) + 2,
    height - ((v - min) / (max - min)) * (height - 4) - 2,
  ]);
  const d = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const trend = values[values.length - 1] >= values[values.length - 2];
  const color = trend ? '#1d8348' : '#c0392b';
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r={2.5} fill={color} />
    </svg>
  );
}

function QualityBar({ pct }) {
  const color = pct >= 90 ? '#1d8348' : pct >= 80 ? '#e6910a' : '#c0392b';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, fontWeight: 700, color, minWidth: 40, textAlign: 'right' }}>
        {pct.toFixed(1)}%
      </span>
      <div style={{ width: 72, height: 5, background: '#eaeeec', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3 }} />
      </div>
    </div>
  );
}

const SORT_COLS = [
  { id: 'operario',  label: 'Operario',          numeric: false },
  { id: 'contr',     label: 'Contratista',        numeric: false },
  { id: 'total',     label: 'Total',              numeric: true  },
  { id: 'pct_ok',    label: '% OK',               numeric: true  },
  { id: 'pct_corr',  label: '% Corregidos',       numeric: true  },
  { id: 'pct_rech',  label: '% Rechazados',       numeric: true  },
  { id: 'pendientes',label: 'Pendientes',          numeric: true  },
  { id: 'spark',     label: 'Tendencia (8 sem.)',  numeric: false },
];

export function DashboardOperarios() {
  const [contFilter, setContFilter] = useState('');
  const [sortCol, setSortCol]       = useState('total');
  const [sortDir, setSortDir]       = useState('desc');

  const operStats = useMemo(() => {
    const map = {};
    PARTES_DATA.forEach((p) => {
      if (!map[p.operario_nombre]) {
        map[p.operario_nombre] = { operario: p.operario_nombre, contr: p.contratista, total: 0, ok: 0, corr: 0, rech: 0, pend: 0 };
      }
      const o = map[p.operario_nombre];
      o.total++;
      if (p.id_traza === 1) o.ok++;
      if (p.fue_corregido) o.corr++;
      if (p.id_estado === 3) o.rech++;
      if (p.id_estado === 2) o.pend++;
    });
    return Object.values(map).map((o) => ({
      ...o,
      pct_ok:   (o.ok   / o.total) * 100,
      pct_corr: (o.corr / o.total) * 100,
      pct_rech: (o.rech / o.total) * 100,
      pendientes: o.pend,
      spark: seededSparkline(o.operario),
    }));
  }, []);

  const filtered = contFilter ? operStats.filter((o) => o.contr === contFilter) : operStats;

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = a[sortCol]; const bv = b[sortCol];
      const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sortCol, sortDir]);

  function handleSort(col) {
    if (sortCol === col) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortCol(col); setSortDir('desc'); }
  }

  const topPerf  = [...operStats].sort((a, b) => b.pct_ok - a.pct_ok)[0];
  const avgOk    = operStats.reduce((s, o) => s + o.pct_ok, 0) / operStats.length;
  const avgCorr  = operStats.reduce((s, o) => s + o.pct_corr, 0) / operStats.length;
  const totalP   = operStats.reduce((s, o) => s + o.total, 0);

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
    tableCard:  { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    toolbar:    { padding: '10px 16px', borderBottom: '1px solid #eaeeec', display: 'flex', alignItems: 'center', gap: 10 },
    table:      { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
    th:         { padding: '8px 12px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10.5, letterSpacing: '0.04em', whiteSpace: 'nowrap', cursor: 'pointer', userSelect: 'none' },
    thInner:    { display: 'flex', alignItems: 'center', gap: 4 },
    td:         { padding: '8px 12px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', whiteSpace: 'nowrap', verticalAlign: 'middle' },
    mono:       { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
    filterSel:  { padding: '5px 8px', border: '1px solid #eaeeec', borderRadius: 4, fontSize: 12, color: '#2f3733', background: 'white', cursor: 'pointer' },
    btn:        { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 11px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, fontWeight: 600, color: '#2f3733', cursor: 'pointer' },
  };

  const kpis = [
    { label: 'Operarios activos',  value: operStats.length,                             color: '#111614', sub: 'ambos contratistas'           },
    { label: 'Total partes',       value: totalP,                                       color: '#111614', sub: 'mes en curso'                  },
    { label: 'Calidad promedio',   value: `${avgOk.toFixed(1)}%`,                       color: '#155a2e', sub: `${avgCorr.toFixed(1)}% requirieron corrección` },
    { label: 'Top performer',      value: topPerf?.operario.split(',')[0] || '—',       color: '#124e2f', sub: `${topPerf?.pct_ok.toFixed(1)}% OK · ${topPerf?.contr}` },
  ];

  return (
    <div style={dS.root}>
      <div style={dS.hdr}>
        <div>
          <div style={dS.title}>Análisis de Operarios</div>
          <div style={dS.sub}>Módulo C — Dashboard BI · Rendimiento por operario</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <select style={dS.filterSel} value={contFilter} onChange={(e) => setContFilter(e.target.value)}>
            <option value="">Todos los contratistas</option>
            <option value="CONECTAR">CONECTAR</option>
            <option value="COOPLYF">COOPLYF</option>
          </select>
          <button style={dS.btn}><Icon name="download" size={13} /> Exportar</button>
        </div>
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

      <div style={dS.tableCard}>
        <div style={dS.toolbar}>
          <span style={{ fontSize: 12, color: '#6b7772', fontWeight: 500 }}>
            {sorted.length} operario{sorted.length !== 1 ? 's' : ''}
            {contFilter && ` · ${contFilter}`}
          </span>
          <div style={{ flex: 1 }} />
          {[['#1d8348', 'OK sin corrección'], ['#e6910a', 'Corregidos'], ['#c0392b', 'Rechazados']].map(([c, l]) => (
            <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: c }} />
              <span style={{ fontSize: 10.5, color: '#8f9c97' }}>{l}</span>
            </div>
          ))}
        </div>
        <table style={dS.table}>
          <thead>
            <tr>
              {SORT_COLS.map((col) => (
                <th
                  key={col.id}
                  style={{ ...dS.th, cursor: col.id === 'spark' ? 'default' : 'pointer' }}
                  onClick={() => col.id !== 'spark' && handleSort(col.id)}
                >
                  <div style={dS.thInner}>
                    {col.label}
                    {sortCol === col.id && col.id !== 'spark' && (
                      <Icon name={sortDir === 'asc' ? 'chevron-down' : 'chevron-right'} size={11} color="rgba(255,255,255,0.7)" />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((o, i) => (
              <tr key={o.operario} style={{ background: i % 2 === 0 ? 'white' : '#fafcfb' }}>
                <td style={{ ...dS.td, fontWeight: 600 }}>{o.operario}</td>
                <td style={dS.td}>
                  <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 6px', borderRadius: 3, background: o.contr === 'CONECTAR' ? '#edf5f0' : '#dbeafe', color: o.contr === 'CONECTAR' ? '#124e2f' : '#0d4272' }}>
                    {o.contr}
                  </span>
                </td>
                <td style={{ ...dS.td, ...dS.mono, textAlign: 'right', fontWeight: 700 }}>{o.total}</td>
                <td style={dS.td}><QualityBar pct={o.pct_ok} /></td>
                <td style={{ ...dS.td, ...dS.mono, textAlign: 'right', color: o.pct_corr > 20 ? '#7a4a00' : '#4a5550' }}>
                  {o.pct_corr.toFixed(1)}%
                </td>
                <td style={{ ...dS.td, ...dS.mono, textAlign: 'right', color: o.pct_rech > 10 ? '#7a1c1c' : '#4a5550', fontWeight: o.pct_rech > 10 ? 700 : 400 }}>
                  {o.pct_rech.toFixed(1)}%
                </td>
                <td style={{ ...dS.td, ...dS.mono, textAlign: 'right', color: o.pendientes > 3 ? '#7a4a00' : '#4a5550', fontWeight: o.pendientes > 3 ? 700 : 400 }}>
                  {o.pendientes}
                </td>
                <td style={dS.td}><MiniSparkline values={o.spark} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
