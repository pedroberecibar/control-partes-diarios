"""add_uploads_path_observaciones_imagenes

Revision ID: e3ff7d8f9492
Revises: 5fa4b01cf373
Create Date: 2026-04-28 12:39:54.198645

Cambios:
- `lotes_archivos`: agregar `ruta_archivo` (path al binario en data/uploads/).
- `partes_diarios_procesados`:
    - Reemplazar `traza_calidad: String(100)` por `id_traza: Integer` (FK lógica).
    - Agregar `lote_id`, `contratista_id`, `usr_id` (contexto y FKs).
    - Agregar `valor_uses_origen`, `valor_uses_obs` (Etapa 4).
    - Agregar 8 booleans `obs_*` (observaciones de la app móvil).
    - Agregar `metricas_analitica: JSON` (snapshot del DataFrame del motor).
- Crear tabla `parte_imagenes` (1-5 filas por parte, con orden).

Usa `batch_alter_table` para soportar SQLite (DROP/ALTER limitados nativamente).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3ff7d8f9492'
down_revision: Union[str, Sequence[str], None] = '5fa4b01cf373'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Tabla nueva: parte_imagenes
    op.create_table(
        'parte_imagenes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parte_procesado_id', sa.Integer(), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ['parte_procesado_id'], ['partes_diarios_procesados.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_parte_imagenes_id'), 'parte_imagenes', ['id'])
    op.create_index(
        op.f('ix_parte_imagenes_parte_procesado_id'),
        'parte_imagenes', ['parte_procesado_id'],
    )

    # 2. lotes_archivos.ruta_archivo
    # Se agrega NOT NULL: se asume tabla vacía en el momento de aplicar.
    # Si en el futuro hay datos, se debe agregar con default temporal y luego ALTER.
    with op.batch_alter_table('lotes_archivos') as batch_op:
        batch_op.add_column(sa.Column('ruta_archivo', sa.String(length=500), nullable=False))

    # 3. partes_diarios_procesados — agregar nuevas, reemplazar traza_calidad → id_traza
    with op.batch_alter_table('partes_diarios_procesados') as batch_op:
        # Contexto de lote y contratista
        batch_op.add_column(sa.Column('lote_id', sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column('contratista_id', sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column('usr_id', sa.Integer(), nullable=True))

        # Reemplazo de traza_calidad por id_traza (FK lógica)
        batch_op.add_column(sa.Column('id_traza', sa.Integer(), nullable=False))
        batch_op.drop_column('traza_calidad')

        # Etapa 4 — valoración USES
        batch_op.add_column(sa.Column('valor_uses_origen', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('valor_uses_obs', sa.Float(), nullable=True))

        # 8 observaciones de la app móvil
        batch_op.add_column(sa.Column('obs_gabinete', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('obs_subterraneo', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('obs_altura', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('obs_aereo', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('obs_equipo_medicion_reemplazado', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('obs_acometida_realizada', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('obs_tapa_reemplazada', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('obs_equipo_medicion_instalado', sa.Boolean(), nullable=False, server_default=sa.false()))

        # Snapshot del DataFrame del motor para debug / export
        batch_op.add_column(sa.Column('metricas_analitica', sa.JSON(), nullable=True))

        # Índices y FKs (FK names explícitos para que el downgrade pueda dropearlos)
        batch_op.create_index(
            batch_op.f('ix_partes_diarios_procesados_id_traza'), ['id_traza']
        )
        batch_op.create_index(
            batch_op.f('ix_partes_diarios_procesados_lote_id'), ['lote_id']
        )
        batch_op.create_index(
            batch_op.f('ix_partes_diarios_procesados_usr_id'), ['usr_id']
        )
        batch_op.create_foreign_key(
            'fk_partes_procesados_lote', 'lotes_archivos', ['lote_id'], ['id']
        )
        batch_op.create_foreign_key(
            'fk_partes_procesados_contratista', 'contratistas', ['contratista_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('partes_diarios_procesados') as batch_op:
        batch_op.drop_constraint('fk_partes_procesados_contratista', type_='foreignkey')
        batch_op.drop_constraint('fk_partes_procesados_lote', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_partes_diarios_procesados_usr_id'))
        batch_op.drop_index(batch_op.f('ix_partes_diarios_procesados_lote_id'))
        batch_op.drop_index(batch_op.f('ix_partes_diarios_procesados_id_traza'))
        batch_op.drop_column('metricas_analitica')
        for col in (
            'obs_equipo_medicion_instalado',
            'obs_tapa_reemplazada',
            'obs_acometida_realizada',
            'obs_equipo_medicion_reemplazado',
            'obs_aereo',
            'obs_altura',
            'obs_subterraneo',
            'obs_gabinete',
        ):
            batch_op.drop_column(col)
        batch_op.drop_column('valor_uses_obs')
        batch_op.drop_column('valor_uses_origen')
        batch_op.add_column(sa.Column('traza_calidad', sa.VARCHAR(length=100), nullable=False))
        batch_op.drop_column('id_traza')
        batch_op.drop_column('usr_id')
        batch_op.drop_column('contratista_id')
        batch_op.drop_column('lote_id')

    with op.batch_alter_table('lotes_archivos') as batch_op:
        batch_op.drop_column('ruta_archivo')

    op.drop_index(op.f('ix_parte_imagenes_parte_procesado_id'), table_name='parte_imagenes')
    op.drop_index(op.f('ix_parte_imagenes_id'), table_name='parte_imagenes')
    op.drop_table('parte_imagenes')
