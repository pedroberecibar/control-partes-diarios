from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from api.core.database import Base

class UsuarioApp(Base):
    __tablename__ = "usuarios_app"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    rol = Column(String(20), nullable=False, default="operador") # operador, auditor, supervisor, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Contratista(Base):
    __tablename__ = "contratistas"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    activo = Column(Boolean, default=True)

class LoteArchivo(Base):
    __tablename__ = "lotes_archivos"

    id = Column(Integer, primary_key=True, index=True)
    nombre_archivo = Column(String(255), nullable=False)
    hash_archivo = Column(String(64), index=True, nullable=False)
    ruta_archivo = Column(String(500), nullable=False)  # Path absoluto al binario en data/uploads/
    contratista_id = Column(Integer, ForeignKey("contratistas.id"), nullable=False)
    estado = Column(String(20), nullable=False, default="RECIBIDO") # RECIBIDO, PROCESANDO, ERROR, COMPLETADO, RECHAZADO_SINTAXIS
    subido_por = Column(Integer, ForeignKey("usuarios_app.id"), nullable=False)
    fecha_subida = Column(DateTime(timezone=True), server_default=func.now())
    detalle_error = Column(String, nullable=True)

    contratista = relationship("Contratista")
    usuario = relationship("UsuarioApp")
