"""blindaje_antiduplicidad_y_progreso

Revision ID: af1bd02aea31
Revises: e3ff7d8f9492
Create Date: 2026-05-08 09:00:00.000000

Cambios:
- `lotes_archivos.hash_archivo` pasa a UNIQUE (cierra race condition al subir).
- `lotes_archivos.hash_contenido` (String(64), UNIQUE, nullable) — Capa 2:
    detecta uploads con bytes distintos pero contenido lógico idéntico
    (caso "Excel re-guardado"). Nullable para tolerar lotes pre-existentes.
- `lotes_archivos.paso_actual` (String(40), nullable) — paso del worker.
- `lotes_archivos.progreso_pct` (Integer, default 0) — porcentaje 0-100.

Pre-flight: si ya existen filas con `hash_archivo` duplicado (carga previa
al blindaje), todas excepto la primera se marcan como RECHAZADO con
`detalle_error="duplicado-pre-blindaje"`. Esto permite aplicar el constraint
UNIQUE sin perder filas y deja huella en la auditoría.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'af1bd02aea31'
down_revision: Union[str, Sequence[str], None] = 'e3ff7d8f9492'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Pre-flight: marcar duplicados de hash_archivo previos como RECHAZADO.
    #    Conserva la primera ocurrencia (menor id) por hash y rechaza las demás.
    bind.execute(
        sa.text(
            """
            UPDATE lotes_archivos
            SET estado = 'RECHAZADO',
                detalle_error = COALESCE(detalle_error, '') ||
                                CASE WHEN COALESCE(detalle_error, '') = '' THEN '' ELSE ' | ' END ||
                                'duplicado-pre-blindaje'
            WHERE id IN (
                SELECT l.id
                FROM lotes_archivos l
                JOIN (
                    SELECT hash_archivo, MIN(id) AS keeper_id
                    FROM lotes_archivos
                    GROUP BY hash_archivo
                    HAVING COUNT(*) > 1
                ) d ON d.hash_archivo = l.hash_archivo
                WHERE l.id <> d.keeper_id
            )
            """
        )
    )

    # 2. Cambios estructurales — batch_alter_table soporta SQLite (recreate-table strategy).
    with op.batch_alter_table('lotes_archivos') as batch_op:
        # Recrear índice de hash_archivo como UNIQUE
        batch_op.drop_index('ix_lotes_archivos_hash_archivo')
        batch_op.create_index(
            'ix_lotes_archivos_hash_archivo', ['hash_archivo'], unique=True
        )

        # Capa 2: hash del contenido normalizado
        batch_op.add_column(sa.Column('hash_contenido', sa.String(length=64), nullable=True))
        batch_op.create_index(
            'ix_lotes_archivos_hash_contenido', ['hash_contenido'], unique=True
        )

        # Progreso granular
        batch_op.add_column(sa.Column('paso_actual', sa.String(length=40), nullable=True))
        batch_op.add_column(
            sa.Column(
                'progreso_pct', sa.Integer(),
                nullable=False, server_default=sa.text('0'),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('lotes_archivos') as batch_op:
        batch_op.drop_column('progreso_pct')
        batch_op.drop_column('paso_actual')
        batch_op.drop_index('ix_lotes_archivos_hash_contenido')
        batch_op.drop_column('hash_contenido')
        batch_op.drop_index('ix_lotes_archivos_hash_archivo')
        batch_op.create_index(
            'ix_lotes_archivos_hash_archivo', ['hash_archivo'], unique=False
        )
