# Plan: Filtro Interactivo por Estados en Detalle Lote

Este plan describe los pasos para agregar interactividad a la tarjeta "Distribución por Estados de Proceso", permitiendo que al hacer clic en un estado (ej. "Rechazado"), el gráfico de dona de la izquierda se actualice para mostrar la composición interna de ese estado (qué trazas lo componen y en qué porcentaje).

## 1. Nuevo Estado Local en DetalleLote.jsx
- Añadir un hook de estado: `const [estadoSeleccionado, setEstadoSeleccionado] = useState('Aprobado');`

## 2. Interactividad en la Tarjeta Derecha (Estados)
- Modificar el mapeo de la tarjeta "Distribución por Estados de Proceso".
- Envolver cada fila (`div` correspondiente a cada estado) en un elemento clickeable (`onClick={() => setEstadoSeleccionado(row.label)}`).
- Cambiar el cursor a `pointer`.
- Agregar un estilo visual condicional para indicar cuál es el estado seleccionado (por ejemplo, un borde lateral izquierdo más grueso del color del estado, o un ligero cambio en el `background` de la fila entera).

## 3. Preparación de Datos para el Gráfico
- Crear una función derivada que, basado en `estadoSeleccionado`, filtre `dash.distribucion_trazas` para obtener solo las trazas que pertenecen a ese estado (usando los Sets `TRAZAS_APROBADO`, `TRAZAS_RECHAZADO`, etc.).
- Ordenar estas trazas de mayor a menor `count`.
- (Opcional pero recomendado por UI) Si hay más de 4 o 5 trazas (como pasa en Rechazado), agrupar las trazas menores en una categoría "Otras" para que la dona no quede con micro-rebanadas ilegibles.
- Preparar un array de objetos `{ label, count, color }`. A cada traza se le asignará un color de una paleta predefinida correspondiente al estado padre (ej. distintos tonos de rojo para Rechazado).

## 4. Componente `DonutDistribucion` Genérico
- Reemplazar el actual componente `DonutAprobados` (que está hardcodeado para "directo" y "corregido") por un nuevo componente genérico `DonutDistribucion({ data })`.
- Este componente recibirá el array de datos y calculará matemáticamente los `strokeDasharray` y `strokeDashoffset` para dibujar N rebanadas en el SVG (usando `Math.PI * r * 2`).
- A la derecha (o debajo) del SVG, renderizar la leyenda con los cuadraditos de colores, el nombre de la traza y su porcentaje, reemplazando la leyenda hardcodeada actual.

## 5. Actualización de Textos
- El título de la tarjeta izquierda debe ser dinámico: `"COMPOSICIÓN DEL ESTADO: " + estadoSeleccionado.toUpperCase()`.

## Resumen de Cambios a Ejecutar:
1. Reescritura del bloque SVG de dona para soportar N segmentos proporcionales dinámicos.
2. Inserción de la lógica de filtrado contra los Sets de trazas que definimos en la tarea anterior.
3. Eventos `onClick` y UI feedback en la lista de estados de la derecha.
