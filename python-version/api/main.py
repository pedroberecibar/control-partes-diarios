import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import lotes, partes, auditoria

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Partes Diarios Web App API",
    description="API para la gestión, validación y auditoría de partes diarios operativos.",
    version="1.0.0",
)

# Configuración CORS para permitir peticiones del frontend local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Puerto típico de Vite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["General"])
def read_root():
    return {"message": "API de Partes Diarios funcionando correctamente"}


@app.get("/health", tags=["General"])
def health_check():
    """Endpoint para verificar la salud del servicio."""
    return {"status": "ok", "service": "webapp-api"}


# --- Registrar Routers ---
app.include_router(lotes.router, prefix="/api/v1/lotes", tags=["Lotes"])
app.include_router(partes.router, prefix="/api/v1/partes", tags=["Partes Diarios"])
app.include_router(auditoria.router, prefix="/api/v1/auditoria", tags=["Auditoría"])
