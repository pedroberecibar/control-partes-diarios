"""Tests de no-regresión para KPIs del Core y Control de Observaciones.

Estrategia:
  - La primera corrida genera un snapshot en tests/fixtures/kpis_snapshot.json.
  - Las corridas posteriores comparan contra ese snapshot.
  - Si el usuario valida un cambio de datos, borra el snapshot y la siguiente
    corrida lo regenera con los nuevos números.

Uso:
    python -m pytest tests/test_kpis_core.py -v
    python -m pytest tests/test_kpis_core.py -v --update-snapshot   # fuerza regeneración
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SNAPSHOT_CORE = FIXTURE_DIR / "kpis_core_snapshot.json"
SNAPSHOT_OBS  = FIXTURE_DIR / "kpis_obs_snapshot.json"




@pytest.fixture(scope="session")
def update_snapshot(request):
    return request.config.getoption("--update-snapshot")


@pytest.fixture(scope="session")
def kpis_core():
    """Calcula los KPIs del Core (sin imprimir)."""
    from src.etapa3_panel_kpis import calcular_kpis
    return calcular_kpis()


@pytest.fixture(scope="session")
def kpis_obs():
    """Calcula KPIs del control de observaciones."""
    from src import io_lakehouse as io
    try:
        df = io.read_table("control_obs_app", capa="gold")
    except FileNotFoundError:
        pytest.skip("control_obs_app no existe — ejecutar etapa 4 primero.")
        return None

    discrepancia = df["DISCREPANCIA_CODIGO"].value_counts(dropna=False).to_dict()
    return {
        "total": len(df),
        "por_discrepancia": {str(k): int(v) for k, v in discrepancia.items()},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_or_create_snapshot(path: Path, current: dict, update: bool) -> dict:
    """Carga snapshot existente o crea uno nuevo. Devuelve el snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if update or not path.exists():
        path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        return current
    return json.loads(path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────────────────
# Tests del Core (Etapa 3)
# ─────────────────────────────────────────────────────────────────────────────

class TestKPIsCore:
    """Verifica que los KPIs del Core no cambien entre corridas."""

    def test_snapshot_existe_o_se_crea(self, kpis_core, update_snapshot):
        """El snapshot debe existir o crearse en la primera corrida."""
        snap = _load_or_create_snapshot(SNAPSHOT_CORE, kpis_core, update_snapshot)
        assert snap is not None

    def test_total_ingresados(self, kpis_core, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_CORE, kpis_core, update_snapshot)
        assert kpis_core["calidad_datos"]["total_ingresados"] == snap["calidad_datos"]["total_ingresados"], \
            f"total_ingresados cambio: era {snap['calidad_datos']['total_ingresados']}, " \
            f"ahora {kpis_core['calidad_datos']['total_ingresados']}"

    def test_aprobados(self, kpis_core, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_CORE, kpis_core, update_snapshot)
        assert kpis_core["calidad_datos"]["aprobados"] == snap["calidad_datos"]["aprobados"]

    def test_rechazados(self, kpis_core, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_CORE, kpis_core, update_snapshot)
        assert kpis_core["calidad_datos"]["rechazados"] == snap["calidad_datos"]["rechazados"]

    def test_fuera_alcance(self, kpis_core, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_CORE, kpis_core, update_snapshot)
        assert kpis_core["calidad_datos"]["fuera_alcance"] == snap["calidad_datos"]["fuera_alcance"]

    def test_ocr(self, kpis_core, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_CORE, kpis_core, update_snapshot)
        assert kpis_core["calidad_datos"]["ocr"] == snap["calidad_datos"]["ocr"]

    def test_efectividad_pct(self, kpis_core, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_CORE, kpis_core, update_snapshot)
        assert abs(kpis_core["calidad_datos"]["efectividad_pct"]
                   - snap["calidad_datos"]["efectividad_pct"]) < 0.01

    def test_total_uses_operativo(self, kpis_core, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_CORE, kpis_core, update_snapshot)
        assert abs(kpis_core["operativo"]["total_uses"]
                   - snap["operativo"]["total_uses"]) < 0.01

    def test_total_partes_aprobados(self, kpis_core, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_CORE, kpis_core, update_snapshot)
        assert kpis_core["operativo"]["total_partes_aprobados"] == snap["operativo"]["total_partes_aprobados"]

    def test_rows_fact(self, kpis_core, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_CORE, kpis_core, update_snapshot)
        assert kpis_core["metadata"]["rows_fact"] == snap["metadata"]["rows_fact"], \
            f"rows_fact cambio: era {snap['metadata']['rows_fact']}, ahora {kpis_core['metadata']['rows_fact']}"

    def test_desglose_traza_no_vacio(self, kpis_core):
        """Sanity: el desglose de trazas debe tener al menos 1 entrada."""
        assert len(kpis_core["calidad_datos"]["desglose_traza_aprobados"]) > 0

    def test_contratistas_presentes(self, kpis_core):
        """Sanity: debe haber al menos 1 contratista en el desglose."""
        assert len(kpis_core["operativo"]["por_contratista"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Tests del Control de Observaciones (Etapa 4)
# ─────────────────────────────────────────────────────────────────────────────

class TestKPIsObs:
    """Verifica que los KPIs del control de observaciones no cambien."""

    def test_snapshot_existe_o_se_crea(self, kpis_obs, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_OBS, kpis_obs, update_snapshot)
        assert snap is not None

    def test_total_controlados(self, kpis_obs, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_OBS, kpis_obs, update_snapshot)
        assert kpis_obs["total"] == snap["total"], \
            f"total cambio: era {snap['total']}, ahora {kpis_obs['total']}"

    def test_discrepancia_sin_discrepancia(self, kpis_obs, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_OBS, kpis_obs, update_snapshot)
        actual = kpis_obs["por_discrepancia"].get("Sin Discrepancia", 0)
        esperado = snap["por_discrepancia"].get("Sin Discrepancia", 0)
        assert actual == esperado

    def test_discrepancia_sobrevaloracion(self, kpis_obs, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_OBS, kpis_obs, update_snapshot)
        clave = "Sobrevaloración"
        actual = kpis_obs["por_discrepancia"].get(clave, 0)
        esperado = snap["por_discrepancia"].get(clave, 0)
        assert actual == esperado

    def test_discrepancia_subvaloracion(self, kpis_obs, update_snapshot):
        snap = _load_or_create_snapshot(SNAPSHOT_OBS, kpis_obs, update_snapshot)
        clave = "Subvaloración"
        actual = kpis_obs["por_discrepancia"].get(clave, 0)
        esperado = snap["por_discrepancia"].get(clave, 0)
        assert actual == esperado


# ─────────────────────────────────────────────────────────────────────────────
# Tests de integridad cruzada
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegridad:
    """Verifica relaciones entre tablas del data lake."""

    def test_control_obs_equals_aprobados(self, kpis_core, kpis_obs):
        """control_obs_app debe tener EXACTAMENTE los mismos aprobados que la fact."""
        assert kpis_obs["total"] == kpis_core["calidad_datos"]["aprobados"], \
            f"control_obs={kpis_obs['total']} vs fact_aprobados={kpis_core['calidad_datos']['aprobados']}"

    def test_fact_tiene_filas(self, kpis_core):
        """Sanity: la fact no puede estar vacia."""
        assert kpis_core["metadata"]["rows_fact"] > 0

    def test_sum_estados_equals_total(self, kpis_core):
        """La suma de estados debe dar el total de la fact."""
        cd = kpis_core["calidad_datos"]
        suma = cd["aprobados"] + cd["rechazados"] + cd["ocr"] + cd["fuera_alcance"]
        assert suma == cd["total_ingresados"]
