import { useState } from 'react';
import { Sidebar } from './components/layout/Sidebar';
import { Toast } from './components/Toast';
import { TopBar } from './components/layout/TopBar';
import { MODULE_DEFAULT_SCREEN, ROLE_ACCESS, ROLE_LABELS, SCREEN_META, SCREEN_TO_MODULE } from './data/nav';
import { BandejaAuditoria } from './pages/BandejaAuditoria';
import { CentroExports } from './pages/CentroExports';
import { DashboardCalidad } from './pages/DashboardCalidad';
import { DashboardEvolucion } from './pages/DashboardEvolucion';
import { DashboardMapa } from './pages/DashboardMapa';
import { DashboardOperarios } from './pages/DashboardOperarios';
import { DetallePartes } from './pages/DetallePartes';
import { ListaLotes } from './pages/ListaLotes';
import { MapeoCodigosAdmin } from './pages/MapeoCodigosAdmin';
import { SubidaArchivos } from './pages/SubidaArchivos';
import { UsuariosRolesAdmin } from './pages/UsuariosRolesAdmin';

export default function App() {
  const [screen, setScreen]           = useState('bandeja');
  const [role, setRole]               = useState('auditor');
  const [collapsed, setCollapsed]     = useState(false);
  const [activeParte, setActiveParte] = useState(null);
  const [activeLoteId, setActiveLoteId] = useState(null);
  const [toasts, setToasts]           = useState([]);

  const meta = SCREEN_META[screen] || { title: screen, subtitle: '' };

  function addToast(msg, type = 'info') {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, msg, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3500);
  }
  function removeToast(id) { setToasts((t) => t.filter((x) => x.id !== id)); }

  function handleNav(s) {
    setScreen(s);
    if (s !== 'detalle') setActiveParte(null);
    if (s === 'bandeja') setActiveLoteId(null);
  }

  function handleVerEnBandeja(loteId) {
    setActiveLoteId(loteId);
    setScreen('bandeja');
  }

  function handleOpenDetalle(parte) {
    setActiveParte(parte);
    setScreen('detalle');
  }

  function handleRoleChange(newRole) {
    setRole(newRole);
    // Si la pantalla actual no es accesible para el nuevo rol, redirigir.
    const allowed = ROLE_ACCESS[newRole] || [];
    const curModule = SCREEN_TO_MODULE[screen];
    if (curModule && !allowed.includes(curModule)) {
      const firstModule = allowed[0];
      setScreen(MODULE_DEFAULT_SCREEN[firstModule] || 'lotes');
    }
    addToast(`Rol cambiado a ${ROLE_LABELS[newRole]}`, 'info');
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar
        activeScreen={screen}
        onNav={handleNav}
        role={role}
        collapsed={collapsed}
        onToggle={() => setCollapsed((v) => !v)}
      />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: '#f5f7f6' }}>
        <TopBar
          title={meta.title}
          subtitle={meta.subtitle}
          role={role}
          onRoleChange={handleRoleChange}
        />
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {screen === 'bandeja'    && <BandejaAuditoria onOpenDetalle={handleOpenDetalle} initialLoteId={activeLoteId} />}
          {screen === 'detalle'    && <DetallePartes parte={activeParte} onBack={() => setScreen('bandeja')} />}
          {screen === 'lotes'      && <ListaLotes onSubir={() => setScreen('subida')} onVerEnBandeja={handleVerEnBandeja} />}
          {screen === 'subida'     && <SubidaArchivos onBack={() => setScreen('lotes')} />}
          {screen === 'calidad'    && <DashboardCalidad />}
          {screen === 'operarios'  && <DashboardOperarios />}
          {screen === 'mapa'       && <DashboardMapa />}
          {screen === 'evolución'  && <DashboardEvolucion />}
          {screen === 'exports'    && <CentroExports />}
          {screen === 'mapeo'      && <MapeoCodigosAdmin />}
          {screen === 'usuarios'   && <UsuariosRolesAdmin />}
        </div>
      </div>
      <Toast toasts={toasts} onRemove={removeToast} />
    </div>
  );
}
