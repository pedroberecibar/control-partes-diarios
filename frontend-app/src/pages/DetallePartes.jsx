import { useState } from 'react';
import { Icon, PARTE_ESTADO_CONFIG, StatusChip, TRAZA_CONFIG } from '../components/Icon';
import { EmbeddedVisor } from '../components/visor/Visor';
import { getPartePhotos } from '../data/visorMock';

const CRUCE_RESULTS = {
  A: { match: true,  detail: 'ORD_NRO CE-482301 encontrada en dim_ord. TOR=CE, estado=VÁLIDO, SRV_CODIGO coincide.' },
  B: { match: true,  detail: 'Medidor declarado M74829103 presente en SIGEC para SRV_CODIGO=412881. USES=1.00.' },
  C: { match: false, detail: 'COD_EPEC declarado 1003 difiere del SIGEC (1004). Flag: USES_DIFF = +0.25.' },
};

const BITACORA_EVENTS = [
  { ts:'01/04/2025 09:14', actor:'Sistema',   action:'Parte ingresado en lote CONECTAR_2025-04-01', type:'system'  },
  { ts:'01/04/2025 09:14', actor:'Sistema',   action:'Validación sintáctica OK — 0 errores de formato', type:'system'  },
  { ts:'01/04/2025 09:17', actor:'Sistema',   action:'Cruce A: ORD_NRO CE-482301 match encontrado', type:'system'  },
  { ts:'01/04/2025 09:17', actor:'Sistema',   action:'Cruce B: Medidor M74829103 match en SIGEC',   type:'system'  },
  { ts:'01/04/2025 09:17', actor:'Sistema',   action:'Cruce C: divergencia COD_EPEC 1003 ≠ SIGEC 1004 → TRAZA=Error Sumi Nro Med', type:'warning' },
  { ts:'01/04/2025 10:42', actor:'López, M.', action:'Abrió detalle del parte para revisión',       type:'user'    },
  { ts:'01/04/2025 10:55', actor:'López, M.', action:'Modificó COD_EPEC: 1003 → 1004 · Motivo: "SIGEC actualizado hoy"', type:'edit' },
  { ts:'01/04/2025 10:55', actor:'Sistema',   action:'Recalculó USES: 1.00 → 1.25 · Recomputó Control Obs', type:'system' },
  { ts:'01/04/2025 11:01', actor:'López, M.', action:'TRAZA actualizada: Error Sumi Nro Med → Corregido Medidor', type:'edit' },
  { ts:'01/04/2025 11:03', actor:'López, M.', action:'Parte Aprobado · versión 2', type:'success' },
];

const BITACORA_COLORS = {
  system:  { icon: 'circle',        color: '#b5bfbb', bg: '#f5f7f6' },
  warning: { icon: 'alert-circle',  color: '#e6910a', bg: '#fff3cd' },
  user:    { icon: 'user',          color: '#1565c0', bg: '#dbeafe' },
  edit:    { icon: 'edit',          color: '#7a4a00', bg: '#fff3cd' },
  success: { icon: 'check-circle',  color: '#1d8348', bg: '#d4edda' },
};

const TABS = [
  { id: 'detalle',  label: 'Detalle' },
  { id: 'bitacora', label: 'Bitácora' },
];

