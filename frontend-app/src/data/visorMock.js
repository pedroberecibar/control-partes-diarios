// Mock para el visor de imágenes.
// `getPartePhotos` y `getMockObs` derivan resultados deterministas a partir del
// `parteId` para que la misma fila siempre tenga la misma cantidad de fotos
// y observaciones en los re-renders.

const ALL_PHOTOS = [
  '/assets/ejemplo-imagen1.jpg',
  '/assets/ejemplo-imagen2.jpg',
  '/assets/ejemplo-imagen3.jpg',
  '/assets/ejemplo-imagen4.jpg',
  '/assets/ejemplo-imagen5.jpg',
];

export function getPartePhotos(parteId) {
  if (!parteId) return [];
  const seed = String(parteId).split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const count = [2, 3, 4, 1, 5, 3, 0, 2, 4, 5][seed % 10];
  return Array.from({ length: count }, (_, i) => ALL_PHOTOS[(seed + i) % ALL_PHOTOS.length]);
}

export const OBSERVACIONES_LABELS = [
  { key: 'gabinete',     label: 'Gabinete',                 icon: 'package' },
  { key: 'subterraneo',  label: 'Subterráneo',              icon: 'layers' },
  { key: 'altura',       label: 'Altura',                    icon: 'trending-up' },
  { key: 'aereo',        label: 'Aéreo',                     icon: 'zap' },
  { key: 'eq_reempl',    label: 'Equipo Reemplazado',        icon: 'refresh-cw' },
  { key: 'acom_real',    label: 'Acometida Realizada',       icon: 'check-circle' },
  { key: 'tapa_reempl',  label: 'Tapa Reemplazada',          icon: 'square' },
  { key: 'med_reg',      label: 'Mediciones Registradas',    icon: 'activity' },
];

export function getMockObs(parteId) {
  const seed = String(parteId).split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  const out = {};
  OBSERVACIONES_LABELS.forEach((o, i) => { out[o.key] = ((seed >> i) & 1) === 1; });
  return out;
}
