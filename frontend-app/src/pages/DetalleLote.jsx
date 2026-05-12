import { useEffect, useState } from 'react';
import { Icon, LOTE_ESTADO_CONFIG, StatusChip } from '../components/Icon';
import { getLote, getLoteDashboard } from '../api/lotesApi';

// ── Donut genérico: N segmentos proporcionales ────────────────────────────
function DonutDistribucion({ data, estadoLabel }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  if (total === 0) return <div style={{ color: '#8f9c97', fontSize: 12 }}>Sin datos</div>;
  const r = 38, cx = 60, cy = 60, sw = 14;
  const circ = 2 * Math.PI * r;
  let accumulated = 0;
  return (
    <svg width={120} height={120} style={{ flexShrink: 0 }}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#e0e7e4" strokeWidth={sw} />
      {data.map((seg, i) => {
        const arc = (seg.count / total) * circ;
        const angle = (accumulated / circ) * 360 - 90;
        accumulated += arc;
        return (
          <circle key={i} cx={cx} cy={cy} r={r} fill="none"
            stroke={seg.color} strokeWidth={sw}
            strokeDasharray={`${arc} ${circ - arc}`}
            style={{ transform: `rotate(${angle}deg)`, transformOrigin: `${cx}px ${cy}px` }}
          />
        );
      })}
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize="11" fontWeight="700" fill="#111614">
        {estadoLabel.split(' ')[0]}
      </text>
      <text x={cx} y={cy + 9} textAnchor="middle" fontSize="9" fill="#8f9c97">
        {total.toLocaleString()}
      </text>
    </svg>
  );
}

