import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from contextlib import contextmanager
from datetime import datetime, date
import calendar
import re
import hashlib
import io
import streamlit as st
from PIL import Image
from supabase import create_client, Client

# ==============================================================================
# CONFIGURACIÓN GENERAL Y MAPEO EXACTO DE TODOS LOS MÓDULOS
# ==============================================================================
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
MEDIOS = ["Efectivo", "Depósito / Transferencia"]
MESES_NUM = {m: i + 1 for i, m in enumerate(MESES)}
MESES_NOMBRES = {v: k for k, v in MESES_NUM.items()}

# Mapeo de los módulos con los nombres de archivo de tu carpeta pages/
MAPA_MODULOS_SIDEBAR = {
    "miembros": ["1_miembros", "miembros", "padron"],
    "diezmos": ["2_diezmos", "diezmos"],
    "foro / recordatorios": ["3_foro_recordatorios", "foro_recordatorios", "recordatorios", "foro"],
    "pagos programados": ["4_pagos_programados", "pagos_programados", "programados"],
    "sostenimiento pastoral": ["5_sostenimiento_pastoral", "sostenimiento_pastoral", "sostenimiento", "pastoral"],
    "actividades": ["6_actividades", "actividades"],
    "tesorería": ["7_tesoreria", "tesoreria"],
    "configuración": ["8_configuracion", "configuracion", "config"]
}

# ==============================================================================
# SEGURIDAD, LOGIN Y VERIFICACIÓN DE ACCESOS
# ==============================================================================
def verificar_licencia():
    pass 

def encriptar_clave(password: str) -> str:
    return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()

