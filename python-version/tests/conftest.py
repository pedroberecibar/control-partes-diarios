"""Configuración compartida de pytest."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def pytest_addoption(parser):
    parser.addoption("--update-snapshot", action="store_true", default=False,
                     help="Fuerza la regeneracion del snapshot de KPIs")


@pytest.fixture
def db():
    """Sesión SQLAlchemy contra SQLite en memoria con todas las tablas creadas.

    Importa los modelos para que `Base.metadata.create_all()` registre las tablas
    de domain_models y base_models. Útil para tests de servicios que necesitan
    tablas locales sin tocar la DB de la app.
    """
    from api.core.database import Base
    # Importa los módulos para que los modelos se registren en Base.metadata
    import api.db.models.base_models   # noqa: F401
    import api.db.models.domain_models  # noqa: F401

    # SQLite in-memory + StaticPool para que todos los queries usen la MISMA
    # conexión (de lo contrario cada checkout abre una DB nueva, vacía).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
