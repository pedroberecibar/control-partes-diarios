"""ix_ordenativo_equipo_ste_numero

Revision ID: c3d2e1f0a8b9
Revises: af1bd02aea31
Create Date: 2026-05-11 09:00:00.000000

Cambios:
- Índice no-unique en `ordenativos_oracle_equipos.ste_numero` para acelerar
  búsqueda B del rescate (medidor → suministros → ordenativos CE).
  El ORM ya declara index=True; esta migración lo materializa en DBs existentes.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3d2e1f0a8b9'
down_revision: Union[str, Sequence[str], None] = 'af1bd02aea31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('ordenativos_oracle_equipos') as batch_op:
        batch_op.create_index(
            'ix_ordenativo_equipo_ste_numero', ['ste_numero'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('ordenativos_oracle_equipos') as batch_op:
        batch_op.drop_index('ix_ordenativo_equipo_ste_numero')
