import { useState } from 'react';
import { Icon } from '../components/Icon';

const EXPORT_TYPES = [
  {
    id: 'excel_completo',
    icon: 'file-text',
    title: 'Excel completo — Partes del mes',
    desc: 'Todas las columnas del pipeline: datos crudos + TRAZA_CALIDAD + USES + Control Obs.',
    ext: '.xlsx',
    size: '~2.4 MB',
    color: '#155a2e',
    bg: '#d4edda',
    tags: ['Partes', 'Pipeline', 'KPIs'],
  },
  {
    id: 'pdf_resumen',
    icon: 'receipt',
    title: 'PDF resumen ejecutivo',
    desc: 'Dashboard PDF con KPIs de calidad, distribución de trazas y tabla de lotes del mes.',
    ext: '.pdf',
    size: '~0.8 MB',
    color: '#7a1c1c',
    bg: '#fde8e8',
    tags: ['Resumen', 'Dirección'],
  },
  {
    id: 'csv_obs',
    icon: 'activity',
    title: 'CSV — Partes con observaciones',
    desc: 'Solo partes que poseen TRAZA diferente de "Original OK". Útil para auditoría focalizada.',
    ext: '.csv',
    size: '~180 KB',
    color: '#7a4a00',
    bg: '#fff3cd',
    tags: ['Observaciones', 'Auditoría'],
  },
  {
    id: 'csv_rechazados',
    icon: 'x-circle',
    title: 'CSV — Partes rechazados / anulados',
    desc: 'Partes con estado Rechazado o Anulado, con historial de motivos desde la bitácora.',
    ext: '.csv',
    size: '~42 KB',
    color: '#7a1c1c',
    bg: '#fde8e8',
    tags: ['Rechazados', 'Auditoría'],
  },
  {
    id: 'excel_operarios',
    icon: 'users',
    title: 'Excel — Rendimiento por operario',
    desc: 'Métricas agregadas por operario: total partes, % OK, % corrección, pendientes.',
    ext: '.xlsx',
    size: '~120 KB',
    color: '#0d4272',
    bg: '#dbeafe',
    tags: ['Operarios', 'BI'],
  },
  {
    id: 'zip_fotos',
    icon: 'camera',
    title: 'ZIP — Fotografías de partes observados',
    desc: 'Pack comprimido con las fotos de todos los partes con TRAZA crítica del mes seleccionado.',
    ext: '.zip',
    size: '~45 MB',
    color: '#4a5550',
    bg: '#eaeeec',
    tags: ['Fotos', 'App móvil'],
  },
];

const RECENT_EXPORTS = [
  { id: 1, type: 'Excel completo — Partes del mes', user: 'López, M.', fecha: '29/04/2025 08:41', size: '2.4 MB', estado: 'OK',       icon: 'file-text' },
  { id: 2, type: 'CSV — Partes con observaciones',  user: 'García, J.', fecha: '28/04/2025 17:22', size: '178 KB', estado: 'OK',       icon: 'activity' },
  { id: 3, type: 'PDF resumen ejecutivo',           user: 'Torres, R.', fecha: '28/04/2025 14:05', size: '0.8 MB', estado: 'OK',       icon: 'receipt' },
  { id: 4, type: 'ZIP — Fotografías obs.',          user: 'Romero, S.', fecha: '27/04/2025 09:30', size: '44 MB',  estado: 'OK',       icon: 'camera' },
  { id: 5, type: 'Excel — Rendimiento operarios',  user: 'López, M.', fecha: '25/04/2025 11:17', size: '119 KB', estado: 'OK',       icon: 'users' },
  { id: 6, type: 'CSV — Partes rechazados',         user: 'García, J.', fecha: '22/04/2025 16:44', size: '39 KB',  estado: 'ERROR',    icon: 'x-circle' },
];

function DownloadButton({ onDownload, loading, done }) {
  if (done) {
    return (
      <button style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', border: 'none', borderRadius: 4, background: '#1d8348', color: 'white', fontSize: 12, fontWeight: 600, cursor: 'default' }}>
        <Icon name="check" size={13} /> Descargado
      </button>
    );
  }
  if (loading) {
    return (
      <button style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', color: '#4a5550', fontSize: 12, fontWeight: 600, cursor: 'default' }}>
        <Icon name="loader" size={13} /> Generando…
      </button>
    );
  }
  return (
    <button
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', color: '#124e2f', fontSize: 12, fontWeight: 600, cursor: 'pointer', transition: 'all 0.12s' }}
      onClick={onDownload}
      onMouseEnter={(e) => { e.currentTarget.style.background = '#edf5f0'; e.currentTarget.style.borderColor = '#a8d9c0'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'white'; e.currentTarget.style.borderColor = '#d5ddd9'; }}
    >
      <Icon name="download" size={13} /> Descargar
    </button>
  );
}

