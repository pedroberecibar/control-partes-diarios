"""add_codigo_contratista_procesados

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
Create Date: 2026-05-15 09:00:00.000000

Cambios:
- `partes_diarios_procesados.codigo_contratista`: columna STRING(20) nullable
  para persistir el código operativo declarado por el contratista en su Excel
  (ej. "01", "04"). Hasta hoy viajaba solo en `metricas_analitica` (JSON);
  ahora queda en columna dedicada para exposición vía API y UI.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('partes_diarios_procesados') as b:
        b.add_column(sa.Column('codigo_contratista', sa.String(20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('partes_diarios_procesados') as b:
        b.drop_column('codigo_contratista')