def validar_login(usuario: str, password_plana: str):
    u_limpio = usuario.strip().lower()
    p_hash = encriptar_clave(password_plana)
    
    if u_limpio == "admin" and password_plana.strip() == "Nazareth2026*":
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.usuarios_sistema (usuario, password_hash, nombre, rol, activo, permisos)
                        VALUES ('admin', %s, 'Administrador General', 'Administrador', TRUE, 'TODOS')
                        ON CONFLICT (usuario) 
                        DO UPDATE SET password_hash = %s, activo = TRUE, permisos = 'TODOS'
                        """,
                        (p_hash, p_hash)
                    )
                conn.commit()
        except Exception:
            pass

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("ALTER TABLE public.usuarios_sistema ADD COLUMN IF NOT EXISTS permisos TEXT DEFAULT 'TODOS';")
                    conn.commit()
                except Exception:
                    conn.rollback()

                cur.execute(
                    """
                    SELECT usuario, nombre, rol, COALESCE(permisos, 'TODOS') AS permisos 
                    FROM public.usuarios_sistema 
                    WHERE LOWER(TRIM(usuario)) = %s AND password_hash = %s AND activo = TRUE
                    """,
                    (u_limpio, p_hash)
                )
                fila = cur.fetchone()
                if fila:
                    return dict(fila)
    except Exception as e:
        st.error(f"Error de conexión al autenticar: {e}")
    return None

def requerir_login():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
        st.session_state["usuario_actual"] = None

    if not st.session_state["autenticado"]:
        st.markdown("""
        <style>
            [data-testid="stSidebar"], [data-testid="collapsedControl"], header { display: none !important; }
        </style>
        """, unsafe_allow_html=True)
        
        col_espacio, col_form, col_espacio2 = st.columns([1, 1.8, 1])
        with col_form:
            st.markdown("""
            <div style="background: #FFFFFF; padding: 30px; border-radius: 18px; border: 1px solid #E2E8F0; box-shadow: 0 10px 25px rgba(15,23,42,0.06); margin-top: 45px;">
                <div style="text-align: center; font-size: 38px; margin-bottom: 8px;">⛪</div>
                <h3 style="color: #1E3A8A; text-align: center; margin-bottom: 2px; font-weight: 800;">Sistema Nazareth</h3>
                <p style="text-align: center; font-size: 13px; color: #64748B; margin-bottom: 25px;">Acceso Gerencial y Administrativo</p>
            """, unsafe_allow_html=True)

            with st.form("form_login"):
                u_in = st.text_input("Usuario", placeholder="Ingresa tu usuario")
                p_in = st.text_input("Contraseña", type="password", placeholder="Ingresa tu contraseña")
                btn_entrar = st.form_submit_button("Iniciar Sesión", type="primary", use_container_width=True)

                if btn_entrar:
                    datos_user = validar_login(u_in, p_in)
                    if datos_user:
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_actual"] = datos_user
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos.")

            st.markdown("</div>", unsafe_allow_html=True)
        st.stop()
    else:
        with st.sidebar:
            st.markdown(f"👤 **{st.session_state['usuario_actual']['nombre']}**")
            st.caption(f"Rol: {st.session_state['usuario_actual']['rol']}")
            if st.button("🚪 Cerrar Sesión", use_container_width=True):
                st.session_state["autenticado"] = False
                st.session_state["usuario_actual"] = None
                st.rerun()
            st.markdown("---")

def verificar_acceso_pagina(nombre_modulo: str):
    """Impide la ejecución de la página si el usuario no tiene permiso asignado."""
    requerir_login()
    user = st.session_state.get("usuario_actual", {})
    if user.get("rol") == "Administrador":
        return True
    
    permisos_raw = user.get("permisos", "")
    if "TODOS" in permisos_raw.upper():
        return True

    permisos_lista = [p.strip().lower() for p in permisos_raw.split(",") if p.strip()]
    if nombre_modulo.strip().lower() not in permisos_lista:
        st.error(f"⛔ **Acceso Restringido**: No tienes autorización para ingresar al módulo de **{nombre_modulo}**.")
        st.info("Comunícate con el Administrador General para solicitar acceso.")
        st.stop()
    return True

# ==============================================================================
# CONEXIÓN DIRECTA CON SUPABASE STORAGE
# ==============================================================================
@st.cache_resource
def init_supabase() -> Client:
    url: str = str(st.secrets["API_URL"]).strip()
    key: str = str(st.secrets["API_KEY"]).strip()
    return create_client(url, key)

supabase = init_supabase()

def comprimir_y_subir_foto(archivo_subido, nombre_base):
    if archivo_subido is None:
        return ""
    try:
        img = Image.open(archivo_subido)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.thumbnail((800, 800))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=75, optimize=True)
        byte_data = buf.getvalue()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        ruta_supabase = f"fotos_miembros/{nombre_base}_{timestamp}.jpg"
        supabase.storage.from_("archivos_iglesia").upload(
            path=ruta_supabase,
            file=byte_data,
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )
        return supabase.storage.from_("archivos_iglesia").get_public_url(ruta_supabase)
    except Exception as e:
        st.warning(f"Aviso de Storage: {e}")
        return ""

@contextmanager
def get_db():
    url = st.secrets["SUPABASE_DB_URL"]
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO public;")
        yield conn
    finally:
        conn.close()

def es_periodo_cerrado(fecha_param):
    if not fecha_param: return False
    str_val = str(fecha_param)
    coincidencia = re.search(r"\b(\d{4}-\d{2})\b", str_val)
    if not coincidencia: return False
    periodo = coincidencia.group(1)
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT estado FROM public.cierres_mensuales WHERE periodo = %s", (periodo,))
                fila = cur.fetchone()
                if fila and fila["estado"] == "Cerrado": return True
    except Exception: pass
    return False

def query_db(query, params=(), commit=True):
    q_limpia = query.strip().upper()
    es_modificacion = q_limpia.startswith("INSERT") or q_limpia.startswith("UPDATE") or q_limpia.startswith("DELETE")
    tablas_exentas = ["CIERRES_MENSUALES", "AUDITORIA", "CONFIG_IGLESIA", "FONDOS_CATALOGO", "RESPONSABLES_CATALOGO", "RUBROS_CATALOGO", "USUARIOS_SISTEMA"]
    es_exenta = any(t in q_limpia for t in tablas_exentas)
    
    if es_modificacion and not es_exenta:
        for p in params:
            if isinstance(p, (str, date, datetime)):
                str_p = str(p)
                if es_periodo_cerrado(str_p):
                    per_bloqueado = re.search(r"\b(\d{4}-\d{2})\b", str_p).group(1)
                    st.error(f"🔒 **OPERACIÓN BLOQUEADA**: El periodo `{per_bloqueado}` se encuentra CERRADO.")
                    st.stop()
                    
    pg_query = query.replace("?", "%s")
    
    tiene_returning = "RETURNING" in q_limpia
    if q_limpia.startswith("INSERT") and not tiene_returning:
        if "MIEMBROS" not in q_limpia and "AUDITORIA" not in q_limpia:
            pg_query += " RETURNING id"

    params_limpios = [p.item() if hasattr(p, "item") else p for p in params]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(pg_query, tuple(params_limpios))
            inserted_id = None
            if q_limpia.startswith("INSERT") and ("RETURNING id" in pg_query):
                try:
                    res = cur.fetchone()
                    if res and 'id' in res:
                        inserted_id = res['id']
                except Exception:
                    pass
            if commit:
                conn.commit()
                st.cache_data.clear()
            return inserted_id

@st.cache_data
def read_db(query, params=()):
    pg_query = query.replace("?", "%s")
    params_limpios = [p.item() if hasattr(p, "item") else p for p in params]
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(pg_query, tuple(params_limpios))
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                data = cur.fetchall()
                return pd.DataFrame(data, columns=columns)
            return pd.DataFrame()

def registrar_log(modulo, accion, descripcion):
    query_db("INSERT INTO public.auditoria (fecha_hora, modulo, accion, descripcion) VALUES (%s, %s, %s, %s)", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), modulo, accion, descripcion))

# ==============================================================================
# DISEÑO Y ESTILOS GLOBALES (OCULTAMIENTO DE MÓDULOS DE LA BARRA LATERAL)
# ==============================================================================
def aplicar_estilos_base():
    verificar_licencia()

    css_ocultar_paginas = ""
    usuario_act = st.session_state.get("usuario_actual")
    if usuario_act and usuario_act.get("rol") != "Administrador":
        permisos_raw = usuario_act.get("permisos", "")
        if "TODOS" not in permisos_raw.upper():
            permisos_user = [p.strip().lower() for p in permisos_raw.split(",") if p.strip()]

            # Ocultar página raíz / Panel Principal si no fue autorizada
            if "panel principal" not in permisos_user:
                css_ocultar_paginas += """
                [data-testid="stSidebarNav"] li:has(a[href="/"]),
                [data-testid="stSidebarNav"] li:has(a[href=""]),
                [data-testid="stSidebarNav"] li:has(a[href*="inicio" i]),
                [data-testid="stSidebarNav"] li:has(a[href*="panel" i]),
                [data-testid="stSidebarNav"] li:has(a[href*="app" i]) {
                    display: none !important;
                }
                """

            # Ocultar módulos de pages/ que no estén en la lista de permisos
            for mod_nombre, keywords in MAPA_MODULOS_SIDEBAR.items():
                if mod_nombre not in permisos_user:
                    for kw in keywords:
                        css_ocultar_paginas += f"""
                        [data-testid="stSidebarNav"] li:has(a[href*="{kw}" i]),
                        [data-testid="stSidebarNav"] a[href*="{kw}" i] {{
                            display: none !important;
                        }}
                        """

    css_string = f"""
