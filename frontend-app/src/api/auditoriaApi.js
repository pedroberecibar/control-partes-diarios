import { apiFetch } from './client';

export function getAuditoria(params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v != null && v !== '')
  );
  return apiFetch(`/api/v1/auditoria?${qs}`);
}
