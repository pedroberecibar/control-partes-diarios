import { useEffect, useState } from 'react';
import { Icon, PARTE_ESTADO_CONFIG, StatusChip, TRAZA_CONFIG } from '../components/Icon';
import { VisorModal } from '../components/visor/Visor';
import { getPartes, getCodEpecValores } from '../api/partesApi';
import { getLotes } from '../api/lotesApi';
import { normalizeParte } from '../api/normalizers';

const PER_PAGE = 25;
const TRAZAS_DANGER = ['Sin Orden Asociada', 'Repetido X Sumi', 'Error Sumi Nro Med'];

const COLS = [
  { id: 'contratista', label: 'Contratista',     w: 96  },
  { id: 'operario',    label: 'Operario',        w: 130 },
  { id: 'fecha',       label: 'Fecha',           w: 80  },
  { id: 'suministro',  label: 'Suministro',      w: 90  },
  { id: 'cod_epec',    label: 'Cód. EPEC',       w: 76  },
  { id: 'ord_nro',     label: 'ORD_NRO',         w: 130 },
  { id: 'traza',       label: 'TRAZA_CALIDAD',   w: 170 },
  { id: 'uses',        label: 'USES',            w: 62  },
  { id: 'estado',      label: 'Estado',          w: 90  },
  { id: 'fotos',       label: 'Fotos',           w: 52  },
];

// Backend sort key mapping (frontend col id → backend sort_by param)
const SORT_COL_BACKEND = {
  id:          'id',
  fecha:       'fecha',
  suministro:  'suministro',
  ord_nro:     'ord_nro',
  traza:       'traza',
  estado:      'estado',
  uses:        'uses',
};

// Static sidebar options — IDs match dim_traza_calidad_bi and dim_estado_bi
const TRAZAS_OPCIONES = [
  { id: 1,  label: 'Original OK' },
  { id: 2,  label: 'Corregido Nro EQP Invertidos' },
  { id: 3,  label: 'Corregido Nro Medidor' },
  { id: 4,  label: 'Corregido Sumi' },
  { id: 5,  label: 'Corregido Sumi Nro EQP' },
  { id: 6,  label: 'No Corresponde TOR CE' },
  { id: 7,  label: 'Sin Orden Asociada' },
  { id: 8,  label: 'Error Sumi Sin Nro Medidor' },
  { id: 9,  label: 'Error Sumi Y Nro Medidor' },
  { id: 10, label: 'Informados con ORD-SUMI aprobado' },
  { id: 11, label: 'Otro Origen' },
  { id: 12, label: 'Corregido Medidor Vacio' },
  { id: 13, label: 'Informado - No Ejecutado' },
  { id: 14, label: 'Código de Tarea No Mapeado' },
  { id: 15, label: 'Fecha Inválida' },
  { id: 19, label: 'Rescatado por Oracle' },
  { id: 20, label: 'Múltiples Candidatos Oracle' },
];

const ESTADOS_OPCIONES = [
  { id: 1, label: 'Aprobado' },
  { id: 2, label: 'Revisión' },
  { id: 3, label: 'Rechazado' },
  { id: 4, label: 'Fuera de Alcance' },
];

const CONTRATISTAS_OPCIONES = [
  { id: 1, label: 'CONECTAR' },
  { id: 2, label: 'COOPLYF' },
];

const STORAGE_KEY = 'bandeja_estado';
const DEFAULTS = { filters: { id_trazas: [], id_estados: [], contratista_ids: [], lote_ids: [], cod_epec_ids: [], search: '' }, page: 1, sortCol: 'id', sortDir: 'desc' };

