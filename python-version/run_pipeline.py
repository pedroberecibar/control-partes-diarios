"""Orquestador del pipeline local.

Sustituye a la "canalización" de Fabric. Etapas implementadas:

    0) Seeds (Oracle)  → src/etapa0_seeds.py
    1) Maestros        → src/etapa1_maestros.py
    2) Adapters        → src/etapa2_adapter_{conectar,cooplyf}.py
    3) Core            → src/etapa3_core.py (waterfall)
       3.1+3.2 Dims BI  → src/etapa3_dims_bi.py
       3.3 Waterfall     → src/etapa3_core.py
       3.4 Dims Geo/Cal  → src/etapa3_dims_geo_calendario.py
       3.5 Panel KPIs    → src/etapa3_panel_kpis.py
    4) Control Obs     → src/etapa4_control_obs.py

Orden recomendado para una corrida end-to-end:

    etapa1 → etapa2 → seeds → etapa3 → etapa4

Uso:
    python run_pipeline.py                          # etapas 1-4 completas
    python run_pipeline.py --solo-etapa 1
    python run_pipeline.py --solo-etapa 2 --reproceso
    python run_pipeline.py --solo-etapa 3           # core + dims + panel KPIs
    python run_pipeline.py --solo-etapa 4           # control de observaciones
    python run_pipeline.py --refrescar-seeds        # 1 + 2 + seeds + 3 + 4
    python run_pipeline.py --solo-seeds             # solo seeds (independientes + eqp)
    python run_pipeline.py --solo-seeds dim_ord usuarios_gral
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime

from src import config


def _configurar_logging() -> None:
    config.ensure_layout()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = config.CAPAS["logs"] / f"run_{ts}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )


def _correr_etapa1(log: logging.Logger) -> None:
    log.info("=== Etapa 1: Maestros ===")
    from src import etapa1_maestros
    log.info("Etapa 1 OK: %s", etapa1_maestros.run())


def _correr_etapa2(log: logging.Logger, modo_reproceso: bool) -> None:
    log.info("=== Etapa 2a: Adapter CONECTAR ===")
    from src import etapa2_adapter_conectar
    log.info("Adapter CONECTAR OK: %s", etapa2_adapter_conectar.run(modo_reproceso))

    log.info("=== Etapa 2b: Adapter COOPLYF ===")
    from src import etapa2_adapter_cooplyf
    log.info("Adapter COOPLYF OK: %s", etapa2_adapter_cooplyf.run(modo_reproceso))


def _correr_seeds(log: logging.Logger, seleccion: list[str] | None) -> None:
    """Ejecuta etapa0_seeds. Si `seleccion` es None, refresca todo."""
    log.info("=== Etapa 0: Seeds (Oracle) ===")
    from src import etapa0_seeds

    if not seleccion:
        independientes = list(etapa0_seeds.SEEDS_INDEPENDIENTES)
        incluye_eqp = True
    else:
        independientes = [s for s in seleccion if s in etapa0_seeds.SEEDS_INDEPENDIENTES]
        incluye_eqp    = "eqp_equipos_ultimos_10" in seleccion

    if independientes:
        for m in etapa0_seeds.run_independientes(independientes):
            log.info("Seed OK: %s", m)

    if incluye_eqp:
        log.info("--- eqp_equipos_ultimos_10 (filtrado por staging+fact) ---")
        log.info("Seed OK: %s", etapa0_seeds.refresh_eqp_ultimos_10())


def _correr_etapa3(log: logging.Logger) -> None:
    """Etapa 3 completa: dims BI + core waterfall + dims geo/cal + panel KPIs."""
    log.info("=== Etapa 3.1+3.2: Dimensiones BI estaticas + dim_archivo ===")
    from src import etapa3_dims_bi
    log.info("Dims BI OK: %s", etapa3_dims_bi.run())

    log.info("=== Etapa 3.3: Core Waterfall ===")
    from src import etapa3_core
    log.info("Core Waterfall OK: %s", etapa3_core.run())

    log.info("=== Etapa 3.4: Dims Geo + Calendario ===")
    from src import etapa3_dims_geo_calendario
    log.info("Dims Geo/Calendario OK: %s", etapa3_dims_geo_calendario.run())

    log.info("=== Etapa 3.5: Panel KPIs ===")
    from src import etapa3_panel_kpis
    etapa3_panel_kpis.run()


def _correr_etapa4(log: logging.Logger) -> None:
    """Etapa 4: Control de observaciones y valoracion economica (USES)."""
    log.info("=== Etapa 4: Control de Observaciones ===")
    from src import etapa4_control_obs
    resultado = etapa4_control_obs.run()
    log.info("Etapa 4 OK: control_obs_app=%d filas, dim_img_app_pd=%d filas.",
             resultado.get("control_obs_app", 0), resultado.get("dim_img_app_pd", 0))


def main(
    solo_etapa: int | None = None,
    modo_reproceso: bool = False,
    refrescar_seeds: bool = False,
    solo_seeds: list[str] | None = None,
) -> None:
    _configurar_logging()
    log = logging.getLogger("pipeline")

    if solo_seeds is not None:
        # Modo "solo seeds": ignora todo lo demás.
        _correr_seeds(log, solo_seeds or None)
        return

    if solo_etapa in (None, 1):
        _correr_etapa1(log)

    if solo_etapa in (None, 2):
        _correr_etapa2(log, modo_reproceso)

    if refrescar_seeds and solo_etapa is None:
        # Después de etapa2, así eqp tiene los SRV_CODIGOs del staging.
        _correr_seeds(log, None)

    if solo_etapa in (None, 3):
        _correr_etapa3(log)

    if solo_etapa in (None, 4):
        _correr_etapa4(log)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline local de Partes Diarios")
    parser.add_argument("--solo-etapa", type=int, choices=[1, 2, 3, 4], default=None)
    parser.add_argument("--reproceso", action="store_true",
                        help="Ignora la bitacora y reprocesa todos los archivos de input")
    parser.add_argument("--refrescar-seeds", action="store_true",
                        help="Despues de etapa2, refresca todas las seeds desde Oracle")
    parser.add_argument("--solo-seeds", nargs="*", default=None,
                        metavar="SEED",
                        help="Corre solo el refresh de seeds (sin args = todas). "
                             "Nombres validos: usuarios_gral, dim_stk_stock_equipos, "
                             "sigec_general, dim_ord, pivot_resul_app_movil, "
                             "eqp_equipos_ultimos_10")
    args = parser.parse_args()
    main(
        solo_etapa=args.solo_etapa,
        modo_reproceso=args.reproceso,
        refrescar_seeds=args.refrescar_seeds,
        solo_seeds=args.solo_seeds,
    )
