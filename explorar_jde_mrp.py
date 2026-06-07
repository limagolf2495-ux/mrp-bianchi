"""
Exploración de vistas/funciones JDE para los 4 inputs del MRP.
Ejecutar una sola vez para identificar los objetos correctos.
Resultados se guardan en exploración_jde_mrp.xlsx
"""

import sys
import io
import pandas as pd
from db_connection import query

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

KEYWORDS_POR_INPUT = {
    "STOCK (saldo inventario)": ["STOCK", "INVENT", "SALDO", "EXIST"],
    "OC (órdenes de compra)":   ["ORDEN", "COMPRA", "OC", "PURCHASE", "PURCH"],
    "BOM (lista de materiales)": ["BOM", "FORMULA", "COMP", "LISTA", "MATER", "RECETA"],
    "FORECAST (ventas/plan)":   ["FOREC", "PRON", "PLAN", "VENTA", "DEMAND"],
}

resultados = {}

print("=" * 60)
print("EXPLORACIÓN DE OBJETOS JDE PARA MRP")
print("=" * 60)

# ── 1. Todas las vistas disponibles ──────────────────────────────
print("\n[1] Listando todas las vistas del esquema PRODDTA...")
try:
    df_todas = query("""
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.VIEWS
        WHERE TABLE_SCHEMA = 'PRODDTA'
        ORDER BY TABLE_NAME
    """)
    print(f"    → {len(df_todas)} vistas encontradas")
    resultados["Todas las vistas"] = df_todas
except Exception as e:
    print(f"    ERROR: {e}")
    df_todas = pd.DataFrame(columns=["TABLE_SCHEMA", "TABLE_NAME"])

# ── 2. Buscar por keywords para cada input ───────────────────────
for input_mrp, keywords in KEYWORDS_POR_INPUT.items():
    print(f"\n[2] Buscando objetos para: {input_mrp}")
    like_clauses = " OR ".join([f"TABLE_NAME LIKE '%{kw}%'" for kw in keywords])
    sql = f"""
        SELECT TABLE_TYPE, TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE ({like_clauses})
        ORDER BY TABLE_TYPE, TABLE_NAME
    """
    try:
        df = query(sql)
        print(f"    → {len(df)} objetos encontrados: {df['TABLE_NAME'].tolist()}")
        resultados[input_mrp] = df
    except Exception as e:
        print(f"    ERROR: {e}")
        resultados[input_mrp] = pd.DataFrame()

# ── 3. Buscar funciones de tabla ──────────────────────────────────
print("\n[3] Listando funciones de tabla disponibles en PRODDTA...")
try:
    df_fns = query("""
        SELECT o.name AS Funcion, o.type_desc AS Tipo,
               p.name AS Parametro, t.name AS TipoDato
        FROM sys.objects o
        LEFT JOIN sys.parameters p ON p.object_id = o.object_id AND p.parameter_id > 0
        LEFT JOIN sys.types t ON p.user_type_id = t.user_type_id
        WHERE o.schema_id = SCHEMA_ID('PRODDTA')
          AND o.type IN ('IF','TF','FN')
        ORDER BY o.name, p.parameter_id
    """)
    print(f"    → {len(df_fns)} filas (funciones + parámetros)")
    resultados["Funciones de tabla"] = df_fns
except Exception as e:
    print(f"    ERROR: {e}")

# ── 4. Ver columnas de candidatos encontrados ─────────────────────
candidatos_conocidos = [
    "VISTA_SALIDAS_DE_INVENTARIO",
    "VISTA_SEG_VTA_COMEX",
    "PBI_REMITOS_A_CALICO",
]
print("\n[4] Inspeccionando columnas de vistas ya conocidas...")
for nombre in candidatos_conocidos:
    try:
        df_cols = query(f"""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{nombre}' AND TABLE_SCHEMA = 'PRODDTA'
            ORDER BY ORDINAL_POSITION
        """)
        print(f"\n    {nombre}:")
        for _, row in df_cols.iterrows():
            print(f"      - {row['COLUMN_NAME']} ({row['DATA_TYPE']})")
        resultados[f"Cols_{nombre}"] = df_cols
    except Exception as e:
        print(f"    ERROR en {nombre}: {e}")

# ── 5. Guardar resultados ─────────────────────────────────────────
output_path = "exploracion_jde_mrp.xlsx"
print(f"\n[5] Guardando resultados en {output_path}...")
with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
    for sheet_name, df in resultados.items():
        if df is not None and not df.empty:
            safe_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)

print(f"\n✅ Exploración completa. Abrí {output_path} y buscá las vistas")
print("   correctas para cada input del MRP.")
print("\n   Una vez identificadas, completar actualizar_mrp.py con los nombres reales.")