function readStorage() {
  try { return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
}

export function BandejaAuditoria({ onOpenDetalle, initialLoteId }) {
  const [partes, setPartes]           = useState([]);
  const [total, setTotal]             = useState(0);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [filters, setFilters]         = useState(() => {
    const stored = readStorage().filters ?? DEFAULTS.filters;
    // Garantizar que lote_ids exista aunque venga de storage viejo
    return { ...DEFAULTS.filters, ...stored };
  });
  const [codEpecOpciones, setCodEpecOpciones] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sortCol, setSortCol]         = useState(() => readStorage().sortCol ?? DEFAULTS.sortCol);
  const [sortDir, setSortDir]         = useState(() => readStorage().sortDir ?? DEFAULTS.sortDir);
  const [page, setPage]               = useState(() => readStorage().page ?? DEFAULTS.page);
  const [visorParte, setVisorParte]   = useState(null);
  const [lotesDisponibles, setLotesDisponibles] = useState([]);

  // Cargar valores distinct de cod_epec para el filtro de sidebar
  useEffect(() => {
    getCodEpecValores()
      .then((vals) => setCodEpecOpciones(Array.isArray(vals) ? vals : []))
      .catch(() => {});
  }, []);

  // Cargar lista de lotes procesados para el filtro manual
  useEffect(() => {
    getLotes(0, 200)
      .then((res) => {
        const procesados = (res.items || []).filter((l) => l.estado === 'APROBADO');
        setLotesDisponibles(procesados.map((l) => ({ id: l.id, label: l.nombre_archivo })));
      })
      .catch(() => {}); // silencioso — si falla, el filtro queda vacío
  }, []);

  // Cuando App.jsx navega desde ListaLotes con un loteId, aplicar el filtro inmediatamente
  useEffect(() => {
    if (initialLoteId != null) {
      setFilters((f) => ({ ...f, lote_ids: [initialLoteId] }));
      setPage(1);
    }
  }, [initialLoteId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    getPartes({
      skip: (page - 1) * PER_PAGE,
      limit: PER_PAGE,
      id_trazas: filters.id_trazas,
      id_estados: filters.id_estados,
      contratista_ids: filters.contratista_ids,
      lote_ids: filters.lote_ids ?? [],
      cod_epec_ids: filters.cod_epec_ids ?? [],
      search: filters.search || undefined,
      sort_by: SORT_COL_BACKEND[sortCol] || 'id',
      sort_dir: sortDir,
    })
      .then((res) => {
        if (!cancelled) {
          setPartes(res.items.map(normalizeParte));
          setTotal(res.total);
        }
      })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [page, sortCol, sortDir, filters]);

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ filters, page, sortCol, sortDir }));
  }, [filters, page, sortCol, sortDir]);

  const totalPages = Math.max(1, Math.ceil(total / PER_PAGE));

  function toggleFilter(key, id) {
    setFilters((f) => {
      const arr = f[key] ?? [];
      return { ...f, [key]: arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id] };
    });
    setPage(1);
  }
  function toggleRow(id) {
    setSelectedIds((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  }
  function toggleAll() {
    if (partes.every((r) => selectedIds.has(r.id))) {
      setSelectedIds((s) => {
        const n = new Set(s);
        partes.forEach((r) => n.delete(r.id));
        return n;
      });
    } else {
      setSelectedIds((s) => {
        const n = new Set(s);
        partes.forEach((r) => n.add(r.id));
        return n;
      });
    }
  }
  function handleSort(col) {
    if (sortCol === col) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortCol(col); setSortDir('asc'); }
  }

  const allSelected = partes.length > 0 && partes.every((r) => selectedIds.has(r.id));
  const someSelected = selectedIds.size > 0;

  const activeFilterCount =
    filters.id_trazas.length + filters.id_estados.length + filters.contratista_ids.length + (filters.lote_ids?.length ?? 0) + (filters.cod_epec_ids?.length ?? 0);

  const bS = {
    root: { display: 'flex', height: '100%', overflow: 'hidden', background: '#f5f7f6' },
    filterSidebar: {
      width: sidebarOpen ? 220 : 0,
      flexShrink: 0,
      background: 'white',
      borderRight: '1px solid #eaeeec',
      overflowY: 'auto',
      overflowX: 'hidden',
      transition: 'width 0.18s ease',
      display: 'flex',
      flexDirection: 'column',
    },
    filterHeader: { padding: '12px 14px 8px', borderBottom: '1px solid #eaeeec', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 },
    filterTitle: { fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: '#6b7772' },
    filterSection: { padding: '10px 14px', borderBottom: '1px solid #f5f7f6' },
    filterSectionLabel: { fontSize: 10.5, fontWeight: 700, color: '#4a5550', marginBottom: 6, letterSpacing: '0.05em', textTransform: 'uppercase' },
    clearBtn: { fontSize: 10.5, color: '#124e2f', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 },
    main: { flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' },
    toolbar: { padding: '10px 16px', background: 'white', borderBottom: '1px solid #eaeeec', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 },
    searchWrap: { display: 'flex', alignItems: 'center', gap: 7, background: '#f5f7f6', border: '1px solid #eaeeec', borderRadius: 4, padding: '5px 10px', flex: 1, maxWidth: 280 },
    searchInput: { border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: '#111614', width: '100%' },
    count: { fontSize: 12, color: '#6b7772', fontWeight: 500, whiteSpace: 'nowrap' },
    btn: { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 11px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, fontWeight: 600, color: '#2f3733', cursor: 'pointer', whiteSpace: 'nowrap' },
    bulkBar: { padding: '8px 16px', background: '#edf5f0', borderBottom: '1px solid #a8d9c0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 },
    bulkCount: { fontSize: 12, fontWeight: 600, color: '#124e2f', flex: 1 },
    bulkBtn: { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', border: '1px solid #a8d9c0', borderRadius: 4, background: 'white', fontSize: 11.5, fontWeight: 600, cursor: 'pointer', color: '#124e2f' },
    bulkBtnDanger: { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', border: '1px solid #f5b7b1', borderRadius: 4, background: '#fde8e8', fontSize: 11.5, fontWeight: 600, cursor: 'pointer', color: '#7a1c1c' },
    tableWrap: { flex: 1, overflow: 'auto' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
    th: { padding: '8px 10px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10.5, letterSpacing: '0.04em', whiteSpace: 'nowrap', position: 'sticky', top: 0, zIndex: 2, userSelect: 'none', cursor: 'pointer' },
    thInner: { display: 'flex', alignItems: 'center', gap: 4 },
    td: { padding: '7px 10px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', whiteSpace: 'nowrap', verticalAlign: 'middle' },
    mono: { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
    trHover: { cursor: 'pointer', transition: 'background 0.08s' },
    checkbox: { width: 14, height: 14, cursor: 'pointer', accentColor: '#124e2f' },
    pagination: { padding: '10px 16px', background: 'white', borderTop: '1px solid #eaeeec', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 },
    pageBtn: { width: 28, height: 28, border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, cursor: 'pointer', color: '#4a5550', display: 'flex', alignItems: 'center', justifyContent: 'center' },
    pageBtnActive: { background: '#124e2f', color: 'white', border: '1px solid #124e2f' },
    actionBtn: { border: 'none', background: 'transparent', cursor: 'pointer', color: '#8f9c97', display: 'inline-flex', alignItems: 'center', padding: '3px', borderRadius: 3 },
  };

  return (
    <div style={bS.root}>
      <div style={bS.filterSidebar}>
        <div style={bS.filterHeader}>
          <span style={bS.filterTitle}>Filtros</span>
          {activeFilterCount > 0 && (
            <button
              style={bS.clearBtn}
              onClick={() => { setFilters({ id_trazas: [], id_estados: [], contratista_ids: [], lote_ids: [], cod_epec_ids: [], search: '' }); setPage(1); }}
            >
              Limpiar
            </button>
          )}
        </div>

        <div style={bS.filterSection}>
          <div style={bS.filterSectionLabel}>Traza Calidad</div>
          {TRAZAS_OPCIONES.map((t) => {
            const active = filters.id_trazas.includes(t.id);
            return (
              <div
                key={t.id}
                style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, cursor: 'pointer' }}
                onClick={() => toggleFilter('id_trazas', t.id)}
              >
                <input type="checkbox" checked={active} readOnly style={bS.checkbox} />
                <span style={{ fontSize: 11.5, color: active ? '#124e2f' : '#4a5550', fontWeight: active ? 600 : 400 }}>{t.label}</span>
              </div>
            );
          })}
        </div>

        <div style={bS.filterSection}>
          <div style={bS.filterSectionLabel}>Estado</div>
          {ESTADOS_OPCIONES.map((e) => {
            const active = filters.id_estados.includes(e.id);
            return (
              <div
                key={e.id}
                style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, cursor: 'pointer' }}
                onClick={() => toggleFilter('id_estados', e.id)}
              >
                <input type="checkbox" checked={active} readOnly style={bS.checkbox} />
                <span style={{ fontSize: 11.5, color: active ? '#124e2f' : '#4a5550', fontWeight: active ? 600 : 400 }}>{e.label}</span>
              </div>
            );
          })}
        </div>

        <div style={bS.filterSection}>
          <div style={bS.filterSectionLabel}>Contratista</div>
          {CONTRATISTAS_OPCIONES.map((c) => {
            const active = filters.contratista_ids.includes(c.id);
            return (
              <div
                key={c.id}
                style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, cursor: 'pointer' }}
                onClick={() => toggleFilter('contratista_ids', c.id)}
              >
                <input type="checkbox" checked={active} readOnly style={bS.checkbox} />
                <span style={{ fontSize: 11.5, color: active ? '#124e2f' : '#4a5550', fontWeight: active ? 600 : 400 }}>{c.label}</span>
              </div>
            );
          })}
        </div>

        {/* Sección: Cód. EPEC */}
        <div style={bS.filterSection}>
          <div style={bS.filterSectionLabel}>Cód. EPEC</div>
          {codEpecOpciones.length === 0 ? (
            <span style={{ fontSize: 11, color: '#aab5b0', fontStyle: 'italic' }}>Sin datos</span>
          ) : (
            codEpecOpciones.map((code) => {
              const active = (filters.cod_epec_ids ?? []).includes(code);
              return (
                <div
                  key={code}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, cursor: 'pointer' }}
                  onClick={() => toggleFilter('cod_epec_ids', code)}
                >
                  <input type="checkbox" checked={active} readOnly style={bS.checkbox} />
                  <span style={{ fontSize: 11.5, color: active ? '#124e2f' : '#4a5550', fontWeight: active ? 600 : 400, fontFamily: "'JetBrains Mono', monospace" }}>{code}</span>
                </div>
              );
            })
          )}
        </div>

        {/* Sección: Archivo / Lote */}
        <div style={bS.filterSection}>
          <div style={bS.filterSectionLabel}>Archivo (Lote)</div>
          {lotesDisponibles.length === 0 ? (
            <span style={{ fontSize: 11, color: '#aab5b0', fontStyle: 'italic' }}>Sin lotes procesados</span>
          ) : (
            lotesDisponibles.map((lote) => {
              const active = (filters.lote_ids ?? []).includes(lote.id);
              return (
                <div
                  key={lote.id}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, cursor: 'pointer' }}
                  onClick={() => toggleFilter('lote_ids', lote.id)}
                >
                  <input type="checkbox" checked={active} readOnly style={bS.checkbox} />
                  <span
                    title={lote.label}
                    style={{
                      fontSize: 11,
                      color: active ? '#124e2f' : '#4a5550',
                      fontWeight: active ? 600 : 400,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      maxWidth: 160,
                    }}
                  >
                    {lote.label}
                  </span>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div style={bS.main}>
        {error && (
          <div style={{ padding: '5px 14px', background: '#fde8e8', borderBottom: '1px solid #f5b7b1', fontSize: 11, color: '#7a1c1c', fontWeight: 600, flexShrink: 0 }}>
            Backend no disponible
          </div>
        )}

        <div style={bS.toolbar}>
          <button style={{ ...bS.btn, padding: '5px 8px' }} onClick={() => setSidebarOpen((v) => !v)} title="Filtros">
            <Icon name="filter" size={13} />
            {activeFilterCount > 0 && (
              <span style={{ background: '#124e2f', color: 'white', borderRadius: 9, padding: '0 5px', fontSize: 10, fontWeight: 700 }}>
                {activeFilterCount}
              </span>
            )}
          </button>
          <div style={bS.searchWrap}>
            <Icon name="search" size={13} color="#8f9c97" />
            <input
              style={bS.searchInput}
              placeholder="ID, suministro, orden…"
              value={filters.search}
              onChange={(e) => { setFilters((f) => ({ ...f, search: e.target.value })); setPage(1); }}
            />
          </div>
          <span style={bS.count}>{total} partes</span>
          <div style={{ flex: 1 }} />
          <button style={bS.btn}><Icon name="download" size={13} /> Exportar</button>
          <button style={bS.btn}><Icon name="columns" size={13} /> Columnas</button>
        </div>

        {someSelected && (
          <div style={bS.bulkBar}>
            <span style={bS.bulkCount}>{selectedIds.size} seleccionados</span>
            <button style={bS.bulkBtn}><Icon name="check-circle" size={13} /> Aprobar</button>
            <button style={bS.bulkBtnDanger}><Icon name="x-circle" size={13} /> Rechazar</button>
            <button style={bS.bulkBtn}><Icon name="download" size={13} /> Exportar selección</button>
            <button style={{ ...bS.clearBtn, fontSize: 11 }} onClick={() => setSelectedIds(new Set())}>Cancelar</button>
          </div>
        )}

        <div style={bS.tableWrap}>
          {loading && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 0', gap: 12 }}>
              <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
              <Icon name="loader" size={28} color="#8f9c97" style={{ animation: 'spin 1s linear infinite' }} />
              <div style={{ color: '#8f9c97', fontSize: 13, fontWeight: 500 }}>Cargando partes…</div>
            </div>
          )}
          {!loading && partes.length === 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 0', gap: 8 }}>
              <Icon name={usingMock ? 'alert-circle' : 'inbox'} size={28} color="#d5ddd9" />
              <span style={{ fontSize: 13, color: '#8f9c97' }}>
                {usingMock
                  ? 'No se pudo conectar al backend.'
                  : activeFilterCount > 0 || filters.search
                    ? 'No hay partes que coincidan con los filtros activos.'
                    : 'No hay partes procesados aún. Cargá un lote para comenzar.'}
              </span>
            </div>
          )}
          {!loading && partes.length > 0 && <table style={bS.table}>
            <thead>
              <tr>
                <th style={{ ...bS.th, width: 36, padding: 8 }}>
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} style={{ ...bS.checkbox, display: 'block' }} />
                </th>
                {COLS.map((col) => (
                  <th key={col.id} style={{ ...bS.th, width: col.w }} onClick={() => handleSort(col.id)}>
                    <div style={bS.thInner}>
                      {col.label}
                      {sortCol === col.id && (
                        <Icon name={sortDir === 'asc' ? 'chevron-down' : 'chevron-right'} size={11} color="rgba(255,255,255,0.7)" />
                      )}
                    </div>
                  </th>
                ))}
                <th style={{ ...bS.th, width: 64 }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {partes.map((row, i) => {
                const selected = selectedIds.has(row.id);
                const tc = TRAZA_CONFIG[row.traza] || {};
                const ec = PARTE_ESTADO_CONFIG[row.estado] || {};
                const isDanger = TRAZAS_DANGER.includes(row.traza);
                const baseBg = selected ? '#edf5f0' : isDanger ? '#fff9f9' : i % 2 === 0 ? 'white' : '#fafcfb';
                const photoCount = row.cant_imagenes ?? 0;
                return (
                  <tr
                    key={row.id}
                    style={{ ...bS.trHover, background: baseBg }}
                    onClick={() => onOpenDetalle(row)}
                    onMouseEnter={(e) => { if (!selected) e.currentTarget.style.background = '#f5f7f6'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = baseBg; }}
                  >
                    <td style={{ ...bS.td, width: 36, padding: '7px 8px' }} onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" checked={selected} onChange={() => toggleRow(row.id)} style={bS.checkbox} />
                    </td>
                    <td style={bS.td}>
                      <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 6px', borderRadius: 3, background: row.contratista === 'CONECTAR' ? '#edf5f0' : '#dbeafe', color: row.contratista === 'CONECTAR' ? '#124e2f' : '#0d4272' }}>
                        {row.contratista}
                      </span>
                    </td>
                    <td style={bS.td}>{row.operario}</td>
                    <td style={{ ...bS.td, ...bS.mono, color: '#4a5550' }}>{row.fecha}</td>
                    <td style={{ ...bS.td, ...bS.mono }}>{row.suministro}</td>
                    <td style={{ ...bS.td, ...bS.mono, fontWeight: 600 }}>{row.cod_epec}</td>
                    <td style={{ ...bS.td, ...bS.mono, color: row.ord_nro === '—' ? '#b5bfbb' : '#2f3733' }}>{row.ord_nro}</td>
                    <td style={bS.td}><StatusChip label={tc.label || row.traza} config={tc} /></td>
                    <td style={{ ...bS.td, ...bS.mono, textAlign: 'right', color: '#4a5550' }}>{row.uses}</td>
                    <td style={bS.td}><StatusChip label={row.estado} config={ec} /></td>
                    <td style={{ ...bS.td, textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                      <div style={{ position: 'relative', display: 'inline-flex' }}>
                        <button
                          style={{ ...bS.actionBtn, color: photoCount > 0 ? '#124e2f' : '#d5ddd9' }}
                          title={photoCount > 0 ? `Ver ${photoCount} foto${photoCount > 1 ? 's' : ''}` : 'Sin fotos cargadas'}
                          onClick={() => setVisorParte(row)}
                          onMouseEnter={(e) => (e.currentTarget.style.background = '#edf5f0')}
                          onMouseLeave={(e) => (e.currentTarget.style.background = '')}
                        >
                          <Icon name="camera" size={14} color={photoCount > 0 ? '#124e2f' : '#d5ddd9'} />
                        </button>
                        {photoCount > 0 && (
                          <span
                            style={{
                              position: 'absolute', top: -4, right: -4,
                              width: 15, height: 15, borderRadius: 8,
                              background: '#124e2f', color: 'white',
                              fontSize: 8.5, fontWeight: 700,
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              border: '1.5px solid white',
                              animation: 'popIn 0.2s cubic-bezier(0.34,1.56,0.64,1)',
                            }}
                          >
                            {photoCount}
                          </span>
                        )}
                      </div>
                    </td>
                    <td style={bS.td} onClick={(e) => e.stopPropagation()}>
                      <button
                        style={bS.actionBtn}
                        title="Ver detalle"
                        onClick={() => onOpenDetalle(row)}
                        onMouseEnter={(e) => { e.currentTarget.style.background = '#edf5f0'; e.currentTarget.style.color = '#124e2f'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = ''; e.currentTarget.style.color = '#8f9c97'; }}
                      >
                        <Icon name="eye" size={14} />
                      </button>
                      <button
                        style={bS.actionBtn}
                        title="Ver bitácora"
                        onMouseEnter={(e) => { e.currentTarget.style.background = '#edf5f0'; e.currentTarget.style.color = '#124e2f'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = ''; e.currentTarget.style.color = '#8f9c97'; }}
                      >
                        <Icon name="clock" size={14} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>}
        </div>

        <div style={bS.pagination}>
          <span style={{ fontSize: 12, color: '#6b7772' }}>
            {total === 0 ? '0 partes' : `${(page - 1) * PER_PAGE + 1}–${Math.min(page * PER_PAGE, total)} de ${total} partes`}
          </span>
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <button style={bS.pageBtn} onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
              <Icon name="chevron-left" size={13} />
            </button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let p;
              if (totalPages <= 7) p = i + 1;
              else if (page <= 4) p = i + 1;
              else if (page >= totalPages - 3) p = totalPages - 6 + i;
              else p = page - 3 + i;
              return (
                <button key={p} style={{ ...bS.pageBtn, ...(p === page ? bS.pageBtnActive : {}) }} onClick={() => setPage(p)}>
                  {p}
                </button>
              );
            })}
            <button style={bS.pageBtn} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
              <Icon name="chevron-right" size={13} />
            </button>
          </div>
          <span style={{ fontSize: 12, color: '#6b7772' }}>Página {page} de {totalPages}</span>
        </div>
      </div>

      {visorParte && (
        <VisorModal
          parte={visorParte}
          onClose={() => setVisorParte(null)}
          onGoToDetalle={() => { onOpenDetalle(visorParte); setVisorParte(null); }}
        />
      )}
    </div>
  );
}
