# MRP Bianchi — versión rediseñada (tema "Claro corporativo")

Reemplazo visual de los módulos **MRP** y **Producción**, conservando intacta toda
tu lógica de cálculo. Listo para correr en local.

## Archivos

```
app.py                  ← app principal rediseñada (reemplaza tu app.py)
tema.py                 ← capa visual: CSS corporativo + tarjetas (NUEVO)
.streamlit/config.toml  ← tema base de Streamlit (colores + fuentes)
```

## Cómo probarlo

1. Copiá estos 3 archivos a la carpeta de tu proyecto (junto a `requirements.txt`).
   - `app.py` reemplaza al actual (hacé un backup del tuyo: `app_original.py`).
   - `tema.py` es nuevo.
   - La carpeta `.streamlit/` con `config.toml` va en la raíz del proyecto.
2. Corré como siempre:
   ```
   streamlit run app.py
   ```
3. Cargá tus archivos (stock / ordenes / bom / forecast) desde el panel izquierdo.

No agrega dependencias nuevas: usa las mismas (`streamlit`, `pandas`, `openpyxl`,
`xlsxwriter`).

## Qué cambió

**Visual / tema**
- Paleta clara corporativa (fondo frío, superficies blancas) con acento vino `#7a1f2b`.
- Tipografía **IBM Plex Sans** + **IBM Plex Mono** para los números (legibilidad).
- Tabs, botones, inputs y métricas restilizados.

**Módulo MRP**
- **Resumen ejecutivo** en tarjetas: Críticos / Parciales / Cubiertos / Compra
  sugerida total / Próximo quiebre.
- Banner de antigüedad del stock con color de estado.
- Tabla con números alineados y una columna **"Necesidad semanal"** como
  mini-gráfico de barras (sparkline nativo de Streamlit).
- Detalle del insumo con pill de estado, métricas, **gráfico de cobertura** y la
  edición de OC vencidas (igual que antes).

**Módulo Producción**
- **Resumen** en tarjetas: Artículos en plan / Total plan / Forecast / Desvío
  (el Desvío se pinta si te alejás >5% del forecast).
- Tabla editable con una columna **"Distribución"** que grafica el reparto semanal.
- Se mantienen Agregar artículo, Redistribuir y la búsqueda.

## Diferencias con el prototipo HTML (por límites de Streamlit)

- El **panel de detalle** va como sección desplegable debajo de la tabla (Streamlit
  no permite un panel lateral flotante sincronizado).
- El sparkline de cobertura es **monocromo** (el verde/rojo por celda no es nativo
  en las columnas de gráfico); el semáforo va en su propia columna **Estado**.
- El color de acento y el tema se fijan en `config.toml` / `tema.py` (no hay panel
  de "Tweaks" en vivo como en el prototipo).

Si querés, el siguiente paso es trasladar también la pestaña **Datos** y/o sumar el
dashboard de erogaciones por semana.
