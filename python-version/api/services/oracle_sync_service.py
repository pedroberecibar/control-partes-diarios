"""Sync admin Oracle SIGEC → SQLite local (universo CE + PROTELEM).

Operación on-demand disparada por un admin desde la UI. Trae todos los
ordenativos CE+PROTELEM relevantes, sus fotos y los equipos cuyos suministros
aparecen en esos ordenativos. Upsert por clave natural — re-ejecutable sin
duplicar y refleja cambios de estado en Oracle (ej. ABIERTO → CERRADO).

Una sola conexión Oracle por corrida. SQLite es destino transaccional: si algo
falla a mitad del sync, se hace rollback y la DB local queda en su estado
anterior.

Consumidores de la DB local:
- `worker._auto_rescatar_local`        — durante el procesamiento de cada lote.
- `rescate_ordenativos_service`        — endpoint UI "Buscar candidatos".
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from api.db.models.domain_models import (
    OrdenativoOracleEquipo,
    OrdenativoOracleFoto,
    OrdenativoOracleLocal,
)
from api.services.oracle_service import _limpiar_url_firebase
from src import config
from src.oracle_io import OracleReadOnly

log = logging.getLogger("api.services.oracle_sync")

# Límite seguro para IN (...) en Oracle (1000) y SQLite (variables compuestas).
CHUNK_SIZE_IN = 500


# ── SQL templates ────────────────────────────────────────────────────────────

_SQL_ORDENATIVOS = """
    SELECT O.ORD_NUMERO, O.SRV_CODIGO, O.TOR_CODIGO, O.SEC_CODIGO_ORIGEN,
           O.ORD_FECHA_GENERACION, O.ORD_FECHA_INICIO, O.ORD_FECHA_FIN,
           O.ORD_ESTADO, O.ORD_RESULTADO, O.USR_NUMERO_EJEC_ORD,
           U.USR_NOMBRE
    FROM XXSIGEC.ORDENATIVOS O
    JOIN XXSIGEC.XXCO_USUARIOS_V U
      ON O.USR_NUMERO_EJEC_ORD = U.USR_NUMERO
    WHERE O.TOR_CODIGO        = 'CE'
      AND O.SEC_CODIGO_ORIGEN = 'PROTELEM'
      AND (O.ORD_FECHA_GENERACION       >= TO_DATE(:desde, 'DD/MM/YYYY')
           OR O.ORD_FECHA_INICIO         >= TO_DATE(:desde, 'DD/MM/YYYY')
           OR O.ORD_FECHA_FIN            >= TO_DATE(:desde, 'DD/MM/YYYY')
           OR O.ORD_ULTIMA_ACTUALIZACION >= TO_DATE(:desde, 'DD/MM/YYYY'))
