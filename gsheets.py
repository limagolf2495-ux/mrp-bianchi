import pandas as pd
import streamlit as st
import gspread

from config import GD_ESTADOS_ID, get_hoy, COL_OC_COD, COL_OC_QTY, COL_OC_FECHA


def _gs_client():
    try:
        return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    except Exception:
        return None


def _oc_key(cod, fec, qty):
    return (str(cod), str(fec), str(int(round(float(qty)))))


def cargar_oc_estados_sheet():
    """Devuelve set de keys (cod, fecha, qty) que están en estado Pendiente."""
    gc = _gs_client()
    if gc is None:
        return set()
    try:
        ws = gc.open_by_key(GD_ESTADOS_ID).sheet1
        records = ws.get_all_records()
        return {_oc_key(r["codigo"], r["fecha_entrega"], r["cantidad_oc"])
                for r in records if r.get("estado") == "🕐 Pendiente"}
    except Exception:
        return set()


def guardar_oc_estados():
    """Escribe en el Sheet todos los estados Pendiente actuales."""
    gc = _gs_client()
    if gc is None:
        return
    if st.session_state.oc is None:
        return
    oc_df = st.session_state.oc
    oc_idx = {}
    for _, r in oc_df.iterrows():
        cod = str(r[COL_OC_COD]); fec = r[COL_OC_FECHA]; qty = float(r[COL_OC_QTY])
        if pd.isna(fec): continue
        oc_idx.setdefault(cod, []).append((fec, qty))
    rows = [["codigo", "fecha_entrega", "cantidad_oc", "estado"]]
    for cod, estados in st.session_state.mrp_oc_estados.items():
        entries = oc_idx.get(cod, [])
        for i, est in estados.items():
            if est == "🕐 Pendiente" and i < len(entries):
                fec, qty = entries[i]
                rows.append([cod, str(fec), str(int(round(qty))), est])
    try:
        ws = gc.open_by_key(GD_ESTADOS_ID).sheet1
        ws.clear()
        ws.update("A1", rows)
    except Exception as e:
        st.warning(f"⚠️ No se pudieron guardar los estados en Google Sheets: {e}")


def merge_oc_estados(oc_df):
    """Reconstruye mrp_oc_estados aplicando los estados guardados en el Sheet."""
    pendientes = cargar_oc_estados_sheet()
    hoy = get_hoy()
    new_estados = {}
    new_venc_parcial = {}
    oc_idx = {}
    for _, r in oc_df.iterrows():
        cod = str(r[COL_OC_COD]); fec = r[COL_OC_FECHA]; qty = float(r[COL_OC_QTY])
        if pd.isna(fec): continue
        oc_idx.setdefault(cod, []).append((fec, qty))
    for cod, entries in oc_idx.items():
        estados_cod = {}
        total_pend = 0.0
        for i, (fec, qty) in enumerate(entries):
            if fec < hoy and _oc_key(cod, fec, qty) in pendientes:
                estados_cod[i] = "🕐 Pendiente"
                total_pend += qty
        if estados_cod:
            new_estados[cod] = estados_cod
        if total_pend > 0:
            new_venc_parcial[cod] = total_pend
    st.session_state.mrp_oc_estados = new_estados
    st.session_state.mrp_oc_venc_parcial = new_venc_parcial


def cargar_reglas_pt():
    """Carga reglas por artículo desde pestaña 'reglas_pt' del Sheet de estados.
    Devuelve (dict, error_str). error_str es None si fue exitoso."""
    gc = _gs_client()
    if gc is None:
        return {}, "Sin credenciales GCP — configurá .streamlit/secrets.toml localmente"
    try:
        wb = gc.open_by_key(GD_ESTADOS_ID)
        try:
            ws = wb.worksheet("reglas_pt")
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet("reglas_pt", 200, 2)
            ws.update("A1", [["articulo", "regla"]])
            return {}, None
        records = ws.get_all_records()
        result = {str(r["articulo"]): str(r["regla"])
                  for r in records if r.get("articulo") and str(r.get("regla", "")).strip() != ""}
        return result, None
    except Exception as e:
        return {}, str(e)


def guardar_reglas_pt(reglas):
    """Guarda reglas en pestaña 'reglas_pt' del Sheet de estados."""
    gc = _gs_client()
    if gc is None:
        return False
    try:
        wb = gc.open_by_key(GD_ESTADOS_ID)
        try:
            ws = wb.worksheet("reglas_pt")
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet("reglas_pt", 200, 2)
        rows = [["articulo", "regla"]] + [[art, r] for art, r in reglas.items()]
        ws.clear()
        ws.update("A1", rows)
        return True
    except Exception as e:
        st.warning(f"⚠️ No se pudieron guardar las reglas: {e}")
        return False
