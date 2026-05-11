"""
Helpers Oracle SIGEC residuales — quedaron solo dos consumidores:

  - ``_limpiar_url_firebase``: usado por ``oracle_sync_service`` y por las
    queries live de fotos. Limpia el formato sucio que la app móvil graba en
    ``OBO_INFO_ADICIONAL`` (mezcla path local + URL Firebase con `:` en vez
    de `=`).

  - ``get_fotos_por_ord_numeros``: fallback live a Oracle SIGEC para fotos
    cuando la DB local no las tiene (ORD_NRO previo al bootstrap del sync, o
    sync nunca corrido). Lo invoca ``parte_service._fotos_oracle_visor``.

La búsqueda de candidatos en vivo (``buscar_candidatos``) fue reemplazada por
``rescate_ordenativos_service.buscar_candidatos_local`` y removida — todo
consumo en runtime ahora va contra la DB local sincronizada.
"""
from __future__ import annotations

import logging
import re

from src.oracle_io import OracleReadOnly

log = logging.getLogger("api.services.oracle")

_FIREBASE_RE = re.compile(r"https?://\S+")

_CODIGOS_IMAGEN = ("APP4OBS_80", "APP4OBS_81", "APP4OBS_82", "APP4OBS_83", "APP4OBS_84")
_IMAGEN_MAP = {c: f"imagen_{i + 1}" for i, c in enumerate(_CODIGOS_IMAGEN)}


def _limpiar_url_firebase(raw: str) -> str | None:
    """Extrae la URL HTTPS limpia desde OBO_INFO_ADICIONAL (formato sucio app móvil).

    El campo suele venir como ``/storage/emulated/0/.../ORD123.jpg-https://firebasestorage.../?alt:media&token:xxx``.
    Devuelve la URL Firebase con los `:` reemplazados por `=` (codificación errónea de la app);
    si no hay URL HTTP en el string, devuelve ``None`` para descartar la imagen.
    """
    m = _FIREBASE_RE.search(raw)
    if not m:
        return None
    url = m.group(0)
    url = url.replace("?alt:media", "?alt=media").replace("&token:", "&token=")
    return url


def _sql_fotos_batch(ord_numeros: list[int]) -> str:
    nums = ", ".join(str(int(n)) for n in ord_numeros)
    codigos = ", ".join(f"'{c}'" for c in _CODIGOS_IMAGEN)
    return f"""
        SELECT ORD_NUMERO, TOB_CODIGO, OBO_INFO_ADICIONAL
        FROM xxsigec.xxco_observaciones_ordenativ_v
        WHERE ORD_NUMERO IN ({nums})
          AND TOB_CODIGO IN ({codigos})
    """


def get_fotos_por_ord_numeros(ord_numeros: list[int]) -> dict[int, dict]:
    """API pública: ``{ord_numero: {imagen_1: url|None, …, imagen_5: url|None}}``.

    Nunca lanza excepción; devuelve dict vacío si Oracle no está disponible.
    """
    if not ord_numeros:
        return {}
    try:
        with OracleReadOnly() as ora:
            return _cargar_fotos_batch(ora, ord_numeros)
    except Exception as e:
        log.warning("Oracle no disponible para fotos (ord_numeros=%s): %s", ord_numeros, e)
        return {}


def _cargar_fotos_batch(ora: OracleReadOnly, ord_numeros: list[int]) -> dict[int, dict]:
    """Devuelve ``{ord_numero: {imagen_1: url|None, …, imagen_5: url|None}}``."""
    empty = {f"imagen_{i + 1}": None for i in range(5)}
    if not ord_numeros:
        return {}
    try:
        df = ora.read_sql(_sql_fotos_batch(ord_numeros))
        result: dict[int, dict] = {}
        for _, row in df.iterrows():
            try:
                num = int(row["ORD_NUMERO"])
            except (TypeError, ValueError):
                continue
            if num not in result:
                result[num] = {**empty}
            campo = _IMAGEN_MAP.get(str(row.get("TOB_CODIGO", "")))
            val = row.get("OBO_INFO_ADICIONAL")
            if campo and val and str(val).strip():
                cleaned = _limpiar_url_firebase(str(val).strip())
                if cleaned:
                    result[num][campo] = cleaned
        return result
    except Exception as e:
        log.warning("Error cargando fotos batch: %s", e)
        return {}
