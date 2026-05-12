import { LOTES_DATA } from '../data/lotesMock';
import { PARTES_DATA } from '../data/partesMock';

function delay(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

function makeDashStub(lote) {
  const { total_filas: tot, n_aprobados: apr, n_revision: rev, n_rechazado: rech, n_fuera_alcance: fa } = lote;

  const distTrazas = [];
  if (apr > 0) {
    const t1 = Math.round(apr * 0.72);
    distTrazas.push({ id_traza: 1,  desc_traza: 'Original OK',              desc_estado: 'Aprobado',         count: t1,        pct: Math.round(t1 / tot * 100) });
    distTrazas.push({ id_traza: 3,  desc_traza: 'Corregido Nro Medidor',    desc_estado: 'Aprobado',         count: apr - t1,  pct: Math.round((apr - t1) / tot * 100) });
  }
  if (rev > 0) {
    distTrazas.push({ id_traza: 19, desc_traza: 'Rescatado por Oracle',      desc_estado: 'En Revisión',      count: rev,       pct: Math.round(rev / tot * 100) });
  }
  if (rech > 0) {
    const t7 = Math.round(rech * 0.6);
    distTrazas.push({ id_traza: 7,  desc_traza: 'Sin Orden Asociada',        desc_estado: 'Rechazado',        count: t7,        pct: Math.round(t7 / tot * 100) });
    distTrazas.push({ id_traza: 13, desc_traza: 'Informado - No Ejecutado',  desc_estado: 'Rechazado',        count: rech - t7, pct: Math.round((rech - t7) / tot * 100) });
  }
  if (fa > 0) {
    distTrazas.push({ id_traza: 6,  desc_traza: 'No Corresponde TOR CE',     desc_estado: 'Fuera de Alcance', count: fa,        pct: Math.round(fa / tot * 100) });
  }

  const efectividad = tot > 0
    ? Math.round((apr / Math.max(tot - fa, 1)) * 100)
    : 0;

  return {
    total_registros:           tot,
    n_aprobados:               apr,
    n_revision:                rev,
    n_rechazado:               rech,
    efectividad_pct:           efectividad,
    total_uses_aprobados:      parseFloat((apr * 1.42).toFixed(2)),
    total_controlados:         apr,
    delta_uses_sobrevaloracion: 3.1200,
    delta_uses_subvaloracion:   0.8800,
    distribucion_trazas:       distTrazas,
    distribucion_epec: [
      { cod_epec: 1001, desc_epec: 'Cambio de Medidor',         count: Math.round(apr * 0.45), pct_partes: 45, total_uses: parseFloat((apr * 0.45 * 1.50).toFixed(2)) },
      { cod_epec: 1003, desc_epec: 'Inspección de Instalación', count: Math.round(apr * 0.30), pct_partes: 30, total_uses: parseFloat((apr * 0.30 * 1.20).toFixed(2)) },
      { cod_epec: 2001, desc_epec: 'Corte de Suministro',       count: Math.round(apr * 0.25), pct_partes: 25, total_uses: parseFloat((apr * 0.25 * 0.80).toFixed(2)) },
    ],
    distribucion_discrepancias: [
      { tipo: 'Sin Discrepancia', count: Math.round(apr * 0.85), pct: 85 },
      { tipo: 'Sobrevaloración',  count: Math.round(apr * 0.10), pct: 10 },
      { tipo: 'Subvaloración',    count: Math.round(apr * 0.05), pct:  5 },
    ],
    por_operario: [
      { operario: 'García, Juan',    n_total: Math.round(tot * 0.60), n_aprobados: Math.round(apr * 0.62), tasa_aprobacion: 88, total_uses: parseFloat((apr * 0.62 * 1.40).toFixed(2)) },
      { operario: 'Torres, Ricardo', n_total: Math.round(tot * 0.40), n_aprobados: Math.round(apr * 0.38), tasa_aprobacion: 84, total_uses: parseFloat((apr * 0.38 * 1.40).toFixed(2)) },
    ],
  };
}

export async function routeMockRequest(path, _options = {}) {
  await delay(600);

  const [base, queryStr] = path.split('?');
  const clean = base.replace(/\/$/, '');

  if (clean === '/api/v1/lotes') {
    return { items: LOTES_DATA, total: LOTES_DATA.length };
  }

  const loteIdMatch = clean.match(/^\/api\/v1\/lotes\/(\d+)$/);
  if (loteIdMatch) {
    const id = Number(loteIdMatch[1]);
    return LOTES_DATA.find((l) => l.id === id) ?? LOTES_DATA[0];
  }

  const dashMatch = clean.match(/^\/api\/v1\/lotes\/(\d+)\/dashboard$/);
  if (dashMatch) {
    const id = Number(dashMatch[1]);
    const lote = LOTES_DATA.find((l) => l.id === id) ?? LOTES_DATA[0];
    return makeDashStub(lote);
  }

  if (clean === '/api/v1/partes' || clean === '/api/v1/partes/') {
    const qs    = new URLSearchParams(queryStr || '');
    const skip  = Number(qs.get('skip')  || 0);
    const limit = Number(qs.get('limit') || 25);
    return { items: PARTES_DATA.slice(skip, skip + limit), total: PARTES_DATA.length };
  }

  if (clean === '/api/v1/partes/cod-epec/valores') {
    return [...new Set(PARTES_DATA.map((p) => p.cod_epec))].sort((a, b) => a - b);
  }

  const parteIdMatch = clean.match(/^\/api\/v1\/partes\/(\d+)$/);
  if (parteIdMatch) {
    const id = Number(parteIdMatch[1]);
    return PARTES_DATA.find((p) => p.id === id) ?? PARTES_DATA[0];
  }

  if (clean === '/api/v1/admin/reglas') {
    return [];
  }

  if (clean === '/api/v1/admin/contratistas') {
    return [];
  }

  if (clean === '/api/v1/admin/sync-ordenativos-oracle/status') {
    return { running: false, ultimo_sync_at: null, ordenativos_count: 0, fotos_count: 0, equipos_count: 0, last_result: null };
  }

  return {};
}
