"""mapeo_columnas_operario_excel

Revision ID: d4e5f6a7b8c9
Revises: c3d2e1f0a8b9
Create Date: 2026-05-11 10:00:00.000000

Cambios:
- `lotes_archivos.mapeo_columnas`: columna TEXT nullable para persistir el mapeo
  de columnas confirmado por el usuario al subir un lote. Formato JSON:
  ``{"col_excel": "campo_canonico", ...}``. Null = adapter usa MAPA_RENOMBRES.
- `partes_diarios_procesados.operario_excel`: columna STRING(200) nullable para
  guardar el nombre del operario declarado en el Excel cuando la contratista
  lo incluye en su archivo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d2e1f0a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('lotes_archivos') as b:
        b.add_column(sa.Column('mapeo_columnas', sa.Text(), nullable=True))
    with op.batch_alter_table('partes_diarios_procesados') as b:
        b.add_column(sa.Column('operario_excel', sa.String(200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('lotes_archivos') as b:
        b.drop_column('mapeo_columnas')
    with op.batch_alter_table('partes_diarios_procesados') as b:
        b.drop_column('operario_excel')
