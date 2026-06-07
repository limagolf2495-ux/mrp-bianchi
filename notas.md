# Notas de diseño — Refactorización MRP Bianchi

## Contexto
Refactorización de `app.py` (1807 líneas) en módulos separados. Realizada el 07/06/2026.
Sin cambios funcionales — solo reorganización estructural.

---

## Decisiones de diseño

### 1. Estructura plana, no paquetes anidados
Se eligió un directorio plano (`tab_datos.py`, `tab_mrp.py`, etc.) en lugar de crear subcarpetas (`tabs/`, `utils/`).
- Python requiere `__init__.py` para paquetes anidados
- La estructura plana es más simple de mantener
- `streamlit run app.py` funciona sin configuración adicional

### 2. Patrón `render_*()` sin argumentos
Cada tab y el sidebar se convirtieron en funciones `render_tab_X()` que leen y escriben `st.session_state` directamente, sin recibir datos por parámetro.
Refleja el modelo natural de Streamlit: el estado es global a la sesión.

### 3. `app.py` como orquestador puro (~60 líneas)
Solo hace tres cosas: init de session state, autoload de Google Drive, y llamadas a `render_sidebar()` + cada `render_tab_*()`. Sin lógica de negocio.

### 4. Separación cálculo / presentación en MRP
- `mrp_calc.py` — lógica de cálculo pura, escribe en `st.session_state`
- `tab_mrp.py` — solo lee ese estado y renderiza
Permite re-testear la lógica sin levantar Streamlit.

### 5. `config.py` sin imports locales
`config.py` es la única hoja que no depende de ningún otro módulo propio. Todos los demás lo importan a él. Garantiza que no haya ciclos de importación.

Grafo de dependencias (sin ciclos):
```
config  ←── helpers ←── planificacion, mrp_calc
        ←── gsheets ←── sidebar, tab_planificacion, tab_mrp, app
        ←── todos los demás

precios ←── sidebar
tema    ←── tab_*, app
```

### 6. `HOY = date.today()` evaluado una sola vez
Se mantuvo en `config.py` como constante de módulo, no como función. La fecha se fija al momento en que arranca el proceso, preservando el comportamiento original.

### 7. `exportar_cf` local a `tab_cashflow.py`
- `exportar_excel()` (para MRP) → `helpers.py`, es de uso general
- `_exportar_cf()` (para Cash-Flow, con formato diferente y fila TOTAL) → privada en `tab_cashflow.py`, no se reutiliza en otro lugar

### 8. Sin cambios funcionales
Restricción estricta: cero cambios de comportamiento. Los bugs documentados se preservaron tal como estaban.

---

## Módulos resultantes

| Archivo | Responsabilidad |
|---|---|
| `config.py` | Constantes: `GD_IDS`, `MESES`, `HOY`, `DEFAULTS` |
| `helpers.py` | Funciones puras: fechas, `distribuir`, `semaforo`, `exportar_excel` |
| `gsheets.py` | I/O Google Sheets: estados OC, reglas PT |
| `precios.py` | Parser de precios PBI (`_parse_precio_arg`, `procesar_precios_pbi`) |
| `planificacion.py` | `calcular_stock_objetivo` |
| `mrp_calc.py` | Lógica de cálculo MRP completa |
| `sidebar.py` | `render_sidebar()` |
| `tab_datos.py` | `render_tab_datos()` |
| `tab_planificacion.py` | `render_tab_planificacion()` |
| `tab_produccion.py` | `render_tab_produccion()` |
| `tab_mrp.py` | `render_tab_mrp()` |
| `tab_cashflow.py` | `render_tab_cashflow()` |
| `tab_configuracion.py` | `render_tab_configuracion()` |
| `app.py` | Orquestador delgado: init, autoload GD, sidebar, tabs |
| `tema.py` | Estilos/UI — sin modificar |

---

## Auditoría de riesgos en producción (07/06/2026)

Se analizaron todos los módulos buscando puntos de falla. Se identificaron 18 riesgos, clasificados en cuatro categorías.

### Críticos — crash sin catch visible
| # | Dónde | Problema |
|---|---|---|
| 1 | `mrp_calc.py:36` | `stock_df` accedida con columnas hardcodeadas — KeyError si el CSV no coincide |
| 2 | `mrp_calc.py:47` | Ídem `oc_df`: `codigo`, `cantidad_oc`, `fecha_entrega` |
| 3 | `mrp_calc.py:103` | Ídem `bom_df`: `articulo`, `codigo_insumo`, `cantidad_por_unidad` |
| 4 | `mrp_calc.py:34` | `todas_sems[-1][2]` — IndexError si horizonte=0 y fin de mes |
| 5 | `tab_cashflow.py:89` | `sem_totales.idxmax()` — ValueError si `mrp_sem_headers` vacío |
| 6 | `helpers.py:85` | `exportar_excel` usa índice original del df — filas solapadas si df fue filtrado |

### Silenciosos — datos incorrectos sin error visible
| # | Dónde | Problema |
|---|---|---|
| 7 | `app.py:25` | GD autoload parcial: si falla a la mitad, `gd_cargado=True` y datos incompletos sin aviso |
| 8 | `sidebar.py:124` | `dayfirst=True` con `errors="coerce"` — fechas MM/DD parsean sin error pero con mes/día invertido |
| 9 | `tab_cashflow.py:48` | Códigos con ceros a la izquierda en precios.csv vs stock/BOM → match falla silenciosamente |
| 10 | `config.py:4` | `HOY = date.today()` evaluado una vez en deploy — fecha congelada por días/semanas en Cloud |
| 11 | `precios.py:39` | Formato `%d/%m/%Y` hardcodeado — cualquier otro formato deja todas las fechas en NaT |

