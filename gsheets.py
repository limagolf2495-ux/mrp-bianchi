import pandas as pd
import streamlit as st
import gspread

from config import GD_ESTADOS_ID, GD_IDS, get_hoy, COL_OC_COD, COL_OC_QTY, COL_OC_FECHA


def obtener_fechas_drive():
    """Devuelve {key: datetime local} con modifiedTime de cada archivo de GD_IDS.
    Omite los archivos que fallen; {} si no hay credenciales."""
    gc = _gs_client()
    if gc is None:
        return {}
    fechas = {}
    for key, fid in GD_IDS.items():
        try:
            resp = gc.http_client.request(
                "get", f"https://www.googleapis.com/drive/v3/files/{fid}?fields=modifiedTime")
            iso = resp.json().get("modifiedTime")
            if iso:
                fechas[key] = (pd.to_datetime(iso, utc=True)
                                 .tz_convert("America/Argentina/Buenos_Aires")
                                 .tz_localize(None).to_pydatetime())
        except Exception:
            continue
    return fechas


def _gs_client():
    try:
        return gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    except Exception:
        return None


def _oc_key(cod, fec, qty):
    return (str(cod), str(fec), str(int(round(float(qty)))))


def cargar_oc_estados_sheet():
    """Devuelve (pendientes, reprogramadas):
    - pendientes: set de keys (cod, fecha, qty) en estado Pendiente
    - reprogramadas: dict {key: date} con la nueva fecha de entrega"""
    gc = _gs_client()
    if gc is None:
        return set(), {}
    try:
        ws = gc.open_by_key(GD_ESTADOS_ID).sheet1
        records = ws.get_all_records()
        pendientes = set()
        reprogramadas = {}
        for r in records:
            if r.get("estado") != "🕐 Pendiente":
                continue
            key = _oc_key(r["codigo"], r["fecha_entrega"], r["cantidad_oc"])
            pendientes.add(key)
            nf = str(r.get("nueva_fecha", "")).strip()
            if nf:
                try:
                    reprogramadas[key] = pd.to_datetime(nf).date()
                except Exception:
                    pass
        return pendientes, reprogramadas
    except Exception:
        return set(), {}


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
    rows = [["codigo", "fecha_entrega", "cantidad_oc", "estado", "nueva_fecha"]]
    for cod, estados in st.session_state.mrp_oc_estados.items():
        entries = oc_idx.get(cod, [])
        nuevas_cod = st.session_state.mrp_oc_nueva_fecha.get(cod, {})
        for i, est in estados.items():
            if est == "🕐 Pendiente" and i < len(entries):
                fec, qty = entries[i]
                nf = nuevas_cod.get(i)
                rows.append([cod, str(fec), str(int(round(qty))), est,
                             nf.isoformat() if nf else ""])
    try:
        ws = gc.open_by_key(GD_ESTADOS_ID).sheet1
        ws.clear()
        ws.update("A1", rows)
    except Exception as e:
        st.warning(f"⚠️ No se pudieron guardar los estados en Google Sheets: {e}")


def merge_oc_estados(oc_df):
    """Reconstruye mrp_oc_estados aplicando los estados guardados en el Sheet."""
    pendientes, reprogramadas = cargar_oc_estados_sheet()
    hoy = get_hoy()
    new_estados = {}
    new_venc_parcial = {}
    new_nuevas = {}
    oc_idx = {}
    for _, r in oc_df.iterrows():
        cod = str(r[COL_OC_COD]); fec = r[COL_OC_FECHA]; qty = float(r[COL_OC_QTY])
        if pd.isna(fec): continue
        oc_idx.setdefault(cod, []).append((fec, qty))
    for cod, entries in oc_idx.items():
        estados_cod = {}
        nuevas_cod = {}
        total_pend = 0.0
        for i, (fec, qty) in enumerate(entries):
            key = _oc_key(cod, fec, qty)
            if fec < hoy and key in pendientes:
                estados_cod[i] = "🕐 Pendiente"
                total_pend += qty
                if key in reprogramadas:
                    nuevas_cod[i] = reprogramadas[key]
        if estados_cod:
            new_estados[cod] = estados_cod
        if nuevas_cod:
            new_nuevas[cod] = nuevas_cod
        if total_pend > 0:
            new_venc_parcial[cod] = total_pend
    st.session_state.mrp_oc_estados = new_estados
    st.session_state.mrp_oc_venc_parcial = new_venc_parcial
    st.session_state.mrp_oc_nueva_fecha = new_nuevas

    pagados = cargar_pagos_oc_sheet()
    new_pagada = {}
    for cod, entries in oc_idx.items():
        pagada_cod = {}
        for i, (fec, qty) in enumerate(entries):
            if _oc_key(cod, fec, qty) in pagados:
                pagada_cod[i] = True
        if pagada_cod:
            new_pagada[cod] = pagada_cod
    st.session_state.mrp_oc_pagada = new_pagada


