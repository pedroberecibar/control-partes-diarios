import { apiFetch } from './client';

export function getPartes(params = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === '' || (Array.isArray(v) && v.length === 0)) continue;
    if (Array.isArray(v)) {
      v.forEach((item) => qs.append(k, item));
    } else {
      qs.append(k, v);
    }
  }
  console.log('[partesApi] getPartes → params:', params, '| qs:', qs.toString());
  return apiFetch(`/api/v1/partes/?${qs}`);
}

export const getCodEpecValores = () => apiFetch('/api/v1/partes/cod-epec/valores');

export const getParte = (id) => apiFetch(`/api/v1/partes/${id}`);

export const getVisor = (id) => apiFetch(`/api/v1/partes/${id}/visor`);

export const getCandidatosOracle = (id) => apiFetch(`/api/v1/partes/${id}/candidatos-oracle`);

export const getCodigosEpecCandidatos = (id) =>
  apiFetch(`/api/v1/partes/${id}/codigos-epec-candidatos`);

export const getOpcionesCodEpec = () => apiFetch('/api/v1/admin/reglas/cod-epec-opciones');

export function editarParte(id, payload) {
  return apiFetch(`/api/v1/partes/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}
