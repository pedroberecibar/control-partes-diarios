import { BASE_URL, apiFetch } from './client';

export const getLotes = (skip = 0, limit = 200) =>
  apiFetch(`/api/v1/lotes?skip=${skip}&limit=${limit}`);

export const getLote = (id) => apiFetch(`/api/v1/lotes/${id}`);

export const getLoteDashboard = (id) => apiFetch(`/api/v1/lotes/${id}/dashboard`);

export const reprocesarLote = (id) =>
  apiFetch(`/api/v1/lotes/${id}/reprocesar`, { method: 'POST' });

/**
 * Llama al endpoint preview-columnas para detectar columnas del archivo.
 * Sin efecto en DB — solo lectura del encabezado del Excel/CSV.
 */
export function previewColumnas(archivo, contratistaId) {
  const fd = new FormData();
  fd.append('archivo', archivo);
  const url = `${BASE_URL}/api/v1/lotes/preview-columnas?contratista_id=${contratistaId}`;
  return fetch(url, { method: 'POST', body: fd }).then(async (r) => {
    if (r.ok) return r.json();
    const body = await r.json().catch(() => ({}));
    throw new Error(body?.detail || `HTTP ${r.status}`);
  });
}

/**
 * Sube un archivo y crea un lote.
 *
 * Errores 409 conocidos (la API devuelve `detail` como objeto):
 *   - DUP_BYTES      → archivo idéntico ya subido (bytes coinciden)
 *   - DUP_CONTENT    → contenido idéntico (bytes distintos, mismo Excel re-guardado)
 *   - OVERLAP_WARN   → la mayoría de los partes ya existen; reintentar con force=true
 *
 * Esos errores se rethrowean con `err.code` y `err.payload` poblados para que
 * el caller pueda decidir cómo reaccionar (mostrar modal, error duro, etc.).
 *
 * @param {File}   archivo
 * @param {number} contratistaId
 * @param {number} subidoPor
 * @param {{ force?: boolean, mapeo?: Record<string,string>|null }} opts
 *   mapeo: {col_excel: campo_canonico} — null = usar MAPA_RENOMBRES del adapter.
 */
export function crearLote(archivo, contratistaId, subidoPor, { force = false, mapeo = null } = {}) {
  const fd = new FormData();
  fd.append('archivo', archivo);
  if (mapeo) fd.append('mapeo_columnas', JSON.stringify(mapeo));
  const params = new URLSearchParams({
    contratista_id: String(contratistaId),
    subido_por: String(subidoPor),
  });
  if (force) params.set('force', 'true');
  const url = `${BASE_URL}/api/v1/lotes?${params.toString()}`;
  return fetch(url, { method: 'POST', body: fd }).then(async (r) => {
    if (r.ok) return r.json();
    const body = await r.json().catch(() => ({}));
    const detail = body?.detail;
    if (detail && typeof detail === 'object' && detail.code) {
      const err = new Error(detail.mensaje || `HTTP ${r.status}`);
      err.code = detail.code;
      err.payload = detail;
      err.status = r.status;
      throw err;
    }
    throw new Error((typeof detail === 'string' ? detail : null) || `HTTP ${r.status}`);
  });
}
