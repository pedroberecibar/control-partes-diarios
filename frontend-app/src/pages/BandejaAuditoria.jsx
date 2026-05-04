import { useEffect, useMemo, useState } from 'react';
import { Icon, PARTE_ESTADO_CONFIG, StatusChip, TRAZA_CONFIG } from '../components/Icon';
import { VisorModal } from '../components/visor/Visor';
import { getPartes } from '../api/partesApi';
import { normalizeParte } from '../api/normalizers';

const PER_PAGE = 25;
const TRAZAS_DANGER = ['Sin Orden Asociada', 'Repetido X Sumi', 'Error Sumi Nro Med'];

const COLS = [
  { id: 'id',          label: 'ID Parte',       w: 120 },
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

export function BandejaAuditoria({ onOpenDetalle }) {
  const [partes, setPartes]           = useState([]);
  const [loading, setLoading]         = useState(true);
  const [usingMock, setUsingMock]     = useState(false);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [filters, setFilters]         = useState({ traza: [], estado: [], contratista: [], lote: '', search: '' });
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sortCol, setSortCol]         = useState('id');
  const [sortDir, setSortDir]         = useState('asc');
  const [page, setPage]               = useState(1);
  const [visorParte, setVisorParte]   = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const PAGE_SIZE = 1000;
    async function fetchAll() {
      const allItems = [];
      let skip = 0;
      while (true) {
        const res = await getPartes({ skip, limit: PAGE_SIZE });
        allItems.push(...res.items);
        if (allItems.length >= res.total || res.items.length < PAGE_SIZE) break;
        skip += PAGE_SIZE;
      }
      return allItems;
    }

    fetchAll()
      .then((items) => {
        if (!cancelled) {
          setPartes(items.map(normalizeParte));
          setUsingMock(false);
          setFilters({ traza: [], estado: [], contratista: [], lote: '', search: '' });
          setPage(1);
        }
      })
      .catch(() => {
        if (!cancelled) setUsingMock(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  // Derive filter options from loaded data
  const availableTrazas = useMemo(() => {
    const s = new Set(partes.map((p) => p.traza).filter((t) => t && t !== '—'));
    return [...s].sort();
  }, [partes]);

  const availableEstados = useMemo(() => {
    const s = new Set(partes.map((p) => p.estado).filter((e) => e && e !== '—'));
    return [...s].sort();
  }, [partes]);

  const availableContratistas = useMemo(() => {
    const s = new Set(partes.map((p) => p.contratista).filter((c) => c && c !== '—'));
    return [...s].sort();
  }, [partes]);

  const filtered = useMemo(() => {
    let rows = partes;
    if (filters.traza.length)       rows = rows.filter((r) => filters.traza.includes(r.traza));
    if (filters.estado.length)      rows = rows.filter((r) => filters.estado.includes(r.estado));
    if (filters.contratista.length) rows = rows.filter((r) => filters.contratista.includes(r.contratista));
    if (filters.lote)               rows = rows.filter((r) => r.lote === filters.lote);
    if (filters.search) {
      const q = filters.search.toLowerCase();
      rows = rows.filter(
        (r) =>
          r.id.toLowerCase().includes(q) ||
          r.operario.toLowerCase().includes(q) ||
          r.suministro.includes(filters.search) ||
          String(r.ord_nro).toLowerCase().includes(q)
      );
    }
    return rows;
  }, [filters, partes]);

  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const av = a[sortCol] ?? ''; const bv = b[sortCol] ?? '';
      const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [filtered, sortCol, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / PER_PAGE));
  const pageRows = sorted.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  const trazaCounts = useMemo(() => {
    const c = {};
    partes.forEach((r) => { c[r.traza] = (c[r.traza] || 0) + 1; });
    return c;
  }, [partes]);

  function toggleFilter(key, val) {
    setFilters((f) => {
      const arr = f[key];
      return { ...f, [key]: arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val] };
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
    if (pageRows.every((r) => selectedIds.has(r.id))) {
      setSelectedIds((s) => {
        const n = new Set(s);
        pageRows.forEach((r) => n.delete(r.id));
        return n;
      });
    } else {
      setSelectedIds((s) => {
        const n = new Set(s);
        pageRows.forEach((r) => n.add(r.id));
        return n;
      });
    }
  }
  function handleSort(col) {
    if (sortCol === col) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortCol(col); setSortDir('asc'); }
  }

  const allSelected = pageRows.length > 0 && pageRows.every((r) => selectedIds.has(r.id));
  const someSelected = selectedIds.size > 0;

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
    mockBanner: { padding: '5px 14px', background: '#fff3cd', borderBottom: '1px solid #f5d56a', display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#7a4a00', fontWeight: 600, flexShrink: 0 },
  };

  const activeFilterCount =
    filters.traza.length + filters.estado.length + filters.contratista.length + (filters.lote ? 1 : 0);

  return (
    <div style={bS.root}>
      <div style={bS.filterSidebar}>
        <div style={bS.filterHeader}>
          <span style={bS.filterTitle}>Filtros</span>
          {activeFilterCount > 0 && (
            <button
              style={bS.clearBtn}
              onClick={() => setFilters({ traza: [], estado: [], contratista: [], lote: '', search: '' })}
            >
              Limpiar
            </button>
          )}
        </div>

        <div style={bS.filterSection}>
          <div style={bS.filterSectionLabel}>Traza Calidad</div>
          {availableTrazas.map((t) => {
            const active = filters.traza.includes(t);
            return (
              <div
                key={t}
                style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, cursor: 'pointer' }}
                onClick={() => toggleFilter('traza', t)}
              >
                <input type="checkbox" checked={active} readOnly style={bS.checkbox} />
                <span style={{ fontSize: 11.5, color: active ? '#124e2f' : '#4a5550', fontWeight: active ? 600 : 400 }}>{t}</span>
                <span style={{ marginLeft: 'auto', fontSize: 10, color: '#8f9c97' }}>{trazaCounts[t] || 0}</span>
              </div>
            );
          })}
        </div>

        <div style={bS.filterSection}>
          <div style={bS.filterSectionLabel}>Estado</div>
          {availableEstados.map((e) => {
            const active = filters.estado.includes(e);
            return (
              <div
                key={e}
                style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, cursor: 'pointer' }}
                onClick={() => toggleFilter('estado', e)}
              >
                <input type="checkbox" checked={active} readOnly style={bS.checkbox} />
                <span style={{ fontSize: 11.5, color: active ? '#124e2f' : '#4a5550', fontWeight: active ? 600 : 400 }}>{e}</span>
              </div>
            );
          })}
        </div>

        <div style={bS.filterSection}>
          <div style={bS.filterSectionLabel}>Contratista</div>
          {availableContratistas.map((c) => {
            const active = filters.contratista.includes(c);
            return (
              <div
                key={c}
                style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, cursor: 'pointer' }}
                onClick={() => toggleFilter('contratista', c)}
              >
                <input type="checkbox" checked={active} readOnly style={bS.checkbox} />
                <span style={{ fontSize: 11.5, color: active ? '#124e2f' : '#4a5550', fontWeight: active ? 600 : 400 }}>{c}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div style={bS.main}>
        {usingMock && (
          <div style={bS.mockBanner}>
            <Icon name="alert-circle" size={12} color="#e6910a" />
            Backend no disponible — mostrando datos de demostración
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
              placeholder="ID, operario, suministro, orden…"
              value={filters.search}
              onChange={(e) => { setFilters((f) => ({ ...f, search: e.target.value })); setPage(1); }}
            />
          </div>
          <span style={bS.count}>{sorted.length} partes</span>
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
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '60px 0', color: '#8f9c97', fontSize: 13 }}>
              Cargando partes…
            </div>
          )}
          {!loading && sorted.length === 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px 0', gap: 8 }}>
              <Icon name={usingMock ? 'alert-circle' : 'inbox'} size={28} color="#d5ddd9" />
              <span style={{ fontSize: 13, color: '#8f9c97' }}>
                {usingMock
                  ? 'No se pudo conectar al backend.'
                  : activeFilterCount > 0
                    ? 'No hay partes que coincidan con los filtros activos.'
                    : 'No hay partes procesados aún. Cargá un lote para comenzar.'}
              </span>
            </div>
          )}
          {!loading && sorted.length > 0 && <table style={bS.table}>
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
              {pageRows.map((row, i) => {
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
                    <td style={{ ...bS.td, ...bS.mono, color: '#124e2f', fontWeight: 600 }}>{row.id}</td>
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
            {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, sorted.length)} de {sorted.length} partes
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
