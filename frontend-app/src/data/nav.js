// Estructura de navegación, roles y mapeo módulo→pantalla.
// Centralizado acá para que Sidebar, TopBar y App lo compartan.

export const NAV_STRUCTURE = [
  {
    module: 'A', label: 'Ingesta', icon: 'upload',
    items: [
      { id: 'lotes',  label: 'Lista de Lotes', icon: 'package' },
      { id: 'subida', label: 'Subir Archivos', icon: 'file-up' },
    ],
  },
  {
    module: 'B', label: 'Auditoría', icon: 'clipboard',
    items: [
      { id: 'bandeja', label: 'Bandeja',          icon: 'inbox' },
      { id: 'detalle', label: 'Detalle de Parte', icon: 'edit', hidden: true },
    ],
  },
  {
    module: 'C', label: 'Dashboards', icon: 'bar-chart',
    items: [
      { id: 'calidad',   label: 'Calidad de Datos', icon: 'award' },
      { id: 'operarios', label: 'Operarios',         icon: 'users' },
      { id: 'mapa',      label: 'Mapa de Sumi.',     icon: 'map-pin' },
      { id: 'evolución', label: 'Evolución Obs.',    icon: 'trending-up' },
    ],
  },
  {
    module: 'D', label: 'Exports', icon: 'download',
    items: [
      { id: 'exports', label: 'Centro de Exports', icon: 'download' },
    ],
  },
];

export const ADMIN_ITEMS = [
  { id: 'mapeo',    label: 'Mapeo de Códigos', icon: 'hash' },
  { id: 'usuarios', label: 'Usuarios y Roles', icon: 'users' },
];

export const ROLE_LABELS = {
  operador:   'Operador de Carga',
  auditor:    'Auditor',
  supervisor: 'Supervisor',
  admin:      'Administrador',
};

export const ROLE_ACCESS = {
  operador:   ['A'],
  auditor:    ['A', 'B'],
  supervisor: ['A', 'B', 'C', 'D'],
  admin:      ['A', 'B', 'C', 'D', 'ADMIN'],
};

// Pantalla por módulo — usado al cambiar de rol para redirigir si la actual no es accesible.
export const SCREEN_TO_MODULE = {
  lotes: 'A', subida: 'A',
  bandeja: 'B', detalle: 'B',
  calidad: 'C', operarios: 'C', mapa: 'C', 'evolución': 'C',
  exports: 'D',
  mapeo: 'ADMIN', usuarios: 'ADMIN',
};

export const MODULE_DEFAULT_SCREEN = {
  A: 'lotes',
  B: 'bandeja',
  C: 'calidad',
  D: 'exports',
  ADMIN: 'mapeo',
};

export const SCREEN_META = {
  lotes:      { title: 'Lista de Lotes',         subtitle: 'Módulo A — Ingesta de Partes' },
  subida:     { title: 'Subir Archivos',         subtitle: 'Módulo A — Ingesta' },
  bandeja:    { title: 'Bandeja de Auditoría',   subtitle: 'Módulo B — Resolución de Conflictos' },
  detalle:    { title: 'Detalle de Parte',       subtitle: 'Módulo B — Auditoría' },
  calidad:    { title: 'Calidad de Datos',       subtitle: 'Módulo C — Dashboard BI' },
  operarios:  { title: 'Análisis de Operarios',  subtitle: 'Módulo C — Dashboard BI' },
  mapa:       { title: 'Mapa de Suministros',    subtitle: 'Módulo C — Dashboard BI' },
  'evolución':{ title: 'Evolución de Observaciones', subtitle: 'Módulo C — Dashboard BI' },
  exports:    { title: 'Centro de Exports',      subtitle: 'Módulo D' },
  mapeo:      { title: 'Mapeo de Códigos',       subtitle: 'Admin' },
  usuarios:   { title: 'Usuarios y Roles',       subtitle: 'Admin' },
};
