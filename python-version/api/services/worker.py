"""
Worker asíncrono — orquesta el procesamiento end-to-end de un lote.

Flujo:
1. Lee el binario persistido (`lote.ruta_archivo`).
2. Aplica el adapter del contratista para obtener `df_aux` normalizado.
3. Invoca el motor analítico in-memory: Etapa 3 (Core) → Etapa 4 (Control Obs).
4. Delega a `ParteImportService` la persistencia transaccional (raws + procesados + imágenes).
5. Marca el lote como `PROCESADO_OK` o `ERROR` según corresponda.

Principio aplicado: este módulo es un orquestador delgado. La persistencia y el
mapping pesado viven en `ParteImportService`. El motor analítico se invoca como
una función pura (input DataFrame → output DataFrame).
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from api.core.database import SessionLocal
from api.db.models.base_models import Contratista, LoteArchivo
from api.services.parte_import_service import ParteImportService

from src import io_lakehouse as io
from src.etapa3_core import ejecutar_core_para_contratista
from src.etapa4_control_obs import procesar_etapa4

log = logging.getLogger("api.services.worker")


def procesar_lote_en_background(lote_id: int) -> None:
    """Punto de entrada para `BackgroundTasks` de FastAPI.

    Maneja su propia sesión de DB (no comparte la del request).
    """
    with SessionLocal() as db:
        lote = db.query(LoteArchivo).filter(LoteArchivo.id == lote_id).first()
        if not lote:
            log.error("Lote %d no encontrado.", lote_id)
            return

        contratista = (
            db.query(Contratista).filter(Contratista.id == lote.contratista_id).first()
        )
        if not contratista:
            log.error("Contratista %d (lote %d) no encontrado.", lote.contratista_id, lote_id)
            lote.estado = "ERROR"
            lote.detalle_error = "Contratista del lote no existe."
            db.commit()
            return

        lote.estado = "PROCESANDO"
        db.commit()

        try:
            df_aux = _ejecutar_adapter(Path(lote.ruta_archivo), contratista.nombre)
            if df_aux is None or df_aux.empty:
                raise ValueError("El archivo resultó vacío después de la limpieza.")

            df_final, df_img = _ejecutar_motor_analitico(contratista.nombre, df_aux)
            if df_final is None or df_final.empty:
                raise ValueError("El motor analítico no produjo resultados para este lote.")

            metricas = ParteImportService(db).importar_lote(
                lote_id=lote.id,
                contratista_id=contratista.id,
                df_aux=df_aux,
                df_final=df_final,
                df_img=df_img,
            )

            lote.estado = "PROCESADO_OK"
            lote.detalle_error = None
            db.commit()
            log.info(
                "Lote %d procesado OK: raws=%d, procesados=%d, imagenes=%d",
                lote.id, metricas["raws"], metricas["procesados"], metricas["imagenes"],
            )

        except Exception as e:
            db.rollback()
            # Recuperar el lote tras el rollback para poder marcarlo en ERROR.
            lote = db.query(LoteArchivo).filter(LoteArchivo.id == lote_id).first()
            if lote is not None:
                lote.estado = "ERROR"
                lote.detalle_error = str(e)[:500]
                db.commit()
            log.exception("Error procesando lote %d: %s", lote_id, e)


# ----------------------------------------------------------------------
# Helpers — adapters y motor (separados del orquestador para testing aislado)
# ----------------------------------------------------------------------

def _ejecutar_adapter(path: Path, nombre_contratista: str) -> pd.DataFrame | None:
    """Aplica el adapter del contratista y devuelve el DataFrame normalizado."""
    contratista_upper = nombre_contratista.upper()

    if contratista_upper == "CONECTAR":
        from src.etapa2_adapter_conectar import (
            obtener_codigos_habilitados,
            procesar_excel,
        )
        df_aux, _ = procesar_excel(path, obtener_codigos_habilitados())
        return df_aux

    if contratista_upper == "COOPLYF":
        from src.etapa2_adapter_cooplyf import procesar_archivo
        df_aux, _ = procesar_archivo(path)
        return df_aux

    log.warning("Contratista '%s' sin adapter dedicado — fallback a read_excel directo.", nombre_contratista)
    return pd.read_excel(path)


def _ejecutar_motor_analitico(
    nombre_contratista: str,
    df_aux: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Corre Etapa 3 (Core) + Etapa 4 (Control Obs) en memoria."""
    mapa_archivos = (
        io.read_table("mapa_archivos", capa="seed")
        .set_index("ARCHIVO_X")["ID_ARCHIVO"]
        .to_dict()
    )
    df_dim_traza = io.read_table("dim_traza_calidad_bi", capa="dim")

    df_contratista, _metricas3 = ejecutar_core_para_contratista(
        contratista=nombre_contratista.upper(),
        mapa_archivos=mapa_archivos,
        df_dim_traza=df_dim_traza,
        df_pd_input=df_aux,
    )
    if df_contratista is None or df_contratista.empty:
        return df_contratista, None

    df_final, df_img, _metricas4 = procesar_etapa4(df_fact_input=df_contratista)
    return df_final, df_img
