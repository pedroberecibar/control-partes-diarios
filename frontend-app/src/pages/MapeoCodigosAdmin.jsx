import { useCallback, useEffect, useState } from 'react';
import { Icon } from '../components/Icon';
import {
  actualizarRegla,
  crearMapeo,
  crearRegla,
  desactivarMapeo,
  desactivarRegla,
  dispararSyncOracle,
  ejecutarSeed,
  getContratistas,
  getReglas,
  getSyncOracleStatus,
} from '../api/adminCodigosApi';

// ── Constantes ────────────────────────────────────────────────────────────────

const OBS_FIELDS = [
  { key: 'gabinete', label: 'Gabinete' },
  { key: 'subterraneo', label: 'Subterráneo' },
  { key: 'altura', label: 'Altura' },
  { key: 'aereo', label: 'Aéreo' },
  { key: 'equipo_medicion_reemplazado', label: 'Eq.Med. Reemplazado' },
  { key: 'acometida_realizada', label: 'Acometida' },
  { key: 'tapa_reemplazada', label: 'Tapa Reemplazada' },
  { key: 'equipo_medicion_instalado', label: 'Eq.Med. Instalado' },
];

const FASES = ['MON', 'TRI', 'AMBAS'];

const FORM_EMPTY = {
  cod_epec: '', descripcion: '', valor_uses: '',
  gabinete: false, subterraneo: false, altura: false, aereo: false,
  equipo_medicion_reemplazado: false, acometida_realizada: false,
  tapa_reemplazada: false, equipo_medicion_instalado: false,
};

const MAPEO_EMPTY = { contratista_id: '', cod_contratista: '', fase: 'MON' };

// ── Helpers visuales ─────────────────────────────────────────────────────────

function ObsDot({ active }) {
  return (
    <span style={{
      display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
      background: active ? '#124e2f' : '#d5ddd9', flexShrink: 0,
    }} />
  );
}

