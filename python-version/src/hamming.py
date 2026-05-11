"""Helpers vectorizados de distancia Hamming entre vectores de observaciones.

Compartido entre Etapa 4 (motor de scoring batch) y la API de auditoría
(sugerencias de cod_epec en single-parte). Mantener una sola implementación
evita drift numérico entre el motor y el UI.

Invariantes (CLAUDE.md):
  - Vectorización pura — sin `df.apply(axis=1)`.
  - Tipos `int8` para entradas binarias y `int16` para sumas (max=8).
"""

from __future__ import annotations

import numpy as np

from . import config


def hamming_matrix(app_mat: np.ndarray, regla_mat: np.ndarray) -> np.ndarray:
    """Distancia Hamming N×M entre filas de `app_mat` (N×K) y `regla_mat` (M×K).

    Equivale al cross join + sum(abs(diff)) del Spark, pero sin DF intermedio.
    """
    return np.abs(app_mat[:, None, :] - regla_mat[None, :, :]).sum(axis=2).astype("int16")


def campos_diferentes(app_row: np.ndarray, regla_row: np.ndarray) -> list[str]:
    """Devuelve los nombres (UPPER) de obs en las que difiere `app_row` vs `regla_row`.

    Orden de salida = orden de `config.OBS_COLS` (canónico).
    """
    diff = np.asarray(app_row).astype("int16") != np.asarray(regla_row).astype("int16")
    return [cr for (_, cr), d in zip(config.OBS_COLS, diff) if bool(d)]
