"""
Servicio de Importación Masiva de Partes — mapea la salida del motor analítico
(DataFrames de Etapa 3 + Etapa 4) a los registros transaccionales SQL.

Responsabilidad única (SRP): convertir DataFrames del motor en filas de
`partes_diarios_raw`, `partes_diarios_procesados` y `parte_imagenes`. No conoce
HTTP, no conoce Excel, no conoce el motor — solo consume DataFrames ya producidos.

Invariante crítica: el `ID_PARTE_HASH` es la clave de matching raw ↔ procesado.
Como el motor calcula ese hash usando `Suministro_Final` (post-cruces, no
disponible en el adapter), los raws se crean DESPUÉS del motor con el mismo
hash que los procesados. El payload original del Excel se recupera de `df_aux`
vía `ID_Externo` cuando está disponible, o se cae al row del propio `df_final`.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from api.db.models.domain_models import (
    ParteDiarioProcesado,
    ParteDiarioRaw,
    ParteImagen,
)

log = logging.getLogger("api.services.parte_import")


# Mapeo de las 8 observaciones del motor (`_APP_<COL>` en df_final tras Etapa 4)
# a las columnas booleanas del modelo. El orden es el mismo de `src/config.OBS_COLS`.
_OBS_MAPPING: list[tuple[str, str]] = [
    ("_APP_GABINETE",                       "obs_gabinete"),
    ("_APP_SUBTERRANEO",                    "obs_subterraneo"),
    ("_APP_ALTURA",                         "obs_altura"),
    ("_APP_AEREO",                          "obs_aereo"),
    ("_APP_EQUIPO_MEDICION_REEMPLAZADO",    "obs_equipo_medicion_reemplazado"),
    ("_APP_ACOMETIDA_REALIZADA",            "obs_acometida_realizada"),
    ("_APP_TAPA_REEMPLAZADA",               "obs_tapa_reemplazada"),
    ("_APP_EQUIPO_DE_MEDICION_INSTALADO",   "obs_equipo_medicion_instalado"),
]


class ParteImportService:
    """Importa los resultados del motor a la base transaccional."""

    def __init__(self, db: Session):
        self.db = db

    def importar_lote(
        self,
        lote_id: int,
        contratista_id: int,
        df_aux: pd.DataFrame,
        df_final: pd.DataFrame,
        df_img: pd.DataFrame | None,
    ) -> dict[str, int]:
        """Crea raws + procesados + imágenes en una sola transacción lógica.

        El caller (worker) decide cuándo hacer commit/rollback.

        Devuelve métricas: `{"raws": N, "procesados": N, "imagenes": N}`.
        """
        if df_final.empty:
            log.warning("df_final vacío — no hay nada para importar (lote_id=%d).", lote_id)
            return {"raws": 0, "procesados": 0, "imagenes": 0}

        # Idempotencia: limpiar datos de un intento previo del mismo lote.
        self._limpiar_lote_previo(lote_id)

        # Dedup intra-batch: conservar primera ocurrencia de cada hash.
        if "ID_PARTE_HASH" in df_final.columns:
            n_antes = len(df_final)
            df_final = df_final.drop_duplicates(subset=["ID_PARTE_HASH"], keep="first")
            n_dup = n_antes - len(df_final)
            if n_dup:
                log.warning("importar_lote — %d filas con ID_PARTE_HASH duplicado descartadas.", n_dup)

        # Excluir hashes ya existentes en otros lotes (colisión cross-lote).
        df_final = self._excluir_hashes_existentes(df_final, lote_id)

        if df_final.empty:
            log.warning("importar_lote — df_final vacío tras dedup/exclusión (lote_id=%d).", lote_id)
            return {"raws": 0, "procesados": 0, "imagenes": 0}

        raws_by_hash = self._crear_raws(lote_id, df_aux, df_final)
        procesados_by_hash = self._crear_procesados(
            lote_id, contratista_id, df_final, raws_by_hash
        )
        n_imgs = self._crear_imagenes(df_final, df_img, procesados_by_hash)

        return {
            "raws": len(raws_by_hash),
            "procesados": len(procesados_by_hash),
            "imagenes": n_imgs,
        }

    # ------------------------------------------------------------------
    # Raws — un registro por fila procesada por el motor
    # ------------------------------------------------------------------

    def _crear_raws(
        self,
        lote_id: int,
        df_aux: pd.DataFrame,
        df_final: pd.DataFrame,
    ) -> dict[str, ParteDiarioRaw]:
        """Crea `ParteDiarioRaw` con `id_parte_hash` consistente con el motor.

        Recupera el payload original del Excel uniendo por `ID_Externo` con
        `df_aux` cuando esté disponible. Si no, persiste el row del propio
        `df_final` como fallback (sigue siendo trazable).
        """
        df_aux_lookup = self._index_df_aux_por_id_externo(df_aux)

        raws: list[ParteDiarioRaw] = []
        for fila_idx, row in df_final.reset_index(drop=True).iterrows():
            id_parte_hash = row.get("ID_PARTE_HASH")
            if not id_parte_hash or pd.isna(id_parte_hash):
                log.warning("Fila %d sin ID_PARTE_HASH — descartada.", fila_idx)
                continue

            id_externo = row.get("ID_EXTERNO") or row.get("ID_Externo")
            id_externo = self._safe_str(id_externo)

            payload = self._recuperar_payload_original(df_aux_lookup, id_externo, row)

            raws.append(ParteDiarioRaw(
                lote_id=lote_id,
                fila_excel=int(fila_idx),  # 0-based — alineado con la decisión del usuario
                id_externo=id_externo,
                id_parte_hash=str(id_parte_hash),
                datos_crudos=payload,
            ))

        if not raws:
            return {}

        self.db.add_all(raws)
        self.db.flush()  # asigna IDs sin commitear
        return {r.id_parte_hash: r for r in raws}

    @staticmethod
    def _index_df_aux_por_id_externo(df_aux: pd.DataFrame) -> dict[str, dict[str, Any]]:
        """Devuelve un dict {ID_Externo (str) → row dict} si la col existe."""
        col_id = next(
            (c for c in ("ID_Externo", "ID_EXTERNO", "id_externo") if c in df_aux.columns),
            None,
        )
        if col_id is None:
            return {}
        df = df_aux.set_index(col_id, drop=False)
        return {str(k): _row_to_jsonable_dict(v) for k, v in df.iterrows()}

    @staticmethod
    def _recuperar_payload_original(
        df_aux_lookup: dict[str, dict[str, Any]],
        id_externo: str | None,
        row: pd.Series,
    ) -> dict[str, Any]:
        if id_externo and id_externo in df_aux_lookup:
            return df_aux_lookup[id_externo]
        return _row_to_jsonable_dict(row)

    # ------------------------------------------------------------------
    # Procesados — un registro por hash, asociado al raw correspondiente
    # ------------------------------------------------------------------

    def _crear_procesados(
        self,
        lote_id: int,
        contratista_id: int,
        df_final: pd.DataFrame,
        raws_by_hash: dict[str, ParteDiarioRaw],
    ) -> dict[str, ParteDiarioProcesado]:
        procesados: list[ParteDiarioProcesado] = []
        for _, row in df_final.iterrows():
            id_parte_hash = row.get("ID_PARTE_HASH")
            if not id_parte_hash or pd.isna(id_parte_hash):
                continue

            raw = raws_by_hash.get(str(id_parte_hash))
            if raw is None:
                log.warning("Procesado sin raw match (hash=%s) — descartado.", str(id_parte_hash)[:12])
                continue

            procesados.append(ParteDiarioProcesado(
                raw_id=raw.id,
                id_parte_hash=str(id_parte_hash),
                lote_id=lote_id,
                contratista_id=contratista_id,

                # Datos del parte
                suministro=self._safe_str(row.get("SUMINISTRO_RAW")),
                fecha_ejecucion=self._safe_datetime(row.get("FECHA")),
                nro_medidor_retirado=self._safe_str(row.get("NRO_EQP_RETIRADO")),
                nro_medidor_colocado=self._safe_str(row.get("NRO_EQP_COLOCADO")),
                usr_id=self._safe_int(row.get("USR_ID")),

                # Resultado del waterfall
                ord_nro=self._safe_int(row.get("ORD_NRO")),
                cod_epec=self._safe_int(row.get("CODIGO_EPEC")),
                id_estado=int(row["ID_ESTADO"]),    # nullable=False — fail-fast si falta
                id_traza=int(row["ID_TRAZA"]),       # nullable=False — fail-fast si falta

                # Control de obs (Etapa 4) — pueden no estar si el parte no fue procesado por E4
                cod_epec_sugerido=self._safe_int(row.get("COD_EPEC_SUGERIDO")),
                valor_uses_origen=self._safe_float(row.get("VALOR_USES_ORIGEN")),
                valor_uses_obs=self._safe_float(row.get("VALOR_USES_OBS")),
                diferencia_uses=self._safe_float(row.get("DIFERENCIA_USES")),
                tipo_discrepancia=self._safe_str(row.get("DISCREPANCIA_CODIGO")),

                # 8 observaciones de la app móvil
                **self._extraer_observaciones(row),

                # Auditoría
                fue_corregido=bool(row.get("FUE_CORREGIDO", False)),

                # Snapshot completo para debug / export
                metricas_analitica=_row_to_jsonable_dict(row),
            ))

        if not procesados:
            return {}

        self.db.add_all(procesados)
        self.db.flush()
        return {p.id_parte_hash: p for p in procesados}

    @classmethod
    def _extraer_observaciones(cls, row: pd.Series) -> dict[str, bool]:
        """Mapea las cols `_APP_*` (0/1 ints del motor) a los booleans del modelo."""
        out: dict[str, bool] = {}
        for col_motor, col_modelo in _OBS_MAPPING:
            val = row.get(col_motor)
            out[col_modelo] = bool(val) if pd.notna(val) else False
        return out

    # ------------------------------------------------------------------
    # Imágenes — fan-out 1-5 por parte vía ORD_NRO
    # ------------------------------------------------------------------

    def _crear_imagenes(
        self,
        df_final: pd.DataFrame,
        df_img: pd.DataFrame | None,
        procesados_by_hash: dict[str, ParteDiarioProcesado],
    ) -> int:
        if df_img is None or df_img.empty or "ORD_NRO" not in df_img.columns:
            return 0

        # Mapa ORD_NRO → fila de imágenes (las cols son IMAGEN_1..IMAGEN_5).
        df_img_indexed = df_img.set_index("ORD_NRO")

        # Mapa ID_PARTE_HASH → ORD_NRO (un parte tiene un único ord; varios partes
        # pueden compartir el mismo ord — todos ven las mismas fotos).
        if "ORD_NRO" not in df_final.columns:
            return 0
        hash_to_ord = (
            df_final.dropna(subset=["ORD_NRO", "ID_PARTE_HASH"])
            .set_index("ID_PARTE_HASH")["ORD_NRO"]
            .to_dict()
        )

        n_total = 0
        for id_parte_hash, parte in procesados_by_hash.items():
            ord_nro = hash_to_ord.get(id_parte_hash)
            if ord_nro is None or pd.isna(ord_nro):
                continue
            try:
                img_row = df_img_indexed.loc[ord_nro]
            except KeyError:
                continue
            # Si hay múltiples filas en df_img con el mismo ord_nro (no debería),
            # tomar la primera para evitar fan-out.
            if isinstance(img_row, pd.DataFrame):
                img_row = img_row.iloc[0]

            for orden in range(1, 6):
                url = img_row.get(f"IMAGEN_{orden}")
                if url is None or pd.isna(url) or str(url).strip() == "":
                    continue
                self.db.add(ParteImagen(
                    parte_procesado_id=parte.id,
                    orden=orden,
                    url=str(url),
                ))
                n_total += 1

        if n_total > 0:
            self.db.flush()
        return n_total

    # ------------------------------------------------------------------
    # Casts seguros — el motor produce dtypes pandas (Int64, Float64) que
    # SQLAlchemy no acepta directamente. Convertimos a tipos Python nativos.
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if value is None or pd.isna(value):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_str(value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        s = str(value).strip()
        return s if s else None

    @staticmethod
    def _safe_datetime(value: Any):
        if value is None or pd.isna(value):
            return None
        if isinstance(value, pd.Timestamp):
            return value.to_pydatetime()
        return value

    def _limpiar_lote_previo(self, lote_id: int) -> None:
        """Elimina procesados, raws e imágenes de un intento previo del mismo lote."""
        n = (
            self.db.query(ParteDiarioProcesado)
            .filter(ParteDiarioProcesado.lote_id == lote_id)
            .delete(synchronize_session=False)
        )
        self.db.query(ParteDiarioRaw).filter(
            ParteDiarioRaw.lote_id == lote_id
        ).delete(synchronize_session=False)
        if n:
            log.info("_limpiar_lote_previo — %d procesados eliminados para lote %d.", n, lote_id)

    def _excluir_hashes_existentes(self, df_final: pd.DataFrame, lote_id: int) -> pd.DataFrame:
        """Descarta filas cuyo hash ya existe en procesados de otro lote."""
        if "ID_PARTE_HASH" not in df_final.columns:
            return df_final
        all_hashes = df_final["ID_PARTE_HASH"].dropna().unique().tolist()
        if not all_hashes:
            return df_final
        existing = {
            row[0]
            for row in self.db.query(ParteDiarioProcesado.id_parte_hash)
            .filter(ParteDiarioProcesado.id_parte_hash.in_(all_hashes))
            .all()
        }
        if existing:
            n = int(df_final["ID_PARTE_HASH"].isin(existing).sum())
            log.warning(
                "_excluir_hashes_existentes — %d partes con hash ya en otro lote descartados (lote_id=%d).",
                n, lote_id,
            )
            df_final = df_final[~df_final["ID_PARTE_HASH"].isin(existing)].copy()
        return df_final


def _row_to_jsonable_dict(row: pd.Series | dict) -> dict[str, Any]:
    """Convierte una Serie/dict de pandas a un dict JSON-serializable.

    NaN → None, Timestamp → ISO string, numpy scalars → tipos Python.
    """
    if isinstance(row, dict):
        items = row.items()
    else:
        items = row.to_dict().items()

    out: dict[str, Any] = {}
    for k, v in items:
        if v is None:
            out[k] = None
        elif isinstance(v, pd.Timestamp):
            out[k] = v.isoformat()
        elif isinstance(v, (datetime.date, datetime.datetime)):
            out[k] = v.isoformat()
        elif isinstance(v, float) and pd.isna(v):
            out[k] = None
        elif pd.isna(v) if not isinstance(v, (list, dict)) else False:
            out[k] = None
        else:
            try:
                # numpy scalars → Python natives
                out[k] = v.item() if hasattr(v, "item") else v
            except (AttributeError, ValueError):
                out[k] = str(v)
    return out