/** Agrupa los mapeos por nombre de contratista y muestra chips compactos. */
function MapeosCompactos({ mapeos }) {
  if (!mapeos || mapeos.length === 0) return <span style={{ fontSize: 11, color: '#c0c8c4' }}>—</span>;

  const grupos = {};
  for (const m of mapeos) {
    const k = m.contratista_nombre || '?';
    grupos[k] = (grupos[k] || 0) + 1;
  }
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
      {Object.entries(grupos).map(([nombre, count]) => (
        <span key={nombre} style={{
          fontSize: 10.5, fontWeight: 600, padding: '2px 7px', borderRadius: 10,
          background: '#edf5f0', color: '#124e2f', whiteSpace: 'nowrap',
        }}>
          {nombre} ×{count}
        </span>
      ))}
    </div>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div style={{ background: 'white', borderRadius: 6, boxShadow: '0 20px 48px rgba(0,0,0,0.2)', width: 580, maxWidth: '94vw', maxHeight: '92vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '13px 18px', borderBottom: '1px solid #eaeeec', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: '#111614', flex: 1 }}>{title}</span>
          <button style={{ border: 'none', background: 'transparent', cursor: 'pointer' }} onClick={onClose}>
            <Icon name="x" size={16} color="#8f9c97" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ── Componente principal ──────────────────────────────────────────────────────

export function MapeoCodigosAdmin() {
  const [reglas, setReglas] = useState([]);
  const [contratistas, setContratistas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [soloActivas, setSoloActivas] = useState(false);

  // Modal
  const [modal, setModal] = useState(null); // null | { mode, regla? }
  const [form, setForm] = useState(FORM_EMPTY);
  const [formError, setFormError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Mapeos en el modal
  const [mapeosExistentes, setMapeosExistentes] = useState([]); // los que vienen de la API
  const [mapeosEliminar, setMapeosEliminar] = useState([]); // ids a desactivar al guardar
  const [mapeosNuevos, setMapeosNuevos] = useState([]); // filas nuevas a crear al guardar

  // Seed
  const [seedMsg, setSeedMsg] = useState(null);
  const [seeding, setSeeding] = useState(false);

  // Sync Oracle
  const [syncStatus, setSyncStatus]   = useState(null); // { ultimo_sync_at, ordenativos_count, ..., running }
  const [syncMsg, setSyncMsg]         = useState(null);
  const [syncDispatching, setSyncDispatching] = useState(false);
  const [syncError, setSyncError]     = useState(null);

  // ── Carga ────────────────────────────────────────────────────────────────

  const cargar = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [data, cList] = await Promise.all([getReglas(soloActivas), getContratistas()]);
      setReglas(data);
      setContratistas(cList);
    } catch (e) {
      setError(e.message || 'Error al cargar datos');
    } finally {
      setLoading(false);
    }
  }, [soloActivas]);

  useEffect(() => { cargar(); }, [cargar]);

  // ── Sync Oracle ──────────────────────────────────────────────────────────

  const cargarSyncStatus = useCallback(async () => {
    try {
      const res = await getSyncOracleStatus();
      setSyncStatus(res);
      setSyncError(null);
    } catch (e) {
      // 401/403 si el usuario no es admin — no es error de UI grave; solo no mostramos el panel
      setSyncError(e.message || 'No se pudo consultar estado del sync');
      setSyncStatus(null);
    }
  }, []);

  useEffect(() => { cargarSyncStatus(); }, [cargarSyncStatus]);

  // Polling cuando hay un sync en curso
  useEffect(() => {
    if (!syncStatus?.running) return;
    const id = setInterval(cargarSyncStatus, 3000);
    return () => clearInterval(id);
  }, [syncStatus?.running, cargarSyncStatus]);

  async function handleSyncOracle() {
    if (!window.confirm(
      'Sincronizar ordenativos CE+PROTELEM desde Oracle SIGEC. ' +
      'Puede tardar varios minutos. ¿Continuar?'
    )) return;
    setSyncDispatching(true); setSyncMsg(null);
    try {
      await dispararSyncOracle();
      setSyncMsg('Sync iniciado. Tomá un café — actualizamos esta pantalla cuando termine.');
      await cargarSyncStatus();
    } catch (e) {
      setSyncMsg(`Error: ${e.message}`);
    } finally {
      setSyncDispatching(false);
    }
  }

  function fmtFecha(iso) {
    if (!iso) return 'nunca';
    try {
      const d = new Date(iso);
      const f = [String(d.getDate()).padStart(2, '0'), String(d.getMonth() + 1).padStart(2, '0'), d.getFullYear()].join('/');
      const h = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
      return `${f} ${h}`;
    } catch { return String(iso); }
  }

  // ── Filtro ───────────────────────────────────────────────────────────────

  const filtered = reglas.filter((r) => {
    const q = search.toLowerCase();
    return !q || String(r.cod_epec).includes(q) || r.descripcion.toLowerCase().includes(q);
  });

  // ── Modal helpers ────────────────────────────────────────────────────────

  function resetMapeos(regla) {
    setMapeosExistentes(regla ? (regla.mapeos || []) : []);
    setMapeosEliminar([]);
    setMapeosNuevos([]);
  }

  function openCreate() {
    setForm({ ...FORM_EMPTY });
    setFormError(null); setSaved(false);
    resetMapeos(null);
    setModal({ mode: 'create' });
  }

  function openEdit(regla) {
    setForm({
      cod_epec: regla.cod_epec, descripcion: regla.descripcion, valor_uses: regla.valor_uses,
      gabinete: regla.gabinete, subterraneo: regla.subterraneo, altura: regla.altura,
      aereo: regla.aereo, equipo_medicion_reemplazado: regla.equipo_medicion_reemplazado,
      acometida_realizada: regla.acometida_realizada, tapa_reemplazada: regla.tapa_reemplazada,
      equipo_medicion_instalado: regla.equipo_medicion_instalado, activo: regla.activo,
    });
    setFormError(null); setSaved(false);
    // Para edición necesitamos los mapeos completos (con id) — están en regla.mapeos pero
    // solo tienen cod_contratista/nombre/fase (MapeoItemDTO). Hacemos un GET de los mapeos
    // del código para obtener los ids.
    _cargarMapeosConId(regla);
    setModal({ mode: 'edit', regla });
  }

  async function _cargarMapeosConId(regla) {
    // Buscamos los mapeos activos de esta regla en la lista global que ya tenemos
    // pero MapeoItemDTO no tiene id. Recargamos desde /mapeo-codigos filtrando por cod_epec.
    // Por simplicidad, hacemos un getRegla individual para obtener datos frescos.
    try {
      // Reutilizamos el endpoint de reglas que ya trae mapeos embebidos — pero solo
      // tienen nombre/cod/fase. Para eliminar mapeos individuales necesitamos el id.
      // Solución: cargamos GET /mapeo-codigos y filtramos por cod_epec.
      const { getMapeos } = await import('../api/adminCodigosApi');
      const todos = await getMapeos(true);
      const propios = todos.filter((m) => m.cod_epec === regla.cod_epec);
      setMapeosExistentes(propios);
    } catch {
      setMapeosExistentes(regla.mapeos || []);
    }
    setMapeosEliminar([]);
    setMapeosNuevos([]);
  }

  function closeModal() { setModal(null); setFormError(null); }
  function setField(k, v) { setForm((f) => ({ ...f, [k]: v })); }

  // ── Mapeos en el modal ───────────────────────────────────────────────────

  function marcarEliminar(mapeoId) {
    setMapeosEliminar((prev) => [...prev, mapeoId]);
    setMapeosExistentes((prev) => prev.filter((m) => m.id !== mapeoId));
  }

  function agregarFilaNueva() {
    setMapeosNuevos((prev) => [...prev, { ...MAPEO_EMPTY, _key: Date.now() }]);
  }

  function updateFilaNueva(key, field, value) {
    setMapeosNuevos((prev) => prev.map((r) => r._key === key ? { ...r, [field]: value } : r));
  }

  function quitarFilaNueva(key) {
    setMapeosNuevos((prev) => prev.filter((r) => r._key !== key));
  }

  // ── Guardar ──────────────────────────────────────────────────────────────

  async function handleSave() {
    setFormError(null);
    if (!form.cod_epec || !String(form.descripcion).trim() || form.valor_uses === '') {
      setFormError('Código EPEC, descripción y valor USES son obligatorios.');
      return;
    }
    for (const fila of mapeosNuevos) {
      if (!fila.contratista_id || !fila.cod_contratista.trim()) {
        setFormError('Completá contratista y código en todas las filas nuevas.');
        return;
      }
    }
    const payload = {
      ...form,
      cod_epec: parseInt(form.cod_epec, 10),
      valor_uses: parseFloat(form.valor_uses),
    };
    setSaving(true);
    try {
      let codEpec = payload.cod_epec;
      if (modal.mode === 'create') {
        await crearRegla(payload);
      } else {
        const { cod_epec: _cod, ...update } = payload;
        await actualizarRegla(modal.regla.id, update);
        codEpec = modal.regla.cod_epec;
      }
      // Procesar eliminaciones
      await Promise.all(mapeosEliminar.map((id) => desactivarMapeo(id)));
      // Procesar nuevos mapeos
      await Promise.all(
        mapeosNuevos
          .filter((r) => r.contratista_id && r.cod_contratista.trim())
          .map((r) => crearMapeo({
            contratista_id: parseInt(r.contratista_id, 10),
            cod_contratista: r.cod_contratista.trim(),
            fase: r.fase,
            cod_epec: codEpec,
          }))
      );
      setSaved(true);
      await cargar();
      setTimeout(closeModal, 900);
    } catch (e) {
      setFormError(e.message || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  }

  // ── Desactivar regla ─────────────────────────────────────────────────────

  async function handleDesactivar(regla) {
    if (!window.confirm(`¿Desactivar la regla "${regla.descripcion}" (cod ${regla.cod_epec})?`)) return;
    try { await desactivarRegla(regla.id); await cargar(); }
    catch (e) { alert(e.message || 'Error al desactivar'); }
  }

  // ── Seed ─────────────────────────────────────────────────────────────────

  async function handleSeed() {
    if (!window.confirm('Poblar tablas desde literales y Parquet (idempotente). ¿Continuar?')) return;
    setSeeding(true); setSeedMsg(null);
    try {
      const res = await ejecutarSeed();
      setSeedMsg(`${res.mensaje} (reglas: ${res.reglas_insertadas}, mapeos: ${res.mapeos_insertados})`);
      await cargar();
    } catch (e) {
      setSeedMsg(`Error: ${e.message}`);
    } finally {
      setSeeding(false);
    }
  }

  // ── Estilos ──────────────────────────────────────────────────────────────

  const S = {
    root: { padding: 20, overflow: 'auto', height: '100%', boxSizing: 'border-box', background: '#f5f7f6' },
    hdr: { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 18, gap: 12 },
    title: { fontSize: 17, fontWeight: 700, color: '#111614' },
    sub: { fontSize: 12, color: '#8f9c97', marginTop: 2 },
    btnPrim: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', border: 'none', borderRadius: 4, background: '#124e2f', color: 'white', fontSize: 12, fontWeight: 600, cursor: 'pointer' },
    btnSec: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', color: '#2f3733', fontSize: 12, fontWeight: 600, cursor: 'pointer' },
    btnGhost: { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', border: '1px dashed #b7dfc8', borderRadius: 4, background: 'transparent', color: '#124e2f', fontSize: 11.5, fontWeight: 600, cursor: 'pointer' },
    card: { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    toolbar: { padding: '10px 16px', borderBottom: '1px solid #eaeeec', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
    searchWrap: { display: 'flex', alignItems: 'center', gap: 7, background: '#f5f7f6', border: '1px solid #eaeeec', borderRadius: 4, padding: '5px 10px', width: 240 },
    searchInp: { border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: '#111614', width: '100%' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: 11.5 },
    th: { padding: '8px 10px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10, letterSpacing: '0.05em', whiteSpace: 'nowrap' },
    thC: { padding: '8px 6px', textAlign: 'center', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10, letterSpacing: '0.04em', whiteSpace: 'nowrap' },
    td: { padding: '7px 10px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', verticalAlign: 'middle' },
    tdC: { padding: '7px 6px', borderBottom: '1px solid #f0f3f1', textAlign: 'center', verticalAlign: 'middle' },
    mono: { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
    actBtn: { border: 'none', background: 'transparent', cursor: 'pointer', color: '#8f9c97', display: 'inline-flex', alignItems: 'center', padding: '2px 4px', borderRadius: 3 },
    // modal
    mBody: { padding: '16px 18px', overflowY: 'auto', flex: 1 },
    mFoot: { padding: '12px 18px', borderTop: '1px solid #eaeeec', display: 'flex', gap: 8, justifyContent: 'flex-end', flexShrink: 0 },
    fldGrp: { marginBottom: 13 },
    fldLbl: { fontSize: 10.5, fontWeight: 700, color: '#6b7772', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4, display: 'block' },
    fldInp: { width: '100%', padding: '6px 9px', border: '1px solid #d5ddd9', borderRadius: 4, fontSize: 12.5, color: '#111614', outline: 'none', boxSizing: 'border-box' },
    fldSel: { padding: '6px 8px', border: '1px solid #d5ddd9', borderRadius: 4, fontSize: 12, color: '#2f3733', background: 'white', outline: 'none', cursor: 'pointer', boxSizing: 'border-box' },
    obsGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', padding: '10px 12px', background: '#f9fbfa', border: '1px solid #eaeeec', borderRadius: 4 },
    obsRow: { display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' },
    divider: { border: 'none', borderTop: '1px solid #eaeeec', margin: '16px 0 12px' },
    mapeoRow: { display: 'grid', gridTemplateColumns: '1fr 1fr 80px 28px', gap: 6, alignItems: 'center', marginBottom: 6 },
  };

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={S.root}>
      {/* Header */}
      <div style={S.hdr}>
        <div>
          <div style={S.title}>Reglas de Códigos EPEC</div>
          <div style={S.sub}>Administración de reglas de observaciones y valores USES por código EPEC</div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <button style={S.btnSec} onClick={handleSeed} disabled={seeding}>
            <Icon name={seeding ? 'loader' : 'database'} size={13} />
            {seeding ? 'Ejecutando…' : 'Seed inicial'}
          </button>
          <button style={S.btnPrim} onClick={openCreate}>
            <Icon name="plus" size={14} /> Nueva regla
          </button>
        </div>
      </div>

      {seedMsg && (
        <div style={{ marginBottom: 14, padding: '9px 14px', background: '#edf5f0', border: '1px solid #b7dfc8', borderRadius: 4, fontSize: 12, color: '#124e2f', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon name="check-circle" size={14} color="#124e2f" /> {seedMsg}
          <button style={{ marginLeft: 'auto', border: 'none', background: 'transparent', cursor: 'pointer' }} onClick={() => setSeedMsg(null)}>
            <Icon name="x" size={13} color="#6b7772" />
          </button>
        </div>
      )}

      {/* ── Sincronización Oracle ─────────────────────────────────────────── */}
      {syncError ? null : (
        <div style={{ ...S.card, marginBottom: 14, padding: '12px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <Icon name="database" size={14} color="#124e2f" />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#111614' }}>Sincronización Oracle SIGEC</div>
              <div style={{ fontSize: 11, color: '#8f9c97', marginTop: 1 }}>
                Espejo local de ordenativos CE + PROTELEM. Usado por el motor de procesamiento y por la pantalla de detalle.
              </div>
            </div>
            <button
              style={{ ...S.btnPrim, opacity: (syncStatus?.running || syncDispatching) ? 0.6 : 1 }}
              onClick={handleSyncOracle}
              disabled={syncStatus?.running || syncDispatching}
            >
              <Icon name={syncStatus?.running ? 'loader' : 'refresh-cw'} size={13} />
              {syncStatus?.running ? 'Sync en curso…' : 'Sincronizar ahora'}
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginTop: 10 }}>
            <div style={{ padding: '8px 10px', background: '#f9fbfa', border: '1px solid #eaeeec', borderRadius: 4 }}>
              <div style={{ fontSize: 10, color: '#8f9c97', fontWeight: 700, textTransform: 'uppercase' }}>Última sync</div>
              <div style={{ fontSize: 12, color: '#111614', marginTop: 3, fontFamily: "'JetBrains Mono', monospace" }}>{fmtFecha(syncStatus?.ultimo_sync_at)}</div>
            </div>
            <div style={{ padding: '8px 10px', background: '#f9fbfa', border: '1px solid #eaeeec', borderRadius: 4 }}>
              <div style={{ fontSize: 10, color: '#8f9c97', fontWeight: 700, textTransform: 'uppercase' }}>Ordenativos</div>
              <div style={{ fontSize: 14, color: '#124e2f', marginTop: 3, fontWeight: 700 }}>{(syncStatus?.ordenativos_count ?? 0).toLocaleString()}</div>
            </div>
            <div style={{ padding: '8px 10px', background: '#f9fbfa', border: '1px solid #eaeeec', borderRadius: 4 }}>
              <div style={{ fontSize: 10, color: '#8f9c97', fontWeight: 700, textTransform: 'uppercase' }}>Fotos</div>
              <div style={{ fontSize: 14, color: '#124e2f', marginTop: 3, fontWeight: 700 }}>{(syncStatus?.fotos_count ?? 0).toLocaleString()}</div>
            </div>
            <div style={{ padding: '8px 10px', background: '#f9fbfa', border: '1px solid #eaeeec', borderRadius: 4 }}>
              <div style={{ fontSize: 10, color: '#8f9c97', fontWeight: 700, textTransform: 'uppercase' }}>Equipos</div>
              <div style={{ fontSize: 14, color: '#124e2f', marginTop: 3, fontWeight: 700 }}>{(syncStatus?.equipos_count ?? 0).toLocaleString()}</div>
            </div>
          </div>
          {syncMsg && (
            <div style={{ marginTop: 10, padding: '8px 12px', background: syncMsg.startsWith('Error') ? '#fde8e8' : '#edf5f0', border: `1px solid ${syncMsg.startsWith('Error') ? '#f0a0a0' : '#b7dfc8'}`, borderRadius: 4, fontSize: 11.5, color: syncMsg.startsWith('Error') ? '#7a1c1c' : '#124e2f' }}>
              {syncMsg}
            </div>
          )}
          {syncStatus?.last_result?.errores?.length > 0 && (
            <div style={{ marginTop: 8, padding: '8px 12px', background: '#fde8e8', border: '1px solid #f0a0a0', borderRadius: 4, fontSize: 11, color: '#7a1c1c' }}>
              Último sync con errores: {syncStatus.last_result.errores.join('; ')}
            </div>
          )}
        </div>
      )}

      <div style={S.card}>
        {/* Toolbar */}
        <div style={S.toolbar}>
          <div style={S.searchWrap}>
            <Icon name="search" size={13} color="#8f9c97" />
            <input style={S.searchInp} placeholder="Buscar código o descripción…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#2f3733', cursor: 'pointer' }}>
            <input type="checkbox" checked={soloActivas} onChange={(e) => setSoloActivas(e.target.checked)} style={{ accentColor: '#124e2f' }} />
            Solo activas
          </label>
          <span style={{ fontSize: 12, color: '#6b7772', fontWeight: 500 }}>{loading ? '…' : `${filtered.length} reglas`}</span>
        </div>

        {/* Tabla */}
        {error ? (
          <div style={{ padding: 24, textAlign: 'center', color: '#7a1c1c', fontSize: 13 }}>{error}</div>
        ) : loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#8f9c97', fontSize: 12 }}>Cargando…</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>Cód. EPEC</th>
                  <th style={S.th}>Descripción</th>
                  <th style={S.thC}>USES</th>
                  {OBS_FIELDS.map((f) => (
                    <th key={f.key} style={{ ...S.thC, fontSize: 9 }}>{f.label}</th>
                  ))}
                  <th style={S.th}>Contratistas</th>
                  <th style={S.thC}>Estado</th>
                  <th style={S.th}></th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr><td colSpan={13} style={{ ...S.td, textAlign: 'center', color: '#8f9c97', padding: 32 }}>Sin resultados</td></tr>
                ) : filtered.map((r, i) => (
                  <tr key={r.id} style={{ background: i % 2 === 0 ? 'white' : '#fafcfb', opacity: r.activo ? 1 : 0.55 }}>
                    <td style={{ ...S.td, ...S.mono, color: '#124e2f', fontWeight: 700 }}>{r.cod_epec}</td>
                    <td style={{ ...S.td, minWidth: 200, maxWidth: 260, whiteSpace: 'normal', lineHeight: '1.3' }}>{r.descripcion}</td>
                    <td style={{ ...S.tdC, ...S.mono, fontWeight: 600 }}>{r.valor_uses.toFixed(2)}</td>
                    {OBS_FIELDS.map((f) => (
                      <td key={f.key} style={S.tdC}><ObsDot active={r[f.key]} /></td>
                    ))}
                    <td style={{ ...S.td, minWidth: 120 }}><MapeosCompactos mapeos={r.mapeos} /></td>
                    <td style={S.tdC}>
                      <span style={{ fontSize: 10.5, fontWeight: 600, padding: '2px 7px', borderRadius: 3, background: r.activo ? '#d4edda' : '#eaeeec', color: r.activo ? '#155a2e' : '#4a5550' }}>
                        {r.activo ? 'Activa' : 'Inactiva'}
                      </span>
                    </td>
                    <td style={{ ...S.td, whiteSpace: 'nowrap' }}>
                      <button style={S.actBtn} title="Editar" onClick={() => openEdit(r)}
                        onMouseEnter={(e) => { e.currentTarget.style.background = '#edf5f0'; e.currentTarget.style.color = '#124e2f'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.background = ''; e.currentTarget.style.color = '#8f9c97'; }}>
                        <Icon name="edit" size={13} />
                      </button>
                      {r.activo && (
                        <button style={S.actBtn} title="Desactivar" onClick={() => handleDesactivar(r)}
                          onMouseEnter={(e) => { e.currentTarget.style.background = '#fde8e8'; e.currentTarget.style.color = '#7a1c1c'; }}
                          onMouseLeave={(e) => { e.currentTarget.style.background = ''; e.currentTarget.style.color = '#8f9c97'; }}>
                          <Icon name="slash" size={13} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Modal ── */}
      {modal && (
        <Modal
          title={modal.mode === 'create' ? 'Nueva regla EPEC' : `Editar regla — Cód. ${modal.regla.cod_epec}`}
          onClose={closeModal}
        >
          <div style={S.mBody}>
            {/* Identificación */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 13 }}>
              <div style={S.fldGrp}>
                <label style={S.fldLbl}>Código EPEC *</label>
                <input style={{ ...S.fldInp, fontFamily: "'JetBrains Mono', monospace" }}
                  type="number" min="1" value={form.cod_epec}
                  onChange={(e) => setField('cod_epec', e.target.value)}
                  disabled={modal.mode === 'edit'} placeholder="ej. 7" />
              </div>
              <div style={S.fldGrp}>
                <label style={S.fldLbl}>Valor USES *</label>
                <input style={{ ...S.fldInp, fontFamily: "'JetBrains Mono', monospace" }}
                  type="number" step="0.01" min="0.01" value={form.valor_uses}
                  onChange={(e) => setField('valor_uses', e.target.value)} placeholder="ej. 0.10" />
              </div>
            </div>
            <div style={{ ...S.fldGrp, marginBottom: 14 }}>
              <label style={S.fldLbl}>Descripción *</label>
              <input style={S.fldInp} value={form.descripcion}
                onChange={(e) => setField('descripcion', e.target.value)}
                placeholder="Descripción de la variante (ej. Gabinete)"
                onFocus={(e) => (e.target.style.borderColor = '#124e2f')}
                onBlur={(e) => (e.target.style.borderColor = '#d5ddd9')} />
            </div>

            {/* Observaciones */}
            <div style={S.fldGrp}>
              <label style={S.fldLbl}>Observaciones</label>
              <div style={S.obsGrid}>
                {OBS_FIELDS.map((f) => (
                  <label key={f.key} style={S.obsRow}>
                    <input type="checkbox" checked={!!form[f.key]}
                      onChange={(e) => setField(f.key, e.target.checked)}
                      style={{ accentColor: '#124e2f', width: 14, height: 14, cursor: 'pointer' }} />
                    <span style={{ fontSize: 12, color: '#2f3733' }}>{f.label}</span>
                  </label>
                ))}
              </div>
            </div>

            {modal.mode === 'edit' && (
              <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
                <input type="checkbox" id="activo-chk" checked={!!form.activo}
                  onChange={(e) => setField('activo', e.target.checked)}
                  style={{ accentColor: '#124e2f', width: 14, height: 14, cursor: 'pointer' }} />
                <label htmlFor="activo-chk" style={{ fontSize: 13, color: '#2f3733', fontWeight: 500, cursor: 'pointer' }}>Regla activa</label>
              </div>
            )}

            {/* ── Mapeos de contratistas ── */}
            <hr style={S.divider} />
            <div style={{ marginBottom: 10 }}>
              <span style={{ ...S.fldLbl, display: 'inline-block', marginBottom: 8 }}>Códigos de contratista</span>

              {/* Encabezado de columnas */}
              {(mapeosExistentes.length > 0 || mapeosNuevos.length > 0) && (
                <div style={{ ...S.mapeoRow, marginBottom: 4 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Contratista</span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Cód. contratista</span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Fase</span>
                  <span />
                </div>
              )}

              {/* Mapeos existentes */}
              {mapeosExistentes.map((m) => (
                <div key={m.id} style={{ ...S.mapeoRow, opacity: 0.85 }}>
                  <span style={{ fontSize: 12, color: '#2f3733', padding: '5px 0' }}>
                    {m.contratista_nombre || `id:${m.contratista_id}`}
                  </span>
                  <span style={{ ...S.mono, fontSize: 11.5, color: '#2f3733' }}>{m.cod_contratista}</span>
                  <span style={{ fontSize: 11.5, fontWeight: 600, color: '#4a5550', padding: '2px 6px', background: '#eaeeec', borderRadius: 3, textAlign: 'center' }}>{m.fase}</span>
                  <button
                    title="Quitar"
                    style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#c0c8c4', display: 'flex', alignItems: 'center', padding: 2, borderRadius: 3 }}
                    onClick={() => marcarEliminar(m.id)}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#7a1c1c')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#c0c8c4')}
                  >
                    <Icon name="x" size={13} />
                  </button>
                </div>
              ))}

              {/* Filas nuevas */}
              {mapeosNuevos.map((fila) => (
                <div key={fila._key} style={S.mapeoRow}>
                  <select
                    style={{ ...S.fldSel, width: '100%' }}
                    value={fila.contratista_id}
                    onChange={(e) => updateFilaNueva(fila._key, 'contratista_id', e.target.value)}
                  >
                    <option value="">— Contratista —</option>
                    {contratistas.map((c) => (
                      <option key={c.id} value={c.id}>{c.nombre}</option>
                    ))}
                  </select>
                  <input
                    style={{ ...S.fldInp, fontFamily: "'JetBrains Mono', monospace", fontSize: 11.5 }}
                    placeholder="ej. 01MI"
                    value={fila.cod_contratista}
                    onChange={(e) => updateFilaNueva(fila._key, 'cod_contratista', e.target.value)}
                  />
                  <select
                    style={{ ...S.fldSel, width: '100%' }}
                    value={fila.fase}
                    onChange={(e) => updateFilaNueva(fila._key, 'fase', e.target.value)}
                  >
                    {FASES.map((f) => <option key={f} value={f}>{f}</option>)}
                  </select>
                  <button
                    style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#c0c8c4', display: 'flex', alignItems: 'center', padding: 2, borderRadius: 3 }}
                    onClick={() => quitarFilaNueva(fila._key)}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#7a1c1c')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#c0c8c4')}
                  >
                    <Icon name="x" size={13} />
                  </button>
                </div>
              ))}

              <button style={{ ...S.btnGhost, marginTop: 6 }} onClick={agregarFilaNueva}>
                <Icon name="plus" size={12} /> Agregar código
              </button>
            </div>

            {formError && (
              <div style={{ marginTop: 10, padding: '8px 12px', background: '#fde8e8', border: '1px solid #f5b5b5', borderRadius: 4, fontSize: 12, color: '#7a1c1c' }}>
                {formError}
              </div>
            )}
          </div>

          <div style={S.mFoot}>
            <button style={{ padding: '7px 14px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, fontWeight: 600, color: '#4a5550', cursor: 'pointer' }} onClick={closeModal}>
              Cancelar
            </button>
            <button
              style={{ padding: '7px 18px', border: 'none', borderRadius: 4, background: saved ? '#1d8348' : '#124e2f', color: 'white', fontSize: 12, fontWeight: 600, cursor: saving ? 'wait' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, transition: 'background 0.2s' }}
              onClick={handleSave} disabled={saving}
            >
              {saved ? <><Icon name="check" size={13} /> Guardado</> : saving ? <><Icon name="loader" size={13} /> Guardando…</> : <><Icon name="send" size={13} /> Guardar</>}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
