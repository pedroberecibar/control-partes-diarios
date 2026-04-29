import { useState } from 'react';
import { Icon } from '../Icon';
import { NAV_STRUCTURE, ADMIN_ITEMS, ROLE_ACCESS } from '../../data/nav';

export function Sidebar({ activeScreen, onNav, role, collapsed, onToggle }) {
  const allowedModules = ROLE_ACCESS[role] || [];
  const [expandedModule, setExpandedModule] = useState('B');

  const sS = {
    sidebar: {
      width: collapsed ? 52 : 216,
      background: '#0f3d24',
      display: 'flex', flexDirection: 'column', height: '100%', flexShrink: 0,
      transition: 'width 0.18s ease', overflow: 'hidden', position: 'relative',
      borderRight: '1px solid rgba(0,0,0,0.15)',
      fontFamily: "'Plus Jakarta Sans', sans-serif",
    },
    logoRow: {
      display: 'flex', alignItems: 'center',
      justifyContent: collapsed ? 'center' : 'space-between',
      padding: collapsed ? '14px 0' : '14px 12px 12px',
      borderBottom: '1px solid rgba(255,255,255,0.08)', flexShrink: 0, minHeight: 52,
    },
    logoImg: { height: 26, display: 'block', flexShrink: 0 },
    collapseBtn: {
      border: 'none', background: 'transparent', cursor: 'pointer',
      color: 'rgba(255,255,255,0.4)', display: 'flex', alignItems: 'center',
      padding: 4, borderRadius: 4, flexShrink: 0,
    },
    nav: { flex: 1, padding: '6px 6px', overflowY: 'auto', overflowX: 'hidden' },
    moduleGroup: { marginBottom: 2 },
    moduleHeader: {
      display: 'flex', alignItems: 'center', gap: 8,
      padding: collapsed ? '8px 0' : '7px 8px',
      justifyContent: collapsed ? 'center' : 'space-between',
      cursor: 'pointer', borderRadius: 4, color: 'rgba(255,255,255,0.45)',
      fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
      textTransform: 'uppercase', userSelect: 'none', transition: 'color 0.12s',
    },
    moduleHeaderLabel: { flex: 1, overflow: 'hidden' },
    navItem: {
      display: 'flex', alignItems: 'center', gap: 9,
      padding: collapsed ? '8px 0' : '7px 8px 7px 24px',
      justifyContent: collapsed ? 'center' : 'flex-start',
      borderRadius: 4, border: 'none', background: 'transparent',
      color: 'rgba(255,255,255,0.72)', fontSize: 12.5, fontFamily: 'inherit',
      fontWeight: 500, cursor: 'pointer', width: '100%', textAlign: 'left',
      transition: 'background 0.1s, color 0.1s', whiteSpace: 'nowrap',
    },
    navItemActive: { background: 'rgba(255,255,255,0.12)', color: '#ffffff' },
    navItemActiveIndicator: {
      position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
      width: 3, height: 16, background: '#6dbf97', borderRadius: '0 2px 2px 0',
    },
    sectionDivider: { borderTop: '1px solid rgba(255,255,255,0.07)', margin: '6px 6px' },
    bottom: { padding: '6px 6px 12px', flexShrink: 0 },
    bottomItem: {
      display: 'flex', alignItems: 'center', gap: 9,
      padding: collapsed ? '8px 0' : '7px 8px',
      justifyContent: collapsed ? 'center' : 'flex-start',
      borderRadius: 4, border: 'none', background: 'transparent',
      color: 'rgba(255,255,255,0.5)', fontSize: 12, fontFamily: 'inherit',
      fontWeight: 500, cursor: 'pointer', width: '100%', textAlign: 'left',
      transition: 'background 0.1s', whiteSpace: 'nowrap',
    },
  };

  return (
    <aside style={sS.sidebar}>
      <div style={sS.logoRow}>
        {!collapsed && <img src="/assets/epec-logo-white.png" style={sS.logoImg} alt="EPEC" />}
        {collapsed && (
          <div style={{ width: 26, height: 26, overflow: 'hidden', borderRadius: 2, flexShrink: 0 }}>
            <img
              src="/assets/epec-logo-white.png"
              style={{ height: 26, width: 'auto', display: 'block', maxWidth: 'none' }}
              alt="EPEC"
            />
          </div>
        )}
        {!collapsed && (
          <button style={sS.collapseBtn} onClick={onToggle} title="Contraer">
            <Icon name="chevron-left" size={14} />
          </button>
        )}
      </div>

      <nav style={sS.nav}>
        {NAV_STRUCTURE.map((group) => {
          if (!allowedModules.includes(group.module)) return null;
          const isExpanded = expandedModule === group.module;
          return (
            <div key={group.module} style={sS.moduleGroup}>
              <div
                style={sS.moduleHeader}
                onClick={() => !collapsed && setExpandedModule(isExpanded ? null : group.module)}
              >
                {collapsed ? (
                  <Icon name={group.icon} size={15} color="rgba(255,255,255,0.5)" />
                ) : (
                  <>
                    <Icon name={group.icon} size={13} color="rgba(255,255,255,0.4)" />
                    <span style={sS.moduleHeaderLabel}>{group.label.toUpperCase()}</span>
                    <Icon name={isExpanded ? 'chevron-down' : 'chevron-right'} size={12} color="rgba(255,255,255,0.3)" />
                  </>
                )}
              </div>
              {(isExpanded || collapsed) &&
                group.items
                  .filter((i) => !i.hidden)
                  .map((item) => {
                    const active = activeScreen === item.id;
                    return (
                      <div key={item.id} style={{ position: 'relative' }}>
                        {active && !collapsed && <div style={sS.navItemActiveIndicator} />}
                        <button
                          style={{ ...sS.navItem, ...(active ? sS.navItemActive : {}) }}
                          onClick={() => onNav(item.id)}
                          title={collapsed ? item.label : undefined}
                        >
                          <Icon
                            name={item.icon}
                            size={14}
                            color={active ? '#a8d9c0' : 'rgba(255,255,255,0.55)'}
                          />
                          {!collapsed && <span>{item.label}</span>}
                        </button>
                      </div>
                    );
                  })}
            </div>
          );
        })}

        {allowedModules.includes('ADMIN') && (
          <>
            <div style={sS.sectionDivider} />
            <div style={sS.moduleHeader}>
              {collapsed ? (
                <Icon name="settings" size={15} color="rgba(255,255,255,0.4)" />
              ) : (
                <>
                  <Icon name="settings" size={13} color="rgba(255,255,255,0.35)" />
                  <span style={sS.moduleHeaderLabel}>Admin</span>
                </>
              )}
            </div>
            {ADMIN_ITEMS.map((item) => {
              const active = activeScreen === item.id;
              return (
                <button
                  key={item.id}
                  style={{ ...sS.navItem, ...(active ? sS.navItemActive : {}) }}
                  onClick={() => onNav(item.id)}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon name={item.icon} size={14} color={active ? '#a8d9c0' : 'rgba(255,255,255,0.55)'} />
                  {!collapsed && <span>{item.label}</span>}
                </button>
              );
            })}
          </>
        )}
      </nav>

      <div style={sS.sectionDivider} />
      <div style={sS.bottom}>
        {collapsed && (
          <button
            style={{ ...sS.bottomItem, justifyContent: 'center' }}
            onClick={onToggle}
            title="Expandir"
          >
            <Icon name="chevron-right" size={15} color="rgba(255,255,255,0.4)" />
          </button>
        )}
        <button style={sS.bottomItem} title={collapsed ? 'Salir' : undefined}>
          <Icon name="log-out" size={14} color="rgba(255,255,255,0.4)" />
          {!collapsed && <span>Salir</span>}
        </button>
      </div>
    </aside>
  );
}
