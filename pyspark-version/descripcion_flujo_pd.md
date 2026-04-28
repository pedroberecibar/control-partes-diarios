# Descripción General del Flujo de Procesamiento de Partes Diarios

Este documento describe la arquitectura, el flujo de datos (ETL) y la orquestación para el procesamiento de partes diarios. El objetivo del flujo es extraer datos desde orígenes en Sharepoint, transformarlos mediante scripts, almacenarlos estructuradamente en un Lakehouse y disponibilizarlos para su consumo en dashboards.

## 1. Orígenes de Datos
Los datos crudos provienen principalmente de carpetas o listas alojadas en Sharepoint correspondientes a distintos contratistas:
* **Sharepoint CONECTAR**
* **Sharepoint COOPLYF**

## 2. Orden de Ejecución (Orquestación del Pipeline)
El flujo se ejecuta siguiendo una dependencia estricta de tareas, estructurada en cuatro etapas cronológicas.

### Etapa 1: Actualización de Maestros y Dimensiones (Ejecución en Paralelo)
Fase inicial del pipeline. Prepara el terreno actualizando los catálogos antes de que ingresen los datos nuevos. Las siguientes tareas se lanzan en paralelo:
* **Actualizar Maestros / Códigos de Cierre:** Se actualiza la tabla maestra de mapeo (`mapeo_codigos_master`) leyendo los Excel de conversión.
  * 📄 **Script:** `act_mapeo_cod_contratistas_epec.py`
* **Invocar canalización `actual_dim_ord`:** Actualiza la dimensión de órdenes de trabajo.
* **Invocar canalización `actualizar_eqp`:** Actualiza la información de los equipos/medidores.

### Etapa 2: Ingesta de Datos a Staging (Ejecución en Paralelo)
*Condición: Espera a que finalice con éxito toda la Etapa 1.*
Los "adapters" leen los Excels/CSVs crudos del Sharepoint, limpian los datos, estandarizan columnas y cargan las tablas auxiliares (`_aux`). Se ejecutan en paralelo por contratista:
* **Cargar PD CONECTAR:**
  * 📄 **Script:** `ingesta_adapter_CONECTAR (1).py` (Escribe en `pd_conectar_aux`)
* **Cargar PD COOPLYF:**
  * 📄 **Script:** `ingesta_adapter_COOPLYF (2).py` (Escribe en `pd_cooplyf_aux`)

### Etapa 3: Procesamiento Core (Ejecución Secuencial)
*Condición: Espera a que finalice con éxito toda la Etapa 2.*
* **Procesar PD general stage:** El script central toma la información unificada de las tablas `aux`, aplica la cascada de cruces de negocio (Cruce A, B, C), enriquece con las dimensiones y genera la Fact Table normalizada.
  * 📄 **Script:** `procesar_pd_gral_refactor (5).py` (Actualiza `fact_partes_diarios_full`)

### Etapa 4: Control de Observaciones y Dimensiones Derivadas (Ejecución Secuencial)
*Condición: Espera a que finalice con éxito la Etapa 3.*
* **Control de Observaciones:** Consume la Fact Table recién generada para cruzarla contra las reglas de la app móvil. Evalúa faltantes/excedentes, asigna el código sugerido (USES) y genera la dimensión final de imágenes limpias.
  * 📄 **Script:** `control_obs_pd_ce (2).py` (Escribe en `reglas_cod_obs_app`, `control_obs_app` y `dim_img_app_pd`)

## 3. Almacenamiento: Lakehouse (`datos_generales`)
Los datos procesados se organizan en diferentes capas dentro del data lake/lakehouse.

### A. Capa Stage (Tablas Auxiliares)
Almacena los datos crudos extraídos de las fuentes antes de la transformación pesada.
* `pd_conectar_aux`
* `pd_cooplyf_aux`

### B. Capa de Maestros
* `mapeo_codigos_master`
* `usuarios_gral`
* `eqp_equipos_ultimos_10`
* `reglas_cod_obs_app`

### C. Capa de Dimensiones
Tablas dimensionales para el modelo de estrella en la capa semántica.
* `dim_estado_bi`
* `dim_empresa_bi`
* `dim_ord`
* `dim_calendario`
* `dim_usuarios_bi`
* `dim_archivo_bi`
* `dim_img_app_pd`

### D. Tablas Resultados (Capa Gold/Reporting)
Tablas finales listas para ser consumidas.
* `fact_partes_diarios_full` (Tabla de hechos unificada principal)
* `control_obs_app` (Tabla de resultados del control de observaciones)
* `partes_diarios_general_[contratista]`
* `partes_diarios_rechazados_[contratista]`
* `partes_diarios_para_ocr_[contratista]`

## 4. Consumo
* El destino final de los datos modelados es **Power BI** para la visualización y análisis de los KPIs operativos.