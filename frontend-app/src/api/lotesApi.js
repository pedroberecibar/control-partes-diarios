import { BASE_URL, apiFetch } from './client';

export const getLotes = (skip = 0, limit = 200) =>
  apiFetch(`/api/v1/lotes?skip=${skip}&limit=${limit}`);

export const getLote = (id) => apiFetch(`/api/v1/lotes/${id}`);

export const reprocesarLote = (id) =>
  apiFetch(`/api/v1/lotes/${id}/reprocesar`, { method: 'POST' });

export function crearLote(archivo, contratistaId, subidoPor) {
  const fd = new FormData();
  fd.append('archivo', archivo);
  const url = `${BASE_URL}/api/v1/lotes?contratista_id=${contratistaId}&subido_por=${subidoPor}`;
  return fetch(url, { method: 'POST', body: fd }).then((r) =>
    r.ok
      ? r.json()
      : r.json().then((e) => Promise.reject(new Error(e?.detail || `HTTP ${r.status}`)))
  );
}
