from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.core.database import Base


class ParteDiarioRaw(Base):
    """Fila cruda tal cual vino del Excel (JSONB en Postgres, JSON en SQLite)."""
    __tablename__ = "partes_diarios_raw"

    id = Column(Integer, primary_key=True, index=True)
    lote_id = Column(Integer, ForeignKey("lotes_archivos.id"), nullable=False)
    fila_excel = Column(Integer, nullable=False)
    id_externo = Column(String(100), index=True, nullable=True)
    id_parte_hash = Column(String(64), index=True, nullable=False)
    datos_crudos = Column(JSON, nullable=False)

    lote = relationship("LoteArchivo")


class ParteDiarioProcesado(Base):
    """Resultado post-Core (Etapa 3) y Control de Observaciones (Etapa 4).

    Las dimensiones (id_traza, id_estado, contratista_id, usr_id) se guardan
    como FK lógicas (sin constraint físico contra Parquet). El service
    enriquece los DTOs uniendo contra dim_traza_calidad_bi, dim_estado_bi,
    dim_usuarios_bi y la tabla contratistas al construir las respuestas.
    """
    __tablename__ = "partes_diarios_procesados"

    id = Column(Integer, primary_key=True, index=True)
    raw_id = Column(Integer, ForeignKey("partes_diarios_raw.id"), unique=True, nullable=False)
    id_parte_hash = Column(String(64), index=True, nullable=False, unique=True)

    # Identificación / contexto del lote
    lote_id = Column(Integer, ForeignKey("lotes_archivos.id"), nullable=False, index=True)
    contratista_id = Column(Integer, ForeignKey("contratistas.id"), nullable=False)

    # Datos normalizados del parte
    suministro = Column(String(50), index=True, nullable=True)
    fecha_ejecucion = Column(DateTime, nullable=True)
    nro_medidor_retirado = Column(String(50), nullable=True)
    nro_medidor_colocado = Column(String(50), nullable=True)
    usr_id = Column(Integer, nullable=True, index=True)  # FK lógica a dim_usuarios_bi.USR_NUMERO

    # Resultado del waterfall (Etapa 3)
    ord_nro = Column(Integer, index=True, nullable=True)
    cod_epec = Column(Integer, nullable=True)
    id_estado = Column(Integer, nullable=False)            # FK lógica → dim_estado_bi
    id_traza = Column(Integer, nullable=False, index=True) # FK lógica → dim_traza_calidad_bi

    # Control de observaciones (Etapa 4)
    cod_epec_sugerido = Column(Integer, nullable=True)
    valor_uses_origen = Column(Float, nullable=True)
    valor_uses_obs = Column(Float, nullable=True)
    diferencia_uses = Column(Float, nullable=True)
    tipo_discrepancia = Column(String(50), nullable=True)

    # Observaciones cargadas por el operario en la app móvil (8 flags binarios)
    obs_gabinete = Column(Boolean, nullable=False, default=False)
    obs_subterraneo = Column(Boolean, nullable=False, default=False)
    obs_altura = Column(Boolean, nullable=False, default=False)
    obs_aereo = Column(Boolean, nullable=False, default=False)
    obs_equipo_medicion_reemplazado = Column(Boolean, nullable=False, default=False)
    obs_acometida_realizada = Column(Boolean, nullable=False, default=False)
    obs_tapa_reemplazada = Column(Boolean, nullable=False, default=False)
    obs_equipo_medicion_instalado = Column(Boolean, nullable=False, default=False)

    # Snapshot completo del DataFrame del motor analítico — para debug, export y futuros recálculos
    metricas_analitica = Column(JSON, nullable=True)

    # Auditoría e inmutabilidad
    version = Column(Integer, default=1, nullable=False)        # Optimistic Locking
    fue_corregido = Column(Boolean, default=False, nullable=False)
    anulado = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    raw = relationship("ParteDiarioRaw")
    lote = relationship("LoteArchivo")
    imagenes = relationship(
        "ParteImagen",
        back_populates="parte",
        order_by="ParteImagen.orden",
        cascade="all, delete-orphan",
    )


class ParteImagen(Base):
    """Imágenes Firebase asociadas al parte (1-5 por parte). Una fila por imagen.

    Tabla separada (vs. JSON array) para soportar metadata por imagen (rotación
    persistida, marcas de auditor, fechas de carga independiente) y reordenamiento.
    """
    __tablename__ = "parte_imagenes"

    id = Column(Integer, primary_key=True, index=True)
    parte_procesado_id = Column(
        Integer,
        ForeignKey("partes_diarios_procesados.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    orden = Column(Integer, nullable=False)  # 1-5, define el orden de visualización
    url = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parte = relationship("ParteDiarioProcesado", back_populates="imagenes")


class AuditoriaCambio(Base):
    """Bitácora append-only: una fila por cambio de campo en un parte procesado."""
    __tablename__ = "auditoria_cambios"

    id = Column(Integer, primary_key=True, index=True)
    parte_procesado_id = Column(Integer, ForeignKey("partes_diarios_procesados.id"), nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios_app.id"), nullable=False)
    campo_modificado = Column(String(50), nullable=False)
    valor_anterior = Column(String, nullable=True)
    valor_nuevo = Column(String, nullable=True)
    motivo = Column(String, nullable=False)
    fecha_cambio = Column(DateTime(timezone=True), server_default=func.now())
    version_resultante = Column(Integer, nullable=False)

    parte = relationship("ParteDiarioProcesado")
    usuario = relationship("UsuarioApp")
