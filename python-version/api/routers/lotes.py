"""
Router para la gestión de Lotes de Archivos.
Controlador HTTP — delega toda la lógica al LoteService.
"""
import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File, Query, BackgroundTasks
from api.services.worker import procesar_lote_en_background
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.schemas.lote_schemas import LoteResponse, LoteListResponse, PreviewColumnasResponse
from api.services.exceptions import (
    DuplicadoBytesError,
    DuplicadoContenidoError,
    OverlapWarning,
)
from api.services.lote_service import LoteService

router = APIRouter()


@router.post("/preview-columnas", response_model=PreviewColumnasResponse, summary="Detectar columnas del archivo")
async def preview_columnas(
    archivo: UploadFile = File(..., description="Archivo Excel (.xlsx / .xls / .csv)"),
    contratista_id: int = Query(..., description="ID de la contratista"),
    db: Session = Depends(get_db),
):
    """Lee el encabezado del archivo y devuelve columnas detectadas con mapeo sugerido.

    Sin efecto en DB — solo lectura del archivo para inferir el mapeo.
    """
    from api.db.models.base_models import Contratista
    from api.services.columnas_preview_service import detectar_columnas

    contratista = db.query(Contratista).filter(Contratista.id == contratista_id).first()
    if not contratista:
        raise HTTPException(status_code=400, detail=f"Contratista con id={contratista_id} no existe.")

    contenido = await archivo.read()
    suffix = Path(archivo.filename or "file.xlsx").suffix or ".xlsx"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contenido)
        tmp_path = Path(tmp.name)

    try:
        resultado = detectar_columnas(tmp_path, contratista.nombre)
    finally:
        tmp_path.unlink(missing_ok=True)

    return PreviewColumnasResponse(**resultado)


@router.get("/", response_model=LoteListResponse, summary="Listar lotes")
def listar_lotes(
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(50, ge=1, le=200, description="Cantidad máxima de resultados"),
    db: Session = Depends(get_db),
):
    """Devuelve todos los lotes de archivos subidos, ordenados por fecha descendente."""
    service = LoteService(db)
    return service.listar_lotes(skip=skip, limit=limit)


@router.get("/{lote_id}", response_model=LoteResponse, summary="Detalle de un lote")
def obtener_lote(lote_id: int, db: Session = Depends(get_db)):
    """Devuelve el detalle de un lote específico por su ID."""
    service = LoteService(db)
    lote = service.obtener_lote(lote_id)
    if not lote:
        raise HTTPException(status_code=404, detail=f"Lote con id={lote_id} no encontrado.")
    return LoteResponse.model_validate(lote)


@router.post("/", response_model=LoteResponse, status_code=201, summary="Subir un nuevo lote")
async def crear_lote(
    background_tasks: BackgroundTasks,
    contratista_id: int = Query(..., description="ID de la contratista"),
    subido_por: int = Query(..., description="ID del usuario que sube"),
    force: bool = Query(False, description="Si True, omite el warning de overlap (Capa 3)"),
    archivo: UploadFile = File(..., description="Archivo Excel (.xlsx / .xls / .csv)"),
    mapeo_columnas: str | None = Form(None, description='JSON {"col_excel":"campo_canonico",...} o null'),
    db: Session = Depends(get_db),
):
    """Sube un archivo Excel y crea un registro de lote con estado RECIBIDO.

    Antiduplicidad de tres capas (ver `LoteService.crear_lote`):
        * 409 `DUP_BYTES`     — los bytes coinciden con un lote previo.
        * 409 `DUP_CONTENT`   — el contenido lógico coincide con un lote previo.
        * 409 `OVERLAP_WARN`  — la mayoría de los partes ya existen; reintentar
                                con `?force=true` si se quiere continuar.
    """
    contenido = await archivo.read()

    # Validar JSON del mapeo si se proveyó
    if mapeo_columnas:
        try:
            json.loads(mapeo_columnas)
        except ValueError:
            raise HTTPException(status_code=400, detail="mapeo_columnas no es JSON válido.")

    service = LoteService(db)
    try:
        lote = service.crear_lote(
            nombre_archivo=archivo.filename or "sin_nombre.xlsx",
            contenido_bytes=contenido,
            contratista_id=contratista_id,
            subido_por=subido_por,
            force=force,
            mapeo_columnas=mapeo_columnas,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicadoBytesError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": e.code,
                "lote_existente_id": e.lote_existente_id,
                "mensaje": str(e),
            },
        )
    except DuplicadoContenidoError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": e.code,
                "lote_existente_id": e.lote_existente_id,
                "mensaje": str(e),
            },
        )
    except OverlapWarning as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": e.code,
                "overlap_pct": e.overlap_pct,
                "n_existentes": e.n_existentes,
                "n_total": e.n_total,
                "requires_force": True,
                "mensaje": str(e),
            },
        )

    # Lanzar procesamiento en background
    background_tasks.add_task(procesar_lote_en_background, lote.id)

    return LoteResponse.model_validate(lote)


@router.post("/{lote_id}/reprocesar", response_model=LoteResponse, summary="Reprocesar un lote existente")
def reprocesar_lote(
    lote_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Resetea el estado del lote a RECIBIDO y vuelve a lanzar el worker de procesamiento.

    Útil para reintentar lotes que terminaron en ERROR sin necesidad de re-subir el archivo.
    El binario original persiste en `data/uploads/` y se reutiliza tal cual.
    """
    from api.db.models.base_models import LoteArchivo
    lote = db.query(LoteArchivo).filter(LoteArchivo.id == lote_id).first()
    if not lote:
        raise HTTPException(status_code=404, detail=f"Lote con id={lote_id} no encontrado.")
    lote.estado = "RECIBIDO"
    lote.detalle_error = None
    db.commit()
    db.refresh(lote)
    background_tasks.add_task(procesar_lote_en_background, lote.id)
    return LoteResponse.model_validate(lote)


@router.patch("/{lote_id}/estado", response_model=LoteResponse, summary="Actualizar estado del lote")
def actualizar_estado_lote(
    lote_id: int,
    nuevo_estado: str = Query(..., description="Nuevo estado (PROCESANDO, COMPLETADO, ERROR, etc.)"),
    detalle_error: str | None = Query(None, description="Detalle del error si aplica"),
    db: Session = Depends(get_db),
):
    """Actualiza el estado de un lote. Usado internamente por el worker de procesamiento."""
    service = LoteService(db)
    try:
        lote = service.actualizar_estado(lote_id, nuevo_estado, detalle_error)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return LoteResponse.model_validate(lote)
