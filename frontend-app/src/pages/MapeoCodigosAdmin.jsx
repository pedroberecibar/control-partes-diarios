import { useState } from 'react';
import { Icon } from '../components/Icon';

const INITIAL_CODIGOS = [
  { cod: '1001', desc: 'Cambio de Medidor — BT Estándar',       tipo: 'CAMBIO',       contrato: 'AMBOS',    activo: true  },
  { cod: '1002', desc: 'Cambio de Medidor — MT',                tipo: 'CAMBIO',       contrato: 'CONECTAR', activo: true  },
  { cod: '1003', desc: 'Cambio de Medidor — GD Bidireccional',  tipo: 'CAMBIO',       contrato: 'AMBOS',    activo: true  },
  { cod: '1004', desc: 'Reparación de Medidor',                 tipo: 'REPARACION',   contrato: 'AMBOS',    activo: true  },
  { cod: '1005', desc: 'Retiro de Medidor',                     tipo: 'RETIRO',       contrato: 'COOPLYF',  activo: true  },
  { cod: '2001', desc: 'Relevamiento — Sin Cambio',             tipo: 'RELEVAMIENTO', contrato: 'AMBOS',    activo: true  },
  { cod: '2002', desc: 'Relevamiento — Con Cambio',             tipo: 'RELEVAMIENTO', contrato: 'AMBOS',    activo: true  },
  { cod: '3001', desc: 'Inspección — Detección Anomalía',       tipo: 'INSPECCION',   contrato: 'AMBOS',    activo: true  },
  { cod: '3002', desc: 'Inspección — Sin Anomalía',             tipo: 'INSPECCION',   contrato: 'AMBOS',    activo: true  },
  { cod: '4001', desc: 'Urgencia — Fraude o Irregularidad',     tipo: 'URGENCIA',     contrato: 'AMBOS',    activo: false },
];

const TIPO_COLORS = {
  CAMBIO:       { bg: '#d4edda', color: '#155a2e' },
  REPARACION:   { bg: '#fff3cd', color: '#7a4a00' },
  RETIRO:       { bg: '#fde8e8', color: '#7a1c1c' },
  RELEVAMIENTO: { bg: '#dbeafe', color: '#0d4272' },
  INSPECCION:   { bg: '#eaeeec', color: '#4a5550' },
  URGENCIA:     { bg: '#fde8e8', color: '#7a1c1c' },
};

const TIPOS_LIST   = ['CAMBIO', 'REPARACION', 'RETIRO', 'RELEVAMIENTO', 'INSPECCION', 'URGENCIA'];
const CONTRATOS    = ['AMBOS', 'CONECTAR', 'COOPLYF'];

