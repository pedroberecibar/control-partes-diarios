"""
Servicio de Lotes — Capa de lógica de negocio para la ingesta de archivos.
Principio SOLID: Single Responsibility — este servicio solo orquesta lotes.
"""
import hashlib
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from api.core.database import BASE_DIR
from api.db.models.base_models import LoteArchivo, Contratista
from api.schemas.lote_schemas import LoteResponse, LoteListResponse

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
            .order_by(LoteArchivo.fecha_subida.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return LoteListResponse(
            total=total,
            items=[LoteResponse.model_validate(i) for i in items],
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
    ) -> LoteArchivo:
        """Crea un nuevo lote a partir de un archivo subido.

        Pasos:
        1. Valida que la contratista exista.
        2. Calcula el hash SHA256 (idempotencia).
        3. Si el hash ya existe → rechaza.
        4. Persiste el binario en `data/uploads/<sha256>.xlsx` (nombre por hash:
           idempotente, sin colisiones, sin caracteres problemáticos del nombre original).
        5. Persiste el registro `LoteArchivo` con `ruta_archivo` y estado RECIBIDO.
        """
        # 1. Validar contratista
        contratista = self.db.query(Contratista).filter(Contratista.id == contratista_id).first()
        if not contratista:
            raise ValueError(f"Contratista con id={contratista_id} no existe.")

        # 2. Hash del archivo
        hash_archivo = hashlib.sha256(contenido_bytes).hexdigest()

        # 3. Idempotencia
        existente = (
            self.db.query(LoteArchivo)
            .filter(LoteArchivo.hash_archivo == hash_archivo)
            .first()
        )
        if existente:
            logger.warning(
                "Archivo duplicado detectado (hash=%s...). Lote existente id=%d",
                hash_archivo[:12], existente.id,
            )
            raise ValueError(
                f"Este archivo ya fue subido anteriormente (lote_id={existente.id}, "
                f"estado={existente.estado}). Suba un archivo distinto o reprocese el lote existente."
            )

        # 4. Persistir binario en disco
        ruta_archivo = self._persistir_binario(hash_archivo, nombre_archivo, contenido_bytes)

        # 5. Persistir registro
        lote = LoteArchivo(
            nombre_archivo=nombre_archivo,
            hash_archivo=hash_archivo,
            ruta_archivo=str(ruta_archivo),
            contratista_id=contratista_id,
            estado="RECIBIDO",
            subido_por=subido_por,
        )
        self.db.add(lote)
        self.db.commit()
        self.db.refresh(lote)
        logger.info(
            "Lote creado: id=%d, archivo=%s, hash=%s..., ruta=%s",
            lote.id, nombre_archivo, hash_archivo[:12], ruta_archivo,
        )
        return lote

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
