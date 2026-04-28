"""Prueba de conectividad y acceso a las 6 tablas seed (SIGEC / GEOREF).

Para cada origen:
  - hace COUNT(*) (volumen total con los filtros del .md)
  - lee 5 filas (verifica columnas devueltas)

NO escribe nada en la BD: usa `OracleReadOnly`, que pone la sesión en
`READ ONLY` server-side y valida cada query client-side.

Ejecución:
    python scripts/test_oracle_seeds.py
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

# Permite correr el script desde cualquier cwd sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.oracle_io import OracleReadOnly  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("test_oracle_seeds")


# Las 6 consultas portadas literal de docs/masters_actualization.md.
# Estas son EXACTAMENTE las que va a ejecutar el extractor real cuando
# se construya etapa0_seeds.py (sin los wrappers de COUNT/SAMPLE de abajo).
QUERIES: dict[str, str] = {
    # dim_ord: bootstrap del baseline local. "Fecha de ejecución >= 2025-01-01"
    # según pedido (jefatura). Una vez bootstrapeado, etapa0_seeds podrá pasar a
    # un MERGE incremental por sysdate-N (como el .md de Fabric).
    "dim_ord": """
        SELECT *
        FROM xxsigec.ordenativos ord
        WHERE ord.ord_fecha_fin           >= TO_DATE('2025-01-01','YYYY-MM-DD')
           OR ord.ord_fecha_inicio        >= TO_DATE('2025-01-01','YYYY-MM-DD')
           OR ord.ord_ultima_actualizacion >= TO_DATE('2025-01-01','YYYY-MM-DD')
    """,
    # eqp_equipos_raw: probamos con un filtro chico solo para validar acceso.
    # En el extractor real (etapa0_seeds) se filtrará por
    # `SRV_CODIGO IN (suministros del staging + fact)` para no traer toda
    # XXSIGEC.EQUIPOS — el Core solo usa SRV_CODIGO, STE_NUMERO_ULTIMO y
    # STE_NUMERO_ANTERIOR_1 vía pivot top-10 por SRV.
    "eqp_equipos_raw_sample": """
        SELECT
            eqp.srv_codigo,
            eqp.ste_numero,
            eqp.eqp_orden,
            eqp.grm_numero,
            eqp.eqp_fecha_instal,
            eqp.eqp_precinto,
            eqp.eqp_fecha_retiro,
            eqp.eqp_estado,
            eqp.eqp_observaciones,
            TO_CHAR(eqp.EQP_FACTOR_INTENSIDAD) AS FACTOR_CORRIENTE_MEDIDOR,
            TO_CHAR(eqp.EQP_FACTOR_TENSION)    AS FACTOR_TENSION_MEDIDOR,
            eqp.eqp_programa,
            eqp.eqp_ultima_actualizacion
        FROM XXSIGEC.EQUIPOS eqp
        WHERE TRUNC(eqp.eqp_fecha_instal)         > TRUNC(SYSDATE - 10)
           OR TRUNC(eqp.eqp_ultima_actualizacion) > TRUNC(SYSDATE - 10)
    """,
    "dim_stk_stock_equipos": """
        SELECT
            stk.STE_NUMERO, stk.STE_FACTOR_EQUIPO, stk.SCF_CODIGO,
            stk.STE_AMPERAJE, stk.STE_MARCA, stk.STE_FECHA_BAJA,
            stk.STE_TIPO, stk.STE_TENSION, stk.STE_SERIE,
            stk.STE_PRECINTO, stk.STE_MODELO, stk.STE_ESTADO,
            stk.STE_ANIO_FABRICACION, stk.STE_DESCRIPCION,
            stk.STE_CLASE, stk.STE_FECHA_ALTA,
            TO_CHAR(stk.STE_AMPERAJE_MAXIMO)  AS AMPERAJE_MAXIMO_MEDIDOR,
            TO_CHAR(stk.STE_AMPERAJE_NOMINAL) AS AMPERAJE_NOMINAL_MEDIDOR,
            stk.STE_FASES, stk.STE_HORARIOS,
            stk.STE_MIDE_ACTIVA, stk.STE_MIDE_HORA, stk.STE_MIDE_POTENCIA,
            stk.STE_MIDE_REACTIVA, stk.STE_MIGRADO, stk.GRC_CODIGO
        FROM XXSIGEC.STOCK_EQUIPOS stk
    """,
    "usuarios_gral": """
        SELECT *
        FROM XXSIGEC.XXCO_USUARIOS_V
    """,
    "dim_suministros_geo": """
        SELECT *
        FROM GEOREF.VM_SUMINISTROS
    """,
    "pivot_resul_app_movil": """
        SELECT *
        FROM (
            SELECT obs_ord.ORD_NUMERO, obs_ord.TOB_CODIGO,
                   obs_ord.TOB_DESCRIPCION, obs_ord.OBO_INFO_ADICIONAL,
                   obs_ord.IMD_ID
            FROM xxsigec.xxco_observaciones_ordenativ_v obs_ord,
                 xxsigec.ordenativos ord
            WHERE ord.ord_numero      = obs_ord.ord_numero
              AND ord.tor_codigo      = 'CE'
              AND ord.sec_codigo_origen = 'PROTELEM'
        )
        PIVOT (
            MAX(TOB_DESCRIPCION), MAX(OBO_INFO_ADICIONAL) AS TOB_DESCRIPCION
            FOR TOB_CODIGO IN (
                'APP4SITIO_1', 'APP4SITIO_2', 'APP4SITIO_3', 'APP4SITIO_4',
                'APP4TRAB_1',  'APP4TRAB_2',  'APP4TRAB_3',  'APP4TRAB_4', 'APP4TRAB_5',
                'APP4OBS_4',   'APP4OBS_80',  'APP4OBS_81',  'APP4OBS_82',
                'APP4OBS_83',  'APP4OBS_84',  'APP4OBS_11'
            )
        )
    """,
}


def _wrap_count(query: str) -> str:
    return f"SELECT COUNT(*) AS N FROM ({query})"


def _wrap_sample(query: str, n: int = 5) -> str:
    # ROWNUM (en lugar de FETCH FIRST) por compatibilidad con PIVOT y DBs viejas.
    return f"SELECT * FROM ({query}) WHERE ROWNUM <= {n}"


def main() -> int:
    resultados: list[dict] = []
    try:
        with OracleReadOnly() as ora:
            log.info("Conexión OK. Probando %d tablas...", len(QUERIES))
            for nombre, q in QUERIES.items():
                row: dict = {"tabla": nombre, "ok": False}
                t0 = time.perf_counter()
                try:
                    df_count = ora.read_sql(_wrap_count(q))
                    n_filas  = int(df_count.iloc[0, 0])

                    df_sample = ora.read_sql(_wrap_sample(q))
                    row.update({
                        "ok":            True,
                        "filas_total":   n_filas,
                        "columnas":      len(df_sample.columns),
                        "tiempo_seg":    round(time.perf_counter() - t0, 2),
                        "muestra_cols":  list(df_sample.columns[:6]),
                    })
                    log.info(
                        "[OK]   %-25s  filas=%-9d  cols=%-3d  t=%.2fs",
                        nombre, n_filas, len(df_sample.columns), row["tiempo_seg"],
                    )
                except Exception as e:
                    row["error"]      = f"{type(e).__name__}: {e}"
                    row["tiempo_seg"] = round(time.perf_counter() - t0, 2)
                    log.error("[FAIL] %-25s  %s", nombre, row["error"])
                resultados.append(row)
    except Exception as e:
        log.exception("No se pudo abrir la conexión: %s", e)
        return 2

    print("\n=== RESUMEN ===")
    for r in resultados:
        if r.get("ok"):
            print(
                f"  [OK]   {r['tabla']:25s}  filas={r['filas_total']:>9,}  "
                f"cols={r['columnas']:>3}  ({r['tiempo_seg']}s)"
            )
            print(f"           cols[0:6] = {r['muestra_cols']}")
        else:
            print(f"  [FAIL] {r['tabla']:25s}  ({r['tiempo_seg']}s)")
            print(f"           {r['error']}")

    n_ok    = sum(1 for r in resultados if r.get("ok"))
    n_total = len(resultados)
    print(f"\n  {n_ok}/{n_total} tablas accesibles.")
    return 0 if n_ok == n_total else 1


if __name__ == "__main__":
    raise SystemExit(main())