function Modal({ title, children, onClose }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div style={{ background: 'white', borderRadius: 6, boxShadow: '0 20px 48px rgba(0,0,0,0.2)', width: 460, maxWidth: '90vw', overflow: 'hidden', animation: 'modalIn 0.16s ease' }}>
        <div style={{ padding: '14px 18px', borderBottom: '1px solid #eaeeec', display: 'flex', alignItems: 'center', gap: 10 }}>
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

export function MapeoCodigosAdmin() {
  const [codigos, setCodigos] = useState(INITIAL_CODIGOS);
  const [search, setSearch]   = useState('');
  const [tipoFil, setTipoFil] = useState('');
  const [editing, setEditing] = useState(null);
  const [adding, setAdding]   = useState(false);
  const [form, setForm]       = useState({ cod: '', desc: '', tipo: 'CAMBIO', contrato: 'AMBOS', activo: true });
  const [saved, setSaved]     = useState(false);

  const filtered = codigos.filter((c) => {
    const q = search.toLowerCase();
    const mS = !q || c.cod.includes(q) || c.desc.toLowerCase().includes(q);
    const mT = !tipoFil || c.tipo === tipoFil;
    return mS && mT;
  });

  function openEdit(c) {
    setForm({ ...c });
    setEditing(c.cod);
    setAdding(false);
  }
  function openAdd() {
    setForm({ cod: '', desc: '', tipo: 'CAMBIO', contrato: 'AMBOS', activo: true });
    setAdding(true);
    setEditing(null);
  }
  function handleSave() {
    if (adding) {
      setCodigos((prev) => [...prev, { ...form }]);
    } else {
      setCodigos((prev) => prev.map((c) => (c.cod === editing ? { ...form } : c)));
    }
    setSaved(true);
    setTimeout(() => { setSaved(false); setEditing(null); setAdding(false); }, 1200);
  }
  function toggleActivo(cod) {
    setCodigos((prev) => prev.map((c) => (c.cod === cod ? { ...c, activo: !c.activo } : c)));
  }

  const dS = {
    root:      { padding: 20, overflow: 'auto', height: '100%', boxSizing: 'border-box', background: '#f5f7f6' },
    hdr:       { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 },
    title:     { fontSize: 17, fontWeight: 700, color: '#111614' },
    sub:       { fontSize: 12, color: '#8f9c97', marginTop: 2 },
    tableCard: { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    toolbar:   { padding: '10px 16px', borderBottom: '1px solid #eaeeec', display: 'flex', alignItems: 'center', gap: 10 },
    searchWrap:{ display: 'flex', alignItems: 'center', gap: 7, background: '#f5f7f6', border: '1px solid #eaeeec', borderRadius: 4, padding: '5px 10px', width: 240 },
    searchInp: { border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: '#111614', width: '100%' },
    filterSel: { padding: '5px 8px', border: '1px solid #eaeeec', borderRadius: 4, fontSize: 12, color: '#2f3733', background: 'white', cursor: 'pointer' },
    btnPrim:   { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', border: 'none', borderRadius: 4, background: '#124e2f', color: 'white', fontSize: 12, fontWeight: 600, cursor: 'pointer' },
    btn:       { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 10px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, fontWeight: 600, color: '#2f3733', cursor: 'pointer' },
    table:     { width: '100%', borderCollapse: 'collapse', fontSize: 12 },
    th:        { padding: '8px 12px', textAlign: 'left', background: '#124e2f', color: 'white', fontWeight: 600, fontSize: 10.5, letterSpacing: '0.04em', whiteSpace: 'nowrap' },
    td:        { padding: '8px 12px', borderBottom: '1px solid #f0f3f1', color: '#2f3733', whiteSpace: 'nowrap', verticalAlign: 'middle' },
    mono:      { fontFamily: "'JetBrains Mono', monospace", fontSize: 11 },
    actionBtn: { border: 'none', background: 'transparent', cursor: 'pointer', color: '#8f9c97', display: 'inline-flex', alignItems: 'center', padding: '2px 4px', borderRadius: 3, transition: 'all 0.1s' },
    fieldGrp:  { marginBottom: 14 },
    fieldLbl:  { fontSize: 10.5, fontWeight: 700, color: '#6b7772', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 },
    fieldInp:  { width: '100%', padding: '6px 9px', border: '1px solid #d5ddd9', borderRadius: 4, fontSize: 12.5, color: '#111614', outline: 'none', boxSizing: 'border-box' },
    fieldSel:  { width: '100%', padding: '6px 9px', border: '1px solid #d5ddd9', borderRadius: 4, fontSize: 12, color: '#2f3733', outline: 'none', background: 'white', cursor: 'pointer', boxSizing: 'border-box' },
  };

  const showModal = editing !== null || adding;

  return (
    <div style={dS.root}>
      <div style={dS.hdr}>
        <div>
          <div style={dS.title}>Mapeo de Códigos EPEC</div>
          <div style={dS.sub}>Admin — Gestión de COD_EPEC y sus descripciones / contratos</div>
        </div>
        <button style={dS.btnPrim} onClick={openAdd}>
          <Icon name="plus" size={14} /> Nuevo código
        </button>
      </div>

      <div style={dS.tableCard}>
        <div style={dS.toolbar}>
          <div style={dS.searchWrap}>
            <Icon name="search" size={13} color="#8f9c97" />
            <input style={dS.searchInp} placeholder="Buscar código o descripción…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <select style={dS.filterSel} value={tipoFil} onChange={(e) => setTipoFil(e.target.value)}>
            <option value="">Todos los tipos</option>
            {TIPOS_LIST.map((t) => (<option key={t} value={t}>{t}</option>))}
          </select>
          <span style={{ fontSize: 12, color: '#6b7772', fontWeight: 500 }}>{filtered.length} códigos</span>
          <div style={{ flex: 1 }} />
          <button style={dS.btn}><Icon name="download" size={13} /> Exportar</button>
        </div>
        <table style={dS.table}>
          <thead>
            <tr>
              {['Código', 'Descripción', 'Tipo', 'Contrato', 'Estado', 'Acciones'].map((h) => (
                <th key={h} style={dS.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((c, i) => {
              const tc = TIPO_COLORS[c.tipo] || {};
              return (
                <tr key={c.cod} style={{ background: i % 2 === 0 ? 'white' : '#fafcfb', opacity: c.activo ? 1 : 0.5 }}>
                  <td style={{ ...dS.td, ...dS.mono, color: '#124e2f', fontWeight: 700 }}>{c.cod}</td>
                  <td style={{ ...dS.td, color: '#2f3733', minWidth: 240 }}>{c.desc}</td>
                  <td style={dS.td}>
                    <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 3, background: tc.bg, color: tc.color }}>
                      {c.tipo}
                    </span>
                  </td>
                  <td style={dS.td}>
                    <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 6px', borderRadius: 3, background: c.contrato === 'AMBOS' ? '#eaeeec' : c.contrato === 'CONECTAR' ? '#edf5f0' : '#dbeafe', color: c.contrato === 'AMBOS' ? '#4a5550' : c.contrato === 'CONECTAR' ? '#124e2f' : '#0d4272' }}>
                      {c.contrato}
                    </span>
                  </td>
                  <td style={dS.td}>
                    <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 3, background: c.activo ? '#d4edda' : '#eaeeec', color: c.activo ? '#155a2e' : '#4a5550' }}>
                      {c.activo ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td style={dS.td}>
                    <button
                      style={dS.actionBtn}
                      title="Editar"
                      onClick={() => openEdit(c)}
                      onMouseEnter={(e) => { e.currentTarget.style.background = '#edf5f0'; e.currentTarget.style.color = '#124e2f'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = ''; e.currentTarget.style.color = '#8f9c97'; }}
                    >
                      <Icon name="edit" size={13} />
                    </button>
                    <button
                      style={dS.actionBtn}
                      title={c.activo ? 'Desactivar' : 'Activar'}
                      onClick={() => toggleActivo(c.cod)}
                      onMouseEnter={(e) => { e.currentTarget.style.background = '#fde8e8'; e.currentTarget.style.color = '#7a1c1c'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = ''; e.currentTarget.style.color = '#8f9c97'; }}
                    >
                      <Icon name={c.activo ? 'slash' : 'check-circle'} size={13} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {showModal && (
        <Modal
          title={adding ? 'Nuevo código EPEC' : `Editar código ${editing}`}
          onClose={() => { setEditing(null); setAdding(false); }}
        >
          <div style={{ padding: 18 }}>
            <div style={dS.fieldGrp}>
              <div style={dS.fieldLbl}>Código EPEC</div>
              <input
                style={{ ...dS.fieldInp, fontFamily: "'JetBrains Mono', monospace" }}
                value={form.cod}
                onChange={(e) => setForm((f) => ({ ...f, cod: e.target.value }))}
                disabled={!adding}
                placeholder="ej. 1001"
              />
            </div>
            <div style={dS.fieldGrp}>
              <div style={dS.fieldLbl}>Descripción</div>
              <input
                style={dS.fieldInp}
                value={form.desc}
                onChange={(e) => setForm((f) => ({ ...f, desc: e.target.value }))}
                placeholder="Descripción completa del código"
                onFocus={(e) => (e.target.style.borderColor = '#124e2f')}
                onBlur={(e) => (e.target.style.borderColor = '#d5ddd9')}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div style={dS.fieldGrp}>
                <div style={dS.fieldLbl}>Tipo de servicio</div>
                <select style={dS.fieldSel} value={form.tipo} onChange={(e) => setForm((f) => ({ ...f, tipo: e.target.value }))}>
                  {TIPOS_LIST.map((t) => (<option key={t} value={t}>{t}</option>))}
                </select>
              </div>
              <div style={dS.fieldGrp}>
                <div style={dS.fieldLbl}>Aplica a contrato</div>
                <select style={dS.fieldSel} value={form.contrato} onChange={(e) => setForm((f) => ({ ...f, contrato: e.target.value }))}>
                  {CONTRATOS.map((c) => (<option key={c} value={c}>{c}</option>))}
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0' }}>
              <input
                type="checkbox"
                checked={form.activo}
                onChange={(e) => setForm((f) => ({ ...f, activo: e.target.checked }))}
                style={{ width: 14, height: 14, accentColor: '#124e2f', cursor: 'pointer' }}
              />
              <span style={{ fontSize: 13, color: '#2f3733', fontWeight: 500 }}>Código activo</span>
            </div>
          </div>
          <div style={{ padding: '12px 18px', borderTop: '1px solid #eaeeec', display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button
              style={{ padding: '7px 14px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, fontWeight: 600, color: '#4a5550', cursor: 'pointer' }}
              onClick={() => { setEditing(null); setAdding(false); }}
            >
              Cancelar
            </button>
            <button
              style={{ padding: '7px 16px', border: 'none', borderRadius: 4, background: saved ? '#1d8348' : '#124e2f', color: 'white', fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, transition: 'background 0.2s' }}
              onClick={handleSave}
              disabled={!form.cod || !form.desc}
            >
              {saved ? <><Icon name="check" size={13} /> Guardado</> : <><Icon name="send" size={13} /> Guardar</>}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
