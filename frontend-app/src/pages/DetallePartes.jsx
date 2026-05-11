import { useEffect, useState } from 'react';
import { Icon, PARTE_ESTADO_CONFIG, StatusChip, TRAZA_CONFIG } from '../components/Icon';
import { EmbeddedVisor, ImageViewer } from '../components/visor/Visor';
import { getPartePhotos } from '../data/visorMock';
import {
  editarParte,
  getCandidatosOracle,
  getCodigosEpecCandidatos,
  getOpcionesCodEpec,
  getParte,
} from '../api/partesApi';
import { getAuditoria } from '../api/auditoriaApi';
import { normalizeParteDetalle } from '../api/normalizers';

const USUARIO_ID_DEFAULT = 1; // placeholder hasta wiring de auth

// Trazas que indican match en Cruce A (vinculación con orden CE propia)
const TRAZAS_CRUCE_A = new Set([
  'Original OK', 'Corregido Nro EQP Invertidos', 'Corregido Nro Medidor',
  'Corregido Medidor Vacio', 'Informado - No Ejecutado',
]);
// Trazas que indican match en Cruce B (orden existe pero no es CE)
const TRAZAS_CRUCE_B = new Set(['No Corresponde TOR CE']);
// Trazas que indican rescate en Cruce C (suministro corregido por medidor)
const TRAZAS_CRUCE_C = new Set(['Corregido Sumi', 'Corregido Sumi Nro EQP']);

