"""
Router para la consulta de la Bitácora de Auditoría.
Controlador HTTP — solo lectura (append-only desde los servicios).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from api.core.database import get_db
from api.db.models.domain_models import AuditoriaCambio
from api.schemas.auditoria_schemas import AuditoriaResponse, AuditoriaListResponse

router = APIRouter()


@router.get("/", response_model=AuditoriaListResponse, summary="Listar registros de auditoría")
def listar_auditoria(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    parte_id: int | None = Query(None, description="Filtrar por ID de parte procesado"),
    usuario_id: int | None = Query(None, description="Filtrar por ID de usuario auditor"),
    db: Session = Depends(get_db),
):
    """Devuelve los registros de auditoría (bitácora inmutable) con filtros opcionales."""
    query = db.query(AuditoriaCambio)

    if parte_id is not None:
        query = query.filter(AuditoriaCambio.parte_procesado_id == parte_id)
    if usuario_id is not None:
        query = query.filter(AuditoriaCambio.usuario_id == usuario_id)

    total = query.count()
    rows = (
        query.options(joinedload(AuditoriaCambio.usuario))
        .order_by(AuditoriaCambio.fecha_cambio.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return AuditoriaListResponse(
        total=total,
        items=[
            AuditoriaResponse(
                id=i.id,
                parte_procesado_id=i.parte_procesado_id,
                usuario_id=i.usuario_id,
                usuario_nombre=i.usuario.username if i.usuario else None,
                campo_modificado=i.campo_modificado,
                valor_anterior=i.valor_anterior,
                valor_nuevo=i.valor_nuevo,
                motivo=i.motivo,
                fecha_cambio=i.fecha_cambio,
                version_resultante=i.version_resultante,
            )
            for i in rows
        ],
    )