<style translate="no">
#MainMenu {{ visibility: hidden !important; }}
footer {{ visibility: hidden !important; }}
.stDeployButton {{ display: none !important; }}

header[data-testid="stHeader"] {{
    background: transparent !important;
    display: flex !important;
    z-index: 100 !important;
}}

/* BOTÓN FLOTANTE PERMANENTE PARA ABRIR / CERRAR MENÚ (EN PC Y MÓVIL) */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {{
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    position: fixed !important;
    top: 12px !important;
    left: 12px !important;
    z-index: 9999999 !important;
    background: #1E3A8A !important;
    color: #FFFFFF !important;
    border: 1.5px solid #3B82F6 !important;
    border-radius: 10px !important;
    padding: 6px 12px !important;
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.3) !important;
    cursor: pointer !important;
}}

[data-testid="collapsedControl"] svg,
[data-testid="stSidebarCollapsedControl"] svg {{
    fill: #FFFFFF !important;
    stroke: #FFFFFF !important;
    width: 22px !important;
    height: 22px !important;
}}

[data-testid="stSidebarCollapseButton"] {{
    display: flex !important;
    visibility: visible !important;
    color: #1E3A8A !important;
}}

/* Barra lateral */
[data-testid="stSidebar"] {{ 
    background: #FFFFFF !important; 
    border-right: 1px solid #E2E8F0 !important; 
    box-shadow: 4px 0 15px rgba(15, 23, 42, 0.05) !important; 
}}
[data-testid="stSidebarNav"] span {{ 
    font-size: 14px !important; 
    font-weight: 600 !important; 
    color: #334155 !important; 
}}
[data-testid="stSidebarNav"] [aria-current="page"] {{ 
    background: linear-gradient(90deg, rgba(30, 64, 175, 0.1) 0%, transparent 100%) !important; 
    border-left: 4px solid #1E40AF !important; 
}}
[data-testid="stSidebarNav"] [aria-current="page"] span {{ 
    font-weight: 800 !important; 
    color: #1E40AF !important; 
}}