def cargar_pagos_oc_sheet() -> set:
    """Devuelve set de keys (cod, fecha, qty) que tienen pagada=True."""
    gc = _gs_client()
    if gc is None:
        return set()
    try:
        wb = gc.open_by_key(GD_ESTADOS_ID)
        try:
            ws = wb.worksheet("pagos_oc")
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet("pagos_oc", 500, 4)
            ws.update("A1", [["codigo", "fecha_entrega", "cantidad_oc", "pagada"]])
            return set()
        records = ws.get_all_records()
        return {_oc_key(r["codigo"], r["fecha_entrega"], r["cantidad_oc"])
                for r in records
                if str(r.get("pagada", "")).strip() in ("True", "true", "1")}
    except Exception:
        return set()


def guardar_pagos_oc():
    """Escribe en la pestaña 'pagos_oc' todas las OC marcadas como pagadas."""
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
    rows = [["codigo", "fecha_entrega", "cantidad_oc", "pagada"]]
    for cod, pagos_cod in st.session_state.mrp_oc_pagada.items():
        entries = oc_idx.get(cod, [])
        for i, val in pagos_cod.items():
            if val and i < len(entries):
                fec, qty = entries[i]
                rows.append([cod, str(fec), str(int(round(qty))), "True"])
    try:
        wb = gc.open_by_key(GD_ESTADOS_ID)
        try:
            ws = wb.worksheet("pagos_oc")
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet("pagos_oc", 500, 4)
        ws.clear()
        ws.update("A1", rows)
    except Exception as e:
        st.warning(f"⚠️ No se pudieron guardar los pagos en Google Sheets: {e}")


def _get_tipo_insumo(cod: str) -> str:
    """Retorna tipo_insumo del codigo desde st.session_state.stock. Retorna '' si no encuentra."""
    try:
        stock_df = st.session_state.stock
        if stock_df is None:
            return ""
        row = stock_df[stock_df["codigo"].astype(str) == str(cod)]
        if row.empty:
            return ""
        return str(row.iloc[0].get("tipo_insumo", ""))
    except Exception:
        return ""


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


def cargar_plan_produccion():
    """Carga el plan de producción desde pestaña 'plan_produccion' del Sheet de estados.
    Devuelve (dict, error_str). Setea st.session_state.plan_produccion_fecha como side-effect."""
    gc = _gs_client()
    if gc is None:
        return {}, "Sin credenciales GCP — configurá .streamlit/secrets.toml localmente"
    try:
        wb = gc.open_by_key(GD_ESTADOS_ID)
        try:
            ws = wb.worksheet("plan_produccion")
        except gspread.exceptions.WorksheetNotFound:
            return {}, ""
        records = ws.get_all_records()
        result = {}
        fecha = ""
        for r in records:
            art = str(r.get("articulo", "")).strip()
            if not art:
                continue
            entry = {
                "desc": str(r.get("descripcion", "")),
                "forecast": float(r.get("forecast", 0) or 0),
            }
            for si in range(1, 6):
                val = r.get(f"s{si}", "")
                if val != "" and val is not None:
                    try:
                        entry[f"s{si}"] = int(float(val))
                    except (ValueError, TypeError):
                        pass
            if not fecha:
                fecha = str(r.get("fecha_guardado", ""))
            result[art] = entry
        st.session_state.plan_produccion_fecha = fecha
        return result, ""
    except Exception as e:
        return {}, str(e)


def guardar_plan_produccion(prod: dict) -> bool:
    """Guarda el plan de producción en pestaña 'plan_produccion' del Sheet de estados."""
    from datetime import datetime
    gc = _gs_client()
    if gc is None:
        return False
    try:
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
        wb = gc.open_by_key(GD_ESTADOS_ID)
        try:
            ws = wb.worksheet("plan_produccion")
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet("plan_produccion", 300, 9)
        rows = [["articulo", "descripcion", "forecast", "s1", "s2", "s3", "s4", "s5", "fecha_guardado"]]
        for art, d in prod.items():
            s5_val = int(d["s5"]) if d.get("s5") is not None else ""
            rows.append([
                art,
                str(d.get("desc", "")),
                int(d.get("forecast", 0)),
                int(d.get("s1", 0)),
                int(d.get("s2", 0)),
                int(d.get("s3", 0)),
                int(d.get("s4", 0)),
                s5_val,
                fecha,
            ])
        ws.clear()
        ws.update("A1", rows)
        st.session_state.plan_produccion_fecha = fecha
        return True
    except Exception as e:
        st.warning(f"⚠️ No se pudo guardar el plan: {e}")
        return False
