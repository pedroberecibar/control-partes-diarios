import { apiFetch } from './client';

export function getPartes(params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null && v !== '')
  );
  return apiFetch(`/api/v1/partes/?${qs}`);
}

export const getParte = (id) => apiFetch(`/api/v1/partes/${id}`);

export const getVisor = (id) => apiFetch(`/api/v1/partes/${id}/visor`);

export function editarParte(id, payload) {
  return apiFetch(`/api/v1/partes/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}
