# Guía de Ejecución y Prueba del Sistema Completo

---

## 1. Configuración del Entorno (Solo la primera vez)

### Backend

```powershell
# Primero ingresamos a la carpeta del backend
cd python-version

# Activamos el entorno virtual específico del backend
.\venv\Scripts\activate

# Instalamos dependencias y preparamos la base de datos
pip install -r requirements.txt
alembic upgrade head
```

### Frontend

```powershell
cd frontend-app
# Usamos npm.cmd en lugar de npm para evitar el bloqueo de ejecución de scripts (.ps1) de PowerShell
npm.cmd install
```

---

## 2. Poblar datos paramétricos (obligatorio antes del primer lote)

### 2.1 — SQLite: contratistas y usuario admin

Crea las filas requeridas por las Foreign Keys de `lotes_archivos`
(contratistas id=1/CONECTAR e id=2/COOPLYF, usuario id=1/admin).
Es idempotente — se puede correr más de una vez sin duplicar.

```powershell
cd python-version
python scripts/seed_webapp_db.py
```

Salida esperada:
```
Tablas verificadas / creadas.
contratistas  — insertadas: 2, ya existían: 0
usuarios_app  — insertadas: 2, ya existían: 0

Seed completado. La DB está lista para recibir lotes.
```

### 2.2 — Parquets del motor analítico

El motor analítico (Etapa 3 + 4) necesita tablas Parquet en `data/seed/`,
`data/master/` y `data/dim/`. Hay dos vías:

#### Opción A — Con conexión Oracle (datos reales, red EPEC/VPN)

Descarga seeds reales desde PRODEBS y genera maestros y dims:

```powershell
cd python-version
python run_pipeline.py --solo-seeds   # Etapa 0: users, stock, dim_ord, etc.
python -c "from src.etapa1_maestros import run; run()"   # master/
python -c "from src.etapa3_dims_bi import run; run()"    # dim/
```

#### Opción B — Sin Oracle (datos de prueba, siempre disponible)

Genera todos los Parquets con datos mock para poder procesar lotes
sin VPN ni Oracle. Los partes quedarán mayormente con traza
"Sin Orden Asociada" (no hay órdenes reales de SIGEC), pero el
pipeline completo corre sin errores.

```powershell
cd python-version
python scripts/generar_mock_parquets.py
```

Salida esperada:
```
── Seeds ─────────────────────────────────────────────────────────
  ✓  seed/mapa_archivos.parquet  (0 filas)
  ✓  seed/dim_ord.parquet  (7 filas)
  ✓  seed/eqp_equipos_ultimos_10.parquet  (6 filas)
  ✓  seed/usuarios_gral.parquet  (5 filas)
  ✓  seed/dim_stk_stock_equipos.parquet  (8 filas)
  ✓  seed/sigec_general.parquet  (6 filas)
  ✓  seed/pivot_resul_app_movil.parquet  (0 filas)

── Masters ───────────────────────────────────────────────────────
  ✓  master/mapeo_codigos_master.parquet  (19 filas)
  ✓  master/reglas_cod_obs_app.parquet  (21 filas)

── Dims BI ───────────────────────────────────────────────────────
  ✓  dim/dim_empresa_bi.parquet  (2 filas)
  ✓  dim/dim_estado_bi.parquet  (4 filas)
  ✓  dim/dim_traza_calidad_bi.parquet  (13 filas)
  ✓  dim/dim_usuarios_bi.parquet  (5 filas)
  ✓  dim/dim_archivo_bi.parquet  (0 filas)

Listo. Parquets en: ...python-version\data
```

---

## 3. Levantar el sistema (Modo Desarrollo)

Abrir **dos terminales** simultáneamente.

### Terminal A — Backend (FastAPI)

```powershell
cd python-version
.\venv\Scripts\activate
uvicorn api.main:app --reload --port 8000
```

### Terminal B — Frontend (Vite/React)

```powershell
cd frontend-app
npm.cmd run dev
```

Abrir en el navegador: `http://localhost:5173/control-partes-diarios/`

---

## 4. Verificación de la conexión

1. Abrir DevTools (`F12`) → pestaña **Network**.
2. Recargar la página.
3. Verificar petición `200 OK` a `http://localhost:8000/api/v1/partes`.
4. Si la bandeja muestra datos o "sin partes", la integración es exitosa.

---

## 5. Flujo de prueba de subida de lotes

Con el sistema levantado y los datos paramétricos cargados (paso 2):

1. Ir a **Lista de Lotes → Subir Archivos**.
2. Seleccionar un Excel de COOPLYF o CONECTAR.
3. Elegir el contratista correcto en el formulario.
4. El backend recibe el archivo, responde `201 Created` con `estado=RECIBIDO`
   y lanza el procesamiento en background.
5. Refrescar la Lista de Lotes: el estado avanzará de `RECIBIDO → PROCESANDO → PROCESADO_OK` (o `ERROR` si el archivo tiene problemas).

---

## 6. Estructura de datos del sistema

| Capa | Ubicación | Descripción |
|---|---|---|
| **SQLite (webapp)** | `data/db/webapp_pd.db` | Lotes, partes raw, procesados, auditoría |
| **Parquets seed** | `data/seed/*.parquet` | Dim. Oracle: órdenes, usuarios, stock |
| **Parquets master** | `data/master/*.parquet` | Mapeo códigos, reglas observaciones |
| **Parquets dim** | `data/dim/*.parquet` | Dimensiones BI (empresa, estado, traza…) |
| **Parquets gold** | `data/gold/*.parquet` | Fact table del motor analítico |
| **Uploads** | `data/uploads/` | Archivos Excel/CSV subidos (guardados por hash SHA256) |

---

## 7. Comandos de mantenimiento

```powershell
# Re-correr solo el motor para lotes ya cargados (sin re-subir archivo)
python run_pipeline.py --stage 3

# Regenerar dimensiones BI tras actualizar seeds reales de Oracle
python -c "from src.etapa3_dims_bi import run; run()"

# Inspeccionar un parte específico
python scripts/inspect_parte.py --hash <ID_PARTE_HASH>
```

---

## Solución de problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Error de integridad FK` al subir lote | `contratistas` o `usuarios_app` vacíos | Ejecutar `seed_webapp_db.py` (paso 2.1) |
| `FileNotFoundError: Tabla no encontrada` en el motor | Parquets de seed/master/dim ausentes | Ejecutar `generar_mock_parquets.py` (paso 2.2 opción B) |
| Lote queda en `ERROR` con "DataFrame vacío" | Archivo Excel con formato no reconocido por el adapter | Verificar columnas del archivo contra `MAPA_RENOMBRES` del adapter |
| Bandeja vacía tras procesar | Motor corrió OK pero partes tienen traza de descarte | Normal con datos mock — sin órdenes SIGEC reales el waterfall asigna "Sin Orden Asociada" |
| Error 404 en el frontend | `base` en `vite.config.js` no coincide con la URL | Verificar que `base: '/control-partes-diarios/'` |
| Error de CORS | Puerto del frontend distinto al configurado | Actualizar `allow_origins` en `api/main.py` |
