# Guía Power Automate — Actualización automática de datos MRP

## Contexto

Esta guía documenta la configuración de los flujos de Power Automate que
reemplazan la carga manual de datos en el MRP Bodegas Bianchi.

**Dataset Power BI origen:** `Prueba Insumos v4.0` (publicado en Power BI Service)
**Destino:** carpeta `Archivos/` dentro del proyecto en OneDrive
**Archivos generados:** `stock.csv`, `ordenes.csv`, `bom.csv`
**Archivo manual:** `forecast.xlsx` (el analista lo actualiza cuando cambia)

---

## Estructura de cada bloque (se repite ×3)

```
Paso 1 — Run a query against a dataset   (conector: Power BI)
Paso 2 — Parse JSON                       (conector: Data Operations)
Paso 3 — Create CSV table                 (conector: Data Operations)
Paso 4 — Get file metadata using path     (conector: OneDrive for Business)
Paso 5 — Update file                      (conector: OneDrive for Business)
```

---

## BLOQUE 1 — stock.csv

### Paso 1: Run a query against a dataset
- **Workspace:** (seleccionar workspace de Bianchi)
- **Dataset:** Prueba Insumos v4.0
- **Query DAX:**
```dax
EVALUATE
SUMMARIZECOLUMNS(
    'PRODDTA Fn_Exp_Form_Cost'[Cod. Composición],
    'PRODDTA Fn_Exp_Form_Cost'[Desc. Composición],
    'PRODDTA Fn_Exp_Form_Cost'[Texto de Busqueda],
    "stock", [Cantidad Insumos v2]
)
ORDER BY 'PRODDTA Fn_Exp_Form_Cost'[Cod. Composición]
```

### Paso 2: Parse JSON
- **Content** (expresión):
```
body('Query_Stock')?['results'][0]?['tables'][0]?['rows']
```
- **Schema:**
```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "PRODDTA Fn_Exp_Form_Cost[Cod. Composición]": {"type": "string"},
      "PRODDTA Fn_Exp_Form_Cost[Desc. Composición]": {"type": "string"},
      "PRODDTA Fn_Exp_Form_Cost[Texto de Busqueda]": {"type": "string"},
      "stock": {"type": "number"}
    }
  }
}
```

### Paso 3: Create CSV table
- **From:** `Body` del paso Parse JSON (contenido dinámico)
- **Columns:** Custom

| Header | Value (expresión) |
|---|---|
| `codigo` | `item()?['PRODDTA Fn_Exp_Form_Cost[Cod. Composición]']` |
| `descripcion` | `item()?['PRODDTA Fn_Exp_Form_Cost[Desc. Composición]']` |
| `tipo_insumo` | `item()?['PRODDTA Fn_Exp_Form_Cost[Texto de Busqueda]']` |
| `stock` | `item()?['stock']` |

### Paso 4: Get file metadata using path
- **File path:** `/PowerBI/Automatizaciones/Prueba MRP/MRP Bianchi/Archivos/stock.csv`

### Paso 5: Update file
- **Id:** `ID` (contenido dinámico del paso 4)
- **File content:** output del paso 3 (Create CSV table)

---

## BLOQUE 2 — ordenes.csv

### Paso 1: Run a query against a dataset
- **Query DAX:**
```dax
EVALUATE
CALCULATETABLE(
    SUMMARIZECOLUMNS(
        'PRODDTA Fn_Pendientes_OC'[2° número de artículo],
        'PRODDTA Fn_Pendientes_OC'[Fecha solic],
        "cantidad_oc", SUM('PRODDTA Fn_Pendientes_OC'[Cantidad])
    ),
    'PRODDTA Fn_Pendientes_OC'[Tipo de orden] IN {"9R", "O9"}
)
ORDER BY 'PRODDTA Fn_Pendientes_OC'[2° número de artículo],
         'PRODDTA Fn_Pendientes_OC'[Fecha solic]
```

### Paso 2: Parse JSON
- **Content** (expresión):
```
body('Query_Ordenes')?['results'][0]?['tables'][0]?['rows']
```
- **Schema:**
```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "PRODDTA Fn_Pendientes_OC[2° número de artículo]": {"type": "string"},
      "PRODDTA Fn_Pendientes_OC[Fecha solic]": {"type": "string"},
      "cantidad_oc": {"type": "number"}
    }
  }
}
```

### Paso 3: Create CSV table
- **From:** `Body` del paso Parse JSON
- **Columns:** Custom

