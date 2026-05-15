"""Tests unitarios para `api.services.parte_dedup_helpers.contar_hashes_existentes`.

Cubre el parámetro `lote_id_excluir` que evita el W-5 self-overlap al reprocesar:
los hashes del propio lote no deben aparecer como duplicados históricos.
"""
from __future__ import annotations


def _insertar_parte(db, *, raw_id: int, lote_id: int, hash_: str) -> None:
    """Inserta un ParteDiarioProcesado mínimo (las FK no se enforced en SQLite por default)."""
    from api.db.models.domain_models import ParteDiarioProcesado

    db.add(ParteDiarioProcesado(
        raw_id=raw_id,
        lote_id=lote_id,
        contratista_id=1,
        id_parte_hash=hash_,
        id_estado=1,
        id_traza=1,
    ))
    db.commit()


class TestContarHashesExistentes:

    def test_sin_exclusion_detecta_todos(self, db):
        from api.services.parte_dedup_helpers import contar_hashes_existentes

        _insertar_parte(db, raw_id=1, lote_id=1, hash_="H1")
        _insertar_parte(db, raw_id=2, lote_id=2, hash_="H2")

        out = contar_hashes_existentes(db, ["H1", "H2", "H3"])
        assert out == {"H1", "H2"}

    def test_exclusion_mismo_lote_evita_self_overlap(self, db):
        """Reprocesar lote=1: sus hashes viejos no deben aparecer como duplicados."""
        from api.services.parte_dedup_helpers import contar_hashes_existentes

        _insertar_parte(db, raw_id=1, lote_id=1, hash_="H1")

        out = contar_hashes_existentes(db, ["H1"], lote_id_excluir=1)
        assert out == set()

    def test_exclusion_otro_lote_no_aplica(self, db):
        """Excluir lote=2 no afecta a hashes pertenecientes a lote=1."""
        from api.services.parte_dedup_helpers import contar_hashes_existentes

        _insertar_parte(db, raw_id=1, lote_id=1, hash_="H1")

        out = contar_hashes_existentes(db, ["H1"], lote_id_excluir=2)
        assert out == {"H1"}

    def test_exclusion_separa_overlap_cross_lote(self, db):
        """Mismo hash en varios lotes: excluir uno revela el resto como overlap real."""
        # H1 aparece en lote=1 y en lote=2 (escenario imposible por unique constraint
        # en producción, pero útil para validar la query SQL en aislamiento).
        # Lo simulamos con dos hashes distintos asignados a distintos lotes.
        from api.services.parte_dedup_helpers import contar_hashes_existentes

        _insertar_parte(db, raw_id=1, lote_id=1, hash_="HA")
        _insertar_parte(db, raw_id=2, lote_id=2, hash_="HB")

        # Reprocesando lote=1: HA queda excluido, HB sigue contando como cross-lote.
        out = contar_hashes_existentes(db, ["HA", "HB"], lote_id_excluir=1)
        assert out == {"HB"}

    def test_lista_vacia_devuelve_set_vacio(self, db):
        from api.services.parte_dedup_helpers import contar_hashes_existentes

        out = contar_hashes_existentes(db, [], lote_id_excluir=1)
        assert out == set()
