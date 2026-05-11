"""
Servicio de Lotes — Capa de lógica de negocio para la ingesta de archivos.
Principio SOLID: Single Responsibility — este servicio solo orquesta lotes.
"""
import logging
from collections import defaultdict
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from api.core.database import BASE_DIR, SessionLocal
from api.db.models.base_models import LoteArchivo, Contratista
from api.db.models.domain_models import ParteDiarioProcesado
from api.schemas.lote_schemas import LoteResponse, LoteListResponse
from api.services.adapter_dispatcher import ejecutar_adapter
from api.services.exceptions import (
    DuplicadoBytesError,
    DuplicadoContenidoError,
    OverlapWarning,
)
from api.services.hash_service import hash_bytes, hash_contenido_normalizado
from api.services.parte_dedup_helpers import contar_overlap_business_keys
from src.config import OVERLAP_WARNING_THRESHOLD

logger = logging.getLogger("api.services.lote")


# Carpeta de uploads — alineada con `BASE_DIR` (python-version/) ya usada en database.py.
# Los binarios se conservan indefinidamente para auditoría.
UPLOADS_DIR = Path(BASE_DIR) / "data" / "uploads"


class LoteService:
    """Servicio para operaciones sobre lotes de archivos."""

    def __init__(self, db: Session):
        self.db = db

    def listar_lotes(self, skip: int = 0, limit: int = 50) -> LoteListResponse:
        """Lista todos los lotes ordenados por fecha de subida descendente."""
        total = self.db.query(LoteArchivo).count()
        items = (
            self.db.query(LoteArchivo)
            .options(joinedload(LoteArchivo.contratista), joinedload(LoteArchivo.usuario))
            .order_by(LoteArchivo.fecha_subida.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        lote_ids = [i.id for i in items]
        # Single grouped query: counts per (lote_id, id_estado)
        counts_rows = (
            self.db.query(
                ParteDiarioProcesado.lote_id,
                ParteDiarioProcesado.id_estado,
                func.count(ParteDiarioProcesado.id).label("cnt"),
            )
            .filter(ParteDiarioProcesado.lote_id.in_(lote_ids))
            .group_by(ParteDiarioProcesado.lote_id, ParteDiarioProcesado.id_estado)
            .all()
        )
        # Build {lote_id: {id_estado: cnt}}
        counts: dict[int, dict[int, int]] = defaultdict(dict)
        for lote_id, id_estado, cnt in counts_rows:
            counts[lote_id][id_estado] = cnt

        def _build_response(lote: LoteArchivo) -> LoteResponse:
            c = counts.get(lote.id, {})
            n_aprobados    = c.get(1, 0)
            n_revision     = c.get(2, 0)
            n_rechazado    = c.get(3, 0)
            n_fuera_alcance = c.get(4, 0)
            total_filas    = sum(c.values())
            data = {
                "id": lote.id,
                "nombre_archivo": lote.nombre_archivo,
                "hash_archivo": lote.hash_archivo,
                "contratista_id": lote.contratista_id,
                "contratista_nombre": lote.contratista.nombre if lote.contratista else None,
                "estado": lote.estado,
                "subido_por": lote.subido_por,
                "usuario_nombre": lote.usuario.username if lote.usuario else None,
                "fecha_subida": lote.fecha_subida,
                "detalle_error": lote.detalle_error,
                "paso_actual": lote.paso_actual,
                "progreso_pct": lote.progreso_pct or 0,
                "total_filas": total_filas,
                "n_aprobados": n_aprobados,
                "n_revision": n_revision,
                "n_rechazado": n_rechazado,
                "n_fuera_alcance": n_fuera_alcance,
            }
            return LoteResponse.model_validate(data)

        return LoteListResponse(
            total=total,
            items=[_build_response(i) for i in items],
        )

    def obtener_lote(self, lote_id: int) -> LoteArchivo | None:
        """Obtiene un lote por su ID."""
        return self.db.query(LoteArchivo).filter(LoteArchivo.id == lote_id).first()

    def crear_lote(
        self,
        nombre_archivo: str,
        contenido_bytes: bytes,
        contratista_id: int,
        subido_por: int,
        force: bool = False,
    ) -> LoteArchivo:
        """Crea un nuevo lote aplicando antiduplicidad de tres capas.

        Capa 1 — `hash_archivo` (SHA256 de los bytes). El UNIQUE en DB cierra
                 race conditions: dos POSTs concurrentes con los mismos bytes
                 producen `IntegrityError` en uno de los dos.
        Capa 2 — `hash_contenido` (SHA256 del df_aux normalizado tras parsear
                 con el adapter). Detecta el caso "Excel re-guardado" (bytes
                 distintos pero contenido idéntico).
        Capa 3 — Overlap soft-warning: cuenta cuántas parejas (Suministro, Fecha)
                 del nuevo lote ya existen para el contratista. Si la fracción
                 supera `OVERLAP_WARNING_THRESHOLD`, levanta `OverlapWarning`
                 (HTTP 409 con `requires_force`) salvo que el caller pase
                 `force=True`.

        Excepciones:
            * `ValueError`         — contratista inexistente.
            * `DuplicadoBytesError` — Capa 1.
            * `DuplicadoContenidoError` — Capa 2.
            * `OverlapWarning`      — Capa 3 (sólo si `force=False`).
        """
        contratista = self.db.query(Contratista).filter(Contratista.id == contratista_id).first()
        if not contratista:
            raise ValueError(f"Contratista con id={contratista_id} no existe.")

        # ---------- Capa 1 — bytes ----------
        hash_arch = hash_bytes(contenido_bytes)
        ruta_archivo = self._persistir_binario(hash_arch, nombre_archivo, contenido_bytes)

        lote = LoteArchivo(
            nombre_archivo=nombre_archivo,
            hash_archivo=hash_arch,
            hash_contenido=None,  # Se completa tras Capa 2
            ruta_archivo=str(ruta_archivo),
            contratista_id=contratista_id,
            estado="RECIBIDO",
            subido_por=subido_por,
            paso_actual="RECIBIENDO",
            progreso_pct=0,
        )
        self.db.add(lote)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existente = (
                self.db.query(LoteArchivo)
                .filter(LoteArchivo.hash_archivo == hash_arch)
                .first()
            )
            existente_id = existente.id if existente else 0
            logger.warning(
                "Capa 1 — archivo duplicado por bytes (hash=%s...). Lote existente id=%d",
                hash_arch[:12], existente_id,
            )
            raise DuplicadoBytesError(existente_id)
        self.db.refresh(lote)

        # ---------- Capa 2 — contenido normalizado ----------
        try:
            df_aux = ejecutar_adapter(Path(ruta_archivo), contratista.nombre)
        except Exception as e:
            # Si el adapter explota, dejamos pasar el lote (el worker volverá a
            # intentar y rechazará con detalle_error). Sin contenido parseable
            # no podemos calcular hash_contenido ni overlap.
            logger.warning("Capa 2 — adapter falló parseando %s: %s. Continuando sin hash_contenido.",
                           ruta_archivo, e)
            df_aux = None

        hash_cont: str | None = None
        if df_aux is not None and not df_aux.empty:
            hash_cont = hash_contenido_normalizado(df_aux)
            lote.hash_contenido = hash_cont
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                existente = (
                    self.db.query(LoteArchivo)
                    .filter(LoteArchivo.hash_contenido == hash_cont)
                    .first()
                )
                existente_id = existente.id if existente else 0
                logger.warning(
                    "Capa 2 — contenido duplicado (hash_contenido=%s...). Lote existente id=%d",
                    hash_cont[:12], existente_id,
                )
                self._rollback_lote(lote.id, ruta_archivo)
                raise DuplicadoContenidoError(existente_id)
            self.db.refresh(lote)

        # ---------- Capa 3 — overlap warning ----------
        if not force and df_aux is not None and not df_aux.empty:
            n_existentes, n_total = contar_overlap_business_keys(
                self.db, contratista_id, df_aux
            )
            if n_total > 0 and (n_existentes / n_total) > OVERLAP_WARNING_THRESHOLD:
                overlap_pct = n_existentes / n_total
                logger.info(
                    "Capa 3 — overlap %.0f%% (%d/%d) supera threshold para lote_id=%d, "
                    "se requiere force.",
                    overlap_pct * 100, n_existentes, n_total, lote.id,
                )
                self._rollback_lote(lote.id, ruta_archivo)
                raise OverlapWarning(overlap_pct, n_existentes, n_total)

        logger.info(
            "Lote creado: id=%d, archivo=%s, hash_bytes=%s..., hash_contenido=%s, ruta=%s",
            lote.id, nombre_archivo, hash_arch[:12],
            (hash_cont[:12] + "...") if hash_cont else "<none>",
            ruta_archivo,
        )
        return lote

    def _rollback_lote(self, lote_id: int, ruta_archivo: Path) -> None:
        """Elimina el registro `LoteArchivo` y el binario en disco.

        Llamado cuando una capa rechaza el lote después de que ya se persistió
        parcialmente. El binario solo se borra si no es referenciado por otro
        lote (caso edge: hash colisión imposible vía SHA256, pero defensivo).
        """
        lote = self.db.query(LoteArchivo).filter(LoteArchivo.id == lote_id).first()
        if lote is not None:
            self.db.delete(lote)
            self.db.commit()
        try:
            otros = (
                self.db.query(LoteArchivo)
                .filter(LoteArchivo.ruta_archivo == str(ruta_archivo))
                .count()
            )
            if otros == 0 and Path(ruta_archivo).exists():
                Path(ruta_archivo).unlink()
        except Exception as e:
            logger.warning("No se pudo limpiar binario %s tras rollback: %s", ruta_archivo, e)

    def actualizar_progreso(self, lote_id: int, paso: str, pct: int) -> None:
        """Actualiza `paso_actual` y `progreso_pct` con sesión propia.

        Usado por el worker en cada transición. Sesión propia para no enredar
        la transacción larga del worker (que puede hacer rollback masivo en
        caso de error del motor).
        """
        try:
            with SessionLocal() as session:
                lote = session.query(LoteArchivo).filter(LoteArchivo.id == lote_id).first()
                if lote is None:
                    return
                lote.paso_actual = paso
                lote.progreso_pct = max(0, min(100, int(pct)))
                session.commit()
        except Exception as e:
            # En SQLite, esto puede fallar por "database is locked" si el worker
            # tiene una transacción abierta con flushes pendientes.
            # No es crítico: preferimos seguir procesando que fallar por un log de progreso.
            logger.warning("No se pudo actualizar progreso del lote %d (%s): %s", lote_id, paso, e)

    def actualizar_estado(self, lote_id: int, nuevo_estado: str, detalle_error: str | None = None) -> LoteArchivo:
        """Actualiza el estado de un lote (usado por el worker de procesamiento)."""
        lote = self.obtener_lote(lote_id)
        if not lote:
            raise ValueError(f"Lote con id={lote_id} no existe.")
        lote.estado = nuevo_estado
        if detalle_error:
            lote.detalle_error = detalle_error
        self.db.commit()
        self.db.refresh(lote)
        return lote

    @staticmethod
    def _persistir_binario(hash_archivo: str, nombre_original: str, contenido: bytes) -> Path:
        """Guarda el binario en `data/uploads/<sha256><ext>`. Devuelve el path absoluto.

        Naming por hash: idempotente y libre de caracteres problemáticos. La extensión
        viene del archivo original para preservar la semántica al reabrir.
        """
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        extension = Path(nombre_original).suffix or ".xlsx"
        ruta = UPLOADS_DIR / f"{hash_archivo}{extension}"
        # Si ya existe (reintento tras crash entre persistencia y commit), no re-escribir.
        if not ruta.exists():
            ruta.write_bytes(contenido)
        return ruta
