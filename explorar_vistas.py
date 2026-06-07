"""
Explorador de vistas SQL Server — MRP Bianchi
Lee credenciales desde .env y lista todas las vistas disponibles.
Solo lectura. No modifica ningún dato.
"""
import os
import sys
import pyodbc
import pandas as pd
from dotenv import load_dotenv

# Forzar UTF-8 en la salida para evitar errores de encoding en Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

SERVER   = os.getenv("JDE_SERVER")
DATABASE = os.getenv("JDE_DATABASE")
USERNAME = os.getenv("JDE_USER")
PASSWORD = os.getenv("SQL_PASSWORD")

conn_str = (
    f"DRIVER={{SQL Server}};"
    f"SERVER={SERVER};"
    f"DATABASE={DATABASE};"
    f"UID={USERNAME};"
    f"PWD={PASSWORD};"
    f"TrustServerCertificate=yes;"
)

print(f"Conectando a {SERVER} / {DATABASE} ...")

try:
    conn = pyodbc.connect(conn_str, timeout=10)
    print("✓ Conexión exitosa\n")
except Exception as e:
    print(f"✗ Error de conexión: {e}")
    raise SystemExit(1)

queries = {
    "Vistas disponibles": """
        SELECT TABLE_SCHEMA AS esquema, TABLE_NAME AS nombre
        FROM INFORMATION_SCHEMA.VIEWS
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """,
    "Funciones de tabla": """
        SELECT ROUTINE_SCHEMA AS esquema, ROUTINE_NAME AS nombre, ROUTINE_TYPE AS tipo
        FROM INFORMATION_SCHEMA.ROUTINES
        WHERE ROUTINE_TYPE = 'FUNCTION'
        ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
    """,
}

for titulo, sql in queries.items():
    try:
        df = pd.read_sql(sql, conn)
        print(f"── {titulo} ({len(df)} encontradas) ──")
        if df.empty:
            print("   (ninguna)\n")
        else:
            print(df.to_string(index=False))
            print()
    except Exception as e:
        print(f"   Error al consultar: {e}\n")

conn.close()
print("Listo. Compartí el resultado para identificar las vistas a usar.")
