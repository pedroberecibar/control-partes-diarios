// Mock de 120 partes para la Bandeja de Auditoría.
// Reemplazar por llamadas a /api/v1/partes cuando se conecte al backend.

const CONTRATISTAS = ['CONECTAR', 'COOPLYF'];
const OPERARIOS = ['García, J.','López, M.','Fernández, A.','Rodríguez, C.','Martínez, P.','Torres, R.','Romero, S.','Sosa, D.','Gómez, L.','Peralta, E.'];
const COD_EPEC_LIST = ['1001','1002','1003','1004','1005','2001','2002','3001','3002','4001'];

function seededRand(seed) { const x = Math.sin(seed + 1) * 10000; return x - Math.floor(x); }

export const TRAZAS = [
  'Original OK',
  'Corregido Medidor',
  'Corregido Orden',
  'Sin Orden Asociada',
  'Repetido X Sumi',
  'Error Sumi Nro Med',
  'Otro Origen',
  'Informado-No Ejecutado',
];
export const ESTADOS = ['Pendiente','Aprobado','Rechazado','Anulado','En Revisión'];
export const LOTES = ['CONECTAR_2025-04-01','CONECTAR_2025-03-28','COOPLYF_2025-04-01','COOPLYF_2025-03-27'];

export const PARTES = Array.from({ length: 120 }, (_, i) => {
  const s = i + 1;

  const traza = (() => {
    const r = seededRand(s * 7);
    if (r < 0.42) return 'Original OK';
    if (r < 0.55) return 'Corregido Medidor';
    if (r < 0.63) return 'Corregido Orden';
    if (r < 0.72) return 'Sin Orden Asociada';
    if (r < 0.80) return 'Repetido X Sumi';
    if (r < 0.87) return 'Error Sumi Nro Med';
    if (r < 0.93) return 'Otro Origen';
    return 'Informado-No Ejecutado';
  })();

  const estado = (() => {
    if (traza === 'Original OK') return seededRand(s*3) > 0.15 ? 'Aprobado' : 'Pendiente';
    if (traza.startsWith('Corregido')) return seededRand(s*5) > 0.4 ? 'Aprobado' : 'Pendiente';
    return seededRand(s*11) > 0.6 ? 'Pendiente' : seededRand(s*13) > 0.5 ? 'En Revisión' : 'Rechazado';
  })();

  const cont = seededRand(s * 2) > 0.5 ? 'CONECTAR' : 'COOPLYF';
  const day = String(Math.floor(seededRand(s * 17) * 28) + 1).padStart(2,'0');
  const month = seededRand(s*19) > 0.5 ? '04' : '03';

  return {
    id: `PD-2025-${String(s).padStart(5,'0')}`,
    lote: cont === 'CONECTAR'
      ? (seededRand(s*23) > 0.5 ? 'CONECTAR_2025-04-01' : 'CONECTAR_2025-03-28')
      : (seededRand(s*23) > 0.5 ? 'COOPLYF_2025-04-01' : 'COOPLYF_2025-03-27'),
    contratista: cont,
    operario: OPERARIOS[Math.floor(seededRand(s * 41) * OPERARIOS.length)],
    fecha: `${day}/${month}/2025`,
    suministro: String(400000 + Math.floor(seededRand(s * 31) * 500000)).padStart(6,'0'),
    cod_epec: COD_EPEC_LIST[Math.floor(seededRand(s * 37) * COD_EPEC_LIST.length)],
    ord_nro: traza === 'Sin Orden Asociada' ? '—' : `CE-${String(100000 + Math.floor(seededRand(s * 43) * 900000))}`,
    traza,
    estado,
    medidor_dec: `M${String(10000000 + Math.floor(seededRand(s * 53) * 99999999)).slice(0,8)}`,
    uses: (0.5 + seededRand(s * 59) * 2).toFixed(2),
    version: Math.floor(seededRand(s * 61) * 3) + 1,
  };
});

export { CONTRATISTAS };
