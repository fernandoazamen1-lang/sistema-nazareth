# ==============================================================================
# DISEÑO Y ESTILOS GLOBALES PREMIUM
# ==============================================================================
def aplicar_estilos_base():
    verificar_licencia()
    css_string = """
<style translate="no">
/* 1. Ocultar menús nativos y botones de Streamlit sin romper el header */
#MainMenu, footer, .stDeployButton, [data-testid="stToolbar"] { 
    display: none !important; 
    visibility: hidden !important; 
}

/* 2. Dejar el header transparente y sin altura ocupada para no tapar contenido */
header[data-testid="stHeader"] {
    background: transparent !important;
    height: 0px !important;
    overflow: visible !important;
}

/* 3. FORZAR que el botón de la flecha del sidebar nunca desaparezca */
[data-testid="stSidebarCollapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: #1E40AF !important;
    z-index: 99999 !important;
    position: fixed !important;
    top: 10px !important;
    left: 10px !important;
}

html, body, [class*="css"], .stApp { 
    font-family: 'Inter', -apple-system, sans-serif !important; 
    background: linear-gradient(135deg, #F8FAFC 0%, #E0E7FF 100%) !important; 
    color: #0F172A !important; 
    background-attachment: fixed !important; 
}
[data-testid="stSidebar"] { 
    background: #FFFFFF !important; 
    border-right: 1px solid #E2E8F0 !important; 
    box-shadow: 4px 0 15px rgba(15, 23, 42, 0.03) !important; 
    margin-top: 0px !important; 
}
[data-testid="stSidebarNav"] span { 
    font-size: 13.5px !important; 
    font-weight: 500 !important; 
    color: #475569 !important; 
}
[data-testid="stSidebarNav"] [aria-current="page"] { 
    background: linear-gradient(90deg, rgba(30, 64, 175, 0.08) 0%, transparent 100%) !important; 
    border-left: 4px solid #1E40AF !important; 
}
[data-testid="stSidebarNav"] [aria-current="page"] span { 
    font-weight: 800 !important; 
    color: #1E40AF !important; 
}
div[data-testid="stMetric"] { 
    background: rgba(255, 255, 255, 0.85) !important; 
    backdrop-filter: blur(10px) !important; 
    border: 1px solid rgba(255, 255, 255, 0.4) !important; 
    border-radius: 16px !important; 
    padding: 18px 22px !important; 
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04), 0 1px 2px rgba(15, 23, 42, 0.02) !important; 
    transition: transform 0.2s ease, box-shadow 0.2s ease; 
}
div[data-testid="stMetric"]:hover { 
    transform: translateY(-2px); 
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08), 0 2px 4px rgba(15, 23, 42, 0.04) !important; 
}
div[data-testid="stMetricLabel"] p { 
    font-size: 12.5px !important; 
    font-weight: 700 !important; 
    text-transform: uppercase !important; 
    letter-spacing: 0.5px !important; 
    color: #475569 !important; 
}
div[data-testid="stMetricValue"] { 
    font-family: 'Plus Jakarta Sans', sans-serif !important; 
    font-size: 26px !important; 
    font-weight: 800 !important; 
    color: #0F172A !important; 
    margin-top: 2px !important; 
}
.stTabs [data-baseweb="tab-list"] { 
    gap: 12px !important; 
    border-bottom: none !important; 
    padding-bottom: 12px !important; 
    padding-top: 5px !important; 
}
.stTabs [data-baseweb="tab"] { 
    font-family: 'Plus Jakarta Sans', sans-serif !important; 
    font-weight: 700 !important; 
    font-size: 14px !important; 
    padding: 10px 22px !important; 
    border-radius: 10px !important; 
    color: #475569 !important; 
    background: #FFFFFF !important; 
    border: 1px solid #CBD5E1 !important; 
    box-shadow: 0 2px 4px rgba(15, 23, 42, 0.03) !important; 
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important; 
}
.stTabs [data-baseweb="tab"]:hover { 
    border-color: #94A3B8 !important; 
    background: #F8FAFC !important; 
}
.stTabs [aria-selected="true"] { 
    color: #FFFFFF !important; 
    background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%) !important; 
    border: 1px solid #1E3A8A !important; 
    box-shadow: 0 4px 12px rgba(30, 58, 138, 0.35) !important; 
    transform: translateY(-2px); 
}
div[data-testid="stForm"], div[data-testid="stExpander"] { 
    background: rgba(255, 255, 255, 0.9) !important; 
    backdrop-filter: blur(10px) !important; 
    border: 1px solid #E2E8F0 !important; 
    border-radius: 16px !important; 
    padding: 22px !important; 
    box-shadow: 0 4px 15px rgba(15, 23, 42, 0.03) !important; 
}
button[kind="primary"] { 
    background: linear-gradient(135deg, #1E40AF, #1E3A8A) !important; 
    border: none !important; 
    border-radius: 10px !important; 
    font-weight: 600 !important; 
    font-size: 14px !important; 
    padding: 10px 24px !important; 
    color: #FFFFFF !important; 
    box-shadow: 0 4px 10px rgba(30, 58, 138, 0.3) !important; 
    transition: all 0.2s ease !important; 
}
button[kind="primary"]:hover { 
    box-shadow: 0 6px 15px rgba(30, 58, 138, 0.4) !important; 
    transform: translateY(-1px); 
}
button[kind="secondary"] { 
    border-radius: 10px !important; 
    font-weight: 600 !important; 
    border: 1px solid #CBD5E1 !important; 
    background: #FFFFFF !important; 
    color: #334155 !important; 
    box-shadow: 0 2px 4px rgba(15, 23, 42, 0.02) !important; 
}
div[data-baseweb="input"] input, div[data-baseweb="select"] { 
    border-radius: 9px !important; 
    font-size: 13.5px !important; 
    border: 1px solid #E2E8F0 !important; 
    background: #FFFFFF !important; 
}
div[data-baseweb="input"] input:focus, div[data-baseweb="select"]:focus-within { 
    border-color: #2563EB !important; 
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2) !important; 
}
</style>
"""
    st.markdown(css_string, unsafe_allow_html=True)
    components.html("""
    <script>
        function forzarLimpieza() {
            try {
                const doc = window.parent.document;
                if (doc.documentElement.lang !== 'es') { doc.documentElement.lang = 'es'; }
                if (doc.documentElement.getAttribute('translate') !== 'no') { doc.documentElement.setAttribute('translate', 'no'); }
            } catch (e) {}
        }
        forzarLimpieza();
    </script>
    """, height=0, width=0)
    st.markdown("""
<div style="background: #FFFFFF; padding: 14px 22px; border-radius: 14px; display: flex; align-items: center; border: 1px solid #E2E8F0; box-shadow: 0 2px 6px rgba(15,23,42,0.03); margin-bottom: 16px;">
<div style="background: #EFF6FF; width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 24px; margin-right: 16px; border: 1px solid #DBEAFE;">⛪</div>
<div style="flex-grow: 1;">
<div style="font-size: 11px; font-weight: 700; color: #2563EB; letter-spacing: 1.2px; text-transform: uppercase;">Asambleas de Dios del Perú</div>
<div style="font-size: 18px; font-weight: 800; color: #0F172A; font-family: 'Plus Jakarta Sans', sans-serif;">Iglesia Evangélica "Nazareth"</div>
</div>
<div style="background: #F1F5F9; padding: 6px 14px; border-radius: 20px; font-size: 11px; font-weight: 600; color: #475569;">Sistema SaaS en la Nube</div>
</div>
    """, unsafe_allow_html=True)
