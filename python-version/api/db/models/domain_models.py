from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey, Float, Index, UniqueConstraint
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


class ReglaCodEpec(Base):
    """Reglas de observaciones por código EPEC — reemplaza reglas_cod_obs_app.parquet como fuente de verdad.

    Un mismo cod_epec puede tener múltiples variantes (ej: cod 7 tiene 4 filas: gabinete, aereo, altura, subterraneo).
    Etapa 4 calcula la distancia Hamming del operario contra TODAS las reglas activas para encontrar la mejor.
    """
    __tablename__ = "reglas_cod_epec"

    id          = Column(Integer, primary_key=True, index=True)
    cod_epec    = Column(Integer, nullable=False, index=True)
    descripcion = Column(String(200), nullable=False)

    gabinete                    = Column(Boolean, nullable=False, default=False)
    subterraneo                 = Column(Boolean, nullable=False, default=False)
    altura                      = Column(Boolean, nullable=False, default=False)
    aereo                       = Column(Boolean, nullable=False, default=False)
    equipo_medicion_reemplazado = Column(Boolean, nullable=False, default=False)
    acometida_realizada         = Column(Boolean, nullable=False, default=False)
    tapa_reemplazada            = Column(Boolean, nullable=False, default=False)
    equipo_medicion_instalado   = Column(Boolean, nullable=False, default=False)

    valor_uses  = Column(Float, nullable=False)
    activo      = Column(Boolean, default=True, nullable=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by  = Column(Integer, ForeignKey("usuarios_app.id"), nullable=True)

    # Unicidad (cod_epec, descripcion) validada en service; no hay partial index en SQLite via ORM.
    __table_args__ = (
        Index("ix_regla_cod_desc", "cod_epec", "descripcion"),
    )


class MapeoCodigoContratista(Base):
    """Mapeo código contratista → COD_EPEC — reemplaza mapeo_codigos_master.parquet.

    Asocia el código interno que el operario escribe en el Excel al código EPEC correspondiente.
    El USES vive en ReglaCodEpec, no aquí.
    """
    __tablename__ = "mapeo_codigos_contratista"

    id               = Column(Integer, primary_key=True, index=True)
    contratista_id   = Column(Integer, ForeignKey("contratistas.id"), nullable=False)
    cod_contratista  = Column(String(20), nullable=False)
    fase             = Column(String(5), nullable=False)   # MON | TRI | AMBAS
    cod_epec         = Column(Integer, nullable=False, index=True)
    descripcion_codigo = Column(String(200), nullable=True)
    activo           = Column(Boolean, default=True, nullable=False)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    contratista = relationship("Contratista")


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


# =============================================================================
# Espejo local de Oracle SIGEC — universo CE + PROTELEM
# =============================================================================
# Estas tres tablas se pueblan vía sync admin (oracle_sync_service) y son
# consumidas por el motor (auto-rescate batch) y por el endpoint UI
# (candidatos para auditor). Eliminan la dependencia de Oracle en runtime.

class OrdenativoOracleLocal(Base):
    """Espejo local de xxsigec.ordenativos filtrado por TOR_CODIGO='CE' AND SEC_CODIGO_ORIGEN='PROTELEM'.

    PK natural = ORD_NUMERO (no autoincrement). El sync hace upsert por esta clave.
    """
    __tablename__ = "ordenativos_oracle_local"

    ord_numero            = Column(Integer, primary_key=True)
    srv_codigo            = Column(String(50), nullable=True, index=True)
    tor_codigo            = Column(String(20), nullable=False)   # siempre 'CE' por filtro
    sec_codigo_origen     = Column(String(50), nullable=True)    # siempre 'PROTELEM' por filtro
    ord_fecha_generacion  = Column(DateTime, nullable=True, index=True)
    ord_fecha_inicio      = Column(DateTime, nullable=True, index=True)
    ord_fecha_fin         = Column(DateTime, nullable=True)
    ord_estado            = Column(String(20), nullable=True)
    ord_resultado         = Column(String(10), nullable=True)
    usr_numero_ejec_ord   = Column(Integer, nullable=True)
    usr_nombre            = Column(String(150), nullable=True)   # del JOIN con XXCO_USUARIOS_V
    sincronizado_at       = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OrdenativoOracleFoto(Base):
    """Fotos Firebase asociadas a un ordenativo (1-5 por ordenativo).

    Origen: xxsigec.xxco_observaciones_ordenativ_v con TOB_CODIGO IN APP4OBS_80..APP4OBS_84.
    Tabla separada (vs columnas en OrdenativoOracleLocal) para mantener flexibilidad y evolucionar
    independientemente si Oracle agrega más slots de imagen.
    """
    __tablename__ = "ordenativos_oracle_fotos"

    id          = Column(Integer, primary_key=True)
    ord_numero  = Column(
        Integer,
        ForeignKey("ordenativos_oracle_local.ord_numero", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    posicion    = Column(Integer, nullable=False)               # 1-5
    url         = Column(String(2048), nullable=True)

    __table_args__ = (UniqueConstraint("ord_numero", "posicion", name="uq_oracle_foto_ord_pos"),)


class OrdenativoOracleEquipo(Base):
    """Espejo de XXSIGEC.EQUIPOS para los SRV_CODIGO presentes en OrdenativoOracleLocal.

    Permite búsqueda B (medidor → suministro real) sin consultar Oracle: dado un STE_NUMERO,
    se obtiene el SRV_CODIGO al que pertenece para luego buscar ordenativos CE de ese suministro.
    Un mismo STE_NUMERO puede aparecer con varios SRV_CODIGO si el medidor cambió de suministro.
    """
    __tablename__ = "ordenativos_oracle_equipos"

    id               = Column(Integer, primary_key=True)
    ste_numero       = Column(String(50), nullable=False, index=True)
    srv_codigo       = Column(String(50), nullable=False, index=True)
    eqp_fecha_instal = Column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("ste_numero", "srv_codigo", name="uq_oracle_eqp_ste_srv"),)