"""

_CODIGOS_IMAGEN = ("APP4OBS_80", "APP4OBS_81", "APP4OBS_82", "APP4OBS_83", "APP4OBS_84")
_IMAGEN_POS_MAP = {c: i + 1 for i, c in enumerate(_CODIGOS_IMAGEN)}


def _sql_fotos_chunk(ord_numeros: list[int]) -> str:
    nums = ", ".join(str(int(n)) for n in ord_numeros)
    codigos = ", ".join(f"'{c}'" for c in _CODIGOS_IMAGEN)
    return f"""
        SELECT ORD_NUMERO, TOB_CODIGO, OBO_INFO_ADICIONAL
        FROM xxsigec.xxco_observaciones_ordenativ_v
        WHERE ORD_NUMERO IN ({nums})
          AND TOB_CODIGO IN ({codigos})
    """


def _sql_equipos_chunk(srv_codigos_int: list[int]) -> str:
    nums = ", ".join(str(int(c)) for c in srv_codigos_int)
    return f"""
        SELECT STE_NUMERO, SRV_CODIGO, EQP_FECHA_INSTAL
        FROM XXSIGEC.EQUIPOS
        WHERE SRV_CODIGO IN ({nums})
    """


# ── API pública ──────────────────────────────────────────────────────────────

def sincronizar_ordenativos_protelem(
    db: Session,
    desde_fecha: str | None = None,
) -> dict[str, Any]:
    """Sync transaccional Oracle → SQLite. Upsert por clave natural.

    Args:
        db: sesión SQLAlchemy de la app.
        desde_fecha: corte inferior en formato ``DD/MM/YYYY``. Si None, usa
            ``config.RESCATE_FECHA_INICIO_BOOTSTRAP``.

    Returns:
        Dict con métricas: ordenativos/fotos/equipos upserted, duracion_s,
        errores, desde_fecha. ``errores`` no vacío indica fallo (rollback ya hecho).
    """
    desde = desde_fecha or config.RESCATE_FECHA_INICIO_BOOTSTRAP
    inicio = time.time()
    metricas: dict[str, Any] = {
        "ordenativos_upserted": 0,
        "fotos_upserted":       0,
        "equipos_upserted":     0,
        "duracion_s":           0.0,
        "errores":              [],
        "desde_fecha":          desde,
    }

    try:
        with OracleReadOnly() as ora:
            # ── Paso 1: ordenativos CE+PROTELEM con nombre del ejecutante
            log.info("Sync Oracle paso 1/3: ordenativos CE+PROTELEM desde %s", desde)
            df_ord = ora.read_sql(_SQL_ORDENATIVOS, params={"desde": desde})
            log.info("  %d ordenativos traídos de Oracle", len(df_ord))

            if df_ord.empty:
                log.warning("  Sin ordenativos para sincronizar — abortando.")
                db.commit()
                metricas["duracion_s"] = round(time.time() - inicio, 2)
                return metricas

            now = datetime.now(timezone.utc)
            rows_ord = [_row_ordenativo(r, now) for r in df_ord.to_dict(orient="records")]
            metricas["ordenativos_upserted"] = _bulk_upsert(
                db, OrdenativoOracleLocal, rows_ord, ["ord_numero"]
            )
            db.flush()

            # ── Paso 2: fotos
            ord_numeros = [int(n) for n in df_ord["ORD_NUMERO"].dropna().unique()]
            log.info("Sync Oracle paso 2/3: fotos de %d ordenativos", len(ord_numeros))
            rows_fotos: list[dict] = []
            for i in range(0, len(ord_numeros), CHUNK_SIZE_IN):
                chunk = ord_numeros[i:i + CHUNK_SIZE_IN]
                df_fotos = ora.read_sql(_sql_fotos_chunk(chunk))
                rows_fotos.extend(_rows_fotos(df_fotos))
            metricas["fotos_upserted"] = _bulk_upsert(
                db, OrdenativoOracleFoto, rows_fotos, ["ord_numero", "posicion"]
            )
            db.flush()

            # ── Paso 3: equipos (limitado a SRV_CODIGOs presentes en ordenativos)
            srv_codigos_int = _srv_codigos_unicos_int(df_ord["SRV_CODIGO"])
            log.info("Sync Oracle paso 3/3: equipos de %d suministros", len(srv_codigos_int))
            rows_eqp: list[dict] = []
            for i in range(0, len(srv_codigos_int), CHUNK_SIZE_IN):
                chunk = srv_codigos_int[i:i + CHUNK_SIZE_IN]
                if not chunk:
                    continue
                df_eqp = ora.read_sql(_sql_equipos_chunk(chunk))
                rows_eqp.extend(_rows_equipos(df_eqp))
            metricas["equipos_upserted"] = _bulk_upsert(
                db, OrdenativoOracleEquipo, rows_eqp, ["ste_numero", "srv_codigo"]
            )

        db.commit()
        log.info(
            "Sync Oracle OK: ord=%d fotos=%d eqp=%d en %.1fs",
            metricas["ordenativos_upserted"],
            metricas["fotos_upserted"],
            metricas["equipos_upserted"],
            time.time() - inicio,
        )
    except Exception as e:
        db.rollback()
        log.exception("Sync Oracle FALLÓ: %s", e)
        metricas["errores"].append(f"{type(e).__name__}: {str(e)[:300]}")

    metricas["duracion_s"] = round(time.time() - inicio, 2)
    return metricas


def obtener_estado_sync(db: Session) -> dict[str, Any]:
    """Estado actual del sync para la UI admin."""
    last_sync = db.query(func.max(OrdenativoOracleLocal.sincronizado_at)).scalar()
    return {
        "ultimo_sync_at":     last_sync.isoformat() if last_sync else None,
        "ordenativos_count":  db.query(func.count(OrdenativoOracleLocal.ord_numero)).scalar() or 0,
        "fotos_count":        db.query(func.count(OrdenativoOracleFoto.id)).scalar() or 0,
        "equipos_count":      db.query(func.count(OrdenativoOracleEquipo.id)).scalar() or 0,
    }


# ── Helpers internos ─────────────────────────────────────────────────────────

def _bulk_upsert(
    db: Session,
    model,
    rows: list[dict],
    conflict_cols: list[str],
    chunk_size: int = CHUNK_SIZE_IN,
) -> int:
    """Upsert chunked usando SQLite ``INSERT ... ON CONFLICT DO UPDATE``."""
    if not rows:
        return 0

    pk_names = {c.name for c in model.__table__.primary_key.columns}
    excluded_from_update = set(conflict_cols) | pk_names | {"created_at"}

    n = 0
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        stmt = sqlite_insert(model).values(chunk)
        update_cols = {
            col.name: stmt.excluded[col.name]
            for col in model.__table__.columns
            if col.name not in excluded_from_update
        }
        if update_cols:
            stmt = stmt.on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=conflict_cols)
        db.execute(stmt)
        n += len(chunk)
    return n


def _to_dt(val: Any) -> datetime | None:
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


def _to_str(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    s = str(val).strip()
    return s or None


def _to_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        if isinstance(val, float) and pd.isna(val):
            return None
        return int(val)
    except (TypeError, ValueError):
        return None


def _row_ordenativo(r: dict, sync_ts: datetime) -> dict:
    return {
        "ord_numero":           int(r["ORD_NUMERO"]),
        "srv_codigo":           _to_str(r.get("SRV_CODIGO")),
        "tor_codigo":           _to_str(r.get("TOR_CODIGO")) or "CE",
        "sec_codigo_origen":    _to_str(r.get("SEC_CODIGO_ORIGEN")),
        "ord_fecha_generacion": _to_dt(r.get("ORD_FECHA_GENERACION")),
        "ord_fecha_inicio":     _to_dt(r.get("ORD_FECHA_INICIO")),
        "ord_fecha_fin":        _to_dt(r.get("ORD_FECHA_FIN")),
        "ord_estado":           _to_str(r.get("ORD_ESTADO")),
        "ord_resultado":        _to_str(r.get("ORD_RESULTADO")),
        "usr_numero_ejec_ord":  _to_int(r.get("USR_NUMERO_EJEC_ORD")),
        "usr_nombre":           _to_str(r.get("USR_NOMBRE")),
        "sincronizado_at":      sync_ts,
    }


def _rows_fotos(df_fotos: pd.DataFrame) -> list[dict]:
    out: list[dict] = []
    if df_fotos is None or df_fotos.empty:
        return out
    for r in df_fotos.to_dict(orient="records"):
        pos = _IMAGEN_POS_MAP.get(_to_str(r.get("TOB_CODIGO")) or "")
        if pos is None:
            continue
        raw = r.get("OBO_INFO_ADICIONAL")
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            continue
        raw_str = str(raw).strip()
        if not raw_str:
            continue
        cleaned = _limpiar_url_firebase(raw_str)
        ord_numero = _to_int(r.get("ORD_NUMERO"))
        if ord_numero is None:
            continue
        if cleaned is None:
            log.debug("Sin URL Firebase en OBO_INFO_ADICIONAL (ord=%s pos=%s) — omitida.", ord_numero, pos)
            continue
        out.append({
            "ord_numero": ord_numero,
            "posicion":   pos,
            "url":        cleaned,
        })
    return out


def _rows_equipos(df_eqp: pd.DataFrame) -> list[dict]:
    out: list[dict] = []
    if df_eqp is None or df_eqp.empty:
        return out
    for r in df_eqp.to_dict(orient="records"):
        ste = _to_str(r.get("STE_NUMERO"))
        srv = _to_str(r.get("SRV_CODIGO"))
        if ste is None or srv is None:
            continue
        out.append({
            "ste_numero":       ste,
            "srv_codigo":       srv,
            "eqp_fecha_instal": _to_dt(r.get("EQP_FECHA_INSTAL")),
        })
    return out


def _srv_codigos_unicos_int(serie: pd.Series) -> list[int]:
    """Convierte la columna SRV_CODIGO a lista de enteros únicos. Filtra los no convertibles."""
    out: set[int] = set()
    for v in serie.dropna().unique():
        try:
            out.add(int(v))
        except (TypeError, ValueError):
            continue
    return sorted(out)
