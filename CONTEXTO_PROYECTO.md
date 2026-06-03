# MRP Bodegas Bianchi — Contexto del Proyecto

## Qué es esta app

Aplicación Streamlit (Python) que corre localmente para calcular el
Plan de Compras de insumos (MRP) en base a stock, órdenes de compra,
lista de materiales (BOM) y forecast de ventas.

---

## Archivos del proyecto

```
MRP_Bianchi/
├── app.py              ← aplicación principal (Streamlit)
├── tema.py             ← estilos y componentes visuales (tema claro corporativo)
├── requirements.txt    ← dependencias Python
├── instalar.bat        ← instala dependencias (Windows, una sola vez)
├── iniciar.bat         ← corre la app (Windows, cada vez que se usa)
├── logo_bianchi.png    ← logo del sidebar (embebido en base64)
└── Archivos/           ← datos de prueba reales
```

---

## Archivos de datos que carga el usuario

| Archivo        | Formato | Columnas clave                                              |
|----------------|---------|-------------------------------------------------------------|
| stock.csv      | CSV     | codigo, descripcion, tipo_insumo, stock                     |
| ordenes.csv    | CSV     | codigo, cantidad_oc, fecha_entrega                          |
| bom.csv        | CSV     | articulo, codigo_insumo, descripcion_insumo, cantidad_por_unidad |
| forecast.xlsx  | Excel   | articulo, descripcion, + columnas de meses (ene_26…dic_26)  |

**Nota sobre el forecast:** las columnas de meses pueden venir como
fechas datetime de Excel (2026-06-01). La app las convierte automáticamente.

---

## Lógica del MRP

### Módulo Producción
- Carga automática de todos los artículos con forecast > 0 en el mes actual
- Distribución automática en semanas: 30/30/30/10 (4 sem) o 25/25/25/15/10 (5 sem)
- Semana 1 = día 1 del mes hasta el día anterior al primer lunes
- Semana 2 en adelante = lunes a domingo
- Solo muestra semanas desde la semana actual en adelante (las pasadas se ocultan)
- Permite editar cantidades manualmente por semana
- Permite agregar artículos sin forecast
- Tarjetas de resumen (Artículos / Total plan / Forecast / Desvío) actualizadas
  en tiempo real al editar celdas, usando `st.empty()` como placeholder

### Módulo MRP
- **Mes actual:** usa el plan de producción manual + artículos del forecast
  del mes actual que no estén en producción
- **Meses siguientes (horizonte):** usa el forecast distribuido en semanas
  con la misma distribución % configurable
- **Nunca lee meses anteriores al actual**
- Fórmula: Stock + OC vigentes + OC vencidas parciales - Necesidad bruta = Nec. neta
- Sugerencia de compra = Nec. neta redondeada al múltiplo configurado (default 500)
- Semáforo: 🔴 sin cobertura / 🟡 cobertura parcial / 🟢 cubierto
- Fecha de pedido = semana de necesidad - lead time del tipo de insumo
- Tabla principal muestra "OC disp." con label completo: "1.500 (incl. 300 venc.)"
- Panel de detalle tiene búsqueda por código y por descripción
- Gráfico de barras por semana en el detalle de cada insumo

### OC vencidas
- No suman automáticamente a la cobertura
- En el detalle de cada insumo, el usuario puede cambiar OC vencidas a
  estado "🕐 Pendiente" para indicar que espera recibirlas
- Esa cantidad se suma a OC vigentes y se muestra como
  "1.500 (incl. 300 venc.)" en la columna OC disponibles
- Al recalcular el MRP, la app lee los valores de todos los estados
  activos y los aplica antes de correr el cálculo

---

## Configuración disponible (pestaña Configuración)

- **Horizonte de planificación:** meses a proyectar (default 2)
- **Múltiplo de compra:** redondeo de sugerencias (default 500)
- **Distribución % por semanas:** configurable para 4 y 5 semanas
- **Lead times por tipo de insumo:** días corridos por tipo (default 15)

---

## Stack técnico