function buildCruces(p) {
  const traza = p.traza || '';

  const matchA = TRAZAS_CRUCE_A.has(traza);
  const matchB = TRAZAS_CRUCE_B.has(traza);
  const matchC = TRAZAS_CRUCE_C.has(traza);

  // Cruce A: vinculación parte ↔ orden CE de la misma contratista por suministro + tolerancia de fecha
  const detailA = matchA
    ? `Orden CE ${p.ord_nro !== '—' ? p.ord_nro : 'encontrada'} vinculada por suministro ${p.suministro} dentro de la ventana de tolerancia.`
    : matchB || matchC
      ? 'No aplica — el parte fue procesado por Cruce B o C.'
      : 'Sin orden CE propia encontrada para este suministro en la ventana de fecha.';

  // Cruce B: clasificación de partes con orden existente pero de tipo no-CE (IC, CX, MP, RX, etc.)
  const detailB = matchB
    ? `Orden ${p.ord_nro !== '—' ? p.ord_nro : 'detectada'} encontrada pero corresponde a un tipo no-CE (${p.tipo_discrepancia || 'IC/CX/MP/RX'}); fuera del alcance del proceso de pago.`
    : matchA
      ? 'No aplica — el parte fue resuelto en Cruce A.'
      : matchC
        ? 'No aplica — el parte fue resuelto en Cruce C.'
        : 'No se encontró ninguna orden (CE ni no-CE) para este suministro.';

  // Cruce C: rescate por número de medidor cuando el operario declaró un suministro incorrecto
  const detailC = matchC
    ? traza === 'Corregido Sumi'
      ? `Suministro corregido vía número de medidor (EQP coincide con base técnica); suministro real asignado: ${p.suministro}.`
      : `Suministro corregido vía número de medidor (EQP con discrepancia en retirado); suministro real asignado: ${p.suministro}.`
    : matchA
      ? 'No aplica — el parte fue resuelto en Cruce A.'
      : matchB
        ? 'No aplica — el parte fue descartado en Cruce B.'
        : 'El número de medidor no coincidió con ningún suministro en la base técnica.';

  return {
    A: { match: matchA, detail: detailA },
    B: { match: matchB, detail: detailB },
    C: { match: matchC, detail: detailC },
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
  const [p, setP] = useState(parte || {
    id: 'PD-2025-00042', contratista: 'CONECTAR', operario: 'López, M.',
    fecha: '01/04/2025', suministro: '412881', cod_epec: '1003', ord_nro: 'CE-482301',
    traza: 'Error Sumi Nro Med', estado: 'En Revisión', medidor_dec: 'M74829103',
    uses: '1.00', lote: 'CONECTAR_2025-04-01', version: 2,
  });

  const [loadingDetail, setLoadingDetail] = useState(false);

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
  const [oracleCandidatos, setOracleCandidatos] = useState(null);
  const [oracleLoading, setOracleLoading]       = useState(false);
  const [oracleAviso, setOracleAviso]           = useState(null);
  const [oracleModal, setOracleModal]           = useState(null); // {type:'detalle'|'fotos'|'asociar', cand}
  const [asociarMotivo, setAsociarMotivo]       = useState('');
  const [asociando, setAsociando]               = useState(false);
  const [asociarError, setAsociarError]         = useState(null);
  const [asociarSuccess, setAsociarSuccess]     = useState(null); // {ord_numero}
  const [rejectMotivo, setRejectMotivo]   = useState('');
  const [approving, setApproving]         = useState(false);
  const [rejecting, setRejecting]         = useState(false);

  // Sugerencias cod_epec
  const [opcionesCodEpec, setOpcionesCodEpec]           = useState([]);
  const [candidatosEpec, setCandidatosEpec]             = useState(null);
  const [candidatosEpecLoading, setCandidatosEpecLoading] = useState(false);
  const [candidatosEpecError, setCandidatosEpecError]   = useState(null);
  // {cod_epec, descripcion, hamming, campos_diferentes, modo:'simple'|'warning'}
  const [confirmCodEpecModal, setConfirmCodEpecModal]   = useState(null);
  const [confirmCodEpecObs, setConfirmCodEpecObs]       = useState('');
  const [confirmCodEpecSaving, setConfirmCodEpecSaving] = useState(false);

  // Bitácora state
  const [bitacora, setBitacora]       = useState(null); // null = not loaded yet
  const [bitacoraLoading, setBitacoraLoading] = useState(false);
  const [bitacoraError, setBitacoraError]     = useState(null);

  useEffect(() => {
    if (parte && typeof parte.id === 'number') {
      let cancelled = false;
      setLoadingDetail(true);
      getParte(parte.id)
        .then((res) => {
          if (cancelled) return;
          const full = normalizeParteDetalle(res);
          setP(full);
          setEditFields(prev => ({
            ...prev,
            cod_epec: full.cod_epec || '',
            ord_nro: full.ord_nro || '',
            medidor: full.medidor_dec || '',
          }));
        })
        .catch((err) => console.error("Error al cargar detalle:", err))
        .finally(() => { if (!cancelled) setLoadingDetail(false); });
      return () => { cancelled = true; };
    }
  }, [parte]);

  // Cargar opciones del dropdown una sola vez (catálogo de cod_epec activos).
  useEffect(() => {
    let cancelled = false;
    getOpcionesCodEpec()
      .then((res) => { if (!cancelled) setOpcionesCodEpec(Array.isArray(res) ? res : []); })
      .catch((err) => { if (!cancelled) console.error('Error al cargar opciones cod_epec:', err); });
    return () => { cancelled = true; };
  }, []);

  // Si el parte ya tiene cod_epec pero el dropdown no tiene descripción seleccionada,
  // resolverla por la primera opción que matchee — refleja el estado actual.
  useEffect(() => {
    if (!editFields.cod_epec || editFields.cod_epec_desc || opcionesCodEpec.length === 0) return;
    const codeInt = parseInt(editFields.cod_epec);
    if (isNaN(codeInt)) return;
    const opt = opcionesCodEpec.find((o) => o.cod_epec === codeInt);
    if (opt) {
      setEditFields((prev) => ({ ...prev, cod_epec_desc: opt.descripcion }));
    }
  }, [editFields.cod_epec, editFields.cod_epec_desc, opcionesCodEpec]);

  // Cargar candidatos cuando el parte es Aprobado (id_estado=1) y tiene id real.
  useEffect(() => {
    if (typeof p.id !== 'number' || p.id_estado !== 1) {
      setCandidatosEpec(null);
      setCandidatosEpecError(null);
      return;
    }
    let cancelled = false;
    setCandidatosEpecLoading(true);
    setCandidatosEpecError(null);
    getCodigosEpecCandidatos(p.id)
      .then((res) => { if (!cancelled) setCandidatosEpec(res); })
      .catch((err) => { if (!cancelled) setCandidatosEpecError(err.message || 'Error al cargar candidatos'); })
      .finally(() => { if (!cancelled) setCandidatosEpecLoading(false); });
    return () => { cancelled = true; };
  }, [p.id, p.id_estado]);

  // Auto-load candidatos Oracle cuando el parte tiene traza "Múltiples Candidatos Oracle" (id_traza=20)
  useEffect(() => {
    if (typeof p.id !== 'number' || p.id_traza !== 20) return;
    handleConsultarOracle();
  }, [p.id, p.id_traza]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load bitácora when switching to that tab (only if real parte)
  useEffect(() => {
    if (tab !== 'bitacora') return;
    if (typeof p.id !== 'number') { setBitacora(BITACORA_MOCK); return; }
    setBitacoraLoading(true);
    setBitacoraError(null);
    getAuditoria({ parte_id: p.id, limit: 100 })
      .then((res) => {
        if (res.items.length === 0) {
          setBitacora([]);
        } else {
          setBitacora(res.items.map((item) => ({
            ts: fmtDateTime(item.fecha_cambio),
            actor: item.usuario_nombre || `Usuario #${item.usuario_id}`,
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
  }, [tab, p.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function callEditarParte(payload) {
    if (typeof p.id !== 'number') {
      setSaving(true);
      setTimeout(() => { setSaving(false); setSaved(true); setTimeout(() => setSaved(false), 2000); }, 900);
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await editarParte(p.id, payload);
      const full = normalizeParteDetalle(updated);
      setP(full);
      setEditFields({
        cod_epec:    full.cod_epec    || '',
        ord_nro:     full.ord_nro     || '',
        medidor:     full.medidor_dec || '',
        observacion: '',
      });
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
    const rawCodEpec = parseInt(editFields.cod_epec);
    const codEpecCambio = !isNaN(rawCodEpec) && rawCodEpec !== (p.cod_epec ?? null);

    // Si cambió cod_epec → modal obligatorio (sin requerir motivo previo).
    if (codEpecCambio) {
      const cand = candidatosEpec?.todas?.find(c =>
        c.cod_epec === rawCodEpec && c.descripcion === editFields.cod_epec_desc,
      ) || candidatosEpec?.todas?.find(c => c.cod_epec === rawCodEpec);
      const hamming = cand?.hamming ?? null;
      const campos_diferentes = cand?.campos_diferentes ?? [];
      const descripcion = cand?.descripcion ?? editFields.cod_epec_desc ?? '';
      setConfirmCodEpecModal({
        cod_epec: rawCodEpec,
        descripcion,
        hamming,
        campos_diferentes,
        modo: hamming != null && hamming >= 2 ? 'warning' : 'simple',
      });
      setConfirmCodEpecObs('');
      return;
    }

    // Camino legacy: cambios solo de ord_nro / medidor → exige motivo en textarea.
    if (!editFields.observacion.trim() || editFields.observacion.trim().length < 5) {
      setSaveError('El motivo del cambio debe tener al menos 5 caracteres.');
      return;
    }
    const payload = {
      motivo:     editFields.observacion.trim(),
      usuario_id: USUARIO_ID_DEFAULT,
      version:    p.version ?? 1,
    };
    const rawOrd = parseInt(String(editFields.ord_nro));
    if (!isNaN(rawOrd)) payload.ord_nro = rawOrd;
    if (editFields.medidor) payload.nro_medidor_colocado = editFields.medidor;
    callEditarParte(payload);
  }

  function handleAsociarCodEpec(cand) {
    setEditFields((prev) => ({
      ...prev,
      cod_epec: String(cand.cod_epec),
      cod_epec_desc: cand.descripcion,
    }));
    setConfirmCodEpecModal({
      cod_epec: cand.cod_epec,
      descripcion: cand.descripcion,
      hamming: cand.hamming,
      campos_diferentes: cand.campos_diferentes ?? [],
      modo: cand.hamming >= 2 ? 'warning' : 'simple',
    });
    setConfirmCodEpecObs('');
  }

  async function handleConfirmCodEpec() {
    const m = confirmCodEpecModal;
    if (!m) return;
    const hammingTxt = m.hamming != null ? `Hamming=${m.hamming}` : 'sin candidato';
    const motivo_base = m.modo === 'simple'
      ? `Asociación de cod_epec acorde a observaciones cargadas (${hammingTxt})`
      : `Asociación de cod_epec con discrepancia significativa vs observaciones (${hammingTxt})`;
    const obsExtra = confirmCodEpecObs.trim();
    const motivo_final = obsExtra ? `${motivo_base} — Obs auditor: ${obsExtra}` : motivo_base;

    const payload = {
      cod_epec:   m.cod_epec,
      motivo:     motivo_final,
      usuario_id: USUARIO_ID_DEFAULT,
      version:    p.version ?? 1,
    };
    // Acompañar cambios pendientes de ord_nro / medidor si los hay.
    const rawOrd = parseInt(String(editFields.ord_nro));
    if (!isNaN(rawOrd) && rawOrd !== (p.ord_nro ?? null)) payload.ord_nro = rawOrd;
    if (editFields.medidor && editFields.medidor !== (p.medidor_dec ?? '')) {
      payload.nro_medidor_colocado = editFields.medidor;
    }

    setConfirmCodEpecSaving(true);
    try {
      await callEditarParte(payload);
      // Refrescar candidatos tras el cambio.
      if (typeof p.id === 'number') {
        try {
          const res = await getCodigosEpecCandidatos(p.id);
          setCandidatosEpec(res);
        } catch { /* silencioso */ }
      }
      setConfirmCodEpecModal(null);
    } finally {
      setConfirmCodEpecSaving(false);
    }
  }

  async function handleAprobar() {
    const motivo = 'Aprobado por auditor';
    if (typeof p.id !== 'number') {
      setApproving(true);
      setTimeout(() => setApproving(false), 800);
      return;
    }
    setApproving(true);
    try {
      const updated = await editarParte(p.id, { id_estado: 1, motivo, usuario_id: USUARIO_ID_DEFAULT, version: p.version ?? 1 });
      const full = normalizeParteDetalle(updated);
      setP(full);
      setEditFields({ cod_epec: full.cod_epec || '', ord_nro: full.ord_nro || '', medidor: full.medidor_dec || '', observacion: '' });
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
    if (typeof p.id !== 'number') {
      setTimeout(() => setRejecting(false), 800);
      return;
    }
    try {
      const updated = await editarParte(p.id, { id_estado: 3, motivo: rejectMotivo.trim(), usuario_id: USUARIO_ID_DEFAULT, version: p.version ?? 1 });
      const full = normalizeParteDetalle(updated);
      setP(full);
      setEditFields({ cod_epec: full.cod_epec || '', ord_nro: full.ord_nro || '', medidor: full.medidor_dec || '', observacion: '' });
      setRejectMotivo('');
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

  async function handleConsultarOracle() {
    if (typeof p.id !== 'number') return;
    setOracleLoading(true);
    setOracleCandidatos(null);
    setOracleAviso(null);
    try {
      const res = await getCandidatosOracle(p.id);
      setOracleCandidatos(res.candidatos || []);
      setOracleAviso(res.aviso || null);
    } catch (err) {
      setOracleAviso(`Error: ${err.message}`);
      setOracleCandidatos([]);
    } finally {
      setOracleLoading(false);
    }
  }

  async function handleAsociar(cand) {
    if (!asociarMotivo.trim() || asociarMotivo.trim().length < 5) {
      setAsociarError('El motivo debe tener al menos 5 caracteres.');
      return;
    }
    if (typeof p.id !== 'number') {
      setAsociarError('No se puede asociar en modo demo (parte sin ID real).');
      return;
    }
    setAsociando(true);
    setAsociarError(null);
    try {
      const updated = await editarParte(p.id, {
        ord_nro: cand.ord_numero,
        id_estado: 1, // Aprobado — el parte queda cerrado al asociar el ordenativo
        motivo: asociarMotivo.trim(),
        usuario_id: USUARIO_ID_DEFAULT,
        version: p.version ?? 1,
      });
      const full = normalizeParteDetalle(updated);
      setP(full);
      setOracleModal(null);
      setAsociarMotivo('');
      setAsociarSuccess({ ord_numero: cand.ord_numero });
      setTimeout(() => setAsociarSuccess(null), 5000);
    } catch (err) {
      const msg = err.message || 'Error desconocido al asociar.';
      if (msg.includes('409') || msg.toLowerCase().includes('conflicto')) {
        setOracleModal(null);
        setShowConflictModal(true);
      } else {
        setAsociarError(msg);
      }
    } finally {
      setAsociando(false);
    }
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

  const photoCount = (p.cant_imagenes != null && typeof p.id === 'number') ? p.cant_imagenes : getPartePhotos(p.id).length;

  return (
    <div style={dS.root}>
      <div style={dS.header}>
        <button style={dS.backBtn} onClick={onBack}>
          <Icon name="arrow-left" size={13} /> Bandeja
        </button>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={dS.parteId}>Sumi {p.suministro}</span>
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

              {/* Observaciones del Operario — solo para Aprobados (pasaron por Etapa 4) */}
              {p.id_estado === 1 && (
                <div style={dS.section}>
                  <div style={dS.sectionHeader}>
                    <Icon name="clipboard" size={14} color="#6b7772" />
                    <span style={dS.sectionTitle}>Observaciones del Operario</span>
                    <span style={{ fontSize: 10.5, color: '#8f9c97' }}>App móvil · 8 ítems</span>
                  </div>
                  {p.observaciones_app ? (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px', paddingTop: 4 }}>
                      {[
                        { key: 'gabinete',                      label: 'Gabinete' },
                        { key: 'subterraneo',                   label: 'Subterráneo' },
                        { key: 'altura',                        label: 'Trabajo en Altura' },
                        { key: 'aereo',                         label: 'Trabajo Aéreo' },
                        { key: 'equipo_medicion_reemplazado',   label: 'Eq. Medición Reemplazado' },
                        { key: 'acometida_realizada',           label: 'Acometida Realizada' },
                        { key: 'tapa_reemplazada',              label: 'Tapa Reemplazada' },
                        { key: 'equipo_medicion_instalado',     label: 'Eq. Medición Instalado' },
                      ].map(({ key, label }) => {
                        const val = p.observaciones_app[key];
                        return (
                          <div key={key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 8px', borderRadius: 4, background: val ? '#edf5f0' : '#f5f7f6' }}>
                            <span style={{ fontSize: 11, color: '#4a5550' }}>{label}</span>
                            <span style={{ fontSize: 11, fontWeight: 700, color: val ? '#155a2e' : '#8f9c97', background: val ? '#d4edda' : '#eaeeec', padding: '1px 7px', borderRadius: 3 }}>
                              {val ? 'Sí' : 'No'}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <span style={{ fontSize: 11.5, color: '#aab5b0', fontStyle: 'italic' }}>Datos de observaciones no disponibles.</span>
                  )}
                </div>
              )}

              {/* Códigos EPEC Candidatos — sugerencias por similitud Hamming con obs del operario */}
              {p.id_estado === 1 && p.observaciones_app && (
                <div style={dS.section}>
                  <div style={dS.sectionHeader}>
                    <Icon name="zap" size={14} color="#6b7772" />
                    <span style={dS.sectionTitle}>Códigos EPEC Candidatos</span>
                    <span style={{ fontSize: 10.5, color: '#8f9c97' }}>
                      Sugerencias por similitud con observaciones cargadas
                    </span>
                  </div>
                  <div style={{ padding: '12px 16px' }}>
                    {candidatosEpecLoading && (
                      <div style={{ padding: '12px 0', textAlign: 'center', color: '#8f9c97', fontSize: 12 }}>
                        <Icon name="loader" size={14} color="#8f9c97" /> Calculando candidatos…
                      </div>
                    )}
                    {candidatosEpecError && (
                      <div style={{ marginBottom: 10, padding: '8px 12px', background: '#fde8e8', border: '1px solid #f5b7b1', borderRadius: 4, fontSize: 11, color: '#7a1c1c' }}>
                        {candidatosEpecError}
                      </div>
                    )}
                    {candidatosEpec && candidatosEpec.sin_observaciones && (
                      <div style={{ marginBottom: 10, padding: '10px 12px', background: '#fff3cd', border: '1px solid #f0d080', borderRadius: 4, fontSize: 11.5, color: '#7a4a00', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                        <Icon name="alert-circle" size={13} color="#e6910a" />
                        <span>
                          El operario no cargó observaciones. Sugerencia automática del motor: <strong>cod_epec 11</strong> (USES bajo 0.0100).
                        </span>
                      </div>
                    )}
                    {candidatosEpec && (candidatosEpec.match_exacto.length > 0 || candidatosEpec.cercanos.length > 0) && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {candidatosEpec.match_exacto.length > 0 && (
                          <div>
                            <div style={{ fontSize: 11, fontWeight: 700, color: '#155a2e', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                              <Icon name="check-circle" size={12} color="#1d8348" />
                              Match exacto (Hamming = 0)
                              <span style={{ fontSize: 10, color: '#8f9c97', fontWeight: 500 }}>
                                {candidatosEpec.match_exacto.length} candidato{candidatosEpec.match_exacto.length === 1 ? '' : 's'}
                              </span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                              {candidatosEpec.match_exacto.map((cand, idx) => {
                                const asignado = p.cod_epec === cand.cod_epec;
                                return (
                                  <div key={`exact-${idx}`} style={{ padding: '8px 12px', border: '1px solid #a8d9c0', borderRadius: 4, background: '#edf5f0', display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 14, fontWeight: 700, color: '#124e2f', minWidth: 40 }}>{cand.cod_epec}</div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{ fontSize: 12, fontWeight: 600, color: '#2f3733', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cand.descripcion}</div>
                                      <div style={{ fontSize: 10.5, color: '#6b7772', marginTop: 2 }}>
                                        Score: {cand.score}/8 · Hamming: {cand.hamming} · USES: {cand.valor_uses.toFixed(4)}
                                      </div>
                                    </div>
                                    {asignado ? (
                                      <span style={{ fontSize: 10.5, fontWeight: 700, color: '#155a2e', background: '#d4edda', padding: '3px 8px', borderRadius: 3 }}>
                                        Asignado actualmente
                                      </span>
                                    ) : (
                                      <button
                                        style={{ padding: '5px 10px', border: '1px solid #1d8348', borderRadius: 4, background: '#1d8348', color: 'white', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
                                        onClick={() => handleAsociarCodEpec(cand)}
                                      >
                                        Asociar este código
                                      </button>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                        {candidatosEpec.cercanos.length > 0 && (
                          <div>
                            <div style={{ fontSize: 11, fontWeight: 700, color: '#7a4a00', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                              <Icon name="alert-circle" size={12} color="#e6910a" />
                              Top {candidatosEpec.cercanos.length} cercanos (Hamming &gt; 0)
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                              {candidatosEpec.cercanos.map((cand, idx) => {
                                const asignado = p.cod_epec === cand.cod_epec;
                                const fuerte = cand.hamming >= 2;
                                return (
                                  <div key={`near-${idx}`} style={{ padding: '8px 12px', border: '1px solid #f0d080', borderRadius: 4, background: '#fff8e7', display: 'flex', alignItems: 'center', gap: 10 }}>
                                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 14, fontWeight: 700, color: '#7a4a00', minWidth: 40 }}>{cand.cod_epec}</div>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <div style={{ fontSize: 12, fontWeight: 600, color: '#2f3733', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cand.descripcion}</div>
                                      <div style={{ fontSize: 10.5, color: '#6b7772', marginTop: 2 }}>
                                        Score: {cand.score}/8 · Hamming: <span style={{ color: fuerte ? '#c0392b' : '#7a4a00', fontWeight: 700 }}>{cand.hamming}</span> · USES: {cand.valor_uses.toFixed(4)}
                                      </div>
                                      {cand.campos_diferentes.length > 0 && (
                                        <div style={{ fontSize: 10, color: '#8f9c97', marginTop: 2, fontStyle: 'italic' }}>
                                          Difiere en: {cand.campos_diferentes.join(', ')}
                                        </div>
                                      )}
                                    </div>
                                    {asignado ? (
                                      <span style={{ fontSize: 10.5, fontWeight: 700, color: '#7a4a00', background: '#fff3cd', padding: '3px 8px', borderRadius: 3 }}>
                                        Asignado actualmente
                                      </span>
                                    ) : (
                                      <button
                                        style={{ padding: '5px 10px', border: `1px solid ${fuerte ? '#c0392b' : '#e6910a'}`, borderRadius: 4, background: 'white', color: fuerte ? '#c0392b' : '#7a4a00', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
                                        onClick={() => handleAsociarCodEpec(cand)}
                                      >
                                        Asociar este código
                                      </button>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    {candidatosEpec && !candidatosEpec.sin_observaciones && candidatosEpec.match_exacto.length === 0 && candidatosEpec.cercanos.length === 0 && (
                      <div style={{ padding: '12px 0', textAlign: 'center', color: '#8f9c97', fontSize: 11.5 }}>
                        Sin reglas activas para evaluar candidatos.
                      </div>
                    )}
                  </div>
                </div>
              )}

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
                        <span style={{ fontSize: 12, fontWeight: 600, color: cruce.match ? '#155a2e' : '#6b7772' }}>
                          {key === 'A' && (cruce.match ? 'Cruce A — Vinculado con orden CE propia' : 'Cruce A — Sin orden CE propia')}
                          {key === 'B' && (cruce.match ? 'Cruce B — Clasificado como No-CE (descartado)' : 'Cruce B — Sin orden no-CE detectada')}
                          {key === 'C' && (cruce.match ? 'Cruce C — Suministro rescatado por medidor' : 'Cruce C — Sin rescate por medidor')}
                        </span>
                        <Icon name={cruce.match ? 'check-circle' : 'minus-circle'} size={13} color={cruce.match ? '#1d8348' : '#b5bfbb'} />
                      </div>
                      <div style={dS.cruceDetail}>{cruce.detail}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Ordenativos CE Candidatos — DB local sincronizada desde Oracle SIGEC */}
              <div style={dS.section}>
                <div style={dS.sectionHeader}>
                  <Icon name="database" size={14} color="#6b7772" />
                  <span style={dS.sectionTitle}>Ordenativos CE Candidatos</span>
                  <button
                    style={{ padding: '4px 12px', border: '1px solid #a8d9c0', borderRadius: 4, background: '#edf5f0', fontSize: 11, fontWeight: 600, color: '#124e2f', cursor: oracleLoading || typeof p.id !== 'number' ? 'not-allowed' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, opacity: typeof p.id !== 'number' ? 0.5 : 1 }}
                    onClick={handleConsultarOracle}
                    disabled={oracleLoading || typeof p.id !== 'number'}
                  >
                    {oracleLoading
                      ? <><Icon name="loader" size={12} /> Buscando…</>
                      : <><Icon name="search" size={12} /> Buscar candidatos</>}
                  </button>
                </div>
                <div style={{ padding: '12px 16px' }}>
                  {p.id_traza === 20 && (
                    <div style={{ marginBottom: 10, padding: '10px 12px', background: '#fff3cd', border: '1px solid #f0d080', borderRadius: 4, fontSize: 12, color: '#7a4a00', display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                      <Icon name="alert-circle" size={14} color="#e6910a" />
                      <span><strong>Requiere desambiguación.</strong> Este parte fue clasificado con múltiples ordenativos candidatos. Revisá la lista y asociá el correcto para resolverlo.</span>
                    </div>
                  )}
                  {asociarSuccess && (
                    <div style={{ marginBottom: 10, padding: '10px 12px', background: '#d4edda', border: '1px solid #a8d9c0', borderRadius: 4, fontSize: 12, color: '#155a2e', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Icon name="check-circle" size={14} color="#1d8348" />
                      <span><strong>Asociación registrada.</strong> El parte quedó vinculado a ORD <strong style={{ fontFamily: "'JetBrains Mono', monospace" }}>{asociarSuccess.ord_numero}</strong> y pasó a estado Revisión.</span>
                      <button onClick={() => setAsociarSuccess(null)} style={{ marginLeft: 'auto', border: 'none', background: 'transparent', cursor: 'pointer', padding: 2 }}>
                        <Icon name="x" size={13} color="#155a2e" />
                      </button>
                    </div>
                  )}
                  {oracleCandidatos === null && !oracleLoading && (
                    <div style={{ padding: '16px 0', textAlign: 'center', color: '#b5bfbb', fontSize: 12 }}>
                      Presioná "Buscar candidatos" para listar ordenativos CE candidatos.
                    </div>
                  )}
                  {oracleAviso && (
                    <div style={{ marginBottom: 10, padding: '8px 12px', background: '#fff3cd', border: '1px solid #f0d080', borderRadius: 4, fontSize: 11, color: '#7a4a00', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                      <Icon name="alert-circle" size={13} color="#e6910a" />
                      <span>{oracleAviso}</span>
                    </div>
                  )}
                  {oracleCandidatos !== null && oracleCandidatos.length === 0 && (
                    <div style={{ padding: '16px 0', textAlign: 'center', color: '#8f9c97', fontSize: 12 }}>
                      No se encontraron ordenativos CE para este suministro/medidores en SIGEC.
                    </div>
                  )}
                  {oracleCandidatos && (() => {
                    const parteOrdNroInt = p.ord_nro && p.ord_nro !== '—' ? parseInt(p.ord_nro, 10) : null;
                    return oracleCandidatos.map((cand) => {
                    const fotoCount = cand.fotos ? Object.values(cand.fotos).filter(Boolean).length : 0;
                    const isAsociado = parteOrdNroInt != null && parteOrdNroInt === cand.ord_numero;
                    const origenColors = {
                      A:          { bg: '#d4edda', color: '#155a2e' },
                      B_colocado: { bg: '#dbeafe', color: '#1565c0' },
                      B_retirado: { bg: '#e8d5f5', color: '#6a1b9a' },
                    };
                    return (
                      <div key={cand.ord_numero} style={{ border: `1px solid ${isAsociado ? '#a8d9c0' : '#eaeeec'}`, borderLeft: isAsociado ? '3px solid #1d8348' : '1px solid #eaeeec', borderRadius: 6, marginBottom: 10, padding: '12px 14px', display: 'flex', alignItems: 'flex-start', gap: 14, background: isAsociado ? '#f0faf4' : '#fafcfb' }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, flexWrap: 'wrap' }}>
                            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 16, fontWeight: 700, color: '#124e2f' }}>{cand.ord_numero}</span>
                            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: '#4a5550', background: '#eaeeec', padding: '2px 8px', borderRadius: 3 }}>{cand.srv_codigo || '—'}</span>
                            <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 3, background: cand.ord_estado === 'CERRADO' ? '#fde8e8' : '#d4edda', color: cand.ord_estado === 'CERRADO' ? '#7a1c1c' : '#155a2e', fontWeight: 600 }}>{cand.ord_estado || '—'}</span>
                            {isAsociado && (
                              <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 3, background: '#1d8348', color: 'white', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                                <Icon name="check-circle" size={10} color="white" /> Asociado
                              </span>
                            )}
                            {(cand.origenes || []).map((o) => {
                              const oc = origenColors[o] || { bg: '#f0f3f1', color: '#4a5550' };
                              return <span key={o} style={{ fontSize: 10, padding: '2px 7px', borderRadius: 3, background: oc.bg, color: oc.color, fontWeight: 600 }}>{o}</span>;
                            })}
                          </div>
                          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 11, color: '#6b7772' }}>
                            {cand.ord_fecha_inicio && <span>Inicio: <strong style={{ color: '#2f3733' }}>{cand.ord_fecha_inicio}</strong></span>}
                            {cand.ord_fecha_fin && <span>Fin: <strong style={{ color: '#2f3733' }}>{cand.ord_fecha_fin}</strong></span>}
                            {cand.sec_codigo_origen && <span>Sección: <strong style={{ color: '#2f3733' }}>{cand.sec_codigo_origen}</strong></span>}
                            {cand.dias_diferencia != null && (
                              <span style={{ color: cand.dias_diferencia <= 7 ? '#1d8348' : cand.dias_diferencia <= 30 ? '#e6910a' : '#c0392b' }}>
                                Δ <strong>{cand.dias_diferencia}d</strong> al parte
                              </span>
                            )}
                          </div>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 5, flexShrink: 0 }}>
                          <button
                            style={{ padding: '4px 10px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 11, fontWeight: 600, color: '#4a5550', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 5 }}
                            onClick={() => setOracleModal({ type: 'detalle', cand })}
                          >
                            <Icon name="eye" size={12} /> Ver detalle
                          </button>
                          <button
                            style={{ padding: '4px 10px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 11, fontWeight: 600, color: '#4a5550', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 5 }}
                            onClick={() => setOracleModal({ type: 'fotos', cand })}
                          >
                            <Icon name="camera" size={12} /> Fotos{fotoCount > 0 && <span style={{ background: '#124e2f', color: 'white', borderRadius: 10, fontSize: 9, padding: '1px 5px', marginLeft: 2 }}>{fotoCount}</span>}
                          </button>
                          <button
                            style={{ padding: '4px 10px', border: '1px solid #a8d9c0', borderRadius: 4, background: '#edf5f0', fontSize: 11, fontWeight: 600, color: '#124e2f', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 5 }}
                            onClick={() => { setAsociarMotivo(''); setAsociarError(null); setOracleModal({ type: 'asociar', cand }); }}
                          >
                            <Icon name="check-circle" size={12} /> Asociar
                          </button>
                        </div>
                      </div>
                    );
                  });
                  })()}
                </div>
              </div>
            </div>

            <div style={dS.sidePanel}>
              <div style={dS.sidePanelHeader}>
                <Icon name="edit" size={14} color="#6b7772" />
                <span style={dS.sidePanelTitle}>Edición y Validación</span>
              </div>
              <div style={dS.sidePanelBody}>
                {/* COD_EPEC: dropdown con preview Hamming */}
                <div style={dS.fieldGroup}>
                  <div style={dS.fieldLabel}>COD_EPEC</div>
                  {(() => {
                    const selKey = `${editFields.cod_epec}|${editFields.cod_epec_desc ?? ''}`;
                    const previewCand = candidatosEpec?.todas?.find((c) =>
                      c.cod_epec === parseInt(editFields.cod_epec) && c.descripcion === editFields.cod_epec_desc,
                    ) || candidatosEpec?.todas?.find((c) => c.cod_epec === parseInt(editFields.cod_epec));
                    const fuerte = previewCand && previewCand.hamming >= 2;
                    return (
                      <>
                        <select
                          style={dS.fieldSelect}
                          value={selKey}
                          onChange={(e) => {
                            const [codStr, desc] = e.target.value.split('|');
                            setEditFields((prev) => ({
                              ...prev,
                              cod_epec: codStr,
                              cod_epec_desc: desc,
                            }));
                          }}
                          onFocus={(e) => (e.target.style.borderColor = '#124e2f')}
                          onBlur={(e) => (e.target.style.borderColor = '#d5ddd9')}
                        >
                          <option value="|">— Seleccionar —</option>
                          {opcionesCodEpec.map((o, i) => (
                            <option key={`${o.cod_epec}-${i}`} value={`${o.cod_epec}|${o.descripcion}`}>
                              {o.cod_epec} — {o.descripcion} (USES {o.valor_uses.toFixed(4)})
                            </option>
                          ))}
                        </select>
                        {previewCand && (
                          <div style={{ fontSize: 10.5, marginTop: 4, color: fuerte ? '#c0392b' : '#155a2e', fontWeight: 600 }}>
                            Hamming: {previewCand.hamming}
                            {previewCand.campos_diferentes.length > 0 && (
                              <span style={{ color: '#6b7772', fontWeight: 400, marginLeft: 6 }}>
                                · Difiere en: {previewCand.campos_diferentes.join(', ')}
                              </span>
                            )}
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
                {[
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
                <span style={{ fontSize: 12, fontWeight: 700, color: '#2f3733' }}>Bitácora de Auditoría — Sumi {p.suministro}</span>
                <span style={{ marginLeft: 'auto', fontSize: 10.5, color: '#8f9c97' }}>
                  {typeof p.id === 'number' ? 'Registro real (API)' : 'Datos de demostración'}
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
          {typeof p.id !== 'number' && <span style={{ marginLeft: 8, color: '#b5bfbb', fontSize: 10.5 }}>(demo — acciones simuladas)</span>}
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

      {confirmCodEpecModal && (() => {
        const m = confirmCodEpecModal;
        const warning = m.modo === 'warning';
        const headerBg = warning ? '#fde8e8' : '#edf5f0';
        const iconName = warning ? 'alert-triangle' : 'check-circle';
        const iconColor = warning ? '#c0392b' : '#1d8348';
        const title = warning ? 'Atención: discrepancia significativa' : 'Confirmar asociación de código';
        const confirmLabel = warning ? 'Continuar de todos modos' : 'Confirmar asociación';
        const confirmStyle = warning
          ? { padding: '8px 16px', border: '1px solid #c0392b', borderRadius: 4, background: '#c0392b', color: 'white', fontSize: 12.5, fontWeight: 600, cursor: 'pointer' }
          : { ...dS.approveBtn, padding: '8px 16px', fontSize: 12.5 };
        return (
          <div style={dS.overlay} onClick={() => !confirmCodEpecSaving && setConfirmCodEpecModal(null)}>
            <div style={{ ...dS.modal, width: 480 }} onClick={(e) => e.stopPropagation()}>
              <div style={{ ...dS.modalHeader, background: headerBg }}>
                <Icon name={iconName} size={16} color={iconColor} />
                <span style={dS.modalTitle}>{title}</span>
                <button style={{ border: 'none', background: 'transparent', cursor: confirmCodEpecSaving ? 'wait' : 'pointer' }} onClick={() => !confirmCodEpecSaving && setConfirmCodEpecModal(null)} disabled={confirmCodEpecSaving}>
                  <Icon name="x" size={16} color="#8f9c97" />
                </button>
              </div>
              <div style={dS.modalBody}>
                <div style={{ fontSize: 12.5, color: '#2f3733', marginBottom: 10 }}>
                  Vas a asociar el código <strong style={{ fontFamily: "'JetBrains Mono', monospace", color: '#124e2f' }}>{m.cod_epec}</strong>
                  {m.descripcion ? <> — <span style={{ color: '#4a5550' }}>{m.descripcion}</span></> : null} a este parte.
                </div>
                {warning ? (
                  <div style={{ padding: '10px 12px', background: '#fde8e8', border: '1px solid #f5b7b1', borderRadius: 4, fontSize: 11.5, color: '#7a1c1c', marginBottom: 12 }}>
                    <div style={{ fontWeight: 700, marginBottom: 4 }}>
                      Hamming = {m.hamming} (≥ 2): el código difiere significativamente de las observaciones cargadas.
                    </div>
                    {m.campos_diferentes.length > 0 && (
                      <div>
                        Difiere en: <strong>{m.campos_diferentes.join(', ')}</strong>.
                      </div>
                    )}
                    <div style={{ marginTop: 6 }}>
                      Esta decisión quedará registrada en bitácora con un mensaje específico.
                    </div>
                  </div>
                ) : (
                  <div style={{ fontSize: 11.5, color: '#6b7772', marginBottom: 12 }}>
                    {m.hamming != null
                      ? `Hamming = ${m.hamming} (< 2): coherente con las observaciones cargadas.`
                      : 'No hay candidato de Hamming asociado para este código.'}
                  </div>
                )}
                <div style={dS.fieldGroup}>
                  <div style={dS.fieldLabel}>Observación adicional <span style={{ color: '#8f9c97', textTransform: 'none', letterSpacing: 0 }}>(opcional)</span></div>
                  <textarea
                    style={{ ...dS.fieldInput, fontFamily: 'inherit', height: 64, resize: 'vertical', lineHeight: 1.4 }}
                    placeholder="Comentario libre del auditor…"
                    value={confirmCodEpecObs}
                    onChange={(e) => setConfirmCodEpecObs(e.target.value)}
                  />
                </div>
                {saveError && (
                  <div style={{ fontSize: 11, color: '#c0392b', marginTop: 4 }}>{saveError}</div>
                )}
              </div>
              <div style={dS.modalFooter}>
                <button style={dS.annulBtn} onClick={() => setConfirmCodEpecModal(null)} disabled={confirmCodEpecSaving}>
                  Cancelar
                </button>
                <button style={confirmStyle} onClick={handleConfirmCodEpec} disabled={confirmCodEpecSaving}>
                  {confirmCodEpecSaving ? <><Icon name="loader" size={13} /> Guardando…</> : confirmLabel}
                </button>
              </div>
            </div>
          </div>
        );
      })()}

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

      {oracleModal?.type === 'detalle' && (
        <div style={dS.overlay} onClick={() => setOracleModal(null)}>
          <div style={{ ...dS.modal, width: 520 }} onClick={(e) => e.stopPropagation()}>
            <div style={dS.modalHeader}>
              <Icon name="eye" size={16} color="#124e2f" />
              <span style={dS.modalTitle}>Detalle — ORD {oracleModal.cand.ord_numero}</span>
              <button style={{ border: 'none', background: 'transparent', cursor: 'pointer' }} onClick={() => setOracleModal(null)}>
                <Icon name="x" size={16} color="#8f9c97" />
              </button>
            </div>
            <div style={dS.modalBody}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 20px' }}>
                {[
                  ['ORD_NUMERO',     oracleModal.cand.ord_numero],
                  ['SRV_CODIGO',     oracleModal.cand.srv_codigo],
                  ['TOR_CODIGO',     oracleModal.cand.tor_codigo],
                  ['Estado',         oracleModal.cand.ord_estado],
                  ['Fecha Inicio',   oracleModal.cand.ord_fecha_inicio],
                  ['Fecha Fin',      oracleModal.cand.ord_fecha_fin],
                  ['Sección Origen', oracleModal.cand.sec_codigo_origen],
                  ['Días al parte',  oracleModal.cand.dias_diferencia != null ? `${oracleModal.cand.dias_diferencia} días` : '—'],
                ].map(([label, val]) => (
                  <div key={label}>
                    <div style={{ fontSize: 10, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>{label}</div>
                    <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, color: '#111614', fontWeight: 500 }}>{val || '—'}</div>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 14 }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>Origen de búsqueda</div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {(oracleModal.cand.origenes || []).map((o) => {
                    const colors = { A: ['#d4edda','#155a2e'], B_colocado: ['#dbeafe','#1565c0'], B_retirado: ['#e8d5f5','#6a1b9a'] };
                    const [bg, color] = colors[o] || ['#f0f3f1','#4a5550'];
                    return <span key={o} style={{ fontSize: 11, padding: '3px 10px', borderRadius: 4, background: bg, color, fontWeight: 600 }}>{o}</span>;
                  })}
                </div>
              </div>
            </div>
            <div style={dS.modalFooter}>
              <button style={dS.annulBtn} onClick={() => setOracleModal(null)}>Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {oracleModal?.type === 'fotos' && (() => {
        const fotos = oracleModal.cand.fotos || {};
        const urls = [fotos.imagen_1, fotos.imagen_2, fotos.imagen_3, fotos.imagen_4, fotos.imagen_5].filter(Boolean);
        return (
          <div
            role="dialog"
            aria-modal="true"
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.72)', zIndex: 500, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
            onClick={(e) => { if (e.target === e.currentTarget) setOracleModal(null); }}
          >
            <div style={{ width: 'min(900px, 90vw)', height: 'min(700px, 85vh)', background: '#1a1f1d', borderRadius: 8, overflow: 'hidden', boxShadow: '0 20px 60px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column' }}>
              <div style={{ padding: '10px 14px', background: '#111614', borderBottom: '1px solid rgba(255,255,255,0.07)', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                <Icon name="camera" size={15} color="#6dbf97" />
                <span style={{ color: 'white', fontSize: 13, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>ORD {oracleModal.cand.ord_numero}</span>
                <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>· {oracleModal.cand.srv_codigo}</span>
                <div style={{ flex: 1 }} />
                <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }}>
                  {urls.length} foto{urls.length !== 1 ? 's' : ''}
                </span>
                <button
                  onClick={() => setOracleModal(null)}
                  style={{ border: 'none', background: 'rgba(255,255,255,0.07)', borderRadius: 4, cursor: 'pointer', color: 'rgba(255,255,255,0.6)', width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.15)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.07)')}
                >
                  <Icon name="x" size={15} color="currentColor" />
                </button>
              </div>
              <div style={{ flex: 1, overflow: 'hidden' }}>
                <ImageViewer photos={urls} parteId={`ORD-${oracleModal.cand.ord_numero}`} embedded onClose={() => setOracleModal(null)} />
              </div>
            </div>
          </div>
        );
      })()}

      {oracleModal?.type === 'asociar' && (
        <div style={dS.overlay} onClick={() => setOracleModal(null)}>
          <div style={dS.modal} onClick={(e) => e.stopPropagation()}>
            <div style={dS.modalHeader}>
              <Icon name="check-circle" size={16} color="#1d8348" />
              <span style={dS.modalTitle}>Asociar ORD {oracleModal.cand.ord_numero}</span>
              <button style={{ border: 'none', background: 'transparent', cursor: 'pointer' }} onClick={() => setOracleModal(null)}>
                <Icon name="x" size={16} color="#8f9c97" />
              </button>
            </div>
            <div style={dS.modalBody}>
              <div style={{ marginBottom: 12, padding: '8px 12px', background: '#edf5f0', border: '1px solid #a8d9c0', borderRadius: 4, fontSize: 12, color: '#2f3733', fontFamily: "'JetBrains Mono', monospace" }}>
                ORD_NRO: {oracleModal.cand.ord_numero} · {oracleModal.cand.srv_codigo}
              </div>
              <div style={{ fontSize: 12, color: '#4a5550', marginBottom: 8 }}>Motivo de la asociación <span style={{ color: '#c0392b' }}>*</span></div>
              <textarea
                style={{ width: '100%', padding: '6px 9px', border: '1px solid #d5ddd9', borderRadius: 4, fontSize: 12, fontFamily: 'inherit', height: 80, resize: 'vertical', boxSizing: 'border-box', outline: 'none' }}
                placeholder="Mínimo 5 caracteres — obligatorio…"
                value={asociarMotivo}
                onChange={(e) => { setAsociarMotivo(e.target.value); if (asociarError) setAsociarError(null); }}
                onFocus={(e) => (e.target.style.borderColor = '#124e2f')}
                onBlur={(e) => (e.target.style.borderColor = '#d5ddd9')}
              />
              <div style={{ marginTop: 8, fontSize: 11, color: '#6b7772', lineHeight: 1.4 }}>
                Al confirmar: el parte será vinculado a este ordenativo y pasará a estado <strong>Aprobado</strong>. El cambio queda registrado en la bitácora.
              </div>
              {asociarError && (
                <div style={{ marginTop: 10, padding: '8px 10px', background: '#fde8e8', border: '1px solid #f5b7b1', borderRadius: 4, fontSize: 11.5, color: '#7a1c1c', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                  <Icon name="alert-triangle" size={13} color="#c0392b" />
                  <span>{asociarError}</span>
                </div>
              )}
            </div>
            <div style={dS.modalFooter}>
              <button style={dS.annulBtn} onClick={() => setOracleModal(null)}>Cancelar</button>
              <button
                style={{ ...dS.approveBtn, opacity: asociarMotivo.trim().length < 5 || asociando ? 0.7 : 1 }}
                disabled={asociarMotivo.trim().length < 5 || asociando}
                onClick={() => handleAsociar(oracleModal.cand)}
              >
                {asociando ? <><Icon name="loader" size={13} /> Asociando…</> : <><Icon name="check-circle" size={13} /> Confirmar Asociación</>}
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
