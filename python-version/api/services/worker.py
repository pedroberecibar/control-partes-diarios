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
import threading
from pathlib import Path

import pandas as pd

from api.core.database import SessionLocal
from api.db.models.base_models import Contratista, LoteArchivo
from api.services.parte_import_service import ParteImportService

from src import io_lakehouse as io
from src.etapa3_core import ejecutar_core_para_contratista
from src.etapa4_control_obs import procesar_etapa4

log = logging.getLogger("api.services.worker")

# El motor escribe Parquets globales (control_obs_app.parquet.tmp, etc.).
# Este lock garantiza que solo un lote corra el motor a la vez.
_motor_lock = threading.Lock()


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

        # Validación temprana: el archivo debe pertenecer a la contratista declarada.
        contratista_detectado = _detectar_contratista_archivo(Path(lote.ruta_archivo))
        if contratista_detectado is not None and contratista_detectado != contratista.nombre.upper():
            lote.estado = "RECHAZADO_SINTAXIS"
            lote.detalle_error = (
                f"El archivo parece corresponder a {contratista_detectado} "
                f"pero el lote fue registrado para {contratista.nombre}. "
                "Verificá que subiste el archivo correcto."
            )
            db.commit()
            log.warning(
                "Lote %d rechazado: archivo detectado como %s pero declarado como %s.",
                lote_id, contratista_detectado, contratista.nombre,
            )
            return

        lote.estado = "PROCESANDO"
        db.commit()

        try:
            df_aux = _ejecutar_adapter(Path(lote.ruta_archivo), contratista.nombre)
            if df_aux is None or df_aux.empty:
                raise ValueError("El archivo resultó vacío después de la limpieza.")

            log.info("Lote %d esperando turno en el motor analítico.", lote_id)
            with _motor_lock:
                log.info("Lote %d ingresó al motor analítico.", lote_id)
                df_final, df_img = _ejecutar_motor_analitico(contratista.nombre, df_aux)

            if df_final is None or df_final.empty:
                raise ValueError("El motor analítico no pudo procesar el lote (output vacío tras core y etapa4).")

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

    df_aprobados, df_img, _metricas4 = procesar_etapa4(df_fact_input=df_contratista)

    if df_aprobados is None or df_aprobados.empty:
        log.info(
            "WORKER motor — etapa4 sin aprobados; importando %d partes desde core (ID_ESTADO≠1).",
            len(df_contratista),
        )
        return df_contratista, None

    # Recombinar aprobados enriquecidos por etapa4 con los no-aprobados del core.
    # Sin esto, los ~15k rechazados/huérfanos se descartan silenciosamente.
    mask_aprobados = df_contratista["ID_PARTE_HASH"].isin(df_aprobados["ID_PARTE_HASH"])
    df_no_aprobados = df_contratista.loc[~mask_aprobados].copy()
    df_completo = pd.concat([df_aprobados, df_no_aprobados], ignore_index=True, sort=False)
    log.info(
        "WORKER motor — etapa4: aprobados=%d, no-aprobados=%d, total=%d",
        len(df_aprobados), len(df_no_aprobados), len(df_completo),
    )
    return df_completo, df_img


# ----------------------------------------------------------------------
# Detección de contratista por firma de columnas
# ----------------------------------------------------------------------

# Columnas exclusivas de cada contratista (no aparecen en el otro).
_FIRMA_CONECTAR = frozenset({"Cuadrilla", "Vehiculos", "Personas", "Obra"})
_FIRMA_COOPLYF  = frozenset({"Tipo de trabajo", "TipoTrabajo", "codTiposTrabajos"})

# Filas de encabezado a intentar (mismo criterio que el adapter CONECTAR).
_HEADER_CANDIDATOS = (0, 1, 2, 3, 4)


def _detectar_contratista_archivo(path: Path) -> str | None:
    """Lee solo los encabezados del archivo y detecta la contratista por firma de columnas.

    Devuelve "CONECTAR", "COOPLYF", o None si no puede determinarlo.
    """
    nombre = path.name.lower()
    col_sets: list[set[str]] = []

    if nombre.endswith(".csv"):
        for sep, enc in ((",", "utf-8"), (";", "latin-1")):
            try:
                df = pd.read_csv(path, sep=sep, nrows=1, dtype=str, encoding=enc)
                if df.shape[1] >= 2:
                    col_sets.append({c.strip() for c in df.columns})
                    break
            except Exception:
                continue
    else:
        for h in _HEADER_CANDIDATOS:
            try:
                df = pd.read_excel(path, header=h, nrows=1, dtype=str)
                col_sets.append({c.strip() for c in df.columns})
            except Exception:
                continue

    for cols in col_sets:
        if cols & _FIRMA_CONECTAR:
            return "CONECTAR"
        if cols & _FIRMA_COOPLYF:
            return "COOPLYF"
    return None