### Degradación silenciosa de funcionalidad
| # | Dónde | Problema |
|---|---|---|
| 12 | `sidebar.py:168` | Encoding Latin-1 en precios.csv → UnicodeDecodeError con mensaje críptico |
| 13 | `gsheets.py:8` | `_gs_client()` devuelve None sin aviso — GSheets desactivado si falta secrets.toml |
| 14–15 | `mrp_calc.py`, `tab_planificacion.py` | Forecast sin columna del mes actual → demanda cero, sin warning claro |
| 16 | `gsheets.py:53` | `ws.update("A1", rows)` sin paginación — falla con muchas OC en estado Pendiente |

### Comportamientos inesperados conocidos
| # | Dónde | Problema |
|---|---|---|
| 17 | `helpers.py:semanas_del_mes` | Bug en meses de 6 semanas (agosto 2026) — ya documentado |
| 18 | `mrp_calc.py:64` | Plan de producción con índices de semana obsoletos si el mes cambió entre sesiones |

---

## Arreglos aplicados (07/06/2026)

### Errores 1, 2, 3 — Columnas hardcodeadas (crash por KeyError)

**Patrón aplicado en los tres casos:**
1. Se movieron los nombres de columna a `config.py` como constantes con nombre descriptivo.
2. Se agregó `validar_columnas(df, cols_requeridas, nombre)` en `helpers.py`, que lanza `ValueError` con mensaje del tipo: `'stock.csv' — columnas faltantes: ['tipo_insumo']. Columnas encontradas: [...]`
3. Se llama a `validar_columnas` en `sidebar.py` (upload manual) y `app.py` (autoload GD), antes de parsear tipos. El `except` existente captura el `ValueError` y muestra `st.error()`.
4. Los consumidores (`mrp_calc.py`, `gsheets.py`) usan las constantes en lugar de strings literales.

**Constantes agregadas en `config.py`:**
```
COLS_STOCK: COL_STOCK_COD, COL_STOCK_DESC, COL_STOCK_TIPO, COL_STOCK_QTY
COLS_OC:    COL_OC_COD, COL_OC_QTY, COL_OC_FECHA
COLS_BOM:   COL_BOM_ART, COL_BOM_INS, COL_BOM_QTY
```

**Archivos modificados:** `config.py`, `helpers.py`, `mrp_calc.py`, `gsheets.py`, `sidebar.py`, `app.py`

---

### Error 10 — `HOY` congelado en Streamlit Cloud

`HOY = date.today()` se evaluaba una sola vez al importar el módulo. En Streamlit Cloud, un worker puede vivir semanas sin restart, dejando la fecha obsoleta.

**Solución:** se reemplazó la constante por una función en `config.py`:
```python
def get_hoy():
    return date.today()
```
En funciones con múltiples usos se llama `hoy = get_hoy()` una vez al inicio (consistencia dentro del render). En usos únicos se llama inline.

**Archivos modificados:** `config.py`, `helpers.py`, `planificacion.py`, `gsheets.py`, `mrp_calc.py`, `tab_datos.py`, `tab_cashflow.py`, `tab_mrp.py`, `tab_planificacion.py`, `tab_produccion.py`, `sidebar.py`, `app.py` (12 archivos en total).

---

### Error 11 — Formato de fecha hardcodeado en `precios.py`

`pd.to_datetime(..., format="%d/%m/%Y")` rechazaba silenciosamente cualquier exportación de Power BI o Excel con formato distinto (ISO, MM/DD, variantes con hora).

**Solución:**
```python
result["fecha_ultima_oc"] = pd.to_datetime(
    df["fecha_recepcion"], dayfirst=True, errors="coerce"
)
nat_count = result["fecha_ultima_oc"].isna().sum()
if nat_count > 0:
    logging.warning(
        "precios: %d/%d fechas en 'fecha_recepcion' no pudieron parsearse (NaT). "
        "Verificá el formato del archivo.", nat_count, len(result)
    )
```
`dayfirst=True` sin `format=` tolera `DD/MM/YYYY`, `D/M/YY`, `YYYY-MM-DD` y otros. El warning aparece en los logs del servidor (visible en `streamlit run` y en Streamlit Cloud) sin interrumpir el flujo.

**Archivos modificados:** `precios.py`

---

## Riesgos pendientes de resolver

Los siguientes riesgos fueron identificados pero **no corregidos** en esta sesión:

| # | Prioridad | Descripción |
|---|---|---|
| 4 | Alta | `todas_sems[-1][2]` — agregar guard si lista vacía |
| 5 | Alta | `idxmax()` sobre Series vacía en `tab_cashflow.py` |
| 6 | Media | `exportar_excel` — resetear índice antes de escribir filas |
| 7 | Media | GD autoload parcial — cargar cada fuente en try/except independiente |
| 8 | Media | Fechas invertidas en ventas/pedidos (MM/DD vs DD/MM) |
| 9 | Baja | Match de códigos con ceros a la izquierda |
| 12 | Baja | Encoding Latin-1 en precios.csv |
| 13 | Baja | GSheets silenciosamente desactivado (falta secrets.toml) |
| 14–15 | Baja | Sin warning cuando forecast no tiene el mes actual |
| 16 | Baja | `ws.update` sin paginación en gspread |
| 17 | Media | Bug meses de 6 semanas (agosto 2026) |
| 18 | Baja | Plan de producción con índices obsoletos entre sesiones |