export function DetallePartes({ parte, onBack }) {
  const p = parte || {
    id: 'PD-2025-00042', contratista: 'CONECTAR', operario: 'López, M.',
    fecha: '01/04/2025', suministro: '412881', cod_epec: '1003', ord_nro: 'CE-482301',
    traza: 'Error Sumi Nro Med', estado: 'En Revisión', medidor_dec: 'M74829103',
    uses: '1.00', lote: 'CONECTAR_2025-04-01', version: 2,
  };

  const [tab, setTab] = useState('detalle');
  const [showOracleModal, setShowOracleModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showConflictModal, setShowConflictModal] = useState(false);
  const [editFields, setEditFields] = useState({
    cod_epec: p.cod_epec || '1003',
    ord_nro: p.ord_nro || 'CE-482301',
    medidor: p.medidor_dec || 'M74829103',
    traza: p.traza || 'Error Sumi Nro Med',
    observacion: '',
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [oracleLoading, setOracleLoading] = useState(false);
  const [oracleResult, setOracleResult] = useState(null);
  const [rejectMotivo, setRejectMotivo] = useState('');

  function handleSave() {
    setSaving(true);
    setTimeout(() => {
      setSaving(false); setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    }, 900);
  }
  function handleOracleQuery() {
    setOracleLoading(true);
    setOracleResult(null);
    setTimeout(() => {
      setOracleResult({ ok: true, ord_nro: editFields.ord_nro, tor: 'CE', estado: 'VÁLIDO', srv: '412881', fecha_cierre: '15/04/2025' });
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

  const photoCount = getPartePhotos(p.id).length;

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
            {p.contratista} · {p.operario} · {p.fecha} · Suministro {p.suministro} · Lote {p.lote}
          </div>
        </div>
        <div style={dS.headerRight}>
          <span style={{ fontSize: 11, color: '#8f9c97' }}>v{p.version}</span>
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
                  <span style={{ fontSize: 10.5, color: '#8f9c97' }}>Lote {p.lote}</span>
                </div>
                <div style={dS.rawGrid}>
                  {[
                    ['Suministro', p.suministro], ['Operario', p.operario],
                    ['Fecha Parte', p.fecha], ['Contratista', p.contratista],
                    ['Medidor Retirado', 'M' + (parseInt(p.medidor_dec?.slice(1) || '74829103') - 1000)], ['Medidor Colocado', p.medidor_dec],
                    ['Lectura Ret.', '12847.5'], ['Lectura Col.', '0.0'],
                    ['COD_EPEC Dec.', p.cod_epec], ['ORD_NRO Dec.', p.ord_nro],
                    ['Observación App', 'Cambio programado CE'], ['COD_EPEC Sug. (Hamming)', '1004'],
                  ].map(([label, val]) => (
                    <div key={label} style={dS.rawCell}>
                      <div style={dS.rawLabel}>{label}</div>
                      <div style={dS.rawValue}>{val}</div>
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
                {Object.entries(CRUCE_RESULTS).map(([key, cruce]) => (
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
                  { label: 'COD_EPEC', declarado: p.cod_epec, sigec: '1004', match: p.cod_epec === '1004' },
                  { label: 'Medidor', declarado: p.medidor_dec, sigec: p.medidor_dec, match: true },
                  { label: 'USES', declarado: '1.00', sigec: '1.25', match: false, delta: '+0.25', deltaOk: false },
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
                  <div style={dS.fieldLabel}>Traza Calidad</div>
                  <select
                    style={dS.fieldSelect}
                    value={editFields.traza}
                    onChange={(e) => setEditFields((prev) => ({ ...prev, traza: e.target.value }))}
                  >
                    {Object.keys(TRAZA_CONFIG).map((t) => (<option key={t} value={t}>{t}</option>))}
                  </select>
                </div>
                <div style={dS.fieldGroup}>
                  <div style={dS.fieldLabel}>Observación (auditor)</div>
                  <textarea
                    style={{ ...dS.fieldInput, fontFamily: 'inherit', height: 72, resize: 'vertical', lineHeight: 1.4 }}
                    placeholder="Ingrese justificación del cambio…"
                    value={editFields.observacion}
                    onChange={(e) => setEditFields((prev) => ({ ...prev, observacion: e.target.value }))}
                    onFocus={(e) => (e.target.style.borderColor = '#124e2f')}
                    onBlur={(e) => (e.target.style.borderColor = '#d5ddd9')}
                  />
                </div>

                <div style={{ marginTop: 4 }}>
                  <div style={dS.fieldLabel}>Consulta Oracle en Vivo</div>
                  <button style={dS.oracleBtn} onClick={handleOracleQuery} disabled={oracleLoading}>
                    {oracleLoading
                      ? <><Icon name="loader" size={13} /> Consultando SIGEC…</>
                      : <><Icon name="database" size={13} /> Consultar Oracle ahora</>
                    }
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
                <button style={{ ...dS.saveBtn, background: saved ? '#1d8348' : '#124e2f' }} onClick={handleSave} disabled={saving}>
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
                <span style={{ marginLeft: 'auto', fontSize: 10.5, color: '#8f9c97' }}>Registro inmutable</span>
                <Icon name="lock" size={12} color="#b5bfbb" />
              </div>
              <div style={{ padding: '8px 16px' }}>
                {BITACORA_EVENTS.map((ev, i) => {
                  const c = BITACORA_COLORS[ev.type] || BITACORA_COLORS.system;
                  return (
                    <div key={i} style={{ display: 'flex', gap: 12, paddingBottom: 16, position: 'relative' }}>
                      {i < BITACORA_EVENTS.length - 1 && (
                        <div style={{ position: 'absolute', left: 14, top: 26, bottom: 0, width: 1, background: '#eaeeec' }} />
                      )}
                      <div style={{ width: 28, height: 28, borderRadius: 14, background: c.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2 }}>
                        <Icon name={c.icon} size={13} color={c.color} />
                      </div>
                      <div style={{ flex: 1, paddingTop: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: '#2f3733' }}>{ev.actor}</span>
                          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: '#8f9c97' }}>{ev.ts}</span>
                        </div>
                        <div style={{ fontSize: 12, color: '#4a5550', marginTop: 2, lineHeight: 1.45 }}>{ev.action}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>

      <div style={dS.actionFooter}>
        <span style={{ fontSize: 11.5, color: '#8f9c97', flex: 1 }}>
          {p.estado === 'Aprobado' ? 'Parte ya aprobado' : 'Aprobar o rechazar este parte'}
        </span>
        <button style={dS.annulBtn} onClick={() => setShowRejectModal(true)}>
          <Icon name="slash" size={13} /> Anular
        </button>
        <button style={dS.rejectBtn} onClick={() => setShowRejectModal(true)}>
          <Icon name="x-circle" size={13} /> Rechazar
        </button>
        <button style={dS.approveBtn}>
          <Icon name="check-circle" size={13} /> Aprobar
        </button>
      </div>

      {showOracleModal && (
        <div style={dS.overlay} onClick={() => setShowOracleModal(false)}>
          <div style={dS.modal} onClick={(e) => e.stopPropagation()}>
            <div style={dS.modalHeader}>
              <Icon name="database" size={16} color="#124e2f" />
              <span style={dS.modalTitle}>Cruce Manual con Oracle</span>
              <button style={{ border: 'none', background: 'transparent', cursor: 'pointer' }} onClick={() => setShowOracleModal(false)}>
                <Icon name="x" size={16} color="#8f9c97" />
              </button>
            </div>
            <div style={dS.modalBody}>
              <div style={{ fontSize: 12, color: '#4a5550', marginBottom: 12 }}>Ingresar ORD_NRO para validar contra SIGEC (TOR='CE', estado VÁLIDO).</div>
              <input style={{ ...dS.fieldInput, width: '100%', boxSizing: 'border-box' }} placeholder="CE-XXXXXX" defaultValue={p.ord_nro} />
            </div>
            <div style={dS.modalFooter}>
              <button style={dS.annulBtn} onClick={() => setShowOracleModal(false)}>Cancelar</button>
              <button style={dS.approveBtn} onClick={() => setShowOracleModal(false)}>Consultar</button>
            </div>
          </div>
        </div>
      )}

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
              <div style={{ fontSize: 12, color: '#4a5550', marginBottom: 12 }}>Ingrese el motivo de rechazo (obligatorio):</div>
              <textarea
                style={{ ...dS.fieldInput, width: '100%', boxSizing: 'border-box', height: 80, fontFamily: 'inherit', resize: 'vertical' }}
                placeholder="Describa el motivo del rechazo…"
                value={rejectMotivo}
                onChange={(e) => setRejectMotivo(e.target.value)}
              />
            </div>
            <div style={dS.modalFooter}>
              <button style={dS.annulBtn} onClick={() => setShowRejectModal(false)}>Cancelar</button>
              <button style={dS.rejectBtn} disabled={!rejectMotivo.trim()} onClick={() => setShowRejectModal(false)}>
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
                <strong>Versión desactualizada.</strong> Otro usuario modificó este parte mientras estabas editando (v{p.version} → v{p.version + 1}).
                Tus cambios no fueron guardados. Recargá para ver la versión más reciente.
              </div>
            </div>
            <div style={dS.modalFooter}>
              <button style={dS.approveBtn} onClick={() => setShowConflictModal(false)}>
                <Icon name="refresh-cw" size={13} /> Recargar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
