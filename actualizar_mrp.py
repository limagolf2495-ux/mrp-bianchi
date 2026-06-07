"""
ETL: JDE SQL Server → Google Sheets del MRP
Ejecutar manualmente o vía Task Scheduler / Power Automate Desktop.

ANTES DE USAR:
  1. Correr explorar_jde_mrp.py para identificar las vistas correctas.
  2. Reemplazar los strings TODO con los nombres reales de vistas/funciones.
  3. Verificar que las columnas coincidan con las esperadas por el MRP.
"""

import sys
import io
import os
from datetime import date, timedelta

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

from db_connection import query

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
load_dotenv()

# ── IDs de Google Sheets (mismos que usa app.py) ─────────────────
GD_IDS = {
    "stock":    "17TsFVJw12V5ndLP_TfVaeMvy-rRA1ScUGZCJIlifM38",
    "ordenes":  "11b__i6OcJUz1Duwzbyo6cy0pEXySob6oOXFpiS0lMCU",
    "bom":      "1CH7jaqmfYiefoGRkHj_n4PwDDnHy1fLX9cEz7dzgqCg",
    "forecast": "1TUEwHs4S7lVJWLAHGJNZd0ZoRDBO5VMGQ4wvq816cqo",
}

# ── Credenciales Google (archivo JSON de la cuenta de servicio) ───
CREDS_JSON = os.getenv("GOOGLE_CREDS_JSON", "creds_google.json")

# ── Vistas JDE (completar tras explorar_jde_mrp.py) ──────────────
# Reemplazar cada TODO con el nombre real de la vista o función.
VISTA_STOCK    = "TODO_VISTA_STOCK"       # ej: "PRODDTA.VISTA_SALDO_INVENTARIO"
VISTA_ORDENES  = "TODO_VISTA_OC"          # ej: "PRODDTA.VISTA_OC_ABIERTAS"
VISTA_BOM      = "TODO_VISTA_BOM"         # ej: "PRODDTA.VISTA_LISTA_MATERIALES"
VISTA_FORECAST = "TODO_VISTA_FORECAST"    # ej: "PRODDTA.VISTA_FORECAST_VENTAS"
#   Si el forecast es una función con fechas, usar:
# VISTA_FORECAST = "PRODDTA.Fn_Forecast('{desde}','{hasta}')"


def extraer_stock() -> pd.DataFrame:
    """Stock actual de insumos. Columnas: codigo, descripcion, tipo_insumo, stock."""
    df = query(f"SELECT * FROM {VISTA_STOCK}")

    # Adaptar nombres de columna al esquema que espera el MRP.
    # Ajustar según las columnas reales que devuelva la vista.
    df = df.rename(columns={
        # "COD_ARTICULO": "codigo",
        # "DESC_ARTICULO": "descripcion",
        # "TIPO": "tipo_insumo",
        # "SALDO": "stock",
    })
    return df[["codigo", "descripcion", "tipo_insumo", "stock"]]


def extraer_ordenes() -> pd.DataFrame:
    """Órdenes de compra abiertas. Columnas: codigo, cantidad_oc, fecha_entrega."""
    df = query(f"SELECT * FROM {VISTA_ORDENES}")

    df = df.rename(columns={
        # "COD_ARTICULO": "codigo",
        # "CANTIDAD":     "cantidad_oc",
        # "FECHA_ENTREGA": "fecha_entrega",
    })
    df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"], errors="coerce")
    return df[["codigo", "cantidad_oc", "fecha_entrega"]]


def extraer_bom() -> pd.DataFrame:
    """Lista de materiales. Columnas: articulo, codigo_insumo, descripcion_insumo, cantidad_por_unidad."""
    df = query(f"SELECT * FROM {VISTA_BOM}")

    df = df.rename(columns={
        # "COD_ARTICULO_PT": "articulo",
        # "COD_INSUMO":      "codigo_insumo",
        # "DESC_INSUMO":     "descripcion_insumo",
        # "CANTIDAD":        "cantidad_por_unidad",
    })
    return df[["articulo", "codigo_insumo", "descripcion_insumo", "cantidad_por_unidad"]]


