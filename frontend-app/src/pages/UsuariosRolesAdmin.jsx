import { useState } from 'react';
import { Icon } from '../components/Icon';
import { ROLE_LABELS } from '../data/nav';

const INITIAL_USERS = [
  { id: 1, nombre: 'García, Juan',    email: 'jgarcia@epec.com.ar',    rol: 'operador',   contratista: 'CONECTAR', activo: true,  ultimo: '29/04/2025 08:34' },
  { id: 2, nombre: 'López, María',    email: 'mlopez@epec.com.ar',     rol: 'auditor',    contratista: null,       activo: true,  ultimo: '29/04/2025 09:17' },
  { id: 3, nombre: 'Fernández, Ana',  email: 'afernandez@epec.com.ar', rol: 'auditor',    contratista: null,       activo: true,  ultimo: '28/04/2025 17:51' },
  { id: 4, nombre: 'Torres, Roberto', email: 'rtorres@epec.com.ar',    rol: 'supervisor', contratista: null,       activo: true,  ultimo: '28/04/2025 16:02' },
  { id: 5, nombre: 'Romero, Sofía',   email: 'sromero@cooplyf.com.ar', rol: 'operador',   contratista: 'COOPLYF',  activo: true,  ultimo: '29/04/2025 07:55' },
  { id: 6, nombre: 'Sosa, Diego',     email: 'dsosa@cooplyf.com.ar',   rol: 'operador',   contratista: 'COOPLYF',  activo: false, ultimo: '15/03/2025 10:22' },
  { id: 7, nombre: 'Martínez, Pablo', email: 'pmartinez@epec.com.ar',  rol: 'admin',      contratista: null,       activo: true,  ultimo: '29/04/2025 09:44' },
];

const ROL_COLORS = {
  operador:   { bg: '#dbeafe', color: '#0d4272' },
  auditor:    { bg: '#d4edda', color: '#155a2e' },
  supervisor: { bg: '#fff3cd', color: '#7a4a00' },
  admin:      { bg: '#fde8e8', color: '#7a1c1c' },
};

