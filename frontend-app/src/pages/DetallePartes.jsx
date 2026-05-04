import { useEffect, useState } from 'react';
import { Icon, PARTE_ESTADO_CONFIG, StatusChip, TRAZA_CONFIG } from '../components/Icon';
import { EmbeddedVisor } from '../components/visor/Visor';
import { getPartePhotos } from '../data/visorMock';
import { editarParte } from '../api/partesApi';
import { getAuditoria } from '../api/auditoriaApi';

const USUARIO_ID_DEFAULT = 1; // placeholder hasta wiring de auth

function buildCruces(p) {
  const ordMatch = p.ord_nro && p.ord_nro !== '—';
  const usesMatch = p.diferencia_uses == null || p.diferencia_uses === 0;
  const codMatch = !p.cod_epec_sugerido || String(p.cod_epec) === String(p.cod_epec_sugerido);
  return {
    A: {
      match: ordMatch,
      detail: ordMatch
        ? `ORD_NRO ${p.ord_nro} encontrada en dim_ord.`
        : 'No se encontró ordenativo para este suministro.',
    },
    B: {
      match: usesMatch,
      detail: usesMatch
        ? `USES declarado (${p.valor_uses_origen ?? '—'}) coincide con SIGEC.`
        : `Diferencia USES detectada: ${p.diferencia_uses > 0 ? '+' : ''}${p.diferencia_uses} (declarado ${p.valor_uses_origen ?? '—'} vs SIGEC ${p.valor_uses_obs ?? '—'}).`,
    },
    C: {
      match: codMatch,
      detail: codMatch
        ? `COD_EPEC ${p.cod_epec} coincide con SIGEC.`
        : `COD_EPEC declarado ${p.cod_epec} difiere del SIGEC (${p.cod_epec_sugerido}).${p.diferencia_uses != null && p.diferencia_uses !== 0 ? ` Flag: USES_DIFF = ${p.diferencia_uses > 0 ? '+' : ''}${p.diferencia_uses}.` : ''}`,
    },
  };
}

const BITACORA_COLORS = {
  system:  { icon: 'circle',        color: '#b5bfbb', bg: '#f5f7f6' },
  warning: { icon: 'alert-circle',  color: '#e6910a', bg: '#fff3cd' },
  user:    { icon: 'user',          color: '#1565c0', bg: '#dbeafe' },
  edit:    { icon: 'edit',          color: '#7a4a00', bg: '#fff3cd' },
  success: { icon: 'check-circle',  color: '#1d8348', bg: '#d4edda' },
};

const BITACORA_MOCK = [
  { ts:'01/04/2025 09:14', actor:'Sistema',   action:'Parte ingresado en lote',                 type:'system'  },
  { ts:'01/04/2025 09:14', actor:'Sistema',   action:'Validación sintáctica OK — 0 errores',    type:'system'  },
  { ts:'01/04/2025 09:17', actor:'Sistema',   action:'Cruce A: ORD_NRO match encontrado',       type:'system'  },
  { ts:'01/04/2025 09:17', actor:'Sistema',   action:'Cruce C: divergencia COD_EPEC detectada', type:'warning' },
];

const TABS = [
  { id: 'detalle',  label: 'Detalle' },
  { id: 'bitacora', label: 'Bitácora' },
];

