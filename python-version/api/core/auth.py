"""Auth dependencies — validación liviana basada en header X-Usuario-Id.

Estado del sistema: no hay middleware de auth real (JWT/OAuth). Los endpoints
sensibles se protegen pidiendo al frontend que envíe `X-Usuario-Id` con el id
del usuario logueado, y este módulo valida que el usuario exista y tenga el rol
necesario.

Cuando se implemente auth real, reemplazar `_resolver_usuario_por_header` por
una validación de JWT / sesión, manteniendo la firma de `require_admin` y
`get_current_user` intacta para no romper los endpoints que las usan.
"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.db.models.base_models import UsuarioApp


def _resolver_usuario_por_header(
    usuario_id: int | None,
    db: Session,
) -> UsuarioApp:
    if usuario_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Falta header X-Usuario-Id.",
        )
    usuario = db.query(UsuarioApp).filter(UsuarioApp.id == usuario_id).first()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Usuario id={usuario_id} no existe.",
        )
    if not usuario.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo.",
        )
    return usuario


def get_current_user(
    x_usuario_id: int | None = Header(default=None, alias="X-Usuario-Id"),
    db: Session = Depends(get_db),
) -> UsuarioApp:
    """Resuelve el usuario logueado desde el header. Útil para endpoints que
    necesitan saber quién hace la acción pero no requieren rol específico."""
    return _resolver_usuario_por_header(x_usuario_id, db)


def require_admin(
    usuario: UsuarioApp = Depends(get_current_user),
) -> UsuarioApp:
    """Dependency que rechaza con 403 si el usuario no tiene rol 'admin'."""
    if usuario.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operación restringida al rol admin (usuario tiene rol='{usuario.rol}').",
        )
    return usuario