export function CentroExports() {
  const [loading, setLoading]   = useState({});
  const [done, setDone]         = useState({});
  const [mesFilter, setMesFilter] = useState('Abril 2025');

  function handleDownload(id) {
    setLoading((l) => ({ ...l, [id]: true }));
    setTimeout(() => {
      setLoading((l) => ({ ...l, [id]: false }));
      setDone((d) => ({ ...d, [id]: true }));
      setTimeout(() => setDone((d) => ({ ...d, [id]: false })), 3000);
    }, 1400);
  }

  const dS = {
    root:      { padding: 20, overflow: 'auto', height: '100%', boxSizing: 'border-box', background: '#f5f7f6' },
    hdr:       { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 },
    title:     { fontSize: 17, fontWeight: 700, color: '#111614' },
    sub:       { fontSize: 12, color: '#8f9c97', marginTop: 2 },
    grid:      { display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 20 },
    exportCard:{ background: 'white', border: '1px solid #eaeeec', borderRadius: 6, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column', gap: 10 },
    iconWrap:  { width: 36, height: 36, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
    cardTitle: { fontSize: 13, fontWeight: 700, color: '#111614', lineHeight: 1.3 },
    cardDesc:  { fontSize: 12, color: '#6b7772', lineHeight: 1.45, flex: 1 },
    tags:      { display: 'flex', gap: 5, flexWrap: 'wrap' },
    tag:       { fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 10, background: '#f0f3f1', color: '#6b7772' },
    footer:    { display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 6, borderTop: '1px solid #f5f7f6' },
    extBadge:  { fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, fontWeight: 700, padding: '2px 7px', borderRadius: 3 },
    sizeText:  { fontSize: 10.5, color: '#b5bfbb', fontFamily: "'JetBrains Mono', monospace" },
    tableCard: { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    cardHdr:   { padding: '10px 16px', borderBottom: '1px solid #eaeeec', background: '#fafcfb', display: 'flex', alignItems: 'center', gap: 8 },
    table:     { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
    th:        { padding: '8px 12px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10.5, letterSpacing: '0.04em', whiteSpace: 'nowrap' },
    td:        { padding: '7px 12px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', whiteSpace: 'nowrap', verticalAlign: 'middle' },
    mono:      { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
    filterSel: { padding: '5px 8px', border: '1px solid #eaeeec', borderRadius: 4, fontSize: 12, color: '#2f3733', background: 'white', cursor: 'pointer' },
  };

  return (
    <div style={dS.root}>
      <div style={dS.hdr}>
        <div>
          <div style={dS.title}>Centro de Exports</div>
          <div style={dS.sub}>Módulo D — Descarga de reportes y packs de datos</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#6b7772', fontWeight: 500 }}>Período:</span>
          <select style={dS.filterSel} value={mesFilter} onChange={(e) => setMesFilter(e.target.value)}>
            {['Abril 2025','Marzo 2025','Febrero 2025','Enero 2025'].map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
      </div>

      <div style={dS.grid}>
        {EXPORT_TYPES.map((et) => (
          <div key={et.id} style={dS.exportCard}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <div style={{ ...dS.iconWrap, background: et.bg }}>
                <Icon name={et.icon} size={18} color={et.color} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={dS.cardTitle}>{et.title}</div>
              </div>
            </div>
            <div style={dS.cardDesc}>{et.desc}</div>
            <div style={dS.tags}>
              {et.tags.map((t) => (<span key={t} style={dS.tag}>{t}</span>))}
            </div>
            <div style={dS.footer}>
              <div style={{ display: 'flex', align: 'center', gap: 8 }}>
                <span style={{ ...dS.extBadge, background: et.bg, color: et.color }}>{et.ext}</span>
                <span style={dS.sizeText}>{et.size}</span>
              </div>
              <DownloadButton
                loading={loading[et.id]}
                done={done[et.id]}
                onDownload={() => handleDownload(et.id)}
              />
            </div>
          </div>
        ))}
      </div>

      <div style={dS.tableCard}>
        <div style={dS.cardHdr}>
          <Icon name="clock" size={14} color="#6b7772" />
          <span style={{ fontSize: 12, fontWeight: 700, color: '#2f3733', flex: 1 }}>Historial de Exports Recientes</span>
          <span style={{ fontSize: 10.5, color: '#8f9c97' }}>últimos 30 días</span>
        </div>
        <table style={dS.table}>
          <thead>
            <tr>
              {['Tipo de export', 'Generado por', 'Fecha y hora', 'Tamaño', 'Estado', 'Acción'].map((h) => (
                <th key={h} style={dS.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {RECENT_EXPORTS.map((r, i) => (
              <tr key={r.id} style={{ background: i % 2 === 0 ? 'white' : '#fafcfb' }}>
                <td style={dS.td}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <Icon name={r.icon} size={13} color="#8f9c97" />
                    <span style={{ fontSize: 12 }}>{r.type}</span>
                  </div>
                </td>
                <td style={dS.td}>{r.user}</td>
                <td style={{ ...dS.td, ...dS.mono, color: '#4a5550' }}>{r.fecha}</td>
                <td style={{ ...dS.td, ...dS.mono }}>{r.size}</td>
                <td style={dS.td}>
                  <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 3, background: r.estado === 'OK' ? '#d4edda' : '#fde8e8', color: r.estado === 'OK' ? '#155a2e' : '#7a1c1c' }}>
                    {r.estado}
                  </span>
                </td>
                <td style={dS.td}>
                  {r.estado === 'OK' ? (
                    <button
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px', border: '1px solid #eaeeec', borderRadius: 3, background: 'white', fontSize: 11, color: '#124e2f', cursor: 'pointer' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#edf5f0')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'white')}
                    >
                      <Icon name="download" size={12} color="#124e2f" /> Re-descargar
                    </button>
                  ) : (
                    <button
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px', border: '1px solid #f5b7b1', borderRadius: 3, background: '#fde8e8', fontSize: 11, color: '#7a1c1c', cursor: 'pointer' }}
                    >
                      <Icon name="refresh-cw" size={12} color="#7a1c1c" /> Reintentar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