function fmtDateTime(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    const date = [
      String(d.getDate()).padStart(2, '0'),
      String(d.getMonth() + 1).padStart(2, '0'),
      d.getFullYear(),
    ].join('/');
    return `${date} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  } catch { return '—'; }
}

export function DetallePartes({ parte, onBack }) {
  const p = parte || {
    id: 'PD-2025-00042', contratista: 'CONECTAR', operario: 'López, M.',
    fecha: '01/04/2025', suministro: '412881', cod_epec: '1003', ord_nro: 'CE-482301',
    traza: 'Error Sumi Nro Med', estado: 'En Revisión', medidor_dec: 'M74829103',
    uses: '1.00', lote: 'CONECTAR_2025-04-01', version: 2,
  };

  const [tab, setTab]                   = useState('detalle');
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showConflictModal, setShowConflictModal] = useState(false);
  const [editFields, setEditFields]     = useState({
    cod_epec:    p.cod_epec    || '',
    ord_nro:     p.ord_nro     || '',
    medidor:     p.medidor_dec || '',
    observacion: '',
  });
  const [saving, setSaving]     = useState(false);
  const [saved, setSaved]       = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [oracleLoading, setOracleLoading] = useState(false);
  const [oracleResult, setOracleResult]   = useState(null);
  const [rejectMotivo, setRejectMotivo]   = useState('');
  const [approving, setApproving]         = useState(false);
  const [rejecting, setRejecting]         = useState(false);

  // Bitácora state
  const [bitacora, setBitacora]       = useState(null); // null = not loaded yet
  const [bitacoraLoading, setBitacoraLoading] = useState(false);
  const [bitacoraError, setBitacoraError]     = useState(null);

  // Load bitácora when switching to that tab (only if real parte)
  useEffect(() => {
    if (tab !== 'bitacora') return;
    if (!p._id) { setBitacora(BITACORA_MOCK); return; }
    setBitacoraLoading(true);
    setBitacoraError(null);
    getAuditoria({ parte_id: p._id, limit: 100 })
      .then((res) => {
        if (res.items.length === 0) {
          setBitacora([]);
        } else {
          setBitacora(res.items.map((item) => ({
            ts: fmtDateTime(item.fecha_cambio),
            actor: `Usuario #${item.usuario_id}`,
            action: `${item.campo_modificado}: ${item.valor_anterior ?? '(vacío)'} → ${item.valor_nuevo ?? '(vacío)'} · "${item.motivo}"`,
            type: 'edit',
            version: item.version_resultante,
          })));
        }
      })
      .catch((err) => {
        setBitacoraError(err.message);
        setBitacora(BITACORA_MOCK);
      })
      .finally(() => setBitacoraLoading(false));
  }, [tab, p._id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function callEditarParte(payload) {
    if (!p._id) {
      // Mock flow for demo data
      setSaving(true);
      setTimeout(() => { setSaving(false); setSaved(true); setTimeout(() => setSaved(false), 2000); }, 900);
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      await editarParte(p._id, payload);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      if (err.message?.includes('409') || err.message?.toLowerCase().includes('conflicto')) {
        setShowConflictModal(true);
      } else {
        setSaveError(err.message);
      }
    } finally {
      setSaving(false);
    }
  }

  function handleSave() {
    if (!editFields.observacion.trim() || editFields.observacion.trim().length < 5) {
      setSaveError('El motivo del cambio debe tener al menos 5 caracteres.');
      return;
    }
    const payload = {
      motivo:     editFields.observacion.trim(),
      usuario_id: USUARIO_ID_DEFAULT,
      version:    p.version ?? 1,
    };
    const rawCodEpec = parseInt(editFields.cod_epec);
    if (!isNaN(rawCodEpec)) payload.cod_epec = rawCodEpec;
    const rawOrd = parseInt(String(editFields.ord_nro).replace(/^CE-/i, ''));
    if (!isNaN(rawOrd)) payload.ord_nro = rawOrd;
    if (editFields.medidor) payload.nro_medidor_colocado = editFields.medidor;
    callEditarParte(payload);
  }

  async function handleAprobar() {
    const motivo = 'Aprobado por auditor';
    if (!p._id) {
      setApproving(true);
      setTimeout(() => setApproving(false), 800);
      return;
    }
    setApproving(true);
    try {
      await editarParte(p._id, { id_estado: 1, motivo, usuario_id: USUARIO_ID_DEFAULT, version: p.version ?? 1 });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      if (err.message?.includes('409') || err.message?.toLowerCase().includes('conflicto')) {
        setShowConflictModal(true);
      } else {
        setSaveError(err.message);
      }
    } finally {
      setApproving(false);
    }
  }

  async function handleRechazar() {
    if (!rejectMotivo.trim() || rejectMotivo.trim().length < 5) return;
    setRejecting(true);
    setShowRejectModal(false);
    if (!p._id) {
      setTimeout(() => setRejecting(false), 800);
      return;
    }
    try {
      await editarParte(p._id, { id_estado: 3, motivo: rejectMotivo.trim(), usuario_id: USUARIO_ID_DEFAULT, version: p.version ?? 1 });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      if (err.message?.includes('409') || err.message?.toLowerCase().includes('conflicto')) {
        setShowConflictModal(true);
      } else {
        setSaveError(err.message);
      }
    } finally {
      setRejecting(false);
    }
  }

  function handleOracleQuery() {
    setOracleLoading(true);
    setOracleResult(null);
    // Oracle sigue siendo mock (sin endpoint real todavía)
    setTimeout(() => {
      setOracleResult({ ok: true, ord_nro: editFields.ord_nro, tor: 'CE', estado: 'VÁLIDO', srv: p.suministro || '412881', fecha_cierre: '15/04/2025' });
      setOracleLoading(false);
    }, 1400);
  }

  const tc = TRAZA_CONFIG[p.traza] || {};
  const ec = PARTE_ESTADO_CONFIG[p.estado] || {};

  const dS = {
    root: { display: 'flex', flexDirection: 'column', height: '100%', background: '#f5f7f6', overflow: 'hidden' },
    header: { background: 'white', borderBottom: '1px solid #eaeeec', padding: '12px 20px', display: 'flex', alignItems: 'center', gap: 14, flexShrink: 0 },
    backBtn: { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, fontWeight: 600, color: '#4a5550', cursor: 'pointer' },
    parteId: { fontFamily: "'JetBrains Mono', monospace", fontSize: 15, fontWeight: 700, color: '#124e2f' },
    meta: { fontSize: 11.5, color: '#6b7772' },
    headerRight: { marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' },
    tabBar: { background: 'white', borderBottom: '1px solid #eaeeec', display: 'flex', gap: 0, padding: '0 20px', flexShrink: 0 },
    tabBtn: { padding: '10px 16px', border: 'none', background: 'transparent', cursor: 'pointer', fontSize: 12.5, fontWeight: 500, color: '#6b7772', borderBottom: '2px solid transparent' },
    tabBtnActive: { color: '#124e2f', fontWeight: 600, borderBottom: '2px solid #124e2f' },
    content: { flex: 1, overflow: 'hidden', display: 'flex' },
    master: { flex: 1, overflow: 'auto', padding: 20 },
    section: { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, marginBottom: 12, overflow: 'hidden' },
    sectionHeader: { padding: '10px 16px', borderBottom: '1px solid #f0f3f1', display: 'flex', alignItems: 'center', gap: 8, background: '#fafcfb' },
    sectionTitle: { fontSize: 12, fontWeight: 700, color: '#2f3733', flex: 1 },
    rawGrid: { display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0 },
    rawCell: { padding: '8px 14px', borderRight: '1px solid #f0f3f1', borderBottom: '1px solid #f0f3f1' },
    rawLabel: { fontSize: 10, fontWeight: 600, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 },
    rawValue: { fontSize: 12.5, color: '#111614', fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 },
    cruceRow: { display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px', borderBottom: '1px solid #f5f7f6' },
    cruceBadge: { width: 28, height: 28, borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, flexShrink: 0 },
    cruceDetail: { fontSize: 11, color: '#6b7772', flex: 2 },
    diffRow: { display: 'flex', alignItems: 'center', gap: 0, padding: '12px 16px', borderBottom: '1px solid #f5f7f6' },
    diffLabel: { width: 140, fontSize: 11.5, fontWeight: 600, color: '#4a5550' },
    diffVal: { padding: '4px 10px', borderRadius: 4, fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 600, minWidth: 100, textAlign: 'center' },
    diffArrow: { padding: '0 12px', color: '#8f9c97' },
    diffDelta: { fontSize: 11, padding: '3px 8px', borderRadius: 3, fontWeight: 600 },
    sidePanel: { width: 320, background: 'white', borderLeft: '1px solid #eaeeec', display: 'flex', flexDirection: 'column', overflow: 'hidden' },
    sidePanelHeader: { padding: '12px 16px', borderBottom: '1px solid #eaeeec', background: '#fafcfb', display: 'flex', alignItems: 'center', gap: 8 },
    sidePanelTitle: { fontSize: 12, fontWeight: 700, color: '#2f3733', flex: 1 },
    sidePanelBody: { flex: 1, overflowY: 'auto', padding: '14px 16px' },
    fieldGroup: { marginBottom: 14 },
    fieldLabel: { fontSize: 10.5, fontWeight: 700, color: '#6b7772', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 },
    fieldInput: { width: '100%', padding: '6px 9px', border: '1px solid #d5ddd9', borderRadius: 4, fontSize: 12.5, fontFamily: "'JetBrains Mono', monospace", color: '#111614', outline: 'none', background: 'white', transition: 'border 0.1s', boxSizing: 'border-box' },
    fieldSelect: { width: '100%', padding: '6px 9px', border: '1px solid #d5ddd9', borderRadius: 4, fontSize: 12, color: '#2f3733', outline: 'none', background: 'white', cursor: 'pointer', boxSizing: 'border-box' },
    oracleBtn: { width: '100%', padding: 7, border: '1px solid #a8d9c0', borderRadius: 4, background: '#edf5f0', fontSize: 12, fontWeight: 600, color: '#124e2f', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, marginTop: 4 },
    oracleResult: { marginTop: 8, padding: '8px 10px', border: '1px solid #a8d9c0', borderRadius: 4, background: '#edf5f0', fontSize: 11 },
    sidePanelFooter: { padding: '12px 16px', borderTop: '1px solid #eaeeec', display: 'flex', flexDirection: 'column', gap: 8 },
    saveBtn: { padding: 8, border: 'none', borderRadius: 4, background: '#124e2f', color: 'white', fontSize: 12.5, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7 },
    actionFooter: { padding: '12px 20px', background: 'white', borderTop: '1px solid #eaeeec', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 },
    approveBtn: { padding: '8px 20px', border: 'none', borderRadius: 4, background: '#1d8348', color: 'white', fontSize: 13, fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 7 },
    rejectBtn: { padding: '8px 20px', border: '1px solid #f5b7b1', borderRadius: 4, background: '#fde8e8', color: '#7a1c1c', fontSize: 13, fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 7 },
    annulBtn: { padding: '8px 16px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', color: '#4a5550', fontSize: 12.5, fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 7 },
    overlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' },
    modal: { background: 'white', borderRadius: 6, boxShadow: '0 20px 48px rgba(0,0,0,0.2)', width: 440, maxWidth: '90vw', overflow: 'hidden' },
    modalHeader: { padding: '14px 18px', borderBottom: '1px solid #eaeeec', display: 'flex', alignItems: 'center', gap: 10 },
    modalTitle: { fontSize: 14, fontWeight: 700, color: '#111614', flex: 1 },
    modalBody: { padding: 18 },
    modalFooter: { padding: '12px 18px', borderTop: '1px solid #eaeeec', display: 'flex', gap: 8, justifyContent: 'flex-end' },
  };

  const photoCount = (p.cant_imagenes != null && p._id) ? p.cant_imagenes : getPartePhotos(p.id).length;

  return (
    <div style={dS.root}>
      <div style={dS.header}>
        <button style={dS.backBtn} onClick={onBack}>
          <Icon name="arrow-left" size={13} /> Bandeja
        </button>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={dS.parteId}>{p.id}</span>
            <StatusChip label={p.traza} config={tc} />
            <StatusChip label={p.estado} config={ec} />
          </div>
          <div style={dS.meta}>
            {p.contratista} · {p.operario} · {p.fecha} · Suministro {p.suministro} · Lote {p.lote || '—'}
          </div>
        </div>
        <div style={dS.headerRight}>
          <span style={{ fontSize: 11, color: '#8f9c97' }}>v{p.version ?? 1}</span>
          <button style={{ ...dS.backBtn, gap: 5 }} onClick={() => setTab('bitacora')}>
            <Icon name="clock" size={13} /> Bitácora
          </button>
        </div>
      </div>

      <div style={dS.tabBar}>
        {TABS.map((t) => (
          <button key={t.id} style={{ ...dS.tabBtn, ...(tab === t.id ? dS.tabBtnActive : {}) }} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <div style={dS.content}>
        {tab === 'detalle' && (
          <>
            <div style={dS.master}>
              <div style={dS.section}>
                <div style={dS.sectionHeader}>
                  <Icon name="camera" size={14} color="#6b7772" />
                  <span style={dS.sectionTitle}>Fotografías del Ordenativo</span>
                  <span style={{ fontSize: 10.5, color: '#8f9c97' }}>{photoCount} foto{photoCount !== 1 ? 's' : ''} · App móvil</span>
                </div>
                <EmbeddedVisor parte={p} />
              </div>

              <div style={dS.section}>
                <div style={dS.sectionHeader}>
                  <Icon name="file-text" size={14} color="#6b7772" />
                  <span style={dS.sectionTitle}>Datos del Excel</span>
                  <span style={{ fontSize: 10.5, color: '#8f9c97' }}>Lote {p.lote || '—'}</span>
                </div>
                <div style={dS.rawGrid}>
                  {[
                    ['Suministro',        p.suministro],
                    ['Operario',          p.operario],
                    ['Fecha Parte',       p.fecha],
                    ['Contratista',       p.contratista],
                    ['Medidor Retirado',  p.nro_medidor_retirado || p.medidor_dec || '—'],
                    ['Medidor Colocado',  p.nro_medidor_colocado || p.medidor_dec || '—'],
                    ['COD_EPEC Dec.',     p.cod_epec],
                    ['ORD_NRO Dec.',      p.ord_nro],
                    ['USES (origen)',     p.valor_uses_origen != null ? p.valor_uses_origen : p.uses],
                    ['USES (obs)',        p.valor_uses_obs ?? '—'],
                    ['Diferencia USES',   p.diferencia_uses ?? '—'],
                    ['Tipo Discrepancia', p.tipo_discrepancia ?? '—'],
                  ].map(([label, val]) => (
                    <div key={label} style={dS.rawCell}>
                      <div style={dS.rawLabel}>{label}</div>
                      <div style={dS.rawValue}>{val ?? '—'}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div style={dS.section}>
                <div style={dS.sectionHeader}>
                  <Icon name="git-branch" size={14} color="#6b7772" />
                  <span style={dS.sectionTitle}>Cruces Aplicados</span>
                  <span style={{ fontSize: 10.5, color: '#6b7772' }}>Waterfall A → B → C</span>
                </div>
                {Object.entries(buildCruces(p)).map(([key, cruce]) => (
                  <div key={key} style={dS.cruceRow}>
                    <div style={{ ...dS.cruceBadge, background: cruce.match ? '#d4edda' : '#fde8e8', color: cruce.match ? '#155a2e' : '#7a1c1c' }}>
                      {key}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: cruce.match ? '#155a2e' : '#c0392b' }}>
                          Cruce {key} — {cruce.match ? 'Match encontrado' : 'Divergencia detectada'}
                        </span>
                        <Icon name={cruce.match ? 'check-circle' : 'alert-triangle'} size={13} color={cruce.match ? '#1d8348' : '#c0392b'} />
                      </div>
                      <div style={dS.cruceDetail}>{cruce.detail}</div>
                    </div>
                  </div>
                ))}
              </div>

              <div style={dS.section}>
                <div style={dS.sectionHeader}>
                  <Icon name="activity" size={14} color="#6b7772" />
                  <span style={dS.sectionTitle}>Diferencias con SIGEC</span>
                </div>
                {[
                  { label: 'COD_EPEC', declarado: p.cod_epec, sigec: p.cod_epec_sugerido ?? p.cod_epec, match: !p.cod_epec_sugerido || String(p.cod_epec) === String(p.cod_epec_sugerido) },
                  { label: 'USES', declarado: p.valor_uses_origen ?? '—', sigec: p.valor_uses_obs ?? '—', match: p.diferencia_uses == null || p.diferencia_uses === 0, delta: p.diferencia_uses != null && p.diferencia_uses !== 0 ? `${p.diferencia_uses > 0 ? '+' : ''}${p.diferencia_uses}` : null, deltaOk: false },
                  { label: 'ORD_NRO', declarado: p.ord_nro === '—' ? '(sin orden)' : p.ord_nro, sigec: p.ord_nro === '—' ? '—' : p.ord_nro, match: p.ord_nro !== '—' },
                ].map((row) => (
                  <div key={row.label} style={dS.diffRow}>
                    <span style={dS.diffLabel}>{row.label}</span>
                    <span style={{ ...dS.diffVal, background: '#f5f7f6', color: '#4a5550' }}>{row.declarado}</span>
                    <span style={dS.diffArrow}><Icon name="chevron-right" size={14} color="#b5bfbb" /></span>
                    <span style={{ ...dS.diffVal, background: row.match ? '#d4edda' : '#fde8e8', color: row.match ? '#155a2e' : '#c0392b' }}>{row.sigec}</span>
                    {row.delta && (
                      <span style={{ ...dS.diffDelta, marginLeft: 10, background: row.deltaOk ? '#d4edda' : '#fff3cd', color: row.deltaOk ? '#155a2e' : '#7a4a00' }}>
                        {row.delta}
                      </span>
                    )}
                    {row.match && <span style={{ marginLeft: 8 }}><Icon name="check-circle" size={13} color="#1d8348" /></span>}
                  </div>
                ))}
              </div>
            </div>

            <div style={dS.sidePanel}>
              <div style={dS.sidePanelHeader}>
                <Icon name="edit" size={14} color="#6b7772" />
                <span style={dS.sidePanelTitle}>Edición y Validación</span>
              </div>
              <div style={dS.sidePanelBody}>
                {[
                  { key: 'cod_epec', label: 'COD_EPEC' },
                  { key: 'ord_nro',  label: 'ORD_NRO' },
                  { key: 'medidor',  label: 'Medidor Colocado' },
                ].map((f) => (
                  <div key={f.key} style={dS.fieldGroup}>
                    <div style={dS.fieldLabel}>{f.label}</div>
                    <input
                      style={dS.fieldInput}
                      value={editFields[f.key]}
                      onChange={(e) => setEditFields((prev) => ({ ...prev, [f.key]: e.target.value }))}
                      onFocus={(e) => (e.target.style.borderColor = '#124e2f')}
                      onBlur={(e) => (e.target.style.borderColor = '#d5ddd9')}
                    />
                  </div>
                ))}
                <div style={dS.fieldGroup}>
                  <div style={dS.fieldLabel}>Motivo del cambio <span style={{ color: '#c0392b' }}>*</span></div>
                  <textarea
                    style={{ ...dS.fieldInput, fontFamily: 'inherit', height: 72, resize: 'vertical', lineHeight: 1.4 }}
                    placeholder="Mínimo 5 caracteres — obligatorio para guardar…"
                    value={editFields.observacion}
                    onChange={(e) => { setEditFields((prev) => ({ ...prev, observacion: e.target.value })); setSaveError(null); }}
                    onFocus={(e) => (e.target.style.borderColor = '#124e2f')}
                    onBlur={(e) => (e.target.style.borderColor = '#d5ddd9')}
                  />
                  {saveError && (
                    <div style={{ fontSize: 11, color: '#c0392b', marginTop: 4 }}>{saveError}</div>
                  )}
                </div>

                <div style={{ marginTop: 4 }}>
                  <div style={dS.fieldLabel}>Consulta Oracle en Vivo</div>
                  <button style={dS.oracleBtn} onClick={handleOracleQuery} disabled={oracleLoading}>
                    {oracleLoading
                      ? <><Icon name="loader" size={13} /> Consultando SIGEC…</>
                      : <><Icon name="database" size={13} /> Consultar Oracle ahora</>}
                  </button>
                  {oracleResult && (
                    <div style={dS.oracleResult}>
                      <div style={{ fontWeight: 700, color: '#155a2e', marginBottom: 4 }}>✓ Orden válida</div>
                      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, lineHeight: 1.6, color: '#2f3733' }}>
                        TOR: {oracleResult.tor}<br />
                        Estado: {oracleResult.estado}<br />
                        SRV: {oracleResult.srv}<br />
                        Cierre: {oracleResult.fecha_cierre}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              <div style={dS.sidePanelFooter}>
                <button
                  style={{ ...dS.saveBtn, background: saved ? '#1d8348' : saving ? '#4a7a60' : '#124e2f', cursor: saving ? 'wait' : 'pointer' }}
                  onClick={handleSave}
                  disabled={saving}
                >
                  {saving ? <><Icon name="loader" size={13} /> Guardando…</>
                    : saved  ? <><Icon name="check"  size={13} /> Guardado</>
                    :          <><Icon name="send"   size={13} /> Guardar cambios</>}
                </button>
              </div>
            </div>
          </>
        )}

        {tab === 'bitacora' && (
          <div style={{ flex: 1, overflow: 'auto', padding: 20 }}>
            <div style={{ background: 'white', border: '1px solid #eaeeec', borderRadius: 6, overflow: 'hidden' }}>
              <div style={{ padding: '12px 16px', borderBottom: '1px solid #eaeeec', background: '#fafcfb', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Icon name="clock" size={14} color="#6b7772" />
                <span style={{ fontSize: 12, fontWeight: 700, color: '#2f3733' }}>Bitácora de Auditoría — {p.id}</span>
                <span style={{ marginLeft: 'auto', fontSize: 10.5, color: '#8f9c97' }}>
                  {p._id ? 'Registro real (API)' : 'Datos de demostración'}
                </span>
                <Icon name="lock" size={12} color="#b5bfbb" />
              </div>
              <div style={{ padding: '8px 16px' }}>
                {bitacoraLoading && (
                  <div style={{ padding: 20, textAlign: 'center', color: '#8f9c97', fontSize: 12 }}>
                    <Icon name="loader" size={16} color="#8f9c97" /> Cargando bitácora…
                  </div>
                )}
                {!bitacoraLoading && bitacora?.length === 0 && (
                  <div style={{ padding: 20, textAlign: 'center', color: '#8f9c97', fontSize: 12 }}>
                    Sin registros de auditoría para este parte.
                  </div>
                )}
                {!bitacoraLoading && bitacora && bitacora.map((ev, i) => {
                  const c = BITACORA_COLORS[ev.type] || BITACORA_COLORS.system;
                  return (
                    <div key={i} style={{ display: 'flex', gap: 12, paddingBottom: 16, position: 'relative' }}>
                      {i < bitacora.length - 1 && (
                        <div style={{ position: 'absolute', left: 14, top: 26, bottom: 0, width: 1, background: '#eaeeec' }} />
                      )}
                      <div style={{ width: 28, height: 28, borderRadius: 14, background: c.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2 }}>
                        <Icon name={c.icon} size={13} color={c.color} />
                      </div>
                      <div style={{ flex: 1, paddingTop: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: '#2f3733' }}>{ev.actor}</span>
                          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#8f9c97' }}>{ev.ts}</span>
                          {ev.version && (
                            <span style={{ fontSize: 10, color: '#b5bfbb', fontFamily: "'JetBrains Mono', monospace" }}>v{ev.version}</span>
                          )}
                        </div>
                        <div style={{ fontSize: 12, color: '#4a5550', marginTop: 2, lineHeight: 1.45 }}>{ev.action}</div>
                      </div>
                    </div>
                  );
                })}
                {bitacoraError && (
                  <div style={{ padding: '8px 0', fontSize: 11, color: '#c0392b' }}>
                    Error cargando bitácora: {bitacoraError}. Mostrando datos de demostración.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <div style={dS.actionFooter}>
        <span style={{ fontSize: 11.5, color: '#8f9c97', flex: 1 }}>
          {p.estado === 'Aprobado' ? 'Parte ya aprobado' : 'Aprobar o rechazar este parte'}
          {!p._id && <span style={{ marginLeft: 8, color: '#b5bfbb', fontSize: 10.5 }}>(demo — acciones simuladas)</span>}
        </span>
        <button style={dS.annulBtn} onClick={() => setShowRejectModal(true)}>
          <Icon name="slash" size={13} /> Anular
        </button>
        <button style={dS.rejectBtn} onClick={() => setShowRejectModal(true)} disabled={rejecting}>
          {rejecting ? <><Icon name="loader" size={13} /> Rechazando…</> : <><Icon name="x-circle" size={13} /> Rechazar</>}
        </button>
        <button style={dS.approveBtn} onClick={handleAprobar} disabled={approving}>
          {approving ? <><Icon name="loader" size={13} /> Aprobando…</> : <><Icon name="check-circle" size={13} /> Aprobar</>}
        </button>
      </div>

      {showRejectModal && (
        <div style={dS.overlay} onClick={() => setShowRejectModal(false)}>
          <div style={dS.modal} onClick={(e) => e.stopPropagation()}>
            <div style={dS.modalHeader}>
              <Icon name="alert-triangle" size={16} color="#c0392b" />
              <span style={dS.modalTitle}>Rechazar Parte</span>
              <button style={{ border: 'none', background: 'transparent', cursor: 'pointer' }} onClick={() => setShowRejectModal(false)}>
                <Icon name="x" size={16} color="#8f9c97" />
              </button>
            </div>
            <div style={dS.modalBody}>
              <div style={{ fontSize: 12, color: '#4a5550', marginBottom: 12 }}>Ingrese el motivo de rechazo (mínimo 5 caracteres):</div>
              <textarea
                style={{ width: '100%', padding: '6px 9px', border: '1px solid #d5ddd9', borderRadius: 4, fontSize: 12, fontFamily: 'inherit', height: 80, resize: 'vertical', boxSizing: 'border-box', outline: 'none' }}
                placeholder="Describa el motivo del rechazo…"
                value={rejectMotivo}
                onChange={(e) => setRejectMotivo(e.target.value)}
                onFocus={(e) => (e.target.style.borderColor = '#124e2f')}
                onBlur={(e) => (e.target.style.borderColor = '#d5ddd9')}
              />
            </div>
            <div style={dS.modalFooter}>
              <button style={dS.annulBtn} onClick={() => setShowRejectModal(false)}>Cancelar</button>
              <button style={{ ...dS.rejectBtn, opacity: rejectMotivo.trim().length < 5 ? 0.5 : 1 }} disabled={rejectMotivo.trim().length < 5} onClick={handleRechazar}>
                Confirmar Rechazo
              </button>
            </div>
          </div>
        </div>
      )}

      {showConflictModal && (
        <div style={dS.overlay}>
          <div style={dS.modal}>
            <div style={dS.modalHeader}>
              <Icon name="lock" size={16} color="#e6910a" />
              <span style={dS.modalTitle}>Conflicto de Versión</span>
            </div>
            <div style={dS.modalBody}>
              <div style={{ padding: '10px 12px', background: '#fff3cd', borderRadius: 4, fontSize: 12, color: '#7a4a00', lineHeight: 1.5 }}>
                <strong>Versión desactualizada.</strong> Otro usuario modificó este parte (v{p.version} → v{(p.version ?? 1) + 1}).
                Tus cambios no fueron guardados. Volvé a la bandeja y reabrí el parte para ver la versión más reciente.
              </div>
            </div>
            <div style={dS.modalFooter}>
              <button style={dS.approveBtn} onClick={() => { setShowConflictModal(false); onBack(); }}>
                <Icon name="arrow-left" size={13} /> Volver a bandeja
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
