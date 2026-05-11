function fmtMedidor(val) {
  if (!val) return '—';
  return String(val).replace(/\.0$/, '');
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return [
      String(d.getDate()).padStart(2, '0'),
      String(d.getMonth() + 1).padStart(2, '0'),
      d.getFullYear(),
    ].join('/');
  } catch {
    return '—';
  }
}

function fmtDateTime(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    const date = [
      String(d.getDate()).padStart(2, '0'),
      String(d.getMonth() + 1).padStart(2, '0'),
      d.getFullYear(),
    ].join('/');
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${date} ${hh}:${mm}`;
  } catch {
    return '—';
  }
}

// LoteResponse → frontend lote shape
export function normalizeLote(l) {
  return {
    id: `LOT-${String(l.id).padStart(7, '0')}`,
    _id: l.id,
    archivo: l.nombre_archivo,
    contratista: l.contratista_nombre || `ID:${l.contratista_id}`,
    subido_por: l.usuario_nombre || `Usuario #${l.subido_por}`,
    fecha: fmtDateTime(l.fecha_subida),
    estado: l.estado,
    filas: l.total_filas ?? 0,
    n_aprobados: l.n_aprobados ?? 0,
    n_revision: l.n_revision ?? 0,
    n_rechazado: l.n_rechazado ?? 0,
    n_fuera_alcance: l.n_fuera_alcance ?? 0,
    detalle_error: l.detalle_error || null,
    paso_actual: l.paso_actual || null,
    progreso_pct: l.progreso_pct ?? 0,
  };
}

// ParteResumenResponse → frontend parte shape
export function normalizeParte(p) {
  return {
    id: p.id,
    id_externo: p.id_externo || null,
    contratista: p.contratista || '—',
    operario: p.operario_nombre || '—',
    fecha: fmtDate(p.fecha_ejecucion),
    suministro: p.suministro || '—',
    cod_epec: p.cod_epec != null ? String(p.cod_epec) : '—',
    ord_nro: p.ord_nro != null ? String(p.ord_nro) : '—',
    traza: p.traza_calidad || '—',
    id_traza: p.id_traza,
    estado: p.estado || '—',
    id_estado: p.id_estado,
    uses: p.valor_uses != null ? String(p.valor_uses) : '—',
    medidor_dec: '—',
    version: 1,
    cant_imagenes: p.cant_imagenes ?? 0,
    fue_corregido: p.fue_corregido,
    anulado: p.anulado,
    lote: '',
    // Control de Observaciones — null cuando no viene del backend (mock o resumen sin detalle)
    observaciones_app: p.observaciones_app ?? null,
  };
}

// ParteDetalleResponse → enriched frontend parte shape
export function normalizeParteDetalle(p) {
  return {
    ...normalizeParte(p),
    lote_id: p.lote_id,
    lote: p.lote_id ? `lote-${p.lote_id}` : '',
    raw_id: p.raw_id,
    nro_medidor_retirado: fmtMedidor(p.nro_medidor_retirado),
    nro_medidor_colocado: fmtMedidor(p.nro_medidor_colocado),
    medidor_dec: fmtMedidor(p.nro_medidor_retirado),
    operario: p.operario_nombre || '—',
    operario_excel: p.operario_excel || null,
    version: p.version,
    cod_epec_sugerido: p.cod_epec_sugerido,
    valor_uses_origen: p.valor_uses_origen,
    valor_uses_obs: p.valor_uses_obs,
    diferencia_uses: p.diferencia_uses,
    tipo_discrepancia: p.tipo_discrepancia,
    observaciones_app: p.observaciones_app,
    imagenes: p.imagenes ?? [],
    fue_corregido: p.fue_corregido,
    anulado: p.anulado,
    created_at: p.created_at,
    updated_at: p.updated_at,
  };
}
