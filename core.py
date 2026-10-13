import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from contextlib import contextmanager
from datetime import datetime, date
import calendar
import re
import hashlib
import streamlit as st

# ==============================================================================
# LIBRERÍAS PARA COMPRESIÓN Y SUBIDA A LA NUBE
# ==============================================================================
import io
from PIL import Image
from supabase import create_client, Client

# ==============================================================================
# CONFIGURACIÓN GENERAL
# ==============================================================================
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
MEDIOS = ["Efectivo", "Depósito / Transferencia"]
MESES_NUM = {m: i + 1 for i, m in enumerate(MESES)}
MESES_NOMBRES = {v: k for k, v in MESES_NUM.items()}

# ==============================================================================
# SEGURIDAD Y LOGIN
# ==============================================================================
def verificar_licencia():
    pass 

def encriptar_clave(password: str) -> str:
    return hashlib.sha256(password.strip().encode("utf-8")).hexdigest()

def validar_login(usuario: str, password_plana: str):
    u_limpio = usuario.strip().lower()
    p_hash = encriptar_clave(password_plana)
    
    # Auto-sincronización del usuario inicial
    if u_limpio == "admin" and password_plana.strip() == "Nazareth2026*":
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO usuarios_sistema (usuario, password_hash, nombre, rol, activo)
                        VALUES ('admin', %s, 'Administrador General', 'Administrador', TRUE)
                        ON CONFLICT (usuario) 
                        DO UPDATE SET password_hash = %s, activo = TRUE
                        """,
                        (p_hash, p_hash)
                    )
                conn.commit()
        except Exception:
            pass

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT usuario, nombre, rol FROM usuarios_sistema WHERE LOWER(TRIM(usuario)) = %s AND password_hash = %s AND activo = TRUE",
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

# ==============================================================================
# CONEXIÓN A BASE DE DATOS Y STORAGE EN LA NUBE (SUPABASE)
# ==============================================================================
@st.cache_resource
def init_supabase() -> Client:
    url: str = st.secrets["API_URL"]
    key: str = st.secrets["API_KEY"]
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
            file_options={"content-type": "image/jpeg"}
        )
        
        return supabase.storage.from_("archivos_iglesia").get_public_url(ruta_supabase)
        
    except Exception as e:
        st.error(f"⚠️ Error al procesar y subir la foto: {e}")
        return ""

@contextmanager
def get_db():
    url = st.secrets["SUPABASE_DB_URL"]
    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    try:
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
                cur.execute("SELECT estado FROM cierres_mensuales WHERE periodo = %s", (periodo,))
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
    
    if q_limpia.startswith("INSERT") and "RETURNING ID" not in q_limpia:
        pg_query += " RETURNING id"

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(pg_query, params)
            inserted_id = None
            if q_limpia.startswith("INSERT"):
                try:
                    inserted_id = cur.fetchone()['id']
                except:
                    pass
            if commit:
                conn.commit()
                st.cache_data.clear()
            return inserted_id

@st.cache_data
def read_db(query, params=()):
    pg_query = query.replace("?", "%s")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(pg_query, params)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                data = cur.fetchall()
                return pd.DataFrame(data, columns=columns)
            return pd.DataFrame()

def registrar_log(modulo, accion, descripcion):
    query_db("INSERT INTO auditoria (fecha_hora, modulo, accion, descripcion) VALUES (%s, %s, %s, %s)", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), modulo, accion, descripcion))

# ==============================================================================
# DISEÑO Y ESTILOS GLOBALES
# ==============================================================================
def aplicar_estilos_base():
    verificar_licencia()
    css_string = """
<style translate="no">
#MainMenu { visibility: hidden !important; }
footer { visibility: hidden !important; }
.stDeployButton { display: none !important; }

header[data-testid="stHeader"] {
    background-color: transparent !important;
}

[data-testid="stSidebar"] { 
    background: #FFFFFF !important; 
    border-right: 1px solid #E2E8F0 !important; 
    box-shadow: 4px 0 15px rgba(15, 23, 42, 0.03) !important; 
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

html, body, [class*="css"], .stApp { 
    font-family: 'Inter', -apple-system, sans-serif !important; 
    background: linear-gradient(135deg, #F8FAFC 0%, #E0E7FF 100%) !important; 
    color: #0F172A !important; 
    background-attachment: fixed !important; 
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
""", unsafe_allow_html=True)
    st.markdown(css_string, unsafe_allow_html=True)

    # El banner de la iglesia se muestra UNA SOLA VEZ aquí
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

def banner_modulo(icono, titulo, subtitulo, tag_derecha="Módulo Cloud"):
    st.markdown(f"""
<div style="background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%); padding: 22px 26px; border-radius: 16px; margin-bottom: 24px; color: #FFFFFF; box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12); display: flex; justify-content: space-between; align-items: center; border: 1px solid rgba(255,255,255,0.1);">
<div>
<div style="font-size: 24px; font-weight: 800; color: #FFFFFF !important; font-family: 'Plus Jakarta Sans', sans-serif; display: flex; align-items: center; gap: 12px;"><span>{icono}</span> <span style="color: #FFFFFF !important;">{titulo}</span></div>
<div style="font-size: 13.5px; color: #93C5FD !important; margin-top: 6px; font-weight: 500; letter-spacing: 0.3px;">{subtitulo}</div>
</div>
<div style="background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, 0.25); padding: 8px 18px; border-radius: 20px; font-size: 12px; font-weight: 700; color: #FFFFFF !important; white-space: nowrap; text-transform: uppercase; letter-spacing: 0.5px;">{tag_derecha}</div>
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
