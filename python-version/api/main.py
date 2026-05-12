import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.core.database import Base, engine
from api.routers import lotes, partes, auditoria, admin

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

log = logging.getLogger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Importar todos los modelos para que Base.metadata los conozca antes del create_all.
    import api.db.models.base_models   # noqa: F401
    import api.db.models.domain_models # noqa: F401
    Base.metadata.create_all(bind=engine)
    log.info("DB tables ensured.")
    yield


app = FastAPI(
    title="Partes Diarios Web App API",
    description="API para la gestión, validación y auditoría de partes diarios operativos.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configuración CORS para permitir peticiones del frontend local
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ],
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
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin — Códigos EPEC"])