- Python 3.x
- Streamlit 1.58.0 (UI)
- Pandas (cálculo y manejo de datos)
- OpenPyXL + XlsxWriter (lectura/escritura Excel)
- Plotly (gráficos interactivos en el detalle de insumo)
- `tema.py` — capa visual separada: paleta, CSS, componentes HTML (`cards`, `banner`, `pill`)
- `.streamlit/config.toml` — tema claro corporativo (primaryColor vino `#7a1f2b`)

---

## Estado actual del código (junio 2026)

La app está estable y funcional. Cambios acumulados:

- **Bugs corregidos en sesión anterior (mayo 2026):**
  - Búsqueda por código/descripción en panel de detalle MRP restaurada
  - Columna "OC disp." en tabla principal vuelve a mostrar label con contexto de vencidas
  - Export Excel crasheaba con NaN en columna "Días al quiebre" → resuelto con `fillna("")`
  - Tarjetas de resumen en Producción no se actualizaban al editar → resuelto con `st.empty()`
  - Logo PNG del sidebar cargado en base64 con fallback al texto si el archivo no existe
  - `tema.py` separado de `app.py`: estilos, padding de tabs y header corregidos
- **Cambios de junio 2026:**
  - Tabla MRP principal: reemplazada columna BarChart ("Cobertura") por columnas numéricas individuales por semana. El Export Excel incluye ahora el desglose semanal de necesidades.
  - Detalle de insumo: gráfico de barras migrado de `st.bar_chart` a Plotly con barras apiladas (🟢 Stock / 🟡 OC vigente+pendiente / 🔴 Sin cobertura) y ordenamiento cronológico explícito (corrige orden alfabético anterior).
  - Dependencia `plotly` agregada a `requirements.txt` e `instalar.bat` la instala vía `pip install -r requirements.txt`.
  - Detalle de insumo: botones masivos "🕐 Todas en Pendiente" y "↺ Restablecer vencidas" para cambiar el estado de todas las OC vencidas de un insumo de una sola vez (aparecen solo si hay OC vencidas). La edición individual sigue disponible.
  - Detalle de insumo: botón "⬇️ Exportar este insumo" que genera un Excel con N° Artículo, Cantidad necesaria y Fecha necesaria (dd/mm/yyyy) por semana con demanda > 0. Para lograrlo se persistió `todas_sems` en `st.session_state.mrp_todas_sems`.

---

## Roadmap priorizado

### 1. Export formato JD Edwards ⬅️ siguiente paso
**Por qué primero:** es la última milla — el analista calcula el MRP pero igual
carga las solicitudes a mano en JDE. Cerrar ese loop convierte la app de
"consulta" a "herramienta de trabajo".
**Qué falta:** ver un ejemplo real del formato de importación de JDE
(layout de columnas, formato de fechas, códigos de artículo, unidades, etc.)
antes de programar. El usuario está buscando un ejemplo.

### 2. Gestión de OC vencidas
**Por qué urgente:** en el archivo de prueba hay 203 OC vencidas de 225 totales
(90%). Sin poder marcarlas como "Recibida" o "Cancelada", cada cálculo MRP
parte de datos contaminados y el analista tiene que override mental los resultados.
**Qué construir:** una vista en la pestaña Datos (o nueva pestaña) para
gestionar OC vencidas en lote — marcar recibidas/canceladas y que salgan
del cálculo hasta que se recargue el archivo.

### 3. Dashboard de erogaciones monetarias por semana
Valor para gerencia/presupuesto. Requiere agregar columna de precio unitario
al stock o BOM. No desbloquea el flujo diario del analista → después de los anteriores.

### 4. Publicar en Streamlit Cloud
**Trampa a resolver primero:** los archivos subidos no persisten entre sesiones.
Opciones: Google Drive como fuente de datos, o aceptar que el usuario sube
los archivos cada vez (viable si el flujo es "abrir → cargar → usar → cerrar").

### 5. Comparativo producción real vs plan al cierre del mes
Útil para mejora continua del forecast. Baja urgencia operativa.

---

## Datos de prueba (Archivos/)

- **521 insumos** en stock
- **225 líneas OC** (203 vencidas — dato relevante para priorizar feature #2)
- **12.523 relaciones BOM**
- **54 artículos** en forecast (meses abr_26 a dic_26)
