import pandas as pd
import streamlit as st

import tema
from config import GD_IDS, MESES, get_hoy, DEFAULTS, COLS_STOCK_REQ, COLS_OC_REQ, COLS_BOM_REQ
from gsheets import merge_oc_estados
from helpers import gsheet_url, validar_columnas
from sidebar import render_sidebar
from tab_cashflow import render_tab_cashflow
from tab_configuracion import render_tab_configuracion
from tab_datos import render_tab_datos
from tab_mrp import render_tab_mrp
from tab_planificacion import render_tab_planificacion
from tab_produccion import render_tab_produccion

st.set_page_config(page_title="MRP — Bodegas Bianchi", page_icon="🍷", layout="wide")
tema.inject()

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Auto-load Google Drive ─────────────────────────────────────────────────────
if not st.session_state.gd_cargado:
    with st.spinner("Cargando datos desde Google Drive..."):
        _url = gsheet_url(GD_IDS["stock"])
        try:
            df = pd.read_csv(_url)
            df.columns = df.columns.str.strip().str.lower()
            validar_columnas(df, COLS_STOCK_REQ, "stock (Google Drive)")
            df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0)
            st.session_state.stock = df
            st.session_state.fecha_corte_stock = get_hoy()
        except ValueError as e:
            st.error(f"⚠️ Stock — {e}")
        except Exception as e:
            st.error(f"⚠️ Stock — no se pudo cargar desde Google Drive.\nURL: {_url}\nError: {e}")

        _url = gsheet_url(GD_IDS["ordenes"])
        try:
            df = pd.read_csv(_url)
            df.columns = df.columns.str.strip().str.lower()
            validar_columnas(df, COLS_OC_REQ, "ordenes (Google Drive)")
            df["cantidad_oc"] = pd.to_numeric(df["cantidad_oc"], errors="coerce").fillna(0)
            df["fecha_entrega"] = pd.to_datetime(df["fecha_entrega"], errors="coerce").dt.date
            st.session_state.oc = df
            merge_oc_estados(df)
        except ValueError as e:
            st.error(f"⚠️ Órdenes de compra — {e}")
        except Exception as e:
            st.error(f"⚠️ Órdenes de compra — no se pudo cargar desde Google Drive.\nURL: {_url}\nError: {e}")

        _url = gsheet_url(GD_IDS["bom"])
        try:
            df = pd.read_csv(_url)
            df.columns = df.columns.str.strip().str.lower()
            validar_columnas(df, COLS_BOM_REQ, "bom (Google Drive)")
            df["cantidad_por_unidad"] = pd.to_numeric(df["cantidad_por_unidad"], errors="coerce").fillna(0)
            st.session_state.bom = df
        except ValueError as e:
            st.error(f"⚠️ BOM — {e}")
        except Exception as e:
            st.error(f"⚠️ BOM — no se pudo cargar desde Google Drive.\nURL: {_url}\nError: {e}")

        _url = gsheet_url(GD_IDS["forecast"], "xlsx")
        try:
            df = pd.read_excel(_url)
            new_cols = []
            for col in df.columns:
                if hasattr(col, "month"):
                    new_cols.append(f"{MESES[col.month-1]}_{str(col.year)[-2:]}")
                else:
                    new_cols.append(str(col).strip().lower())
            df.columns = new_cols
            df = df.loc[:, ~df.columns.duplicated()]
            df = df.loc[:, df.columns != "nan"]
            df = df.dropna(how="all")
            df["articulo"] = df["articulo"].astype(str).str.strip()
            for col in df.columns:
                if col not in ["articulo", "descripcion"]:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            st.session_state.forecast = df
            st.session_state.prod_listo = False
        except ValueError as e:
            st.error(f"⚠️ Forecast — {e}")
        except Exception as e:
            st.error(f"⚠️ Forecast — no se pudo cargar desde Google Drive.\nURL: {_url}\nError: {e}")

    st.session_state.gd_cargado = True

# ── Sidebar ────────────────────────────────────────────────────────────────────
render_sidebar()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_datos, tab_plan, tab_prod, tab_mrp, tab_cf, tab_cfg = st.tabs(
    ["📋 Datos", "📊 Planificación", "🏭 Producción", "📦 MRP", "💰 Cash-Flow", "⚙️ Configuración"]
)

with tab_datos:
    render_tab_datos()
with tab_plan:
    render_tab_planificacion()
with tab_prod:
    render_tab_produccion()
with tab_mrp:
    render_tab_mrp()
with tab_cf:
    render_tab_cashflow()
with tab_cfg:
    render_tab_configuracion()
