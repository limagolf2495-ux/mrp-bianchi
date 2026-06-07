# Conexión SQL a JD Edwards — Referencia para Proyectos Python

## Contexto

El ERP **JD Edwards** expone sus datos a través de vistas y funciones de tabla en SQL Server. El mismo usuario que usa Power BI para los reportes tiene acceso directo a esa base de datos. Esta guía documenta cómo conectarse desde Python y qué objetos están disponibles.

---

## Credenciales y entorno

Las credenciales se guardan en un archivo `.env` en la raíz del proyecto. **Nunca hardcodear credenciales en el código.**

```ini
# .env
JDE_SERVER=SRVJDDBPD
JDE_DATABASE=JDE_PRODUCTION
JDE_USER=ecomm
JDE_PASSWORD=ecomm2025
```

Agregar `.env` al `.gitignore` si el proyecto usa control de versiones.

---

## Dependencias

```bash
pip install pyodbc pandas python-dotenv
```

Requiere tener instalado el driver **SQL Server ODBC** en Windows (viene con SQL Server o se instala por separado desde Microsoft).

---

## Módulo de conexión reutilizable

El archivo `db_connection.py` centraliza la conexión y expone dos funciones:

```python
# db_connection.py
import pyodbc
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

def get_connection():
    return pyodbc.connect(
        f"DRIVER={{SQL Server}};"
        f"SERVER={os.getenv('JDE_SERVER')};"
        f"DATABASE={os.getenv('JDE_DATABASE')};"
        f"UID={os.getenv('JDE_USER')};"
        f"PWD={os.getenv('JDE_PASSWORD')}"
    )

def query(sql: str) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql(sql, conn)
```

**Uso desde cualquier script:**

```python
from db_connection import query

df = query("SELECT TOP 10 * FROM PRODDTA.Fn_IndLog_DespCalico('01/05/2026','31/05/2026')")
```

---

## Exploración de objetos disponibles

### Listar todas las vistas

```python
df_views = query("""
    SELECT TABLE_SCHEMA, TABLE_NAME
    FROM INFORMATION_SCHEMA.VIEWS
    ORDER BY TABLE_SCHEMA, TABLE_NAME
""")
```

### Buscar tablas/vistas por palabra clave

```python
df = query("""
    SELECT TABLE_TYPE, TABLE_SCHEMA, TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%PROD%'
    ORDER BY TABLE_TYPE, TABLE_NAME
""")
```

Keywords útiles en este proyecto: `PROD`, `LOG`, `DESP`, `STOCK`, `PARAD`, `PERSON`, `FOREC`

### Ver columnas de una vista

```python
df_cols = query("""
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'NOMBRE_VISTA' AND TABLE_SCHEMA = 'PRODDTA'
    ORDER BY ORDINAL_POSITION
""")
```

### Ver parámetros de una función de tabla

```python
df_params = query("""
    SELECT p.name AS Parametro, t.name AS Tipo, p.max_length AS Largo
    FROM sys.parameters p
    JOIN sys.types t ON p.user_type_id = t.user_type_id
    WHERE p.object_id = OBJECT_ID('PRODDTA.Fn_NombreFuncion')
    ORDER BY p.parameter_id
""")
```

---

## Objetos de base de datos identificados (esquema `PRODDTA`)

### Vistas

| Objeto | Descripción |
|---|---|
| `VISTA_SALIDAS_DE_INVENTARIO` | Salidas de stock del inventario |
| `VISTA_SEG_VTA_COMEX` | Seguimiento de ventas Comercio Exterior |
| `PBI_REMITOS_A_CALICO` | Remitos enviados a depósito Calico |

### Funciones de tabla (requieren parámetros de fecha)

Los parámetros de fecha se pasan como strings en formato `'DD/MM/YYYY'`.

| Función | Descripción |
|---|---|
| `Fn_IndLog_DespCalico(@desde, @hasta)` | Despachos a Calico — columnas: `UM`, `Cantidad`, `Desc. Dep/Destino` |
| `Fn_IndLog_DespComex(@desde, @hasta)` | Despachos Comercio Exterior (ME) |
| `Fn_IndLog_VtasDirecta(@desde, @hasta)` | Ventas de envío directo |
| `Fn_Movimientos_Logistica(@desde, @hasta)` | Movimientos generales de logística |
| `Fn_Salidas_Logistica(@desde, @hasta)` | Salidas de logística |

**Ejemplo de consulta a una función:**

```python
df = query("SELECT * FROM PRODDTA.Fn_IndLog_DespCalico('01/05/2026','31/05/2026')")

# Filtrar por unidad de medida "caja" y agrupar por destino
import pandas as pd
desglose = (df[df["UM"].str.strip() == "CA"]
            .groupby(df["Desc. Dep/Destino"].str.strip())["Cantidad"]
            .sum()
            .sort_values(ascending=False))
```

---

## Script de diagnóstico / test de conexión

`test_conexion.py` verifica que la conexión esté activa y lista los objetos disponibles. Ejecutarlo antes de empezar un proyecto nuevo:

```bash
python test_conexion.py
```

---

## Consideraciones

- **Encoding**: agregar `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")` al inicio del script si aparecen errores con tildes o ñ al imprimir en consola.
- **Driver**: el string `"DRIVER={SQL Server}"` corresponde al driver nativo de Windows. Si no funciona, listar los drivers disponibles con `pyodbc.drivers()` y usar el que corresponda (puede ser `"ODBC Driver 17 for SQL Server"` o similar).
- **Autenticación**: se usa SQL Authentication (usuario/contraseña), no Windows Authentication. Esto es lo mismo que usa Power BI para conectarse.
- **Esquema por defecto**: todos los objetos del proyecto están bajo el esquema `PRODDTA`.