| Header | Value (expresión) |
|---|---|
| `codigo` | `item()?['PRODDTA Fn_Pendientes_OC[2° número de artículo]']` |
| `cantidad_oc` | `item()?['cantidad_oc']` |
| `fecha_entrega` | `item()?['PRODDTA Fn_Pendientes_OC[Fecha solic]']` |

### Paso 4: Get file metadata using path
- **File path:** `/PowerBI/Automatizaciones/Prueba MRP/MRP Bianchi/Archivos/ordenes.csv`

### Paso 5: Update file
- **Id:** `ID` del paso 4
- **File content:** output del paso 3

---

## BLOQUE 3 — bom.csv

### Paso 1: Run a query against a dataset
- **Query DAX:**
```dax
EVALUATE
SUMMARIZECOLUMNS(
    'PRODDTA Fn_Exp_Form_Cost'[Cod. Articulo],
    'PRODDTA Fn_Exp_Form_Cost'[Cod. Composición],
    'PRODDTA Fn_Exp_Form_Cost'[Desc. Composición],
    "cantidad_por_unidad", SUM('PRODDTA Fn_Exp_Form_Cost'[Cantidad Comp.])
)
ORDER BY 'PRODDTA Fn_Exp_Form_Cost'[Cod. Articulo],
         'PRODDTA Fn_Exp_Form_Cost'[Cod. Composición]
```

### Paso 2: Parse JSON
- **Content** (expresión):
```
body('Query_BOM')?['results'][0]?['tables'][0]?['rows']
```
- **Schema:**
```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "PRODDTA Fn_Exp_Form_Cost[Cod. Articulo]": {"type": "string"},
      "PRODDTA Fn_Exp_Form_Cost[Cod. Composición]": {"type": "string"},
      "PRODDTA Fn_Exp_Form_Cost[Desc. Composición]": {"type": "string"},
      "cantidad_por_unidad": {"type": "number"}
    }
  }
}
```

### Paso 3: Create CSV table
- **From:** `Body` del paso Parse JSON
- **Columns:** Custom

| Header | Value (expresión) |
|---|---|
| `articulo` | `item()?['PRODDTA Fn_Exp_Form_Cost[Cod. Articulo]']` |
| `codigo_insumo` | `item()?['PRODDTA Fn_Exp_Form_Cost[Cod. Composición]']` |
| `descripcion_insumo` | `item()?['PRODDTA Fn_Exp_Form_Cost[Desc. Composición]']` |
| `cantidad_por_unidad` | `item()?['cantidad_por_unidad']` |

### Paso 4: Get file metadata using path
- **File path:** `/PowerBI/Automatizaciones/Prueba MRP/MRP Bianchi/Archivos/bom.csv`

### Paso 5: Update file
- **Id:** `ID` del paso 4
- **File content:** output del paso 3

---

## Trigger del flujo

- **Tipo:** Flujo de nube programado (Scheduled cloud flow)
- **Recurrencia sugerida:** Semanal, lunes 6:00 AM
- Para forzar una actualización inmediata: botón **Ejecutar** en el editor del flujo

---

## Troubleshooting

### Los valores de columna salen vacíos en el CSV
El nombre de la key en el JSON del paso "Run a query" puede diferir levemente.
Para verificar el nombre exacto:
1. Ejecutar el flujo una vez
2. Abrir el historial del flujo → clic en el paso "Run a query"
3. Expandir **Outputs** → buscar la sección `rows`
4. Copiar el nombre exacto de cada key y reemplazarlo en las expresiones `item()?['...']`

### Error en "Parse JSON" — schema no coincide
Ejecutar el flujo, copiar el JSON real del output de "Run a query" (sección rows),
y usar el botón **"Generar desde muestra"** en Parse JSON para que PA infiera el schema automáticamente.

### Error en "Update file" — archivo no encontrado
Verificar que el archivo ya exista en la ruta especificada en OneDrive.
Si nunca existió, usar **Create file** una sola vez para crearlo, luego volver a **Update file**.

---

## Pendiente después de probar los flujos

1. Compartir los 4 archivos en OneDrive (stock.csv, ordenes.csv, bom.csv, forecast.xlsx)
   con **"Cualquier persona con el vínculo puede ver"**
2. Obtener los 4 links → convertir a URL de descarga directa (reemplazar `?e=XXXX` por `?download=1`)
3. Actualizar `app.py`: reemplazar los 4 IDs de Google Sheets (`GD_IDS`) por las URLs de OneDrive
