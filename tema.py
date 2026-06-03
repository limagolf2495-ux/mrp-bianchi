"""
tema.py — Capa visual "Claro corporativo" para el MRP Bianchi.

Importá esto desde app.py:
    import tema
    tema.inject()                      # una vez, al inicio (tras set_page_config)
    st.markdown(tema.cards([...]), unsafe_allow_html=True)

No contiene lógica de negocio: solo estilos y componentes de presentación.
"""
import streamlit as st

# ── Paleta (coherente con .streamlit/config.toml) ──────────────────────────
ACCENT      = "#7a1f2b"
BG          = "#f1f3f6"
SURFACE     = "#ffffff"
SURFACE_2   = "#f7f9fb"
BORDER      = "#e4e8ee"
BORDER_STR  = "#d2d8e1"
TEXT        = "#1f2733"
TEXT_MUTED  = "#5b6573"
TEXT_FAINT  = "#8b95a4"
CRIT, CRIT_BG = "#c0392f", "#fbecea"
WARN, WARN_BG = "#c98a16", "#fbf3e1"
OK,   OK_BG   = "#2f8f5b", "#e8f4ec"


def inject():
    """Inyecta fuentes IBM Plex + estilos corporativos. Llamar una sola vez."""
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

/* Tipografía base */
html, body, [class*="css"], .stApp, .stMarkdown, .stButton, .stTextInput,
.stSelectbox, .stNumberInput, .stDataFrame {{ font-family: 'IBM Plex Sans', system-ui, sans-serif; }}
.stApp {{ background: {BG}; }}

/* Ancho de contenido + padding superior que libera el header fijo de Streamlit.
   El header (botón Deploy + menú ⋮) mide ~3.75rem; sin este espacio los tabs
   quedan tapados/cortados arriba. */
.block-container {{ padding-top: 4.5rem; padding-bottom: 4rem; max-width: 1640px; }}

/* Header de Streamlit: transparente y por detrás del contenido para que no
   tape los tabs (solo el menú/Deploy quedan en la esquina derecha). */
[data-testid="stHeader"] {{ background: transparent; height: 3.5rem; }}
[data-testid="stToolbar"] {{ right: 0.5rem; }}

/* Encabezados */
h1, h2, h3 {{ letter-spacing: -.01em; color: {TEXT}; }}
h1 {{ font-size: 1.55rem; font-weight: 700; }}
h2 {{ font-size: 1.2rem; font-weight: 700; }}

/* Sidebar */
[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
[data-testid="stSidebar"] .block-container {{ padding-top: 2.5rem; }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 2px; background: {SURFACE_2}; padding: 4px;
    border-radius: 10px; border: 1px solid {BORDER}; }}
.stTabs [data-baseweb="tab"] {{ height: 38px; padding: 0 18px; border-radius: 7px;
    font-size: 13px; font-weight: 500; color: {TEXT_MUTED}; }}
.stTabs [aria-selected="true"] {{ background: {SURFACE}; color: {TEXT}; font-weight: 600;
    box-shadow: 0 1px 2px rgba(20,30,50,.07); }}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none; }}

/* Botón primario (vino) */
.stButton button[kind="primary"] {{ background: {ACCENT}; border-color: {ACCENT};
    font-weight: 600; border-radius: 8px; }}
.stButton button[kind="primary"]:hover {{ filter: brightness(1.07); border-color: {ACCENT}; }}
.stButton button {{ border-radius: 8px; font-weight: 500; }}

/* Inputs */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
.stSelectbox div[data-baseweb="select"] > div {{ border-radius: 8px; }}

/* Métricas nativas → tarjetas */
[data-testid="stMetric"] {{ background: {SURFACE}; border: 1px solid {BORDER};
    border-radius: 10px; padding: 14px 16px; box-shadow: 0 1px 2px rgba(20,30,50,.06); }}
[data-testid="stMetricValue"] {{ font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; }}

/* DataFrame — encabezado y números legibles */
[data-testid="stDataFrame"] {{ border-radius: 10px; border: 1px solid {BORDER}; }}

/* ── Tarjetas de resumen ejecutivo (HTML propio) ───────────────────────── */
.mrp-cards {{ display: grid; grid-template-columns: repeat(var(--n,5), 1fr); gap: 12px; margin: 6px 0 4px; }}
.mrp-card {{ position: relative; background: {SURFACE}; border: 1px solid {BORDER};
    border-radius: 10px; box-shadow: 0 1px 2px rgba(20,30,50,.06); overflow: hidden; }}
