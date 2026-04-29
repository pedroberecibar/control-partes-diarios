import { useState } from 'react';
import { Icon, LOTE_ESTADO_CONFIG, StatusChip } from '../components/Icon';
import { LOTES_DATA } from '../data/lotesMock';

export function ListaLotes({ onSubir }) {
  const [search, setSearch] = useState('');
  const [estadoFilter, setEstadoFilter] = useState('');

  const filtered = LOTES_DATA.filter((l) => {
    const q = search.toLowerCase();
    const matchSearch =
      !q ||
      l.archivo.toLowerCase().includes(q) ||
      l.contratista.toLowerCase().includes(q) ||
      l.id.toLowerCase().includes(q);
    const matchEstado = !estadoFilter || l.estado === estadoFilter;
    return matchSearch && matchEstado;
  });

  const lS = {
    root: { padding: 20, overflow: 'auto', height: '100%', boxSizing: 'border-box' },
    pageHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 },
    pageTitle: { fontSize: 17, fontWeight: 700, color: '#111614' },
    pageSub: { fontSize: 12, color: '#8f9c97', marginTop: 2 },
    btnPrimary: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', border: 'none', borderRadius: 4, background: '#124e2f', fontSize: 12.5, fontWeight: 600, color: 'white', cursor: 'pointer' },
    kpiRow: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 18 },
    kpiCard: { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, padding: '14px 16px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    kpiLabel: { fontSize: 10.5, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 },
    kpiValue: { fontSize: 22, fontWeight: 700, color: '#111614', lineHeight: 1.1 },
    kpiSub: { fontSize: 11, color: '#8f9c97', marginTop: 3 },
    tableCard: { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    toolbar: { padding: '10px 16px', borderBottom: '1px solid #eaeeec', display: 'flex', alignItems: 'center', gap: 10 },
    searchWrap: { display: 'flex', alignItems: 'center', gap: 7, background: '#f5f7f6', border: '1px solid #eaeeec', borderRadius: 4, padding: '5px 10px', width: 240 },
    searchInput: { border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: '#111614', width: '100%' },
    filterSelect: { padding: '5px 8px', border: '1px solid #eaeeec', borderRadius: 4, fontSize: 12, color: '#2f3733', background: 'white', cursor: 'pointer' },
    count: { fontSize: 12, color: '#6b7772', fontWeight: 500, flex: 1 },
    btn: { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 11px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, fontWeight: 600, color: '#2f3733', cursor: 'pointer' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
    th: { padding: '8px 12px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10.5, letterSpacing: '0.04em', whiteSpace: 'nowrap' },
    td: { padding: '8px 12px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', whiteSpace: 'nowrap', verticalAlign: 'middle' },
    mono: { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
    trHover: { cursor: 'pointer', transition: 'background 0.08s' },
    actionBtn: { border: 'none', background: 'transparent', cursor: 'pointer', color: '#8f9c97', display: 'inline-flex', alignItems: 'center', padding: '2px 4px', borderRadius: 3, transition: 'all 0.1s' },
  };

  const kpis = [
    { label: 'Total Lotes (mes)', value: LOTES_DATA.length, sub: 'todos los estados' },
    { label: 'Lotes OK',          value: LOTES_DATA.filter((l) => l.estado === 'OK').length, sub: 'procesados correctamente', color: '#155a2e' },
    { label: 'En Proceso',        value: LOTES_DATA.filter((l) => ['VALIDANDO', 'EN_CORE', 'EN_OBS', 'RECIBIDO'].includes(l.estado)).length, sub: 'pendientes de completar', color: '#7a4a00' },
    { label: 'Con Errores',       value: LOTES_DATA.filter((l) => ['RECHAZADO_SINTAXIS', 'ERROR'].includes(l.estado)).length, sub: 'requieren atención', color: '#7a1c1c' },
  ];

  return (
    <div style={lS.root}>
      <div style={lS.pageHeader}>
        <div>
          <div style={lS.pageTitle}>Lista de Lotes</div>
          <div style={lS.pageSub}>Módulo A — Ingesta de Partes Diarios</div>
        </div>
        <button style={lS.btnPrimary} onClick={onSubir}>
          <Icon name="upload" size={14} /> Subir Archivos
        </button>
      </div>

      <div style={lS.kpiRow}>
        {kpis.map((k) => (
          <div key={k.label} style={lS.kpiCard}>
            <div style={lS.kpiLabel}>{k.label}</div>
            <div style={{ ...lS.kpiValue, color: k.color || '#111614' }}>{k.value}</div>
            <div style={lS.kpiSub}>{k.sub}</div>
          </div>
        ))}
      </div>

      <div style={lS.tableCard}>
        <div style={lS.toolbar}>
          <div style={lS.searchWrap}>
            <Icon name="search" size={13} color="#8f9c97" />
            <input
              style={lS.searchInput}
              placeholder="Buscar archivo, contratista…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            style={lS.filterSelect}
            value={estadoFilter}
            onChange={(e) => setEstadoFilter(e.target.value)}
          >
            <option value="">Todos los estados</option>
            {Object.keys(LOTE_ESTADO_CONFIG).map((e) => (
              <option key={e} value={e}>{e}</option>
            ))}
          </select>
          <span style={lS.count}>{filtered.length} lotes</span>
          <div style={{ flex: 1 }} />
          <button style={lS.btn}><Icon name="download" size={13} /> Exportar</button>
        </div>
        <table style={lS.table}>
          <thead>
            <tr>
              {['ID Lote', 'Archivo', 'Contratista', 'Subido por', 'Fecha', 'Estado', 'Filas leídas', 'OK', 'Observ.', 'Errores', 'Acciones'].map((h) => (
                <th key={h} style={lS.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((lote, i) => {
              const ec = LOTE_ESTADO_CONFIG[lote.estado] || {};
              const baseBg = i % 2 === 0 ? 'white' : '#fafcfb';
              return (
                <tr
                  key={lote.id}
                  style={{ ...lS.trHover, background: baseBg }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#f5f7f6')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = baseBg)}
                >
                  <td style={{ ...lS.td, ...lS.mono, color: '#124e2f', fontWeight: 600 }}>{lote.id}</td>
                  <td style={lS.td}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Icon name="file-text" size={13} color="#8f9c97" />
                      <span style={{ fontSize: 12 }}>{lote.archivo}</span>
                    </div>
                  </td>
                  <td style={lS.td}>
                    <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 6px', borderRadius: 3, background: lote.contratista === 'CONECTAR' ? '#edf5f0' : '#dbeafe', color: lote.contratista === 'CONECTAR' ? '#124e2f' : '#0d4272' }}>
                      {lote.contratista}
                    </span>
                  </td>
                  <td style={lS.td}>{lote.subido_por}</td>
                  <td style={{ ...lS.td, ...lS.mono, color: '#4a5550' }}>{lote.fecha}</td>
                  <td style={lS.td}><StatusChip label={lote.estado} config={ec} /></td>
                  <td style={{ ...lS.td, ...lS.mono, textAlign: 'right' }}>{lote.filas.toLocaleString()}</td>
                  <td style={{ ...lS.td, ...lS.mono, textAlign: 'right', color: '#155a2e', fontWeight: 600 }}>{lote.ok.toLocaleString()}</td>
                  <td style={{ ...lS.td, ...lS.mono, textAlign: 'right', color: lote.advertencias > 0 ? '#7a4a00' : '#8f9c97' }}>
                    {lote.advertencias > 0 ? lote.advertencias : '—'}
                  </td>
                  <td style={{ ...lS.td, ...lS.mono, textAlign: 'right', color: lote.errores > 0 ? '#c0392b' : '#8f9c97', fontWeight: lote.errores > 0 ? 700 : 400 }}>
                    {lote.errores > 0 ? lote.errores : '—'}
                  </td>
                  <td style={lS.td}>
                    {['eye', 'refresh-cw', 'download'].map((icon) => (
                      <button
                        key={icon}
                        style={lS.actionBtn}
                        title={icon}
                        onMouseEnter={(e) => { e.currentTarget.style.background = '#edf5f0'; e.currentTarget.style.color = '#124e2f'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = ''; e.currentTarget.style.color = '#8f9c97'; }}
                      >
                        <Icon name={icon} size={13} />
                      </button>
                    ))}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
