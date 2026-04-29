import { useState } from 'react';
import { Icon } from '../Icon';
import { ROLE_LABELS } from '../../data/nav';

const NOTIFICATIONS = [
  { id: 1, type: 'success', msg: 'Lote CONECTAR_2025-04 procesado OK',                         time: 'hace 3 min',  read: false },
  { id: 2, type: 'warning', msg: 'Lote COOPLYF_2025-04 en observación (12 conflictos)',         time: 'hace 18 min', read: false },
  { id: 3, type: 'error',   msg: 'Lote ERROR_TEST falló validación sintáctica',                 time: 'hace 1 h',    read: true  },
  { id: 4, type: 'info',    msg: 'SIGEC seed actualizado correctamente',                       time: 'hace 2 h',    read: true  },
];

const NOTIF_COLORS = { success: '#1d8348', warning: '#e6910a', error: '#c0392b', info: '#1565c0' };
const ROLE_INITIALS = { operador: 'OP', auditor: 'AU', supervisor: 'SU', admin: 'AD' };

export function TopBar({ title, subtitle, role, onRoleChange }) {
  const [searchVal, setSearchVal] = useState('');
  const [showNotif, setShowNotif] = useState(false);
  const [showRoleMenu, setShowRoleMenu] = useState(false);

  const unread = NOTIFICATIONS.filter((n) => !n.read).length;

  const tS = {
    bar: { height: 52, background: 'white', borderBottom: '1px solid #eaeeec', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', flexShrink: 0, gap: 16 },
    titles: { display: 'flex', flexDirection: 'column', minWidth: 0 },
    title: { fontSize: 14, fontWeight: 700, color: '#111614', lineHeight: 1.2, whiteSpace: 'nowrap' },
    subtitle: { fontSize: 11, color: '#8f9c97', lineHeight: 1.3, whiteSpace: 'nowrap' },
    right: { display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 },
    searchWrap: { display: 'flex', alignItems: 'center', gap: 7, background: '#f5f7f6', border: '1px solid #eaeeec', borderRadius: 4, padding: '6px 10px', width: 240 },
    searchInput: { border: 'none', background: 'transparent', outline: 'none', fontSize: 12, color: '#111614', width: '100%' },
    iconBtn: { border: 'none', background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 32, height: 32, borderRadius: 4, color: '#6b7772', position: 'relative', transition: 'background 0.1s' },
    badge: { position: 'absolute', top: 3, right: 3, width: 14, height: 14, borderRadius: 7, background: '#c0392b', color: 'white', fontSize: 9, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '2px solid white' },
    userBtn: { display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', padding: '4px 8px', borderRadius: 4, border: 'none', background: 'transparent' },
    avatar: { width: 30, height: 30, borderRadius: 4, background: '#124e2f', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, flexShrink: 0 },
    userInfo: { textAlign: 'left' },
    userName: { fontSize: 12, fontWeight: 600, color: '#2f3733', display: 'block', lineHeight: 1.2 },
    userRole: { fontSize: 10.5, color: '#8f9c97', display: 'block' },
    notifDropdown: { position: 'absolute', top: 42, right: 0, width: 320, background: 'white', border: '1px solid #eaeeec', borderRadius: 6, boxShadow: '0 8px 24px rgba(0,0,0,0.12)', zIndex: 100 },
    notifHeader: { padding: '10px 14px', borderBottom: '1px solid #eaeeec', fontSize: 12, fontWeight: 600, color: '#2f3733', display: 'flex', justifyContent: 'space-between' },
    notifItem: { padding: '10px 14px', borderBottom: '1px solid #f5f7f6', display: 'flex', gap: 10, alignItems: 'flex-start' },
    notifDot: { width: 7, height: 7, borderRadius: 4, marginTop: 4, flexShrink: 0 },
    notifMsg: { fontSize: 12, color: '#2f3733', lineHeight: 1.4, flex: 1 },
    notifTime: { fontSize: 10.5, color: '#8f9c97', marginTop: 2 },
    roleDropdown: { position: 'absolute', top: 42, right: 0, width: 200, background: 'white', border: '1px solid #eaeeec', borderRadius: 6, boxShadow: '0 8px 24px rgba(0,0,0,0.12)', zIndex: 100, padding: 4 },
    roleItem: { padding: '8px 12px', borderRadius: 4, fontSize: 12, fontWeight: 500, color: '#2f3733', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 },
  };

  return (
    <div style={tS.bar}>
      <div style={tS.titles}>
        <span style={tS.title}>{title}</span>
        {subtitle && <span style={tS.subtitle}>{subtitle}</span>}
      </div>
      <div style={tS.right}>
        <div style={tS.searchWrap}>
          <Icon name="search" size={13} color="#8f9c97" />
          <input
            style={tS.searchInput}
            placeholder="Buscar parte, operario, lote…"
            value={searchVal}
            onChange={(e) => setSearchVal(e.target.value)}
          />
        </div>

        <div style={{ position: 'relative' }}>
          <button
            style={{ ...tS.iconBtn, background: showNotif ? '#f5f7f6' : 'transparent' }}
            onClick={() => { setShowNotif((v) => !v); setShowRoleMenu(false); }}
          >
            <Icon name="bell" size={16} color="#6b7772" />
            {unread > 0 && <span style={tS.badge}>{unread}</span>}
          </button>
          {showNotif && (
            <div style={tS.notifDropdown}>
              <div style={tS.notifHeader}>
                <span>Notificaciones</span>
                <span style={{ color: '#8f9c97', fontWeight: 400 }}>{unread} nuevas</span>
              </div>
              {NOTIFICATIONS.map((n) => (
                <div key={n.id} style={{ ...tS.notifItem, background: n.read ? 'white' : '#fafcfb' }}>
                  <div style={{ ...tS.notifDot, background: NOTIF_COLORS[n.type] }} />
                  <div style={{ flex: 1 }}>
                    <div style={tS.notifMsg}>{n.msg}</div>
                    <div style={tS.notifTime}>{n.time}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ position: 'relative' }}>
          <button
            style={tS.userBtn}
            onClick={() => { setShowRoleMenu((v) => !v); setShowNotif(false); }}
          >
            <div style={tS.avatar}>{ROLE_INITIALS[role]}</div>
            <div style={tS.userInfo}>
              <span style={tS.userName}>Usuario Demo</span>
              <span style={tS.userRole}>{ROLE_LABELS[role]}</span>
            </div>
            <Icon name="chevron-down" size={13} color="#8f9c97" />
          </button>
          {showRoleMenu && (
            <div style={tS.roleDropdown}>
              <div style={{ padding: '6px 12px 4px', fontSize: 10, color: '#8f9c97', fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase' }}>
                Cambiar rol (demo)
              </div>
              {Object.entries(ROLE_LABELS).map(([r, lbl]) => (
                <div
                  key={r}
                  style={{
                    ...tS.roleItem,
                    background: r === role ? '#edf5f0' : 'transparent',
                    color: r === role ? '#124e2f' : '#2f3733',
                  }}
                  onClick={() => { onRoleChange(r); setShowRoleMenu(false); }}
                >
                  {r === role && <Icon name="check" size={13} color="#124e2f" />}
                  {r !== role && <span style={{ width: 13 }} />}
                  {lbl}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
