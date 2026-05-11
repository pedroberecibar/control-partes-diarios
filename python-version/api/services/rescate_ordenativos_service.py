"""Servicio de rescate de partes "Sin Orden Asociada" contra DB local sincronizada.

Reemplaza `oracle_service.buscar_candidatos` (que consultaba Oracle en vivo)
por consultas a las tablas locales pobladas por `oracle_sync_service`. Esto
elimina la dependencia de red en runtime para:
  - Endpoint UI ``GET /partes/{id}/candidatos-oracle``.
  - Auto-rescate batch del worker (``_auto_rescatar_local``).

La función ``buscar_candidatos_local`` mantiene la misma firma de retorno que
``oracle_service.buscar_candidatos`` para que el endpoint UI no rompa.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from api.db.models.domain_models import (
    OrdenativoOracleEquipo,
    OrdenativoOracleFoto,
    OrdenativoOracleLocal,
)

log = logging.getLogger("api.services.rescate")


# ── API pública ──────────────────────────────────────────────────────────────

def buscar_candidatos_local(
    db: Session,
    suministro: str | None,
    nro_medidor_colocado: str | None,
    nro_medidor_retirado: str | None,
    fecha_ref: datetime | None,
) -> dict[str, Any]:
    """Busca ordenativos CE candidatos en la DB local. Misma firma que
    ``oracle_service.buscar_candidatos``.

    Estrategia (replica la del UI original pero contra tablas locales):
      A: ordenativos cuyo SRV_CODIGO == suministro declarado.
      B_colocado: ordenativos del SRV_CODIGO al que está asociado el medidor colocado.
      B_retirado: ídem con medidor retirado.

    Returns:
        ``{"candidatos": [...], "aviso": str|None}``. ``aviso`` se usa cuando
        la DB local nunca se sincronizó.
    """
    if not _hay_sync(db):
        return {
            "candidatos": [],
            "aviso": (
                "La base de ordenativos local nunca fue sincronizada. "
                "Contactá a un administrador para ejecutar el sync inicial."
            ),
        }

    acum: dict[int, dict] = {}

    # Search A — por suministro
    sumi = _norm(suministro)
    if sumi:
        rows_a = (
            db.query(OrdenativoOracleLocal)
            .filter(OrdenativoOracleLocal.srv_codigo == sumi)
            .all()
        )
        for r in rows_a:
            _incorporar(acum, r, "A")

    # Search B — por medidor colocado / retirado
    med_col = _norm(nro_medidor_colocado)
    med_ret = _norm(nro_medidor_retirado)

    if med_col:
        for r in _ordenativos_por_medidor(db, med_col):
            _incorporar(acum, r, "B_colocado")

    if med_ret and med_ret != med_col:
        for r in _ordenativos_por_medidor(db, med_ret):
            _incorporar(acum, r, "B_retirado")

    if not acum:
        return {"candidatos": [], "aviso": None}

    # Cargar fotos batch
    fotos_map = _cargar_fotos_batch(db, list(acum.keys()))

    # Construir lista final con dias_diferencia y fotos
    ref_ts = pd.Timestamp(fecha_ref) if fecha_ref else None
    candidatos: list[dict] = []
    for num, d in acum.items():
        ts_raw = d.pop("_ts_raw", None)
        d["dias_diferencia"] = _dias_dif(ts_raw, ref_ts)
        d["origenes"] = sorted(d["origenes"])
        d["fotos"] = fotos_map.get(num, _fotos_vacias())
        candidatos.append(d)

    candidatos.sort(key=lambda x: (x["dias_diferencia"] is None, x["dias_diferencia"] or 0))
    return {"candidatos": candidatos, "aviso": None}


def rescatar_huerfanos_lote(
    db: Session,
    huerfanos: list[dict],
    dias_tolerancia: int,
) -> dict[str, dict]:
    """Aplica la política de auto-rescate a una lista de partes huérfanos.

    Args:
        huerfanos: lista de dicts con keys ``id_parte_hash``, ``suministro``,
            ``medidor_colocado``, ``medidor_retirado``, ``fecha_ref``.
        dias_tolerancia: umbral para considerar un candidato "cercano" (default 7).

    Returns:
        Dict ``{id_parte_hash: {clasificacion, ord_nro_asignado, candidatos}}`` donde
        ``clasificacion`` es ``"rescate_unico"`` (1 candidato ≤ tolerancia),
        ``"ambiguo_multiple"`` (N≥2 candidatos ≤ tolerancia), o ``"sin_match"``.
        Solo ``"rescate_unico"`` viene con ``ord_nro_asignado`` no-None.
    """
    out: dict[str, dict] = {}
    if not huerfanos:
        return out
    if not _hay_sync(db):
        log.warning("rescatar_huerfanos_lote: DB local sin sync — skip de %d huérfanos.", len(huerfanos))
        return out

    for h in huerfanos:
        resultado = buscar_candidatos_local(
            db,
            suministro=h.get("suministro"),
            nro_medidor_colocado=h.get("medidor_colocado"),
            nro_medidor_retirado=h.get("medidor_retirado"),
            fecha_ref=h.get("fecha_ref"),
        )
        candidatos_cercanos = [
            c for c in resultado["candidatos"]
            if c.get("dias_diferencia") is not None and c["dias_diferencia"] <= dias_tolerancia
        ]
        if len(candidatos_cercanos) == 1:
            clasif = "rescate_unico"
            ord_asignado = candidatos_cercanos[0]["ord_numero"]
        elif len(candidatos_cercanos) >= 2:
            clasif = "ambiguo_multiple"
            ord_asignado = None
        else:
            clasif = "sin_match"
            ord_asignado = None
        out[h["id_parte_hash"]] = {
            "clasificacion":     clasif,
            "ord_nro_asignado":  ord_asignado,
            "candidatos_cercanos": candidatos_cercanos,
        }
    return out


# ── Helpers ──────────────────────────────────────────────────────────────────

def _hay_sync(db: Session) -> bool:
    """True si al menos una vez se sincronizaron ordenativos."""
    return db.query(OrdenativoOracleLocal.ord_numero).limit(1).first() is not None


def _norm(val: str | None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s or None


def _ordenativos_por_medidor(
    db: Session,
    ste_numero: str,
) -> list[OrdenativoOracleLocal]:
    """Búsqueda B: medidor → suministros → ordenativos CE de esos suministros.

    Un mismo medidor puede haber estado asociado a varios suministros (instalaciones
    sucesivas). Buscamos en TODOS, no solo el más reciente — el motor de Etapa 3
    ya filtra por fecha; aquí queremos ver el universo completo y dejar que la
    política de tolerancia decida.
    """
    from sqlalchemy import select
    srvs_subq = (
        select(OrdenativoOracleEquipo.srv_codigo)
        .where(OrdenativoOracleEquipo.ste_numero == ste_numero)
        .distinct()
    )
    return (
        db.query(OrdenativoOracleLocal)
        .filter(OrdenativoOracleLocal.srv_codigo.in_(srvs_subq))
        .all()
    )


def _incorporar(acum: dict[int, dict], r: OrdenativoOracleLocal, origen: str) -> None:
    num = int(r.ord_numero)
    if num not in acum:
        acum[num] = {
            "ord_numero":        num,
            "srv_codigo":        r.srv_codigo or "",
            "tor_codigo":        r.tor_codigo or "",
            "ord_fecha_inicio":  _fmt_date(r.ord_fecha_inicio),
            "ord_fecha_fin":     _fmt_date(r.ord_fecha_fin),
            "sec_codigo_origen": r.sec_codigo_origen or "",
            "ord_estado":        r.ord_estado or "",
            "ord_resultado":     r.ord_resultado or "",
            "usr_nombre":        r.usr_nombre or "",
            "origenes":          set(),
            "_ts_raw":           r.ord_fecha_inicio,
        }
    acum[num]["origenes"].add(origen)


def _cargar_fotos_batch(db: Session, ord_numeros: list[int]) -> dict[int, dict]:
    if not ord_numeros:
        return {}
    rows = (
        db.query(OrdenativoOracleFoto)
        .filter(OrdenativoOracleFoto.ord_numero.in_(ord_numeros))
        .all()
    )
    out: dict[int, dict] = {}
    for r in rows:
        if r.ord_numero not in out:
            out[r.ord_numero] = _fotos_vacias()
        out[r.ord_numero][f"imagen_{r.posicion}"] = r.url
    return out


def _fotos_vacias() -> dict:
    return {f"imagen_{i + 1}": None for i in range(5)}


def _fmt_date(val) -> str | None:
    if val is None:
        return None
    try:
        return pd.Timestamp(val).strftime("%d/%m/%Y")
    except Exception:
        return None


def _dias_dif(ts_raw, ref_ts) -> int | None:
    if ts_raw is None or ref_ts is None:
        return None
    try:
        return abs((pd.Timestamp(ts_raw) - ref_ts).days)
    except Exception:
        return None
