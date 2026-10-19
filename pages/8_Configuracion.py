import streamlit as st
import core
import os
import io
import zipfile
import calendar
import pandas as pd
from datetime import date

# 1. Configuración de página (primera orden de Streamlit)
st.set_page_config(
    page_title="Configuración General", 
    page_icon="⚙️", 
    layout="wide"
)

# 2. Seguridad: Verificar que el usuario tenga acceso a Configuración
core.verificar_acceso_pagina("Configuración")
core.aplicar_estilos_base()

# LISTA COMPLETA Y EXACTA DE TODOS LOS MÓDULOS DEL SISTEMA
TODOS_LOS_MODULOS = [
    "Panel Principal",
    "Miembros",
    "Diezmos",
    "Foro / Recordatorios",
    "Pagos Programados",
    "Sostenimiento Pastoral",
    "Actividades",
    "Tesorería",
    "Configuración"
]

# 3. Estructura de tablas y permisos en PostgreSQL
try:
    with core.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.config_iglesia (
                    clave TEXT PRIMARY KEY,
                    valor TEXT
                );
                CREATE TABLE IF NOT EXISTS public.cierres_mensuales (
                    periodo TEXT PRIMARY KEY,
                    fecha_cierre TEXT,
                    estado TEXT DEFAULT 'Abierto',
                    saldo_cierre NUMERIC(12, 2) DEFAULT 0.0,
                    usuario TEXT DEFAULT 'Tesorería General'
                );
                ALTER TABLE public.cierres_mensuales ADD COLUMN IF NOT EXISTS saldo_cierre NUMERIC(12, 2) DEFAULT 0.0;
                ALTER TABLE public.cierres_mensuales ADD COLUMN IF NOT EXISTS usuario TEXT DEFAULT 'Tesorería General';

                CREATE TABLE IF NOT EXISTS public.responsables_catalogo (
                    id SERIAL PRIMARY KEY,
                    nombre TEXT UNIQUE NOT NULL
                );
                CREATE TABLE IF NOT EXISTS public.fondos_catalogo (
                    id SERIAL PRIMARY KEY,
                    nombre TEXT UNIQUE NOT NULL
                );
                CREATE TABLE IF NOT EXISTS public.rubros_catalogo (
                    id SERIAL PRIMARY KEY,
                    tipo TEXT NOT NULL,
                    categoria TEXT NOT NULL,
                    subcategoria TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS public.usuarios_sistema (
                    id SERIAL PRIMARY KEY,
                    usuario TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    nombre TEXT NOT NULL,
                    rol TEXT NOT NULL,
                    activo BOOLEAN DEFAULT TRUE,
                    permisos TEXT DEFAULT 'Panel Principal,Diezmos,Tesorería',
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                ALTER TABLE public.usuarios_sistema ADD COLUMN IF NOT EXISTS permisos TEXT DEFAULT 'Panel Principal,Diezmos,Tesorería';
                INSERT INTO public.fondos_catalogo (nombre) VALUES ('General') ON CONFLICT (nombre) DO NOTHING;
            """)
        conn.commit()
except Exception:
    pass

def get_config(clave, default=""):
    df = core.read_db("SELECT valor FROM public.config_iglesia WHERE clave=?", (clave,))
    return df.iloc[0]["valor"] if not df.empty else default

def set_config(clave, valor):
    core.query_db("""
        INSERT INTO public.config_iglesia (clave, valor) VALUES (?, ?) 
        ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor
        RETURNING clave
    """, (clave, str(valor).strip()))

def crear_backup_archivos_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for carp in ["fotos_miembros", "comprobantes"]:
            if os.path.exists(carp):
                for r, _, files in os.walk(carp):
                    for f in files:
                        p = os.path.join(r, f)
                        z.write(p, arcname=p)
    return buf.getvalue()

def generar_backup_completo_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        tablas_exportar = [
            ("Miembros", "SELECT * FROM public.miembros ORDER BY id_miembro ASC"),
            ("Diezmos", "SELECT * FROM public.diezmos ORDER BY id DESC"),
            ("Movimientos_Tesoreria", "SELECT * FROM public.movimientos ORDER BY id DESC"),
            ("Fondos", "SELECT * FROM public.fondos_catalogo ORDER BY id ASC"),
            ("Rubros_Catalogo", "SELECT * FROM public.rubros_catalogo ORDER BY tipo ASC, categoria ASC"),
            ("Cierres_Mensuales", "SELECT * FROM public.cierres_mensuales ORDER BY periodo DESC"),
            ("Auditoria", "SELECT * FROM public.auditoria ORDER BY id DESC LIMIT 500"),
            ("Configuracion", "SELECT * FROM public.config_iglesia ORDER BY clave ASC")
        ]
        for sheet_name, sql in tablas_exportar:
            try:
                df_t = core.read_db(sql)
                if not df_t.empty:
                    df_t.to_excel(writer, index=False, sheet_name=sheet_name[:31])
                else:
                    pd.DataFrame({"Aviso": ["Sin registros"]}).to_excel(writer, index=False, sheet_name=sheet_name[:31])
            except Exception:
                pass
    return output.getvalue()

st.subheader("⚙️ Configuración y Administración del Sistema")

rol_actual = st.session_state.get("usuario_actual", {}).get("rol", "")
es_administrador = (rol_actual == "Administrador")

# Respaldo y Usuarios solo aparecen para el Administrador General
if es_administrador:
    secciones_configuracion = [
        "🏛️ Parámetros y Catálogos",
        "🔒 Cierres de Mes y Auditoría",
        "🛡️ Respaldo y Base de Datos",
        "👥 Usuarios y Permisos"
    ]
else:
    secciones_configuracion = [
        "🏛️ Parámetros y Catálogos",
        "🔒 Cierres de Mes y Auditoría"
    ]

seccion_cfg = st.radio(
    "Sección de Configuración:",
    secciones_configuracion,
    horizontal=True
)

st.markdown("---")

# ==============================================================================
# 1. PARÁMETROS Y CATÁLOGOS
# ==============================================================================
if seccion_cfg == "🏛️ Parámetros y Catálogos":
    col_izq, col_der = st.columns(2)

    with col_izq:
        st.markdown("#### 🏛️ Datos de la Iglesia y Firmas")
        with st.form("form_identidad"):
            c_a, c_b = st.columns(2)
            with c_a:
                nom_igl = st.text_input("Nombre de la Iglesia:", value=get_config("nombre_iglesia", "IGLESIA EVANGÉLICA NAZARETH"))
                den_igl = st.text_input("Denominación:", value=get_config("denominacion", "ASAMBLEAS DE DIOS DEL PERÚ"))
                ruc_igl = st.text_input("RUC / Reg. Religioso:", value=get_config("ruc_registro", "20549182910"))
                pas_igl = st.text_input("Pastor(a) Principal:", value=get_config("pastor_principal", "Pastor Titular"))
            with c_b:
                tes_igl = st.text_input("Tesorero(a) General:", value=get_config("tesorero_general", "Tesorero General"))
                dir_igl = st.text_input("Dirección del Templo:", value=get_config("direccion", "Jr. Trujillo 450"))
                tel_igl = st.text_input("Teléfono / WhatsApp:", value=get_config("telefono_contacto", "987654321"))
                lem_igl = st.text_input("Lema / Versículo:", value=get_config("lema_iglesia", "«Dios ama al dador alegre» (2 Corintios 9:7)"))

            if st.form_submit_button("💾 Guardar Datos y Firmas", type="primary"):
                set_config("nombre_iglesia", nom_igl)
                set_config("denominacion", den_igl)
                set_config("ruc_registro", ruc_igl)
                set_config("pastor_principal", pas_igl)
                set_config("tesorero_general", tes_igl)
                set_config("direccion", dir_igl)
                set_config("telefono_contacto", tel_igl)
                set_config("lema_iglesia", lem_igl)
                
                core.query_db(
                    "INSERT INTO public.auditoria (fecha_hora, modulo, accion, descripcion) VALUES (?, 'Config_Tesorero', 'Actualizar', ?)", 
                    (str(date.today()), tes_igl.strip())
                )
                core.registrar_log("Configuración", "Identidad", "Actualizados datos institucionales y firmas.")
                st.toast("✅ Datos institucionales guardados correctamente.")
                st.rerun()

        st.markdown("#### 👤 Catálogo de Responsables / Firmantes")
        df_resp = core.read_db("SELECT id, nombre FROM public.responsables_catalogo ORDER BY nombre ASC")
        st.dataframe(
            df_resp.rename(columns={"nombre": "Autoridades / Responsables Registrados"}), 
            use_container_width=True, 
            hide_index=True
        )

        c_r1, c_r2 = st.columns(2)
        with c_r1:
            with st.form("form_add_resp_mini"):
                n_resp = st.text_input("Añadir Responsable:")
                if st.form_submit_button("➕ Añadir"):
                    if n_resp.strip():
                        core.query_db("INSERT INTO public.responsables_catalogo (nombre) VALUES (?) ON CONFLICT (nombre) DO NOTHING", (n_resp.strip(),))
                        core.registrar_log("Configuración", "Catálogo", f"Añadido responsable: {n_resp.strip()}")
                        st.toast("✅ Responsable añadido.")
                        st.rerun()
        with c_r2:
            if not df_resp.empty:
                r_del = st.selectbox("Eliminar Responsable:", df_resp["nombre"].tolist(), key="sel_resp_del")
                if st.button("🗑️ Eliminar Responsable"):
                    core.query_db("DELETE FROM public.responsables_catalogo WHERE nombre=?", (r_del,))
                    core.registrar_log("Configuración", "Catálogo", f"Eliminado responsable: {r_del}")
                    st.toast("🗑️ Responsable eliminado.")
                    st.rerun()

    with col_der:
        st.markdown("#### 💼 Fondos de Tesorería y Saldos")
        df_f = core.read_db("SELECT id, nombre FROM public.fondos_catalogo ORDER BY id ASC")
        df_movs_f = core.read_db("SELECT fondo, tipo, monto FROM public.movimientos")
        
        saldos_f = {}
        for fn in df_f["nombre"].tolist():
            i = float(df_movs_f[(df_movs_f["fondo"] == fn) & (df_movs_f["tipo"] == "Ingreso")]["monto"].sum()) if not df_movs_f.empty else 0.0
            e = float(df_movs_f[(df_movs_f["fondo"] == fn) & (df_movs_f["tipo"] == "Egreso")]["monto"].sum()) if not df_movs_f.empty else 0.0
            saldos_f[fn] = i - e
            
        df_f["Saldo Actual (S/.)"] = df_f["nombre"].map(saldos_f).fillna(0.0)
        st.dataframe(
            df_f.rename(columns={"nombre": "Fondo"}).style.format({"Saldo Actual (S/.)": "S/. {:,.2f}"}), 
            use_container_width=True, 
            hide_index=True
        )

        c_f1, c_f2 = st.columns(2)
        with c_f1:
            with st.form("form_add_fnd_mini"):
                n_fnd = st.text_input("Nuevo Fondo:")
                if st.form_submit_button("➕ Añadir Fondo"):
                    if n_fnd.strip():
                        core.query_db("INSERT INTO public.fondos_catalogo (nombre) VALUES (?) ON CONFLICT (nombre) DO NOTHING", (n_fnd.strip(),))
                        core.registrar_log("Configuración", "Catálogo", f"Añadido fondo: {n_fnd.strip()}")
                        st.toast("✅ Fondo creado.")
                        st.rerun()
        with c_f2:
            f_del_disp = [f for f in df_f["nombre"].tolist() if f != "General"]
            if f_del_disp:
                f_del = st.selectbox("Eliminar Fondo:", f_del_disp, key="sel_fnd_del")
                df_cant = core.read_db("SELECT COUNT(*) as t FROM public.movimientos WHERE fondo=?", (f_del,))
                cant_m = df_cant.iloc[0]["t"] if not df_cant.empty else 0
                if st.button("🗑️ Eliminar Fondo"):
                    if cant_m > 0:
                        st.error(
