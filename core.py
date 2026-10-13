import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from contextlib import contextmanager
from datetime import datetime, date
import calendar
import re
import streamlit as st
import streamlit.components.v1 as components

# NUEVAS LIBRERÍAS PARA COMPRESIÓN Y SUBIDA A LA NUBE
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
# SEGURIDAD (Desactivada para migrar a Sistema SaaS con Login)
# ==============================================================================
def verificar_licencia():
    pass 

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
    """
    Recibe un archivo de imagen, lo comprime a máx 800x800, baja el peso radicalmente
    y lo sube al bucket 'archivos_iglesia'. Retorna la URL pública de la imagen.
    """
    if archivo_subido is None:
        return ""
    
    try:
        # 1. Abrir la imagen
        img = Image.open(archivo_subido)
        
        # 2. Convertir a RGB (previene errores si suben PNG transparentes)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 3. Redimensionar manteniendo proporciones (máximo 800x800 px)
        img.thumbnail((800, 800))
        
        # 4. Guardar y comprimir en la memoria temporal
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=75, optimize=True)
        byte_data = buf.getvalue()
        
        # 5. Generar un nombre único y subir a Supabase
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        ruta_supabase = f"fotos_miembros/{nombre_base}_{timestamp}.jpg"
        
        supabase.storage.from_("archivos_iglesia").upload(
            path=ruta_supabase,
            file=byte_data,
            file_options={"content-type": "image/jpeg"}
        )
        
        # 6. Retornar el enlace directo a la foto
        url_publica = supabase.storage.from_("archivos_iglesia").get_public_url(ruta_supabase)
        return url_publica
        
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
    tablas_exentas = ["CIERRES_MENSUALES", "AUDITORIA", "CONFIG_IGLESIA", "FONDOS_CATALOGO", "RESPONSABLES_CATALOGO", "RUBROS_CATALOGO"]
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
# DISEÑO Y ESTILOS GLOBALES PREMIUM
# ==============================================================================
def aplicar_estilos_base():
    verificar_licencia()
    css_string = """
<style translate="no">
header, .stDeployButton, [data-testid="stHeader"], [data-testid="stToolbar"] { display: none !important; visibility: hidden !important; opacity: 0 !important; height: 0px !important; pointer-events: none !important; }
#MainMenu, footer { display: none !important; visibility: hidden !important; }
html, body, [class*="css"], .stApp { font-family: 'Inter', -apple-system, sans-serif !important; background: linear-gradient(135deg, #F8FAFC 0%, #E0E7FF 100%) !important; color: #0F172A !important; background-attachment: fixed !important; }
[data-testid="stSidebar"] { background: #FFFFFF !important; border-right: 1px solid #E2E8F0 !important; box-shadow: 4px 0 15px rgba(15, 23, 42, 0.03) !important; margin-top: 0px !important; }
[data-testid="stSidebarNav"] span { font-size: 13.5px !important; font-weight: 500 !important; color: #475569 !important; }
[data-testid="stSidebarNav"] [aria-current="page"] { background: linear-gradient(90deg, rgba(30, 64, 175, 0.08) 0%, transparent 100%) !important; border-left: 4px solid #1E40AF !important; }
[data-testid="stSidebarNav"] [aria-current="page"] span { font-weight: 800 !important; color: #1E40AF !important; }
div[data-testid="stMetric"] { background: rgba(255, 255, 255, 0.85) !important; backdrop-filter: blur(10px) !important; border: 1px solid rgba(255, 255, 255, 0.4) !important; border-radius: 16px !important; padding: 18px 22px !important; box-shadow: 0 4px 12px rgba(15, 23, 42, 0.04), 0 1px 2px rgba(15, 23, 42, 0.02) !important; transition: transform 0.2s ease, box-shadow 0.2s ease; }
div[data-testid="stMetric"]:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08), 0 2px 4px rgba(15, 23, 42, 0.04) !important; }
div[data-testid="stMetricLabel"] p { font-size: 12.5px !important; font-weight: 700 !important; text-transform: uppercase !important; letter-spacing: 0.5px !important; color: #475569 !important; }
div[data-testid="stMetricValue"] { font-family: 'Plus Jakarta Sans', sans-serif !important; font-size: 26px !important; font-weight: 800 !important; color: #0F172A !important; margin-top: 2px !important; }
.stTabs [data-baseweb="tab-list"] { gap: 12px !important; border-bottom: none !important; padding-bottom: 12px !important; padding-top: 5px !important; }
.stTabs [data-baseweb="tab"] { font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 700 !important; font-size: 14px !important; padding: 10px 22px !important; border-radius: 10px !important; color: #475569 !important; background: #FFFFFF !important; border: 1px solid #CBD5E1 !important; box-shadow: 0 2px 4px rgba(15, 23, 42, 0.03) !important; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important; }
.stTabs [data-baseweb="tab"]:hover { border-color: #94A3B8 !important; background: #F8FAFC !important; }
.stTabs [aria-selected="true"] { color: #FFFFFF !important; background: linear-gradient(135deg, #1E40AF 0%, #1E3A8A 100%) !important; border: 1px solid #1E3A8A !important; box-shadow: 0 4px 12px rgba(30, 58, 138, 0.35) !important; transform: translateY(-2px); }
div[data-testid="stForm"], div[data-testid="stExpander"] { background: rgba(255, 255, 255, 0.9) !important; backdrop-filter: blur(10px) !important; border: 1px solid #E2E8F0 !important; border-radius: 16px !important; padding: 22px !important; box-shadow: 0 4px 15px rgba(15, 23, 42, 0.03) !important; }
button[kind="primary"] { background: linear-gradient(135deg, #1E40AF, #1E3A8A) !important; border: none !important; border-radius: 10px !important; font-weight: 600 !important; font-size: 14px !important; padding: 10px 24px !important; color: #FFFFFF !important; box-shadow: 0 4px 10px rgba(30, 58, 138, 0.3) !important; transition: all 0.2s ease !important; }
button[kind="primary"]:hover { box-shadow: 0 6px 15px rgba(30, 58, 138, 0.4) !important; transform: translateY(-1px); }
button[kind="secondary"] { border-radius: 10px !important; font-weight: 600 !important; border: 1px solid #CBD5E1 !important; background: #FFFFFF !important; color: #334155 !important; box-shadow: 0 2px 4px rgba(15, 23, 42, 0.02) !important; }
div[data-baseweb="input"] input, div[data-baseweb="select"] { border-radius: 9px !important; font-size: 13.5px !important; border: 1px solid #E2E8F0 !important; background: #FFFFFF !important; }
div[data-baseweb="input"] input:focus, div[data-baseweb="select"]:focus-within { border-color: #2563EB !important; box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.2) !important; }
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
                const header = doc.querySelector('header');
                if (header) { header.style.display = 'none'; header.style.visibility = 'hidden'; header.style.height = '0px'; }
            } catch (e) {}
        }
        forzarLimpieza();
        setInterval(forzarLimpieza, 500);
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

def inicializar_bd():
    queries = """
    CREATE TABLE IF NOT EXISTS miembros (
        id_miembro TEXT PRIMARY KEY,
        nombre TEXT,
        telefono TEXT,
        direccion TEXT DEFAULT '',
        fecha_nacimiento TEXT DEFAULT '',
        estado_civil TEXT DEFAULT 'Soltero(a)',
        bautizado TEXT DEFAULT 'No',
        miembro_pleno TEXT DEFAULT 'No',
        cargo_eclesiastico TEXT DEFAULT 'Miembro Activo',
        foto TEXT DEFAULT '',
        fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS diezmos (id SERIAL PRIMARY KEY, fecha TEXT, id_miembro TEXT, nombre_miembro TEXT, mes TEXT, medio TEXT, monto REAL, detalle TEXT, codigo_comprobante TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS movimientos (id SERIAL PRIMARY KEY, fecha TEXT, tipo TEXT, categoria TEXT, subcategoria TEXT, fondo TEXT DEFAULT 'General', monto REAL, medio TEXT, comprobante TEXT, detalle TEXT, responsable TEXT, archivo_foto TEXT, estado_credito TEXT DEFAULT 'Cobrado');
    CREATE TABLE IF NOT EXISTS cierres_mensuales (id SERIAL PRIMARY KEY, periodo TEXT UNIQUE, fecha_cierre TEXT, saldo_ini_efectivo REAL, saldo_ini_banco REAL, ingresos_efectivo REAL, ingresos_banco REAL, egresos_efectivo REAL, egresos_banco REAL, saldo_fin_efectivo REAL, saldo_fin_banco REAL, saldo_cierre REAL DEFAULT 0.0, usuario TEXT DEFAULT 'Tesorería General', estado TEXT DEFAULT 'Abierto');
    CREATE TABLE IF NOT EXISTS rubros_catalogo (id SERIAL PRIMARY KEY, tipo TEXT, categoria TEXT, subcategoria TEXT);
    CREATE TABLE IF NOT EXISTS responsables_catalogo (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS fondos_catalogo (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE);
    CREATE TABLE IF NOT EXISTS presupuestos (id SERIAL PRIMARY KEY, periodo TEXT, categoria TEXT, monto_presupuestado REAL, UNIQUE(periodo, categoria));
    CREATE TABLE IF NOT EXISTS auditoria (id SERIAL PRIMARY KEY, fecha_hora TEXT, modulo TEXT, accion TEXT, descripcion TEXT);
    CREATE TABLE IF NOT EXISTS pagos_programados (id SERIAL PRIMARY KEY, titulo TEXT, categoria TEXT, subcategoria TEXT, fondo TEXT, monto REAL, medio TEXT, responsable TEXT, periodicidad TEXT, momento_corte TEXT, dia_fijo INTEGER, fecha_proximo_pago TEXT, ultimo_pago TEXT, estado TEXT DEFAULT 'Pendiente');
    CREATE TABLE IF NOT EXISTS foro_recordatorios (id SERIAL PRIMARY KEY, fecha_creacion TEXT, autor TEXT, titulo TEXT, contenido TEXT, fecha_limite TEXT, prioridad TEXT, leido INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS actividades (id SERIAL PRIMARY KEY, nombre TEXT, fecha TEXT, responsable TEXT, descripcion TEXT, ultima_fecha_corte TEXT DEFAULT '', estado TEXT DEFAULT 'Activa');
    CREATE TABLE IF NOT EXISTS actividad_movimientos (id SERIAL PRIMARY KEY, id_actividad INTEGER, fecha TEXT, tipo TEXT, concepto TEXT, monto REAL, condicion TEXT, cliente_deudor TEXT, estado_cobro TEXT, medio TEXT, fondo_destino TEXT, liquidado INTEGER DEFAULT 0, fecha_corte TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS planilla_pastoral (id SERIAL PRIMARY KEY, codigo_voucher TEXT UNIQUE, fecha_pago TEXT, periodo_mes TEXT, periodo_anio INTEGER, pastor_nombre TEXT, sueldo_bruto REAL, pct_afp REAL, monto_afp REAL, pct_essalud REAL, monto_essalud REAL, neto_pagado REAL, costo_total REAL, medio_pago TEXT, fondo TEXT, detalle TEXT, estado TEXT DEFAULT 'Pagado');
    CREATE TABLE IF NOT EXISTS config_iglesia (clave TEXT PRIMARY KEY, valor TEXT);
    """
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(queries)
            conn.commit()
    except Exception as e:
        print(f"La base de datos ya está inicializada o hubo un error: {e}")
