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
from api.services.adapter_dispatcher import ejecutar_adapter
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

    Maneja su propia sesión de DB (no comparte la del request). Emite
    progreso granular en cada transición vía `LoteService.actualizar_progreso`,
    consumido por la barra de progreso del frontend (polling cada 2s).
    """
    from api.services.lote_service import LoteService

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
            lote.estado = "RECHAZADO"
            lote.detalle_error = "Contratista del lote no existe."
            lote.paso_actual = "RECHAZADO"
            lote.progreso_pct = 100
            db.commit()
            return

        # Validación temprana: el archivo debe pertenecer a la contratista declarada.
        contratista_detectado = _detectar_contratista_archivo(Path(lote.ruta_archivo))
        if contratista_detectado is not None and contratista_detectado != contratista.nombre.upper():
            lote.estado = "RECHAZADO"
            lote.detalle_error = (
                f"El archivo parece corresponder a {contratista_detectado} "
                f"pero el lote fue registrado para {contratista.nombre}. "
                "Verificá que subiste el archivo correcto."
            )
            lote.paso_actual = "RECHAZADO"
            lote.progreso_pct = 100
            db.commit()
            log.warning(
                "Lote %d rechazado: archivo detectado como %s pero declarado como %s.",
                lote_id, contratista_detectado, contratista.nombre,
            )
            return

        lote.estado = "PROCESANDO"
        lote.paso_actual = "VALIDANDO_ESTRUCTURA"
        lote.progreso_pct = 15
        db.commit()

        try:
            df_aux = ejecutar_adapter(Path(lote.ruta_archivo), contratista.nombre)
            if df_aux is None or df_aux.empty:
                raise ValueError("El archivo resultó vacío después de la limpieza.")

            LoteService(db).actualizar_progreso(lote_id, "EJECUTANDO_MOTOR", 40)
            log.info("Lote %d esperando turno en el motor analítico.", lote_id)
            with _motor_lock:
                log.info("Lote %d ingresó al motor analítico.", lote_id)
                df_final, df_img = _ejecutar_motor_analitico(contratista.nombre, df_aux, db=db)

            if df_final is None or df_final.empty:
                raise ValueError("El motor analítico no pudo procesar el lote (output vacío tras core y etapa4).")

            LoteService(db).actualizar_progreso(lote_id, "IMPORTANDO_PARTES", 75)
            metricas = ParteImportService(db).importar_lote(
                lote_id=lote.id,
                contratista_id=contratista.id,
                df_aux=df_aux,
                df_final=df_final,
                df_img=df_img,
            )

            LoteService(db).actualizar_progreso(lote_id, "FINALIZANDO", 95)
            lote = db.query(LoteArchivo).filter(LoteArchivo.id == lote_id).first()
            lote.estado = "APROBADO"
            lote.detalle_error = None
            lote.paso_actual = "APROBADO"
            lote.progreso_pct = 100
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
                lote.estado = "RECHAZADO"
                lote.detalle_error = str(e)[:500]
                lote.paso_actual = "RECHAZADO"
                lote.progreso_pct = 100
                db.commit()
            log.exception("Error procesando lote %d: %s", lote_id, e)


# ----------------------------------------------------------------------
# USES enrichment — cubre partes no-aprobados que Etapa 4 no procesa
# ----------------------------------------------------------------------

def _enriquecer_uses(df: pd.DataFrame, df_reglas: pd.DataFrame) -> pd.DataFrame:
    """Asigna VALOR_USES_ORIGEN a filas donde falta, usando lookup cod_epec → USES.

    Etapa 4 solo calcula USES para partes Aprobados. Este helper aplica el
    mismo lookup (CODIGO_EPEC → reglas.VALOR_USES) al resto del DataFrame.
    No sobreescribe valores ya presentes (preserva lo que calculó Etapa 4).

    Args:
        df:         DataFrame con columna CODIGO_EPEC (Int64 nullable).
        df_reglas:  DataFrame con columnas COD_EPEC y VALOR_USES.

    Returns:
        df con VALOR_USES_ORIGEN rellenado donde sea posible.
    """
    if "CODIGO_EPEC" not in df.columns or df_reglas is None or df_reglas.empty:
        return df

    # Un USES por cod_epec — tomar la primera variante (son consistentes por invariante).
    df_lookup = (
        df_reglas[["COD_EPEC", "VALOR_USES"]]
        .dropna(subset=["COD_EPEC"])
        .drop_duplicates(subset=["COD_EPEC"])
        .rename(columns={"COD_EPEC": "_lkp_cod", "VALOR_USES": "_lkp_uses"})
    )
    df_lookup["_lkp_cod"] = pd.array(df_lookup["_lkp_cod"], dtype="Int64")

    df = df.merge(df_lookup, left_on="CODIGO_EPEC", right_on="_lkp_cod", how="left")
    df = df.drop(columns=["_lkp_cod"])

    if "VALOR_USES_ORIGEN" not in df.columns:
        df["VALOR_USES_ORIGEN"] = df["_lkp_uses"]
    else:
        null_mask = df["VALOR_USES_ORIGEN"].isna()
        df["VALOR_USES_ORIGEN"] = df["VALOR_USES_ORIGEN"].where(~null_mask, df["_lkp_uses"])

    df = df.drop(columns=["_lkp_uses"])

    n_con_uses  = int(df["VALOR_USES_ORIGEN"].notna().sum())
    n_sin_epec  = int(df["CODIGO_EPEC"].isna().sum())
    n_sin_regla = int(
        df["CODIGO_EPEC"].notna().sum() - df.loc[df["CODIGO_EPEC"].notna(), "VALOR_USES_ORIGEN"].notna().sum()
    )
    log.info(
        "_enriquecer_uses — total=%d con_uses=%d sin_epec=%d cod_sin_regla=%d",
        len(df), n_con_uses, n_sin_epec, n_sin_regla,
    )
    if n_sin_regla > 0:
        codigos_faltantes = (
            df.loc[df["CODIGO_EPEC"].notna() & df["VALOR_USES_ORIGEN"].isna(), "CODIGO_EPEC"]
            .dropna().astype(int).unique().tolist()
        )
        log.warning("_enriquecer_uses — CODIGO_EPEC sin regla definida: %s", codigos_faltantes)
    return df


# ----------------------------------------------------------------------
# Helpers — motor (separado del orquestador para testing aislado).
# El dispatch del adapter vive ahora en `api.services.adapter_dispatcher`.
# ----------------------------------------------------------------------

def _ejecutar_motor_analitico(
    nombre_contratista: str,
    df_aux: pd.DataFrame,
    db=None,
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

    df_reglas = None
    mapeo_codigos = None
    if db is not None:
        from api.services.reglas_service import ReglaService
        svc = ReglaService(db)
        df_reglas = svc.cargar_reglas_como_dataframe()
        mapeo_codigos = svc.mapeo_codigos_epec_por_contratista()

    df_aprobados, df_img, _metricas4 = procesar_etapa4(
        df_fact_input=df_contratista,
        df_reglas=df_reglas,
        mapeo_codigos=mapeo_codigos,
    )

    if df_aprobados is None or df_aprobados.empty:
        log.info(
            "WORKER motor — etapa4 sin aprobados; importando %d partes desde core (ID_ESTADO≠1).",
            len(df_contratista),
        )
        # Aún sin aprobados, enriquecer con USES si hay reglas disponibles.
        if df_reglas is not None:
            df_contratista = _enriquecer_uses(df_contratista, df_reglas)
        _auto_rescatar_local(df_contratista, db)
        return df_contratista, None

    # Recombinar aprobados enriquecidos por etapa4 con los no-aprobados del core.
    # Sin esto, los ~15k rechazados/huérfanos se descartan silenciosamente.
    mask_aprobados = df_contratista["ID_PARTE_HASH"].isin(df_aprobados["ID_PARTE_HASH"])
    df_no_aprobados = df_contratista.loc[~mask_aprobados].copy()

    # Etapa 4 solo procesa aprobados, por lo que df_no_aprobados no tiene
    # VALOR_USES_ORIGEN. Lo llenamos aquí con el mismo df_reglas ya cargado.
    if df_reglas is not None and not df_no_aprobados.empty:
        df_no_aprobados = _enriquecer_uses(df_no_aprobados, df_reglas)

    df_completo = pd.concat([df_aprobados, df_no_aprobados], ignore_index=True, sort=False)
    log.info(
        "WORKER motor — etapa4: aprobados=%d, no-aprobados=%d, total=%d",
        len(df_aprobados), len(df_no_aprobados), len(df_completo),
    )

    # Auto-rescate de "Sin Orden Asociada" contra DB local sincronizada (CE+PROTELEM).
    _auto_rescatar_local(df_completo, db)

    return df_completo, df_img


# ----------------------------------------------------------------------
# Auto-rescate vía DB local sincronizada desde Oracle SIGEC (CE + PROTELEM)
# ----------------------------------------------------------------------

def _auto_rescatar_local(df: pd.DataFrame, db) -> dict:
    """Reasigna ID_TRAZA/ID_ESTADO/ORD_NRO a partes con ID_TRAZA==7 ('Sin Orden Asociada').

    Política conservadora:
      • 1 candidato CE con dias_diferencia ≤ tolerancia → ID_TRAZA=19, ID_ESTADO=2, ORD_NRO=candidato.
      • N≥2 candidatos CE en tolerancia → ID_TRAZA=20, ID_ESTADO=2, ORD_NRO=NULL (auditor elige).
      • 0 candidatos / DB local sin sync → sin cambios (queda como hoy).

    Mutates ``df`` in-place. Devuelve métricas para logging.
    """
    metricas = {"total_huerfanos": 0, "rescatados_1cand": 0, "ambiguos_Ncand": 0, "sin_match": 0}
    if db is None or "ID_TRAZA" not in df.columns or df.empty:
        return metricas

    mask_huerfanos = df["ID_TRAZA"] == 7
    n_huerfanos = int(mask_huerfanos.sum())
    metricas["total_huerfanos"] = n_huerfanos
    if n_huerfanos == 0:
        return metricas

    from src.config import RESCATE_DIAS_TOLERANCIA
    from api.services.rescate_ordenativos_service import rescatar_huerfanos_lote
    from api.db.models.domain_models import OrdenativoOracleLocal
    from sqlalchemy import func as sa_func

    huerfanos_input: list[dict] = []
    for r in df.loc[mask_huerfanos].to_dict(orient="records"):
        huerfanos_input.append({
            "id_parte_hash":    r.get("ID_PARTE_HASH"),
            "suministro":       _safe_str(r.get("SUMINISTRO_RAW")),
            "medidor_colocado": _safe_str(r.get("NRO_EQP_COLOCADO")),
            "medidor_retirado": _safe_str(r.get("NRO_EQP_RETIRADO")),
            "fecha_ref":        _safe_dt(r.get("FECHA")),
        })

    resultados = rescatar_huerfanos_lote(db, huerfanos_input, RESCATE_DIAS_TOLERANCIA)
    if not resultados:
        # Sin sync o todo fail — todos cuentan como sin_match.
        metricas["sin_match"] = n_huerfanos
        ultimo_sync = db.query(sa_func.max(OrdenativoOracleLocal.sincronizado_at)).scalar()
        log.warning(
            "_auto_rescatar_local — total_huerfanos=%d skip (DB local sync=%s)",
            n_huerfanos, ultimo_sync,
        )
        return metricas

    # Aplicar resultados al DataFrame
    for h_hash, info in resultados.items():
        idx = df.index[df["ID_PARTE_HASH"] == h_hash]
        if len(idx) == 0:
            continue
        clasif = info["clasificacion"]
        if clasif == "rescate_unico":
            df.loc[idx, "ID_TRAZA"]  = 19
            df.loc[idx, "ID_ESTADO"] = 2
            df.loc[idx, "ORD_NRO"]   = info["ord_nro_asignado"]
            metricas["rescatados_1cand"] += 1
        elif clasif == "ambiguo_multiple":
            df.loc[idx, "ID_TRAZA"]  = 20
            df.loc[idx, "ID_ESTADO"] = 2
            metricas["ambiguos_Ncand"] += 1
        else:
            metricas["sin_match"] += 1

    ultimo_sync = db.query(sa_func.max(OrdenativoOracleLocal.sincronizado_at)).scalar()
    log.info(
        "_auto_rescatar_local — total_huerfanos=%d rescatados_1cand=%d ambiguos_Ncand=%d sin_match=%d ultimo_sync=%s",
        n_huerfanos,
        metricas["rescatados_1cand"],
        metricas["ambiguos_Ncand"],
        metricas["sin_match"],
        ultimo_sync,
    )
    return metricas


def _safe_str(val) -> str | None:
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    s = str(val).strip()
    return s or None


def _safe_dt(val):
    if val is None:
        return None
    try:
        if isinstance(val, float) and pd.isna(val):
            return None
        ts = pd.Timestamp(val)
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None


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