// ── Barra horizontal ──────────────────────────────────────────────────────
function HBar({ pct, color }) {
  return (
    <div style={{ height: 7, background: '#f0f3f1', borderRadius: 4, overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${Math.min(pct, 100)}%`, background: color, borderRadius: 4, transition: 'width 0.4s' }} />
    </div>
  );
}

// ── Colores de discrepancia ───────────────────────────────────────────────
const DISC_COLOR = {
  'Sin Discrepancia':                '#1d8348',
  'Sobrevaloración':                 '#c0392b',
  'Subvaloración':                   '#e6910a',
  'Sin Observaciones':               '#8f9c97',
  'Error Operativo':                 '#9b59b6',
  'Sin Regla Definida':              '#7f8c8d',
  'Sin Regla para Código Declarado': '#7f8c8d',
};

// ── Color chip por estado de traza ────────────────────────────────────────
const ESTADO_CHIP = {
  'Aprobado':      { color: '#155a2e', bg: '#edf5f0' },
  'Revisión':      { color: '#7a4a00', bg: '#fff8eb' },
  'Rechazado':     { color: '#7a1c1c', bg: '#fdf1f0' },
  'Fuera Alcance': { color: '#5b4a00', bg: '#fef9e7' },
};

// ── Trazas clasificadas por Estado de Proceso (1:1 con backend) ──────────
const TRAZAS_APROBADO      = new Set([1, 2, 3, 4, 12]);
const TRAZAS_REVISION      = new Set([5, 19, 20]);
const TRAZAS_RECHAZADO     = new Set([7, 8, 9, 10, 13, 14, 15, 16, 17, 18]);
const TRAZAS_FUERA_ALCANCE = new Set([6, 11]);

// ── Mapeo estado → set y paleta cromática ────────────────────────────────
const SET_POR_ESTADO = {
  'Aprobado':         TRAZAS_APROBADO,
  'Revisión':         TRAZAS_REVISION,
  'Rechazado':        TRAZAS_RECHAZADO,
  'Fuera de Alcance': TRAZAS_FUERA_ALCANCE,
};
const PALETAS = {
  'Aprobado':         ['#1d8348', '#27ae60', '#52be80', '#82e0aa', '#a9dfbf'],
  'Revisión':         ['#e6910a', '#f0b429', '#f9cc70'],
  'Rechazado':        ['#922b21', '#c0392b', '#e74c3c', '#ec7063', '#f1948a'],
  'Fuera de Alcance': ['#5b4a00', '#b7950b'],
};

function formatFecha(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch { return iso; }
}

function SectionTitle({ label }) {
  return (
    <div style={{ fontSize: 10.5, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 10, marginTop: 24, paddingBottom: 6, borderBottom: '1px solid #eaeeec' }}>
      {label}
    </div>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{ background: 'white', border: '1px solid #eaeeec', borderRadius: 6, padding: '14px 16px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', ...style }}>
      {children}
    </div>
  );
}

function Skeleton() {
  const bar = (w, h = 12, mb = 6) => (
    <div style={{ width: w, height: h, background: '#eaeeec', borderRadius: 4, marginBottom: mb, animation: 'dashPulse 1.5s ease-in-out infinite' }} />
  );
  return (
    <div style={{ padding: 20 }}>
      <style>{`@keyframes dashPulse { 0%,100%{opacity:1} 50%{opacity:.45} }`}</style>
      {bar('55%', 18, 8)}
      {bar('35%', 11, 22)}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12, marginBottom: 16 }}>
        {[...Array(5)].map((_, i) => (
          <div key={i} style={{ height: 70, background: '#eaeeec', borderRadius: 6, animation: 'dashPulse 1.5s ease-in-out infinite' }} />
        ))}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
        {[...Array(2)].map((_, i) => (
          <div key={i} style={{ height: 160, background: '#eaeeec', borderRadius: 6, animation: 'dashPulse 1.5s ease-in-out infinite' }} />
        ))}
      </div>
      {bar('100%', 180, 0)}
    </div>
  );
}

export function DetalleLote({ loteId, onBack }) {
  const [lote, setLote]     = useState(null);
  const [dash, setDash]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);
  const [estadoSeleccionado, setEstadoSeleccionado] = useState('Aprobado');

  useEffect(() => {
    if (!loteId) return;
    setLoading(true);
    setError(null);
    Promise.all([getLote(loteId), getLoteDashboard(loteId)])
      .then(([l, d]) => { setLote(l); setDash(d); setLoading(false); })
      .catch((e) => { setError(e.message || 'Error al cargar datos'); setLoading(false); });
  }, [loteId]);

  if (loading) return <Skeleton />;

  if (error) return (
    <div style={{ padding: 20 }}>
      <button onClick={onBack} style={{ border: 'none', background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, color: '#124e2f', fontWeight: 600, fontSize: 12, marginBottom: 16, padding: 0 }}>
        <Icon name="arrow-left" size={13} /> Volver a Lotes
      </button>
      <div style={{ color: '#c0392b', fontSize: 13 }}>Error: {error}</div>
    </div>
  );

  if (!lote || !dash) return null;

  const ec = LOTE_ESTADO_CONFIG[lote.estado] || {};

  // Conteos por Estado de Proceso
  let cntAprobado = 0, cntRevision = 0, cntRechazado = 0, cntFueraAlcance = 0;
  for (const t of dash.distribucion_trazas) {
    if (TRAZAS_APROBADO.has(t.id_traza))           cntAprobado     += t.count;
    else if (TRAZAS_REVISION.has(t.id_traza))      cntRevision     += t.count;
    else if (TRAZAS_RECHAZADO.has(t.id_traza))     cntRechazado    += t.count;
    else if (TRAZAS_FUERA_ALCANCE.has(t.id_traza)) cntFueraAlcance += t.count;
  }
  const totalBase = dash.total_registros || 1;

  // Datos para la dona dinámica según estado seleccionado
  const MAX_SLICES = 5;
  const setActivo = SET_POR_ESTADO[estadoSeleccionado];
  const palette   = PALETAS[estadoSeleccionado];
  const trazasFiltradas = dash.distribucion_trazas
    .filter(t => setActivo.has(t.id_traza) && t.count > 0)
    .sort((a, b) => b.count - a.count);
  let donutData;
  if (trazasFiltradas.length <= MAX_SLICES) {
    donutData = trazasFiltradas.map((t, i) => ({ label: t.desc_traza, count: t.count, color: palette[i % palette.length] }));
  } else {
    const top  = trazasFiltradas.slice(0, MAX_SLICES - 1);
    const rest = trazasFiltradas.slice(MAX_SLICES - 1);
    donutData  = [
      ...top.map((t, i) => ({ label: t.desc_traza, count: t.count, color: palette[i] })),
      { label: 'Otras', count: rest.reduce((s, t) => s + t.count, 0), color: '#b0bab6' },
    ];
  }
  const donutTotal = donutData.reduce((s, d) => s + d.count, 0);

  const lS = {
    root:     { padding: 20, overflow: 'auto', height: '100%', boxSizing: 'border-box' },
    backBtn:  { border: 'none', background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5, color: '#8f9c97', fontSize: 11.5, fontWeight: 600, padding: '3px 0', marginBottom: 8 },
    hTitle:   { fontSize: 17, fontWeight: 700, color: '#111614', marginBottom: 3 },
    hMeta:    { fontSize: 11, color: '#8f9c97', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
    kpiGrid:  { display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12, marginBottom: 12 },
    kpiCard:  { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, padding: '12px 14px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    kpiLbl:   { fontSize: 10, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 5 },
    kpiVal:   { fontSize: 19, fontWeight: 700, color: '#111614', lineHeight: 1.1 },
    kpiSub:   { fontSize: 10, color: '#8f9c97', marginTop: 3 },
    twoCol:   { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 },
    cardLbl:  { fontSize: 10.5, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 },
    th:       { padding: '7px 12px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10.5, letterSpacing: '0.04em', whiteSpace: 'nowrap' },
    td:       { padding: '7px 12px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', fontSize: 12 },
    mono:     { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
  };

  const kpis = [
    {
      label: 'Total Registros',
      value: dash.total_registros.toLocaleString(),
      sub: 'filas del lote',
    },
    {
      label: 'Aprobados',
      value: `${dash.n_aprobados.toLocaleString()} (${Math.round((dash.n_aprobados / (dash.total_registros || 1)) * 100)}%)`,
      sub: 'pagables',
      color: '#155a2e',
    },
    {
      label: 'Revisión',
      value: dash.n_revision,
      sub: 'pendientes OCR',
      color: dash.n_revision > 0 ? '#7a4a00' : undefined,
    },
    {
      label: 'Rechazados',
      value: `${dash.n_rechazado.toLocaleString()} (${Math.round((dash.n_rechazado / (dash.total_registros || 1)) * 100)}%)`,
      sub: 'no pagables',
      color: dash.n_rechazado > 0 ? '#7a1c1c' : undefined,
    },
    {
      label: 'Efectividad',
      value: `${dash.efectividad_pct}%`,
      sub: 'excluye fuera de alcance',
      color: dash.efectividad_pct >= 90 ? '#155a2e' : dash.efectividad_pct >= 70 ? '#7a4a00' : '#7a1c1c',
    },
  ];

  return (
    <div style={lS.root}>

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <button
        style={lS.backBtn}
        onClick={onBack}
        onMouseEnter={(e) => (e.currentTarget.style.color = '#124e2f')}
        onMouseLeave={(e) => (e.currentTarget.style.color = '#8f9c97')}
      >
        <Icon name="arrow-left" size={12} /> Volver a Lotes
      </button>

      <div style={{ marginBottom: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4, flexWrap: 'wrap' }}>
          <Icon name="file-text" size={16} color="#124e2f" />
          <span style={lS.hTitle}>{lote.nombre_archivo}</span>
          <StatusChip label={lote.estado} config={ec} size="sm" />
        </div>
        <div style={lS.hMeta}>
          <span style={{
            fontWeight: 600, padding: '1px 7px', borderRadius: 3, fontSize: 11,
            background: lote.contratista_nombre === 'CONECTAR' ? '#edf5f0' : '#dbeafe',
            color: lote.contratista_nombre === 'CONECTAR' ? '#124e2f' : '#0d4272',
          }}>
            {lote.contratista_nombre || '—'}
          </span>
          <span>Lote #{lote.id}</span>
          <span>{formatFecha(lote.fecha_subida)}</span>
          {lote.usuario_nombre && <span>Subido por <strong>{lote.usuario_nombre}</strong></span>}
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
          SECCIÓN A — CALIDAD DE DATOS
      ═══════════════════════════════════════════════════════════════ */}
      <SectionTitle label="Calidad de Datos" />

      {/* A1 — Cards de resumen (5) */}
      <div style={lS.kpiGrid}>
        {kpis.map((k) => (
          <div key={k.label} style={lS.kpiCard}>
            <div style={lS.kpiLbl}>{k.label}</div>
            <div style={{ ...lS.kpiVal, color: k.color || '#111614' }}>{k.value}</div>
            <div style={lS.kpiSub}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* A2 + A4 — Donut aprobados / Breakdown descartados */}
      <div style={lS.twoCol}>

        {/* A2 — Composición del estado seleccionado (dona dinámica) */}
        <Card>
          <div style={lS.cardLbl}>{'Composición: ' + estadoSeleccionado.toUpperCase()}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <DonutDistribucion data={donutData} estadoLabel={estadoSeleccionado} />
            <div style={{ flex: 1, overflow: 'hidden' }}>
              {donutData.length === 0
                ? <div style={{ fontSize: 11, color: '#8f9c97', fontStyle: 'italic' }}>Sin datos para este estado</div>
                : donutData.map((seg) => {
                    const pct = Math.round((seg.count / (donutTotal || 1)) * 100);
                    return (
                      <div key={seg.label} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 9 }}>
                        <div style={{ width: 10, height: 10, borderRadius: 2, background: seg.color, flexShrink: 0, marginTop: 2 }} />
                        <div style={{ overflow: 'hidden' }}>
                          <div style={{ fontSize: 10.5, fontWeight: 600, color: '#2f3733', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {seg.label}{' '}
                            <span style={{ fontFamily: "'JetBrains Mono', monospace", color: seg.color }}>
                              {seg.count.toLocaleString()}
                            </span>
                          </div>
                          <div style={{ fontSize: 9.5, color: '#8f9c97' }}>{pct}%</div>
                        </div>
                      </div>
                    );
                  })
              }
            </div>
          </div>
        </Card>

        {/* A4 — Distribución por Estados de Proceso */}
        <Card>
          <div style={lS.cardLbl}>Distribución por Estados de Proceso</div>
          {[
            {
              label: 'Aprobado',
              count: cntAprobado,
              desc:  'Original OK + corregidos automáticamente (trazas 1,2,3,4,12)',
              color: '#155a2e',
              bg:    '#edf5f0',
            },
            {
              label: 'Revisión',
              count: cntRevision,
              desc:  'Requieren verificación humana antes de aprobar (trazas 5,19,20)',
              color: '#7a4a00',
              bg:    '#fff8eb',
            },
            {
              label: 'Rechazado',
              count: cntRechazado,
              desc:  'No pagables: sin orden, datos inválidos, duplicados (trazas 7,8,9,10,13,14,15,16,17,18)',
              color: '#7a1c1c',
              bg:    '#fdf1f0',
            },
            {
              label: 'Fuera de Alcance',
              count: cntFueraAlcance,
              desc:  'No corresponden al contrato TOR CE actual (trazas 6,11)',
              color: '#5b4a00',
              bg:    '#fef9e7',
            },
          ].map((row) => {
            const pct    = Math.round((row.count / totalBase) * 100);
            const activa = estadoSeleccionado === row.label;
            return (
              <div
                key={row.label}
                onClick={() => setEstadoSeleccionado(row.label)}
                style={{
                  marginBottom: 6, cursor: 'pointer', borderRadius: 4, padding: '4px 6px',
                  borderLeft: `3px solid ${activa ? row.color : 'transparent'}`,
                  background: activa ? row.bg : 'transparent',
                  transition: 'background 0.15s',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#2f3733' }}>{row.label}</span>
                  <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", padding: '1px 5px', borderRadius: 3, background: row.bg, color: row.color, fontWeight: 700 }}>
                    {row.count.toLocaleString()} ({pct}%)
                  </span>
                </div>
                <HBar pct={pct} color={row.color} />
                <div style={{ fontSize: 9.5, color: '#8f9c97', marginTop: 2 }}>{row.desc}</div>
              </div>
            );
          })}
        </Card>
      </div>

      {/* A3 — Distribución de trazas */}
      {dash.distribucion_trazas.length > 0 && (
        <Card style={{ padding: 0, overflow: 'hidden', marginBottom: 0 }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid #eaeeec' }}>
            <span style={{ ...lS.cardLbl, marginBottom: 0 }}>Distribución de Trazas de Calidad</span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  {['#', 'Traza', 'Estado', 'Cantidad', '% lote', 'Barra'].map((h) => (
                    <th key={h} style={{ ...lS.th, textAlign: ['Cantidad', '% lote'].includes(h) ? 'right' : 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dash.distribucion_trazas.map((t, i) => {
                  const chip = ESTADO_CHIP[t.desc_estado] || { color: '#111614', bg: '#f5f7f6' };
                  return (
                    <tr key={`${t.id_traza}-${t.id_estado}`} style={{ background: i % 2 === 0 ? 'white' : '#fafcfb' }}>
                      <td style={{ ...lS.td, ...lS.mono, color: '#8f9c97', width: 28 }}>{t.id_traza}</td>
                      <td style={lS.td}>{t.desc_traza}</td>
                      <td style={lS.td}>
                        <span style={{ fontSize: 10.5, fontWeight: 600, padding: '2px 6px', borderRadius: 3, background: chip.bg, color: chip.color }}>
                          {t.desc_estado}
                        </span>
                      </td>
                      <td style={{ ...lS.td, ...lS.mono, textAlign: 'right', fontWeight: 600 }}>{t.count.toLocaleString()}</td>
                      <td style={{ ...lS.td, ...lS.mono, textAlign: 'right', color: '#4a5550' }}>{t.pct}%</td>
                      <td style={{ ...lS.td, width: 120, paddingRight: 16 }}>
                        <div style={{ height: 6, background: '#f0f3f1', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${Math.min(t.pct, 100)}%`, background: chip.color, borderRadius: 3 }} />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* ═══════════════════════════════════════════════════════════════
          SECCIÓN B — MÉTRICAS OPERATIVAS Y DE NEGOCIO
      ═══════════════════════════════════════════════════════════════ */}
      <SectionTitle label="Métricas Operativas y de Negocio" />

      {/* B1 — Distribución por Código EPEC */}
      {dash.distribucion_epec.length > 0 && (
        <Card style={{ padding: 0, overflow: 'hidden', marginBottom: 12 }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid #eaeeec', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ ...lS.cardLbl, marginBottom: 0 }}>Distribución por Código EPEC (Aprobados)</span>
            <span style={{ fontSize: 11.5, fontFamily: "'JetBrains Mono', monospace", color: '#124e2f', fontWeight: 700 }}>
              {dash.total_uses_aprobados.toFixed(2)} USES totales
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  {['Cód. EPEC', 'Descripción', 'Partes', '% Partes', 'USES Totales', 'Proporción USES'].map((h) => (
                    <th key={h} style={{ ...lS.th, textAlign: ['Partes', '% Partes', 'USES Totales'].includes(h) ? 'right' : 'left' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dash.distribucion_epec.map((ep, i) => {
                  const usesPct = dash.total_uses_aprobados > 0 ? (ep.total_uses / dash.total_uses_aprobados) * 100 : 0;
                  return (
                    <tr key={i} style={{ background: i % 2 === 0 ? 'white' : '#fafcfb' }}>
                      <td style={{ ...lS.td, ...lS.mono, fontWeight: 700, color: '#124e2f', width: 80 }}>
                        {ep.cod_epec != null ? ep.cod_epec : '—'}
                      </td>
                      <td style={lS.td}>
                        {ep.desc_epec || <span style={{ color: '#8f9c97', fontStyle: 'italic' }}>Sin descripción</span>}
                      </td>
                      <td style={{ ...lS.td, ...lS.mono, textAlign: 'right', fontWeight: 600 }}>{ep.count.toLocaleString()}</td>
                      <td style={{ ...lS.td, ...lS.mono, textAlign: 'right', color: '#4a5550' }}>{ep.pct_partes}%</td>
                      <td style={{ ...lS.td, ...lS.mono, textAlign: 'right', fontWeight: 600, color: '#124e2f' }}>{ep.total_uses.toFixed(2)}</td>
                      <td style={{ ...lS.td, width: 140, paddingRight: 16 }}>
                        <div style={{ height: 6, background: '#f0f3f1', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${Math.min(usesPct, 100)}%`, background: '#124e2f', borderRadius: 3 }} />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* B2 + B3 — Discrepancias + Impacto económico */}
      <div style={lS.twoCol}>

        {/* B2 — Análisis de discrepancias */}
        <Card>
          <div style={lS.cardLbl}>
            Análisis de Discrepancias de Valoración
            {dash.total_controlados > 0 && (
              <span style={{ fontWeight: 400, textTransform: 'none', marginLeft: 6, color: '#b0bab6' }}>
                ({dash.total_controlados.toLocaleString()} controlados)
              </span>
            )}
          </div>
          {dash.distribucion_discrepancias.length === 0 ? (
            <div style={{ fontSize: 12, color: '#8f9c97', fontStyle: 'italic' }}>Sin datos de control de observaciones</div>
          ) : (
            dash.distribucion_discrepancias.map((d) => (
              <div key={d.tipo} style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: '#2f3733', maxWidth: '63%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {d.tipo}
                  </span>
                  <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: DISC_COLOR[d.tipo] || '#111614', flexShrink: 0 }}>
                    {d.count.toLocaleString()} ({d.pct}%)
                  </span>
                </div>
                <HBar pct={d.pct} color={DISC_COLOR[d.tipo] || '#8f9c97'} />
              </div>
            ))
          )}
        </Card>

        {/* B3 — Impacto económico */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Card style={{ flex: 1 }}>
            <div style={lS.cardLbl}>Total USES Aprobados</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: '#124e2f', fontFamily: "'JetBrains Mono', monospace", lineHeight: 1.1 }}>
              {dash.total_uses_aprobados.toFixed(2)}
            </div>
            <div style={{ fontSize: 10.5, color: '#8f9c97', marginTop: 6 }}>
              base de pago del lote — {dash.n_aprobados.toLocaleString()} partes aprobados
            </div>
          </Card>
          <Card style={{ flex: 1 }}>
            <div style={lS.cardLbl}>Impacto por Discrepancias</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: 11, color: '#2f3733', fontWeight: 600 }}>Sobrevaloración</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: dash.delta_uses_sobrevaloracion > 0 ? '#c0392b' : '#8f9c97' }}>
                    +{dash.delta_uses_sobrevaloracion.toFixed(4)}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: '#8f9c97' }}>EPEC pagaría de más con estos códigos</div>
              </div>
              <div style={{ borderTop: '1px solid #eaeeec', paddingTop: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: 11, color: '#2f3733', fontWeight: 600 }}>Subvaloración</span>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 700, color: dash.delta_uses_subvaloracion > 0 ? '#e6910a' : '#8f9c97' }}>
                    -{dash.delta_uses_subvaloracion.toFixed(4)}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: '#8f9c97' }}>Contratista cobra menos de lo que corresponde</div>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* B4 — Tabla por operario (solo si hay ≥2 operarios distintos) */}
      {dash.por_operario.length >= 2 && (
        <Card style={{ padding: 0, overflow: 'hidden', marginTop: 0, marginBottom: 12 }}>
          <div style={{ padding: '10px 16px', borderBottom: '1px solid #eaeeec' }}>
            <span style={{ ...lS.cardLbl, marginBottom: 0 }}>
              Distribución por Operario ({dash.por_operario.length} operarios)
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr>
                  {['Operario', 'Total Partes', 'Aprobados', 'Tasa Aprobación', 'USES Totales'].map((h) => (
                    <th key={h} style={{ ...lS.th, textAlign: h === 'Operario' ? 'left' : 'right' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dash.por_operario.map((op, i) => (
                  <tr key={op.operario} style={{ background: i % 2 === 0 ? 'white' : '#fafcfb' }}>
                    <td style={lS.td}>{op.operario}</td>
                    <td style={{ ...lS.td, ...lS.mono, textAlign: 'right' }}>{op.n_total.toLocaleString()}</td>
                    <td style={{ ...lS.td, ...lS.mono, textAlign: 'right', color: '#155a2e', fontWeight: 600 }}>{op.n_aprobados.toLocaleString()}</td>
                    <td style={{
                      ...lS.td, ...lS.mono, textAlign: 'right', fontWeight: 700,
                      color: op.tasa_aprobacion >= 90 ? '#155a2e' : op.tasa_aprobacion >= 70 ? '#7a4a00' : '#7a1c1c',
                    }}>
                      {op.tasa_aprobacion}%
                    </td>
                    <td style={{ ...lS.td, ...lS.mono, textAlign: 'right', color: '#124e2f', fontWeight: 600 }}>
                      {op.total_uses.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

    </div>
  );
}