.mc-accent {{ position: absolute; left: 0; top: 0; bottom: 0; width: 3px; }}
.mc-body {{ padding: 14px 16px; }}
.mc-lbl {{ font-size: 11px; font-weight: 600; color: {TEXT_MUTED}; text-transform: uppercase; letter-spacing: .04em; }}
.mc-val {{ font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums;
    font-size: 28px; font-weight: 600; line-height: 1.05; margin-top: 8px; color: {TEXT}; }}
.mc-unit {{ font-size: 14px; font-weight: 500; color: {TEXT_MUTED}; }}
.mc-sub {{ font-size: 11.5px; color: {TEXT_FAINT}; margin-top: 4px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.k-crit .mc-accent {{ background: {CRIT}; }} .k-crit .mc-val {{ color: {CRIT}; }}
.k-warn .mc-accent {{ background: {WARN}; }} .k-warn .mc-val {{ color: {WARN}; }}
.k-ok   .mc-accent {{ background: {OK}; }}   .k-ok   .mc-val {{ color: {OK}; }}

/* Banner de estado */
.mrp-banner {{ display: flex; align-items: center; gap: 9px; font-size: 12.5px; color: {TEXT_MUTED};
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; padding: 9px 14px; margin-bottom: 4px; }}
.mrp-banner strong {{ color: {TEXT}; font-weight: 600; }}
.mrp-banner .dot {{ width: 7px; height: 7px; border-radius: 50%; }}
.mrp-banner.ok    .dot {{ background: {OK};   box-shadow: 0 0 0 3px {OK_BG}; }}
.mrp-banner.warn  .dot {{ background: {WARN}; box-shadow: 0 0 0 3px {WARN_BG}; }}
.mrp-banner.crit  .dot {{ background: {CRIT}; box-shadow: 0 0 0 3px {CRIT_BG}; }}
.mrp-banner.warn  {{ background: {WARN_BG}; border-color: {WARN}; color: #6b4d10; }}
.mrp-banner.crit  {{ background: {CRIT_BG}; border-color: {CRIT}; color: #7a221c; }}

/* Pill de estado y detalle */
.pill {{ display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600;
    padding: 4px 11px 4px 9px; border-radius: 20px; }}
.pill .dot {{ width: 8px; height: 8px; border-radius: 50%; }}
.pill.crit {{ background: {CRIT_BG}; color: {CRIT}; }} .pill.crit .dot {{ background: {CRIT}; }}
.pill.warn {{ background: {WARN_BG}; color: {WARN}; }} .pill.warn .dot {{ background: {WARN}; }}
.pill.ok   {{ background: {OK_BG};   color: {OK}; }}   .pill.ok   .dot {{ background: {OK}; }}
.det-title {{ font-size: 18px; font-weight: 700; margin: 6px 0 2px; }}
.det-sub {{ font-size: 12px; color: {TEXT_MUTED}; font-family: 'IBM Plex Mono', monospace; }}
.tipo-chip {{ display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 9px;
    border-radius: 6px; background: {SURFACE_2}; border: 1px solid {BORDER}; color: {TEXT_MUTED}; }}
</style>
""", unsafe_allow_html=True)


_KIND = {"crit": "k-crit", "warn": "k-warn", "ok": "k-ok", "": ""}


def cards(specs):
    """Devuelve el HTML de una fila de tarjetas de resumen.
    specs = [{"lbl","val","sub","kind","unit"?}, ...]  kind ∈ crit|warn|ok|''"""
    n = len(specs)
    html = [f'<div class="mrp-cards" style="--n:{n}">']
    for s in specs:
        kind = _KIND.get(s.get("kind", ""), "")
        accent = '<div class="mc-accent"></div>' if kind else ''
        unit = f'<span class="mc-unit"> {s["unit"]}</span>' if s.get("unit") else ''
        html.append(
            f'<div class="mrp-card {kind}">{accent}<div class="mc-body">'
            f'<div class="mc-lbl">{s["lbl"]}</div>'
            f'<div class="mc-val">{s["val"]}{unit}</div>'
            f'<div class="mc-sub">{s.get("sub","")}</div>'
            f'</div></div>'
        )
    html.append('</div>')
    return "".join(html)


def banner(texto_html, kind="ok"):
    """Banner de estado con punto de color. kind ∈ ok|warn|crit"""
    return f'<div class="mrp-banner {kind}"><span class="dot"></span><span>{texto_html}</span></div>'


def pill(kind, label):
    """Pill de estado para usar en st.markdown. kind ∈ crit|warn|ok"""
    return f'<span class="pill {kind}"><span class="dot"></span>{label}</span>'