html, body, [class*="css"], .stApp {{ 
    font-family: 'Inter', -apple-system, sans-serif !important; 
    background: linear-gradient(135deg, #F8FAFC 0%, #E0E7FF 100%) !important; 
    color: #0F172A !important; 
    background-attachment: fixed !important; 
}}

div[data-testid="stRadio"] > div[role="radiogroup"] {{
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
    gap: 8px !important;
    width: 100% !important;
}}

div[data-testid="stRadio"] > div[role="radiogroup"] > label {{
    background: #FFFFFF !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 10px !important;
    padding: 8px 16px !important;
    cursor: pointer !important;
    flex: 1 1 auto !important;
    text-align: center !important;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
}}

div[data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {{
    display: none !important;
}}

div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {{
    background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%) !important;
    border-color: #1E3A8A !important;
    box-shadow: 0 4px 10px rgba(30, 58, 138, 0.3) !important;
}}

div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p,
div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) span {{
    color: #FFFFFF !important;
    font-weight: 700 !important;
}}

div[data-testid="stMetric"] {{ 
    background: rgba(255, 255, 255, 0.85) !important; 
    backdrop-filter: blur(10px) !important; 
    border: 1px solid rgba(255, 255, 255, 0.4) !important; 
    border-radius: 16px !important; 
    padding: 16px 20px !important; 
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04) !important; 
}}
div[data-testid="stMetricLabel"] p {{ 
    font-size: 12px !important; 
    font-weight: 700 !important; 
    text-transform: uppercase !important; 
    color: #475569 !important; 
}}
div[data-testid="stMetricValue"] {{ 
    font-family: 'Plus Jakarta Sans', sans-serif !important; 
    font-size: 24px !important; 
    font-weight: 800 !important; 
    color: #0F172A !important; 
}}

div[data-testid="stForm"], div[data-testid="stExpander"] {{ 
    background: rgba(255, 255, 255, 0.9) !important; 
    backdrop-filter: blur(10px) !important; 
    border: 1px solid #E2E8F0 !important; 
    border-radius: 16px !important; 
    padding: 20px !important; 
    box-shadow: 0 4px 15px rgba(15, 23, 42, 0.03) !important; 
}}

