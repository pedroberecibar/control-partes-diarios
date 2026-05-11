import { apiFetch } from './client';

const BASE = '/api/v1/admin';

// ── Reglas ──────────────────────────────────────────────────────────────────

export const getReglas = (soloActivas = false) =>
  apiFetch(`${BASE}/reglas${soloActivas ? '?solo_activas=true' : ''}`);

export const getRegla = (id) => apiFetch(`${BASE}/reglas/${id}`);

export const crearRegla = (payload) =>
  apiFetch(`${BASE}/reglas`, { method: 'POST', body: JSON.stringify(payload) });

export const actualizarRegla = (id, payload) =>
  apiFetch(`${BASE}/reglas/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });

export const desactivarRegla = (id) =>
  apiFetch(`${BASE}/reglas/${id}`, { method: 'DELETE' });

// ── Mapeos ───────────────────────────────────────────────────────────────────

export const getMapeos = (soloActivos = false) =>
  apiFetch(`${BASE}/mapeo-codigos${soloActivos ? '?solo_activos=true' : ''}`);

export const crearMapeo = (payload) =>
  apiFetch(`${BASE}/mapeo-codigos`, { method: 'POST', body: JSON.stringify(payload) });

export const actualizarMapeo = (id, payload) =>
  apiFetch(`${BASE}/mapeo-codigos/${id}`, { method: 'PATCH', body: JSON.stringify(payload) });

export const desactivarMapeo = (id) =>
  apiFetch(`${BASE}/mapeo-codigos/${id}`, { method: 'DELETE' });

// ── Contratistas (lookup) ────────────────────────────────────────────────────

export const getContratistas = () => apiFetch(`${BASE}/contratistas`);

// ── Seed ─────────────────────────────────────────────────────────────────────

export const ejecutarSeed = () =>
  apiFetch(`${BASE}/seed`, { method: 'POST' });

// ── Sync Oracle (admin) ─────────────────────────────────────────────────────

export const dispararSyncOracle = (desdeFecha) => {
  const qs = desdeFecha ? `?desde_fecha=${encodeURIComponent(desdeFecha)}` : '';
  return apiFetch(`${BASE}/sync-ordenativos-oracle${qs}`, { method: 'POST' });
};

export const getSyncOracleStatus = () =>
  apiFetch(`${BASE}/sync-ordenativos-oracle/status`);