def extraer_forecast() -> pd.DataFrame:
    """
    Forecast de ventas por artículo y mes.
    Columnas: articulo, descripcion, ene_26, feb_26, ..., dic_26
    La vista puede devolver filas (articulo, mes, cantidad); este código la pivotea.
    """
    df = query(f"SELECT * FROM {VISTA_FORECAST}")

    # ── Caso A: la vista ya viene pivoteada (una col por mes) ──────
    # df = df.rename(columns={"COD": "articulo", "DESC": "descripcion"})
    # return df

    # ── Caso B: la vista viene en formato largo (articulo, mes, cantidad) ──
    # Ajustar los nombres de columna según la vista real:
    # df = df.rename(columns={
    #     "COD_ARTICULO": "articulo",
    #     "DESC_ARTICULO": "descripcion",
    #     "MES":          "mes",       # ej: datetime o string "2026-06-01"
    #     "CANTIDAD":     "cantidad",
    # })
    # df["mes"] = pd.to_datetime(df["mes"])
    # meses = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"]
    # df["col_mes"] = df["mes"].apply(lambda d: f"{meses[d.month-1]}_{str(d.year)[-2:]}")
    # pivot = df.pivot_table(index=["articulo","descripcion"],
    #                        columns="col_mes", values="cantidad",
    #                        aggfunc="sum").reset_index()
    # pivot.columns.name = None
    # return pivot

    return df  # reemplazar con uno de los casos de arriba


# ── Google Sheets helpers ─────────────────────────────────────────

def gs_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDS_JSON, scopes=scopes)
    return gspread.authorize(creds)


def subir_a_sheet(gc, sheet_id: str, df: pd.DataFrame, nombre: str):
    """Reemplaza todo el contenido del sheet con el DataFrame."""
    ws = gc.open_by_key(sheet_id).sheet1
    ws.clear()
    df = df.fillna("").astype(str)
    data = [df.columns.tolist()] + df.values.tolist()
    ws.update("A1", data)
    print(f"  ✅ {nombre}: {len(df)} filas subidas")


# ── Main ──────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*55}")
    print(f"  ACTUALIZACIÓN MRP — {date.today().strftime('%d/%m/%Y')}")
    print(f"{'='*55}\n")

    todos_ok = True

    # Verificar que los TODO estén reemplazados
    for nombre, vista in [("STOCK", VISTA_STOCK), ("ORDENES", VISTA_ORDENES),
                           ("BOM", VISTA_BOM), ("FORECAST", VISTA_FORECAST)]:
        if "TODO" in vista:
            print(f"⚠️  {nombre}: todavía tiene placeholder TODO. "
                  f"Correr explorar_jde_mrp.py primero.")
            todos_ok = False

    if not todos_ok:
        print("\nCorrección requerida antes de continuar.")
        return

    print("[1/2] Extrayendo datos desde JDE SQL Server...")

    try:
        df_stock    = extraer_stock()
        print(f"  ✅ Stock: {len(df_stock)} insumos")
    except Exception as e:
        print(f"  ❌ Stock: {e}"); return

    try:
        df_ordenes  = extraer_ordenes()
        print(f"  ✅ OC: {len(df_ordenes)} líneas")
    except Exception as e:
        print(f"  ❌ OC: {e}"); return

    try:
        df_bom      = extraer_bom()
        print(f"  ✅ BOM: {len(df_bom)} relaciones")
    except Exception as e:
        print(f"  ❌ BOM: {e}"); return

    try:
        df_forecast = extraer_forecast()
        print(f"  ✅ Forecast: {len(df_forecast)} artículos")
    except Exception as e:
        print(f"  ❌ Forecast: {e}"); return

    print("\n[2/2] Subiendo a Google Sheets...")
    try:
        gc = gs_client()
        subir_a_sheet(gc, GD_IDS["stock"],    df_stock,    "stock")
        subir_a_sheet(gc, GD_IDS["ordenes"],  df_ordenes,  "ordenes")
        subir_a_sheet(gc, GD_IDS["bom"],      df_bom,      "bom")
        subir_a_sheet(gc, GD_IDS["forecast"], df_forecast, "forecast")
    except Exception as e:
        print(f"  ❌ Error Google Sheets: {e}"); return

    print(f"\n✅ Actualización completa. La próxima sesión del MRP")
    print(f"   cargará los datos nuevos automáticamente.")


if __name__ == "__main__":
    main()