button[kind="primary"] {{ 
    background: linear-gradient(135deg, #1E40AF, #1E3A8A) !important; 
    border: none !important; 
    border-radius: 10px !important; 
    font-weight: 600 !important; 
    font-size: 14px !important; 
    padding: 10px 24px !important; 
    color: #FFFFFF !important; 
    box-shadow: 0 4px 10px rgba(30, 58, 138, 0.3) !important; 
}}
button[kind="secondary"] {{ 
    border-radius: 10px !important; 
    font-weight: 600 !important; 
    border: 1px solid #CBD5E1 !important; 
    background: #FFFFFF !important; 
    color: #334155 !important; 
}}

div[data-baseweb="input"] input, div[data-baseweb="select"] {{ 
    border-radius: 9px !important; 
    font-size: 13.5px !important; 
    border: 1px solid #E2E8F0 !important; 
    background: #FFFFFF !important; 
}}

/* REGLAS CSS PARA OCULTAR PÁGINAS NO AUTORIZADAS */
{css_ocultar_paginas}
</style>
"""
    st.markdown(css_string, unsafe_allow_html=True)

    st.markdown("""
<div style="background: #FFFFFF; padding: 14px 20px; border-radius: 14px; display: flex; align-items: center; border: 1px solid #E2E8F0; box-shadow: 0 2px 6px rgba(15,23,42,0.03); margin-bottom: 16px;">
<div style="background: #EFF6FF; width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 24px; margin-right: 14px; border: 1px solid #DBEAFE; flex-shrink: 0;">⛪</div>
<div style="flex-grow: 1;">
<div style="font-size: 10.5px; font-weight: 700; color: #2563EB; letter-spacing: 1px; text-transform: uppercase;">Asambleas de Dios del Perú</div>
<div style="font-size: 17px; font-weight: 800; color: #0F172A; font-family: 'Plus Jakarta Sans', sans-serif;">Iglesia Evangélica "Nazareth"</div>
</div>
<div style="background: #F1F5F9; padding: 4px 10px; border-radius: 20px; font-size: 10.5px; font-weight: 600; color: #475569; white-space: nowrap;">Cloud</div>
</div>
    """, unsafe_allow_html=True)

def banner_modulo(icono, titulo, subtitulo, tag_derecha="Módulo Cloud"):
    st.markdown(f"""
<div style="background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%); padding: 18px 22px; border-radius: 16px; margin-bottom: 20px; color: #FFFFFF; box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12); display: flex; justify-content: space-between; align-items: center; border: 1px solid rgba(255,255,255,0.1); flex-wrap: wrap; gap: 10px;">
<div>
<div style="font-size: 22px; font-weight: 800; color: #FFFFFF !important; font-family: 'Plus Jakarta Sans', sans-serif; display: flex; align-items: center; gap: 10px;"><span>{icono}</span> <span style="color: #FFFFFF !important;">{titulo}</span></div>
<div style="font-size: 13px; color: #93C5FD !important; margin-top: 4px; font-weight: 500;">{subtitulo}</div>
</div>
<div style="background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.25); padding: 6px 14px; border-radius: 20px; font-size: 11px; font-weight: 700; color: #FFFFFF !important; white-space: nowrap; text-transform: uppercase;">{tag_derecha}</div>
</div>
""", unsafe_allow_html=True)

def selector_periodo(clave):
    col_a, col_m = st.columns(2)
    anio_act = date.today().year
    with col_a:
        anio = st.selectbox("Año:", list(range(anio_act - 5, anio_act + 6)), index=5, key=f"{clave}_a")
    with col_m:
        mes = st.selectbox("Mes:", MESES, index=date.today().month - 1, key=f"{clave}_m")
    num_m = MESES_NUM[mes]
    dia_def = min(date.today().day, calendar.monthrange(anio, num_m)[1])
    return anio, mes, num_m, date(anio, num_m, dia_def)

def inicializar_bd():
    pass
