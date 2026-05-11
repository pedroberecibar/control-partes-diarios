import { Icon } from './Icon';

/**
 * Barra de progreso por pasos discretos. Consume `paso_actual` + `progreso_pct`
 * que el worker emite vía `LoteService.actualizar_progreso`. Refrescada por
 * el polling de 2s ya existente en `ListaLotes.jsx`.
 *
 * Estética alineada con tokens del sistema (warning durante PROCESANDO,
 * success en APROBADO, error en RECHAZADO). Animación shimmer para reforzar
 * la sensación de actividad entre transiciones.
 */
const PASO_LABEL = {
  RECIBIENDO:           'Recibiendo archivo',
  VALIDANDO_ESTRUCTURA: 'Validando estructura',
  EJECUTANDO_MOTOR:     'Ejecutando motor analítico',
  IMPORTANDO_PARTES:    'Importando partes',
  FINALIZANDO:          'Finalizando',
  APROBADO:             'Procesado',
  RECHAZADO:            'Rechazado',
};

export function ProgressBar({ pct = 0, paso = null, estado = 'PROCESANDO', size = 'sm' }) {
  const safePct = Math.max(0, Math.min(100, Number.isFinite(pct) ? pct : 0));
  const label = paso ? (PASO_LABEL[paso] || paso) : (estado === 'APROBADO' ? 'Procesado' : 'Procesando');

  // Paleta por estado — replica LOTE_ESTADO_CONFIG (Icon.jsx).
  let fillColor, fillBg, labelColor, iconName;
  if (estado === 'APROBADO') {
    fillColor  = '#155a2e';
    fillBg     = '#155a2e';
    labelColor = '#155a2e';
    iconName   = 'check-circle';
  } else if (estado === 'RECHAZADO') {
    fillColor  = '#c0392b';
    fillBg     = '#c0392b';
    labelColor = '#7a1c1c';
    iconName   = 'alert-circle';
  } else {
    // PROCESANDO / RECIBIDO — gradiente animado warning.
    fillColor  = '#7a4a00';
    fillBg     = 'linear-gradient(90deg, #f5d56a 0%, #e6910a 100%)';
    labelColor = '#7a4a00';
    iconName   = null;
  }

  const trackHeight = size === 'md' ? 10 : 8;
  const indeterminado = estado !== 'APROBADO' && estado !== 'RECHAZADO';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 160 }}>
      <div style={{
        height: trackHeight,
        background: '#eaeeec',
        borderRadius: 999,
        overflow: 'hidden',
        position: 'relative',
      }}>
        <div style={{
          height: '100%',
          width: `${safePct}%`,
          background: fillBg,
          borderRadius: 999,
          transition: 'width 600ms ease',
          position: 'relative',
          overflow: 'hidden',
        }}>
          {indeterminado && safePct > 0 && (
            <span
              aria-hidden="true"
              style={{
                position: 'absolute',
                inset: 0,
                background: 'linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.55) 50%, rgba(255,255,255,0) 100%)',
                backgroundSize: '600px 100%',
                animation: 'shimmer 1.4s infinite',
              }}
            />
          )}
        </div>
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        fontSize: 11,
        color: labelColor,
        fontWeight: 500,
      }}>
        {iconName && <Icon name={iconName} size={12} color={fillColor} />}
        <span>{label}</span>
        <span style={{ color: '#8f9c97' }}> · {safePct}%</span>
      </div>
    </div>
  );
}