function Modal({ title, children, onClose }) {
  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div style={{ background: 'white', borderRadius: 6, boxShadow: '0 20px 48px rgba(0,0,0,0.2)', width: 480, maxWidth: '90vw', overflow: 'hidden', animation: 'modalIn 0.16s ease' }}>
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

const EMPTY_FORM = { nombre: '', email: '', rol: 'operador', contratista: '', activo: true };

export function UsuariosRolesAdmin() {
  const [users, setUsers]     = useState(INITIAL_USERS);
  const [search, setSearch]   = useState('');
  const [rolFil, setRolFil]   = useState('');
  const [editing, setEditing] = useState(null);
  const [adding, setAdding]   = useState(false);
  const [form, setForm]       = useState(EMPTY_FORM);
  const [saved, setSaved]     = useState(false);
  const [confirm, setConfirm] = useState(null); // user to toggle

  const filtered = users.filter((u) => {
    const q = search.toLowerCase();
    const mS = !q || u.nombre.toLowerCase().includes(q) || u.email.toLowerCase().includes(q);
    const mR = !rolFil || u.rol === rolFil;
    return mS && mR;
  });

  function openEdit(u) {
    setForm({ nombre: u.nombre, email: u.email, rol: u.rol, contratista: u.contratista || '', activo: u.activo });
    setEditing(u.id);
    setAdding(false);
  }
  function openAdd() {
    setForm(EMPTY_FORM);
    setAdding(true);
    setEditing(null);
  }
  function handleSave() {
    if (adding) {
      setUsers((prev) => [...prev, { ...form, id: Date.now(), contratista: form.contratista || null, ultimo: '—' }]);
    } else {
      setUsers((prev) => prev.map((u) => (u.id === editing ? { ...u, ...form, contratista: form.contratista || null } : u)));
    }
    setSaved(true);
    setTimeout(() => { setSaved(false); setEditing(null); setAdding(false); }, 1200);
  }
  function confirmToggle(u) { setConfirm(u); }
  function doToggle() {
    setUsers((prev) => prev.map((u) => (u.id === confirm.id ? { ...u, activo: !u.activo } : u)));
    setConfirm(null);
  }

  const counts = Object.keys(ROLE_LABELS).reduce((acc, r) => {
    acc[r] = users.filter((u) => u.rol === r && u.activo).length;
    return acc;
  }, {});

  const dS = {
    root:      { padding: 20, overflow: 'auto', height: '100%', boxSizing: 'border-box', background: '#f5f7f6' },
    hdr:       { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 },
    title:     { fontSize: 17, fontWeight: 700, color: '#111614' },
    sub:       { fontSize: 12, color: '#8f9c97', marginTop: 2 },
    kpiRow:    { display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 18 },
    kpiCard:   { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, padding: '14px 16px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    kpiLabel:  { fontSize: 10.5, fontWeight: 700, color: '#8f9c97', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 },
    kpiVal:    { fontSize: 22, fontWeight: 700, lineHeight: 1.1 },
    kpiSub:    { fontSize: 11, color: '#8f9c97', marginTop: 3 },
    tableCard: { background: 'white', border: '1px solid #eaeeec', borderRadius: 6, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' },
    toolbar:   { padding: '10px 16px', borderBottom: '1px solid #eaeeec', display: 'flex', alignItems: 'center', gap: 10 },
    searchWrap:{ display: 'flex', alignItems: 'center', gap: 7, background: '#f5f7f6', border: '1px solid #eaeeec', borderRadius: 4, padding: '5px 10px', width: 240 },
    searchInp: { border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: '#111614', width: '100%' },
    filterSel: { padding: '5px 8px', border: '1px solid #eaeeec', borderRadius: 4, fontSize: 12, color: '#2f3733', background: 'white', cursor: 'pointer' },
    btnPrim:   { display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 14px', border: 'none', borderRadius: 4, background: '#124e2f', color: 'white', fontSize: 12, fontWeight: 600, cursor: 'pointer' },
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
          <div style={dS.title}>Usuarios y Roles</div>
          <div style={dS.sub}>Admin — Gestión de accesos al sistema</div>
        </div>
        <button style={dS.btnPrim} onClick={openAdd}>
          <Icon name="plus" size={14} /> Nuevo usuario
        </button>
      </div>

      <div style={dS.kpiRow}>
        {Object.entries(ROLE_LABELS).map(([rol, lbl]) => {
          const rc = ROL_COLORS[rol] || {};
          return (
            <div key={rol} style={dS.kpiCard}>
              <div style={dS.kpiLabel}>{lbl}</div>
              <div style={{ ...dS.kpiVal, color: rc.color || '#111614' }}>{counts[rol]}</div>
              <div style={dS.kpiSub}>usuarios activos</div>
            </div>
          );
        })}
      </div>

      <div style={dS.tableCard}>
        <div style={dS.toolbar}>
          <div style={dS.searchWrap}>
            <Icon name="search" size={13} color="#8f9c97" />
            <input style={dS.searchInp} placeholder="Buscar por nombre o email…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <select style={dS.filterSel} value={rolFil} onChange={(e) => setRolFil(e.target.value)}>
            <option value="">Todos los roles</option>
            {Object.entries(ROLE_LABELS).map(([r, l]) => (<option key={r} value={r}>{l}</option>))}
          </select>
          <span style={{ fontSize: 12, color: '#6b7772', fontWeight: 500 }}>{filtered.length} usuarios</span>
        </div>
        <table style={dS.table}>
          <thead>
            <tr>
              {['Usuario', 'Email', 'Rol', 'Contratista', 'Último acceso', 'Estado', 'Acciones'].map((h) => (
                <th key={h} style={dS.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((u, i) => {
              const rc = ROL_COLORS[u.rol] || {};
              return (
                <tr key={u.id} style={{ background: i % 2 === 0 ? 'white' : '#fafcfb', opacity: u.activo ? 1 : 0.55 }}>
                  <td style={dS.td}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ width: 28, height: 28, borderRadius: '50%', background: u.activo ? '#edf5f0' : '#eaeeec', color: u.activo ? '#124e2f' : '#8f9c97', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 700, flexShrink: 0 }}>
                        {u.nombre.split(',')[0]?.charAt(0)}
                        {u.nombre.split(' ').pop()?.charAt(0)}
                      </div>
                      <span style={{ fontWeight: 600, color: '#2f3733' }}>{u.nombre}</span>
                    </div>
                  </td>
                  <td style={{ ...dS.td, ...dS.mono, color: '#4a5550' }}>{u.email}</td>
                  <td style={dS.td}>
                    <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 3, background: rc.bg, color: rc.color }}>
                      {ROLE_LABELS[u.rol]}
                    </span>
                  </td>
                  <td style={dS.td}>
                    {u.contratista ? (
                      <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 6px', borderRadius: 3, background: u.contratista === 'CONECTAR' ? '#edf5f0' : '#dbeafe', color: u.contratista === 'CONECTAR' ? '#124e2f' : '#0d4272' }}>
                        {u.contratista}
                      </span>
                    ) : (
                      <span style={{ fontSize: 11, color: '#b5bfbb' }}>—</span>
                    )}
                  </td>
                  <td style={{ ...dS.td, ...dS.mono, color: '#4a5550', fontSize: 10.5 }}>{u.ultimo}</td>
                  <td style={dS.td}>
                    <span style={{ fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 3, background: u.activo ? '#d4edda' : '#eaeeec', color: u.activo ? '#155a2e' : '#4a5550' }}>
                      {u.activo ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td style={dS.td}>
                    <button
                      style={dS.actionBtn}
                      title="Editar"
                      onClick={() => openEdit(u)}
                      onMouseEnter={(e) => { e.currentTarget.style.background = '#edf5f0'; e.currentTarget.style.color = '#124e2f'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = ''; e.currentTarget.style.color = '#8f9c97'; }}
                    >
                      <Icon name="edit" size={13} />
                    </button>
                    <button
                      style={dS.actionBtn}
                      title={u.activo ? 'Desactivar usuario' : 'Reactivar usuario'}
                      onClick={() => confirmToggle(u)}
                      onMouseEnter={(e) => { e.currentTarget.style.background = '#fde8e8'; e.currentTarget.style.color = '#7a1c1c'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = ''; e.currentTarget.style.color = '#8f9c97'; }}
                    >
                      <Icon name={u.activo ? 'slash' : 'check-circle'} size={13} />
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
          title={adding ? 'Nuevo usuario' : `Editar — ${users.find((u) => u.id === editing)?.nombre}`}
          onClose={() => { setEditing(null); setAdding(false); }}
        >
          <div style={{ padding: 18 }}>
            <div style={dS.fieldGrp}>
              <div style={dS.fieldLbl}>Nombre completo</div>
              <input
                style={dS.fieldInp}
                value={form.nombre}
                onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
                placeholder="Apellido, Nombre"
                onFocus={(e) => (e.target.style.borderColor = '#124e2f')}
                onBlur={(e) => (e.target.style.borderColor = '#d5ddd9')}
              />
            </div>
            <div style={dS.fieldGrp}>
              <div style={dS.fieldLbl}>Email corporativo</div>
              <input
                style={{ ...dS.fieldInp, fontFamily: "'JetBrains Mono', monospace" }}
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="usuario@epec.com.ar"
                type="email"
                onFocus={(e) => (e.target.style.borderColor = '#124e2f')}
                onBlur={(e) => (e.target.style.borderColor = '#d5ddd9')}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div style={dS.fieldGrp}>
                <div style={dS.fieldLbl}>Rol</div>
                <select style={dS.fieldSel} value={form.rol} onChange={(e) => setForm((f) => ({ ...f, rol: e.target.value }))}>
                  {Object.entries(ROLE_LABELS).map(([r, l]) => (<option key={r} value={r}>{l}</option>))}
                </select>
              </div>
              <div style={dS.fieldGrp}>
                <div style={dS.fieldLbl}>Contratista (si aplica)</div>
                <select style={dS.fieldSel} value={form.contratista} onChange={(e) => setForm((f) => ({ ...f, contratista: e.target.value }))}>
                  <option value="">— Ninguno —</option>
                  <option value="CONECTAR">CONECTAR</option>
                  <option value="COOPLYF">COOPLYF</option>
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0' }}>
              <input
                type="checkbox"
                checked={form.activo}
                onChange={(e) => setForm((f) => ({ ...f, activo: e.target.checked }))}
                style={{ width: 14, height: 14, accentColor: '#124e2f', cursor: 'pointer' }}
              />
              <span style={{ fontSize: 13, color: '#2f3733', fontWeight: 500 }}>Usuario activo</span>
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
              disabled={!form.nombre || !form.email}
            >
              {saved ? <><Icon name="check" size={13} /> Guardado</> : <><Icon name="send" size={13} /> Guardar</>}
            </button>
          </div>
        </Modal>
      )}

      {confirm && (
        <Modal
          title={confirm.activo ? 'Desactivar usuario' : 'Reactivar usuario'}
          onClose={() => setConfirm(null)}
        >
          <div style={{ padding: 18 }}>
            <div style={{ padding: '10px 12px', background: confirm.activo ? '#fff3cd' : '#edf5f0', borderRadius: 4, fontSize: 13, color: confirm.activo ? '#7a4a00' : '#155a2e', lineHeight: 1.5 }}>
              {confirm.activo
                ? <>¿Desactivar a <strong>{confirm.nombre}</strong>? No podrá iniciar sesión hasta ser reactivado.</>
                : <>¿Reactivar a <strong>{confirm.nombre}</strong>? Recuperará acceso según su rol.</>
              }
            </div>
          </div>
          <div style={{ padding: '12px 18px', borderTop: '1px solid #eaeeec', display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button
              style={{ padding: '7px 14px', border: '1px solid #d5ddd9', borderRadius: 4, background: 'white', fontSize: 12, fontWeight: 600, color: '#4a5550', cursor: 'pointer' }}
              onClick={() => setConfirm(null)}
            >
              Cancelar
            </button>
            <button
              style={{ padding: '7px 16px', border: 'none', borderRadius: 4, background: confirm.activo ? '#c0392b' : '#1d8348', color: 'white', fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6 }}
              onClick={doToggle}
            >
              <Icon name={confirm.activo ? 'slash' : 'check-circle'} size={13} />
              {confirm.activo ? 'Desactivar' : 'Reactivar'}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
