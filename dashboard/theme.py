"""CSS theme: RTL layout, Persian font, light / dark mode, cards."""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from config import settings

_LIGHT = dict(bg="#F4F6FB", card="#FFFFFF", text="#1B2A41", muted="#5B6B82", primary="#1F6FEB", border="#DDE3EE", side="#FFFFFF", input="#FFFFFF")
_DARK = dict(bg="#0E1522", card="#172134", text="#E6EDF7", muted="#9FB0C8", primary="#4C9AFF", border="#2A3850", side="#111B2C", input="#1B2840")


def _font_css() -> str:
    for name in ("Vazirmatn-Regular.ttf", "Vazirmatn-Regular.woff2", "Vazir.ttf", "Vazir-Regular.ttf"):
        p = settings.FONTS_DIR / name
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            fmt = "woff2" if p.suffix == ".woff2" else "truetype"
            return f"@font-face {{ font-family: 'GIFont'; src: url(data:font/{p.suffix[1:]};base64,{b64}) format('{fmt}'); }}"
    return ""


def apply_theme(rtl: bool, dark: bool) -> None:
    c = _DARK if dark else _LIGHT
    direction = "rtl" if rtl else "ltr"
    align = "right" if rtl else "left"
    extra = ""
    custom = settings.ASSETS_DIR / "styles" / "custom.css"
    if custom.exists():
        extra = custom.read_text(encoding="utf-8")
    css = f"""
    <style>
    {_font_css()}
    {extra}
    html, body, [class*="css"], .stApp, .stMarkdown, .stTextInput input, .stNumberInput input, .stSelectbox, button, textarea {{
        font-family: 'GIFont', 'Vazirmatn', Tahoma, 'Segoe UI', 'Noto Naskh Arabic', Arial, sans-serif !important;
    }}
    .stApp {{ background: {c['bg']}; color: {c['text']}; }}
    .stApp p, .stApp label, .stApp span, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp div[data-testid="stMarkdownContainer"] {{ color: {c['text']}; }}
    section[data-testid="stSidebar"] {{ background: {c['side']}; border-{'left' if rtl else 'right'}: 1px solid {c['border']}; }}
    .block-container {{ direction: {direction}; text-align: {align}; padding-top: 1.4rem; max-width: 1500px; }}
    section[data-testid="stSidebar"] > div {{ direction: {direction}; text-align: {align}; }}
    .stTabs [data-baseweb="tab-list"] {{ direction: {direction}; gap: 4px; }}
    div[data-testid="stDataFrame"], div[data-testid="stDataEditor"], .js-plotly-plot, pre, code {{ direction: ltr; text-align: left; }}
    .gi-card {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 14px; padding: 16px 18px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }}
    .gi-card .v {{ font-size: 1.9rem; font-weight: 700; color: {c['primary']}; line-height: 1.2; }}
    .gi-card .l {{ color: {c['muted']}; font-size: .9rem; }}
    .gi-badge {{ display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .78rem; background: {c['primary']}22; color: {c['primary']}; margin: 0 2px; }}
    .gi-warn {{ border-{'right' if rtl else 'left'}: 4px solid #E5A100; background: #E5A10018; padding: 8px 12px; border-radius: 8px; margin: 6px 0; }}
    .gi-ok {{ border-{'right' if rtl else 'left'}: 4px solid #1BA672; background: #1BA67218; padding: 8px 12px; border-radius: 8px; margin: 6px 0; }}
    .gi-sample {{ border: 1px dashed #B00020; color: #B00020; padding: 2px 8px; border-radius: 6px; font-size: .8rem; }}
    .stButton > button, .stDownloadButton > button {{ border-radius: 10px; border: 1px solid {c['border']}; }}
    .stButton > button[kind="primary"] {{ background: {c['primary']}; color: white; }}
    .stTextInput input, .stNumberInput input, .stTextArea textarea, div[data-baseweb="select"] > div {{ background: {c['input']}; color: {c['text']}; }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def logo_svg(dark: bool) -> str:
    fg = "#4C9AFF" if dark else "#1F6FEB"
    return (f'<svg width="46" height="46" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">'
            f'<rect x="4" y="4" width="56" height="56" rx="14" fill="{fg}" opacity=".12"/>'
            f'<path d="M12 50 L12 14 M12 50 L52 50" stroke="{fg}" stroke-width="3" fill="none" stroke-linecap="round"/>'
            f'<path d="M16 42 C24 18, 32 46, 40 26 S50 20, 52 18" stroke="#E5484D" stroke-width="3.2" fill="none" stroke-linecap="round"/>'
            f'<circle cx="24" cy="31" r="3" fill="{fg}"/><circle cx="40" cy="30" r="3" fill="{fg}"/></svg>')
