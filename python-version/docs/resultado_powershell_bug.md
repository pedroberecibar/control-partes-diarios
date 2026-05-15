Windows PowerShell
Copyright (C) Microsoft Corporation. Todos los derechos reservados.

Instale la versión más reciente de PowerShell para obtener nuevas características y mejoras. https://aka.ms/PSWindows

PS C:\WINDOWS\System32> Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine
>>   -match 'uvicorn' } | ForEach-Object { Write-Host "Killing python PID $($_.ProcessId)";
>>   Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
-match : El término '-match' no se reconoce como nombre de un cmdlet, función, archivo de script o programa
ejecutable. Compruebe si escribió correctamente el nombre o, si incluyó una ruta de acceso, compruebe que dicha ruta
es correcta e inténtelo de nuevo.
En línea: 2 Carácter: 3
+   -match 'uvicorn' } | ForEach-Object { Write-Host "Killing python PI ...
+   ~~~~~~
    + CategoryInfo          : ObjectNotFound: (-match:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException

Killing python PID 18100
-match : El término '-match' no se reconoce como nombre de un cmdlet, función, archivo de script o programa
ejecutable. Compruebe si escribió correctamente el nombre o, si incluyó una ruta de acceso, compruebe que dicha ruta
es correcta e inténtelo de nuevo.
En línea: 2 Carácter: 3
+   -match 'uvicorn' } | ForEach-Object { Write-Host "Killing python PI ...
+   ~~~~~~
    + CategoryInfo          : ObjectNotFound: (-match:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException

Killing python PID 13784
-match : El término '-match' no se reconoce como nombre de un cmdlet, función, archivo de script o programa
ejecutable. Compruebe si escribió correctamente el nombre o, si incluyó una ruta de acceso, compruebe que dicha ruta
es correcta e inténtelo de nuevo.
En línea: 2 Carácter: 3
+   -match 'uvicorn' } | ForEach-Object { Write-Host "Killing python PI ...
+   ~~~~~~
    + CategoryInfo          : ObjectNotFound: (-match:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException

Killing python PID 11776
-match : El término '-match' no se reconoce como nombre de un cmdlet, función, archivo de script o programa
ejecutable. Compruebe si escribió correctamente el nombre o, si incluyó una ruta de acceso, compruebe que dicha ruta
es correcta e inténtelo de nuevo.
En línea: 2 Carácter: 3
+   -match 'uvicorn' } | ForEach-Object { Write-Host "Killing python PI ...
+   ~~~~~~
    + CategoryInfo          : ObjectNotFound: (-match:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException

Killing python PID 2456
-match : El término '-match' no se reconoce como nombre de un cmdlet, función, archivo de script o programa
ejecutable. Compruebe si escribió correctamente el nombre o, si incluyó una ruta de acceso, compruebe que dicha ruta
es correcta e inténtelo de nuevo.
En línea: 2 Carácter: 3
+   -match 'uvicorn' } | ForEach-Object { Write-Host "Killing python PI ...
+   ~~~~~~
    + CategoryInfo          : ObjectNotFound: (-match:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException

Killing python PID 5716
-match : El término '-match' no se reconoce como nombre de un cmdlet, función, archivo de script o programa
ejecutable. Compruebe si escribió correctamente el nombre o, si incluyó una ruta de acceso, compruebe que dicha ruta
es correcta e inténtelo de nuevo.
En línea: 2 Carácter: 3
+   -match 'uvicorn' } | ForEach-Object { Write-Host "Killing python PI ...
+   ~~~~~~
    + CategoryInfo          : ObjectNotFound: (-match:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException

Killing python PID 17172
-match : El término '-match' no se reconoce como nombre de un cmdlet, función, archivo de script o programa
ejecutable. Compruebe si escribió correctamente el nombre o, si incluyó una ruta de acceso, compruebe que dicha ruta
es correcta e inténtelo de nuevo.
En línea: 2 Carácter: 3
+   -match 'uvicorn' } | ForEach-Object { Write-Host "Killing python PI ...
+   ~~~~~~
    + CategoryInfo          : ObjectNotFound: (-match:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException

Killing python PID 1344
-match : El término '-match' no se reconoce como nombre de un cmdlet, función, archivo de script o programa
ejecutable. Compruebe si escribió correctamente el nombre o, si incluyó una ruta de acceso, compruebe que dicha ruta
es correcta e inténtelo de nuevo.
En línea: 2 Carácter: 3
+   -match 'uvicorn' } | ForEach-Object { Write-Host "Killing python PI ...
+   ~~~~~~
    + CategoryInfo          : ObjectNotFound: (-match:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException

Killing python PID 13584
-match : El término '-match' no se reconoce como nombre de un cmdlet, función, archivo de script o programa
ejecutable. Compruebe si escribió correctamente el nombre o, si incluyó una ruta de acceso, compruebe que dicha ruta
es correcta e inténtelo de nuevo.
En línea: 2 Carácter: 3
+   -match 'uvicorn' } | ForEach-Object { Write-Host "Killing python PI ...
+   ~~~~~~
    + CategoryInfo          : ObjectNotFound: (-match:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException

Killing python PID 19404
PS C:\WINDOWS\System32>   Get-CimInstance Win32_Process -Filter "Name='uvicorn.exe'" | ForEach-Object { Write-Host
>>   "Killing uvicorn PID $($_.ProcessId)"; Stop-Process -Id $_.ProcessId -Force -ErrorAction
>>   SilentlyContinue }
PS C:\WINDOWS\System32>   Start-Sleep -Seconds 2
PS C:\WINDOWS\System32>   Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
PS C:\WINDOWS\System32>




Resultado de segunda ventana de powershell:
PS C:\Users\pberecibar> cd "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version"
PS D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version>  .\venv\Scripts\activate
(venv) PS D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version> uvicorn api.main:app --reload --reload-dir api --reload-dir src --port 8000 --log-level info
INFO:     Will watch for changes in these directories: ['D:\\Usuarios\\pberecibar\\Desktop\\backup pyspark - flujo pd\\python-version\\api', 'D:\\Usuarios\\pberecibar\\Desktop\\backup pyspark - flujo pd\\python-version\\src']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [2784] using WatchFiles
INFO:     Started server process [16728]
INFO:     Waiting for application startup.
INFO api.main: DB tables ensured.
INFO:     Application startup complete.


Resultado reprocesamiento lote 5:

Consola 3:

PS C:\Users\pberecibar> Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/api/v1/lotes/5/reprocesar"


id                 : 5
nombre_archivo     : CONECTAR_11-2025_MI (5).xlsx
hash_archivo       : c8bb52cbd4cfa8b755a91aa52f2bc3fd0594c2c06c37154a4ace2cc23ce7550c
contratista_id     : 1
contratista_nombre : CONECTAR
estado             : RECIBIDO
subido_por         : 1
usuario_nombre     : admin
fecha_subida       : 2026-05-11T13:27:06
detalle_error      :
paso_actual        : APROBADO
progreso_pct       : 100
total_filas        : 0
n_aprobados        : 0
n_revision         : 0
n_rechazado        : 0
n_fuera_alcance    : 0



PS C:\Users\pberecibar>

Consola 2

PS C:\Users\pberecibar> cd "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version"
PS D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version>  .\venv\Scripts\activate
(venv) PS D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version> uvicorn api.main:app --reload --reload-dir api --reload-dir src --port 8000 --log-level info
INFO:     Will watch for changes in these directories: ['D:\\Usuarios\\pberecibar\\Desktop\\backup pyspark - flujo pd\\python-version\\api', 'D:\\Usuarios\\pberecibar\\Desktop\\backup pyspark - flujo pd\\python-version\\src']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [2784] using WatchFiles
INFO:     Started server process [16728]
INFO:     Waiting for application startup.
INFO api.main: DB tables ensured.
INFO:     Application startup complete.
INFO:     127.0.0.1:60327 - "POST /api/v1/lotes/5/reprocesar HTTP/1.1" 200 OK
INFO src.etapa2_adapter_conectar: CONECTAR adapter — header detectado con score=7 cols=['ID', 'Fecha', 'Cuadrilla', 'Vehiculos', 'Personas', 'Obra', 'ID2', 'Suministro', 'Ordenativo', 'Codigo', 'Colocado', 'Retirado']
INFO src.etapa2_adapter_conectar: CONECTAR adapter — codigos norm (archivo): ['01', '02', '03', '04', '07', '71', '05', '06', '10', '11', '12', '13', '15', '16', '20', '21', '22', '23', '25', '28'] | codigos norm (master): ['01', '02', '04', '07', '11', '12', '13', '15', '16', '21', '22', '23', '25', '41', '42', '43', '44', '62', '71', '72', '92']
INFO src.etapa2_adapter_conectar: CONECTAR adapter — c8bb52cbd4cfa8b755a91aa52f2bc3fd0594c2c06c37154a4ace2cc23ce7550c.xlsx: total=149386, aprobados=80581, fecha_invalida=0, cod_invalido=68805
INFO api.services.worker: Lote 5 esperando turno en el motor analítico.
INFO api.services.worker: Lote 5 ingresó al motor analítico.
[WORKER ERROR] Lote 5 falló:
Traceback (most recent call last):
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\arrays\integer.py", line 53, in _safe_cast
    return values.astype(dtype, casting="safe", copy=copy)
           ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: Cannot cast array data from dtype('float64') to dtype('int64') according to the rule 'safe'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\api\services\worker.py", line 109, in procesar_lote_en_background
    df_final, df_img = _ejecutar_motor_analitico(contratista.nombre, df_aux, db=db)
                       ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\api\services\worker.py", line 234, in _ejecutar_motor_analitico
    srv_codigo          = pd.to_numeric(df_aux["Suministro"], errors="coerce").astype("Int64"),
                          ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\generic.py", line 6665, in astype
    new_data = self._mgr.astype(dtype=dtype, copy=copy, errors=errors)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\internals\managers.py", line 449, in astype
    return self.apply(
           ~~~~~~~~~~^
        "astype",
        ^^^^^^^^^
    ...<3 lines>...
        using_cow=using_copy_on_write(),
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\internals\managers.py", line 363, in apply
    applied = getattr(b, f)(**kwargs)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\internals\blocks.py", line 784, in astype
    new_values = astype_array_safe(values, dtype, copy=copy, errors=errors)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\dtypes\astype.py", line 237, in astype_array_safe
    new_values = astype_array(values, dtype, copy=copy)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\dtypes\astype.py", line 182, in astype_array
    values = _astype_nansafe(values, dtype, copy=copy)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\dtypes\astype.py", line 80, in _astype_nansafe
    return dtype.construct_array_type()._from_sequence(arr, dtype=dtype, copy=copy)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\arrays\masked.py", line 153, in _from_sequence
    values, mask = cls._coerce_to_array(scalars, dtype=dtype, copy=copy)
                   ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\arrays\numeric.py", line 272, in _coerce_to_array
    values, mask, _, _ = _coerce_to_data_and_mask(
                         ~~~~~~~~~~~~~~~~~~~~~~~~^
        value, dtype, copy, dtype_cls, default_dtype
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\arrays\numeric.py", line 229, in _coerce_to_data_and_mask
    values = dtype_cls._safe_cast(values, dtype, copy=False)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\arrays\integer.py", line 59, in _safe_cast
    raise TypeError(
        f"cannot safely cast non-equivalent {values.dtype} to {np.dtype(dtype)}"
    ) from err
TypeError: cannot safely cast non-equivalent float64 to int64

ERROR api.services.worker: Error procesando lote 5: cannot safely cast non-equivalent float64 to int64
Traceback (most recent call last):
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\arrays\integer.py", line 53, in _safe_cast
    return values.astype(dtype, casting="safe", copy=copy)
           ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: Cannot cast array data from dtype('float64') to dtype('int64') according to the rule 'safe'

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\api\services\worker.py", line 109, in procesar_lote_en_background
    df_final, df_img = _ejecutar_motor_analitico(contratista.nombre, df_aux, db=db)
                       ~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\api\services\worker.py", line 234, in _ejecutar_motor_analitico
    srv_codigo          = pd.to_numeric(df_aux["Suministro"], errors="coerce").astype("Int64"),
                          ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\generic.py", line 6665, in astype
    new_data = self._mgr.astype(dtype=dtype, copy=copy, errors=errors)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\internals\managers.py", line 449, in astype
    return self.apply(
           ~~~~~~~~~~^
        "astype",
        ^^^^^^^^^
    ...<3 lines>...
        using_cow=using_copy_on_write(),
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\internals\managers.py", line 363, in apply
    applied = getattr(b, f)(**kwargs)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\internals\blocks.py", line 784, in astype
    new_values = astype_array_safe(values, dtype, copy=copy, errors=errors)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\dtypes\astype.py", line 237, in astype_array_safe
    new_values = astype_array(values, dtype, copy=copy)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\dtypes\astype.py", line 182, in astype_array
    values = _astype_nansafe(values, dtype, copy=copy)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\dtypes\astype.py", line 80, in _astype_nansafe
    return dtype.construct_array_type()._from_sequence(arr, dtype=dtype, copy=copy)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\arrays\masked.py", line 153, in _from_sequence
    values, mask = cls._coerce_to_array(scalars, dtype=dtype, copy=copy)
                   ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\arrays\numeric.py", line 272, in _coerce_to_array
    values, mask, _, _ = _coerce_to_data_and_mask(
                         ~~~~~~~~~~~~~~~~~~~~~~~~^
        value, dtype, copy, dtype_cls, default_dtype
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    )
    ^
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\arrays\numeric.py", line 229, in _coerce_to_data_and_mask
    values = dtype_cls._safe_cast(values, dtype, copy=False)
  File "D:\Usuarios\pberecibar\Desktop\backup pyspark - flujo pd\python-version\venv\Lib\site-packages\pandas\core\arrays\integer.py", line 59, in _safe_cast
    raise TypeError(
        f"cannot safely cast non-equivalent {values.dtype} to {np.dtype(dtype)}"
    ) from err
TypeError: cannot safely cast non-equivalent float64 to int64
INFO:     127.0.0.1:54257 - "OPTIONS /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:63002 - "OPTIONS /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:54257 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:54257 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:63002 - "OPTIONS /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:54257 - "OPTIONS /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:49811 - "GET /api/v1/partes/?skip=0&limit=25&sort_by=id&sort_dir=desc HTTP/1.1" 200 OK
INFO:     127.0.0.1:63002 - "GET /api/v1/partes/?skip=0&limit=25&sort_by=id&sort_dir=desc HTTP/1.1" 200 OK
INFO:     127.0.0.1:50297 - "GET /api/v1/partes/cod-epec/valores HTTP/1.1" 200 OK
INFO:     127.0.0.1:54257 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:50297 - "GET /api/v1/partes/cod-epec/valores HTTP/1.1" 200 OK
INFO:     127.0.0.1:63002 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:63002 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:63002 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:50297 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:63002 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK


Resultado segundo reproceso:


INFO:     Application startup complete.
INFO:     127.0.0.1:60734 - "POST /api/v1/lotes/5/reprocesar HTTP/1.1" 200 OK
INFO:     127.0.0.1:51446 - "OPTIONS /api/v1/partes/cod-epec/valores HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "OPTIONS /api/v1/partes/cod-epec/valores HTTP/1.1" 200 OK
INFO:     127.0.0.1:49781 - "OPTIONS /api/v1/partes/?skip=0&limit=25&sort_by=id&sort_dir=desc HTTP/1.1" 200 OK
INFO:     127.0.0.1:52114 - "OPTIONS /api/v1/partes/?skip=0&limit=25&sort_by=id&sort_dir=desc HTTP/1.1" 200 OK
INFO:     127.0.0.1:56575 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:56575 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:56575 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:56575 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/partes/?skip=0&limit=25&sort_by=id&sort_dir=desc HTTP/1.1" 200 OK
INFO:     127.0.0.1:51446 - "GET /api/v1/partes/cod-epec/valores HTTP/1.1" 200 OK
INFO:     127.0.0.1:52114 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:56575 - "GET /api/v1/partes/?skip=0&limit=25&sort_by=id&sort_dir=desc HTTP/1.1" 200 OK
INFO:     127.0.0.1:51446 - "GET /api/v1/partes/cod-epec/valores HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:51446 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO src.etapa2_adapter_conectar: CONECTAR adapter — header detectado con score=7 cols=['ID', 'Fecha', 'Cuadrilla', 'Vehiculos', 'Personas', 'Obra', 'ID2', 'Suministro', 'Ordenativo', 'Codigo', 'Colocado', 'Retirado']
INFO src.etapa2_adapter_conectar: CONECTAR adapter — codigos norm (archivo): ['01', '02', '03', '04', '07', '71', '05', '06', '10', '11', '12', '13', '15', '16', '20', '21', '22', '23', '25', '28'] | codigos norm (master): ['01', '02', '04', '07', '11', '12', '13', '15', '16', '21', '22', '23', '25', '41', '42', '43', '44', '62', '71', '72', '92']
INFO src.etapa2_adapter_conectar: CONECTAR adapter — c8bb52cbd4cfa8b755a91aa52f2bc3fd0594c2c06c37154a4ace2cc23ce7550c.xlsx: total=149386, aprobados=80581, fecha_invalida=0, cod_invalido=68805
INFO api.services.worker: Lote 5 esperando turno en el motor analítico.
INFO api.services.worker: Lote 5 ingresó al motor analítico.
WARNING api.services.worker: Suministro contiene 1 valores con parte decimal no nula — se truncan al entero.
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
WARNING api.services.worker:   OVERLAP_WARNING: 97% de partes del lote ya existen (threshold=50%). Se procesará con Traza 18.
INFO src.etapa3_core: ================================================================================
INFO src.etapa3_core: INICIANDO PROCESO PARA: CONECTAR
INFO src.etapa3_core: ================================================================================
INFO src.etapa3_core:   Cargando maestros y seeds...
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO src.etapa3_core:   Construyendo df_ord_ce / df_ord_ce_propia / df_ord_rechazo_tor...
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO src.etapa3_core:   Construyendo df_base con _row_id...
INFO src.etapa3_core:   Ejecutando Cruce A (suministro + orden CE propia)...
INFO src.etapa3_core:     Cruce A: 26692 matches / 122694 pendientes (de 149386 partes).
INFO src.etapa3_core:   Ejecutando Cruce B (rechazo TOR no-CE)...
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO src.etapa3_core:     Cruce B: 113514 matches / 9180 pendientes (de 122694 entrantes).
INFO src.etapa3_core:   Ejecutando Cruce C (rescate técnico por medidor)...
INFO src.etapa3_core:     Cruce C: 50 matches / 9130 pendientes (de 9180 entrantes).
INFO src.etapa3_core:   Ensamblando waterfall + reglas huérfano + correcciones...
WARNING src.etapa3_core:   Regla Otro Origen: 115586 parte(s) reclasificados (SEC_CODIGO_ORIGEN != PROTELEM). Trazas previas: {'No Corresponde TOR CE': 113473, 'Original OK': 964, 'Corregido Medidor Vacio': 539, 'Informado - No Ejecutado': 330, 'Corregido Nro Medidor': 275, 'Corregido Sumi': 3, 'Corregido Sumi Nro EQP': 2}
WARNING src.etapa3_core:   Traza 18: 145423 parte(s) ya existentes en lote anterior → Registro Ya Procesado en Lote Anterior.
INFO src.etapa3_core:   Enriqueciendo (USR/FASE/precio) + dedup Repetido X Sumi...
INFO src.etapa3_core:   Normalizando a schema COLS_FACT...
[DIAG] TRAZAS_FUERA_ALCANCE runtime: ['No Corresponde TOR CE', 'Otro Origen', 'Código de Tarea No Mapeado']
[DIAG] Filas Traza14 en df: 524
[DIAG] Sample TRAZA_CALIDAD (Traza14): 'Código de Tarea No Mapeado'
[DIAG] Post-select Traza14 id_estado: {4: 524}
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO src.etapa3_core:   Resumen:
INFO src.etapa3_core:     df_pd                     149,386
INFO src.etapa3_core:     df_mc (filtrado)               99
INFO src.etapa3_core:     df_tecnica                 76,982
INFO src.etapa3_core:     df_usr_pool                   101
INFO src.etapa3_core:     df_fases                2,235,154
INFO src.etapa3_core:     df_ord_ce_propia           45,601
INFO src.etapa3_core:     df_ord_rechazo_tor      5,687,276
INFO src.etapa3_core:     df_base                   149,386
INFO src.etapa3_core:     cruce_A matches            26,692
INFO src.etapa3_core:     cruce_A pendientes        122,694
INFO src.etapa3_core:     cruce_A por TRAZA
INFO src.etapa3_core:       Original OK                             20,816
INFO src.etapa3_core:       Corregido Medidor Vacio                  3,715
INFO src.etapa3_core:       Corregido Nro Medidor                    1,688
INFO src.etapa3_core:       Informado - No Ejecutado                   473
INFO src.etapa3_core:     cruce_B matches           113,514
INFO src.etapa3_core:     cruce_B pendientes          9,180
INFO src.etapa3_core:     cruce_B por TIPO_ORDEN
INFO src.etapa3_core:       CO                                      33,248
INFO src.etapa3_core:       RX                                      30,335
INFO src.etapa3_core:       CX                                      12,270
INFO src.etapa3_core:       IC                                       8,794
INFO src.etapa3_core:       ST                                       7,274
INFO src.etapa3_core:       RP                                       5,124
INFO src.etapa3_core:       IN                                       4,880
INFO src.etapa3_core:       RE                                       3,865
INFO src.etapa3_core:       CC                                       2,654
INFO src.etapa3_core:       MP                                       2,462
INFO src.etapa3_core:       NT                                         647
INFO src.etapa3_core:       RO                                         351
INFO src.etapa3_core:       IA                                         211
INFO src.etapa3_core:       VE                                         170
INFO src.etapa3_core:       MT                                         150
INFO src.etapa3_core:       FU                                         150
INFO src.etapa3_core:       CN                                         145
INFO src.etapa3_core:       II                                         136
INFO src.etapa3_core:       PM                                         121
INFO src.etapa3_core:       RF                                         112
INFO src.etapa3_core:       IM                                          67
INFO src.etapa3_core:       TP                                          57
INFO src.etapa3_core:       GF                                          56
INFO src.etapa3_core:       CP                                          42
INFO src.etapa3_core:       TX                                          42
INFO src.etapa3_core:       ET                                          42
INFO src.etapa3_core:       AC                                          39
INFO src.etapa3_core:       IG                                          23
INFO src.etapa3_core:       RC                                           8
INFO src.etapa3_core:       RN                                           8
INFO src.etapa3_core:       AS                                           7
INFO src.etapa3_core:       NE                                           5
INFO src.etapa3_core:       HC                                           4
INFO src.etapa3_core:       TM                                           3
INFO src.etapa3_core:       QS                                           3
INFO src.etapa3_core:       VC                                           2
INFO src.etapa3_core:       HO                                           2
INFO src.etapa3_core:       UC                                           1
INFO src.etapa3_core:       NO                                           1
INFO src.etapa3_core:       CD                                           1
INFO src.etapa3_core:       NR                                           1
INFO src.etapa3_core:       CT                                           1
INFO src.etapa3_core:     cruce_C matches                50
INFO src.etapa3_core:     cruce_C pendientes          9,130
INFO src.etapa3_core:     cruce_C por TRAZA
INFO src.etapa3_core:       Corregido Sumi                              34
INFO src.etapa3_core:       Corregido Sumi Nro EQP                      16
INFO src.etapa3_core:     huerfanos_finales           9,130
INFO src.etapa3_core:     df_full (post-ensamblado)    149,386
INFO src.etapa3_core:     TRAZA_CALIDAD post-ensamblado
INFO src.etapa3_core:       Registro Ya Procesado en Lote Anterior    145,423
INFO src.etapa3_core:       Corregido Medidor Vacio                  2,572
INFO src.etapa3_core:       Corregido Nro Medidor                      819
INFO src.etapa3_core:       Código de Tarea No Mapeado                 524
INFO src.etapa3_core:       Corregido Sumi                              29
INFO src.etapa3_core:       Corregido Sumi Nro EQP                      11
INFO src.etapa3_core:       Otro Origen                                  5
INFO src.etapa3_core:       Sin Orden Asociada                           3
INFO src.etapa3_core:     df_final (post-dedup)     149,386
INFO src.etapa3_core:     TRAZA_CALIDAD final
INFO src.etapa3_core:       Registro Ya Procesado en Lote Anterior    145,423
INFO src.etapa3_core:       Corregido Medidor Vacio                  2,419
INFO src.etapa3_core:       Corregido Nro Medidor                      712
INFO src.etapa3_core:       Código de Tarea No Mapeado                 524
INFO src.etapa3_core:       Informados con ORD-SUMI aprobado           276
INFO src.etapa3_core:       Corregido Sumi                              20
INFO src.etapa3_core:       Otro Origen                                  5
INFO src.etapa3_core:       Corregido Sumi Nro EQP                       4
INFO src.etapa3_core:       Sin Orden Asociada                           3
INFO src.etapa3_core:     USES total              1,396.256
INFO src.etapa3_core:     df_normalizado            149,386
INFO src.etapa3_core:     ID_ESTADO breakdown
INFO src.etapa3_core:       3                                      145,702
INFO src.etapa3_core:       1                                        3,151
INFO src.etapa3_core:       4                                          529
INFO src.etapa3_core:       2                                            4
INFO src.etapa3_core:     Aprobados (ID_ESTADO=1)      3,151
INFO src.etapa4_control_obs:    Sin fan-out: 3151 registros aprobados.
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO src.etapa4_control_obs:    Pivot: 267121 filas, 266009 con al menos 1 observación (99.6%).
INFO src.etapa4_control_obs:    Join pivot: 3151 partes aprobados, 3151 con match en pivot (100.0%).
INFO src.etapa4_control_obs:    Normalización obs: 3150 con obs, 1 sin obs (total=3151).
INFO src.etapa4_control_obs:      _APP_GABINETE                            → 192 positivos
INFO src.etapa4_control_obs:      _APP_SUBTERRANEO                         → 480 positivos
INFO src.etapa4_control_obs:      _APP_ALTURA                              → 1162 positivos
INFO src.etapa4_control_obs:      _APP_AEREO                               → 1320 positivos
INFO src.etapa4_control_obs:      _APP_EQUIPO_MEDICION_REEMPLAZADO         → 3150 positivos
INFO src.etapa4_control_obs:      _APP_ACOMETIDA_REALIZADA                 → 3 positivos
INFO src.etapa4_control_obs:      _APP_TAPA_REEMPLAZADA                    → 860 positivos
INFO src.etapa4_control_obs:      _APP_EQUIPO_DE_MEDICION_INSTALADO        → 3148 positivos
WARNING src.etapa4_control_obs:    2505 registros SIN match con reglas del código declarado.
INFO src.etapa4_control_obs:    Hamming global calculado: 3151 partes × 21 reglas (66171 comparaciones). Restricción por contratista activa (2 contratistas).
INFO src.etapa4_control_obs:    control_obs_app guardada con 3151 filas y 50 columnas.
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO src.etapa4_control_obs: dim_img_app_pd: 3151 ordenativos únicos con fotos.
INFO api.services.worker: _enriquecer_uses — total=146066 con_uses=27862 sin_epec=118204 cod_sin_regla=0
INFO api.services.worker: WORKER motor — etapa4: aprobados=3151, no-aprobados=146066, total=149217
INFO api.services.worker: _auto_rescatar_local — total_huerfanos=3 rescatados_1cand=0 ambiguos_Ncand=0 sin_match=3 ultimo_sync=2026-05-08 14:43:32.617407
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO api.services.parte_import: _limpiar_lote_previo — lote 5: 148688 procesados, 109395 imágenes, 0 auditoría eliminados.
INFO api.services.parte_import: _rescatar_duplicados_intra — 11712 duplicados rescatados (traza=16).
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO api.services.parte_import: importar_lote 5 — USES coverage: total=149217 con_epec_y_uses=28508 sin_uses=0
WARNING api.services.parte_import: importar_lote 5 — 2505 partes APROBADOS sin VALOR_USES_ORIGEN (cod_epec sin regla definida): []
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "OPTIONS /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "OPTIONS /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
WARNING api.services.lote: No se pudo actualizar progreso del lote 5 (FINALIZANDO): (sqlite3.OperationalError) database is locked
[SQL: UPDATE lotes_archivos SET paso_actual=?, progreso_pct=? WHERE lotes_archivos.id = ?]
[parameters: ('FINALIZANDO', 95, 5)]
(Background on this error at: https://sqlalche.me/e/20/e3q8)
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes?skip=0&limit=200 HTTP/1.1" 307 Temporary Redirect
INFO:     127.0.0.1:60951 - "GET /api/v1/lotes/?skip=0&limit=200 HTTP/1.1" 200 OK
INFO api.services.worker: Lote 5 procesado OK: raws=149217, procesados=149217, imagenes=18275