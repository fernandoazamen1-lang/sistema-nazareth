import streamlit as st
import core
import os
import io
import zipfile
import pandas as pd
from datetime import date

st.set_page_config(
    page_title="Configuración General", 
    page_icon="⚙️", 
    layout="wide"
)

# 1. Autenticación y estilos base limpios
core.requerir_login()
core.aplicar_estilos_base()

# 2. Asegurar estructura de tablas en esquema public (PostgreSQL)
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
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO public.fondos_catalogo (nombre) VALUES ('General') ON CONFLICT (nombre) DO NOTHING;
            """)
        conn.commit()
except Exception:
    pass

# Funciones de configuración clave-valor
def get_config(clave, default=""):
    df = core.read_db("SELECT valor FROM public.config_iglesia WHERE clave=?", (clave,))
    return df.iloc[0]["valor"] if not df.empty else default

def set_config(clave, valor):
    core.query_db("""
        INSERT INTO public.config_iglesia (clave, valor) VALUES (?, ?) 
        ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor
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

# Encabezado estándar
st.subheader("⚙️ Configuración y Administración del Sistema")

# Navegación estética y nativa por puntos (st.radio)
seccion_cfg = st.radio(
    "Sección de Configuración:",
    [
        "🏛️ Parámetros y Catálogos",
        "🔒 Cierres de Mes y Auditoría",
        "🛡️ Respaldo y Base de Datos",
        "👥 Usuarios y Permisos"
    ],
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
                
                # Actualizar tesorero para vouchers y reportes
                core.query_db(
                    "INSERT INTO public.auditoria (fecha_hora, modulo, accion, descripcion) VALUES (?, 'Config_Tesorero', 'Actualizar', ?)", 
                    (str(date.today()), tes_igl.strip())
                )
                core.registrar_log("Configuración", "Identidad", "Actualizados datos institucionales y de firmas.")
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
                        st.error(f"No se puede borrar: tiene {cant_m} movimientos asociados.")
                    else:
                        core.query_db("DELETE FROM public.fondos_catalogo WHERE nombre=?", (f_del,))
                        core.registrar_log("Configuración", "Catálogo", f"Eliminado fondo: {f_del}")
                        st.toast("🗑️ Fondo eliminado.")
                        st.rerun()

        st.markdown("#### 📑 Categorías y Rubros de Ingreso / Egreso")
        col_filtro_rub, _ = st.columns([2, 2])
        with col_filtro_rub:
            filtro_t_rub = st.selectbox("Ver Rubros por Tipo:", ["Todos", "Egreso", "Ingreso"])

        sql_rub = "SELECT id, tipo, categoria, subcategoria FROM public.rubros_catalogo"
        if filtro_t_rub != "Todos":
            sql_rub += f" WHERE tipo = '{filtro_t_rub}'"
        sql_rub += " ORDER BY tipo ASC, categoria ASC, subcategoria ASC"
        df_rub = core.read_db(sql_rub)

        st.dataframe(
            df_rub.rename(columns={"tipo": "Tipo", "categoria": "Categoría", "subcategoria": "Rubro"}), 
            use_container_width=True, 
            hide_index=True
        )

        with st.expander("➕ Añadir o Eliminar Rubro", expanded=False):
            c_r_add, c_r_del = st.columns(2)
            with c_r_add:
                with st.form("form_add_rub_mini"):
                    st.caption("Añadir nuevo rubro:")
                    t_rub = st.selectbox("Tipo:", ["Egreso", "Ingreso"])
                    c_rub = st.text_input("Categoría:", placeholder="Ej. Servicios")
                    s_rub = st.text_input("Rubro / Subcategoría:", placeholder="Ej. Internet")
                    if st.form_submit_button("➕ Añadir Rubro"):
                        if c_rub.strip() and s_rub.strip():
                            core.query_db("INSERT INTO public.rubros_catalogo (tipo, categoria, subcategoria) VALUES (?, ?, ?)", (t_rub, c_rub.strip(), s_rub.strip()))
                            core.registrar_log("Configuración", "Catálogo", f"Añadido rubro: {t_rub} - {c_rub.strip()} / {s_rub.strip()}")
                            st.toast("✅ Rubro agregado.")
                            st.rerun()
            with c_r_del:
                if not df_rub.empty:
                    st.caption("Eliminar rubro existente:")
                    opciones_rub_dict = {f"[{r['tipo']}] {r['categoria']} -> {r['subcategoria']}": r["id"] for _, r in df_rub.iterrows()}
                    rub_sel = st.selectbox("Seleccione rubro a eliminar:", list(opciones_rub_dict.keys()))
                    if st.button("🗑️ Eliminar Rubro Seleccionado"):
                        id_r_del = opciones_rub_dict[rub_sel]
                        core.query_db("DELETE FROM public.rubros_catalogo WHERE id=?", (id_r_del,))
                        core.registrar_log("Configuración", "Catálogo", f"Eliminado rubro: {rub_sel}")
                        st.toast("🗑️ Rubro eliminado.")
                        st.rerun()

# ==============================================================================
# 2. CIERRES DE MES Y AUDITORÍA
# ==============================================================================
elif seccion_cfg == "🔒 Cierres de Mes y Auditoría":
    col_cierre, col_aud = st.columns([1, 1])

    with col_cierre:
        st.markdown("#### 🔒 Cierres Mensuales y Bloqueo de Periodos")
        anio_c, mes_c, num_m, _ = core.selector_periodo("cierre_master")
        per_str = f"{anio_c}-{num_m:02d}"

        df_m_per = core.read_db("SELECT tipo, monto FROM public.movimientos WHERE SUBSTRING(fecha::text FROM 1 FOR 7) = ?", (per_str,))
        ing_p = float(df_m_per[df_m_per["tipo"] == "Ingreso"]["monto"].sum()) if not df_m_per.empty else 0.0
        egr_p = float(df_m_per[df_m_per["tipo"] == "Egreso"]["monto"].sum()) if not df_m_per.empty else 0.0
        sal_p = ing_p - egr_p

        cierre_act = core.read_db("SELECT * FROM public.cierres_mensuales WHERE periodo=?", (per_str,))
        esta_cerrado = not cierre_act.empty and cierre_act.iloc[0]["estado"] == "Cerrado"

        m1, m2, m3 = st.columns(3)
        m1.metric("Ingresos", f"S/. {ing_p:,.2f}")
        m2.metric("Egresos", f"S/. {egr_p:,.2f}")
        m3.metric("Saldo Neto", f"S/. {sal_p:,.2f}", delta="Superávit" if sal_p >= 0 else "Déficit")

        if not esta_cerrado:
            st.info(f"Estado del Periodo: **🔓 ABIERTO** ({mes_c} {anio_c})")
            st.caption("Al cerrar el periodo se bloquean automáticamente registros, modificaciones y eliminaciones de movimientos y diezmos en este mes.")
            if st.button("🔒 Ejecutar Cierre y Congelar Mes", type="primary"):
                user_ejecutor = st.session_state.get("usuario_actual", {}).get("nombre", "Tesorería General")
                core.query_db("""
                    INSERT INTO public.cierres_mensuales (periodo, fecha_cierre, estado, saldo_cierre, usuario) 
                    VALUES (?, ?, 'Cerrado', ?, ?) 
                    ON CONFLICT (periodo) DO UPDATE SET 
                        fecha_cierre = EXCLUDED.fecha_cierre, 
                        estado = 'Cerrado', 
                        saldo_cierre = EXCLUDED.saldo_cierre, 
                        usuario = EXCLUDED.usuario
                """, (per_str, str(date.today()), sal_p, user_ejecutor))
                core.registrar_log("Cierres", "Bloqueo", f"Cierre mensual {per_str} por S/. {sal_p:,.2f}")
                st.toast("✅ Mes cerrado y congelado formalmente.")
                st.rerun()
        else:
            f_c = cierre_act.iloc[0].get("fecha_cierre", str(date.today()))
            u_c = cierre_act.iloc[0].get("usuario", "Tesorería")
            st.success(f"Estado del Periodo: **🔒 CERRADO** el {f_c} por {u_c}")
            with st.expander("🔓 Reapertura Extraordinaria del Periodo"):
                mot = st.text_input("Motivo fundamentado para reabrir el mes:")
                if st.button("Confirmar Reapertura", type="secondary"):
                    if mot.strip():
                        core.query_db("UPDATE public.cierres_mensuales SET estado='Abierto' WHERE periodo=?", (per_str,))
                        core.registrar_log("Cierres", "Reapertura", f"Reabierto {per_str}: {mot.strip()}")
                        st.toast("🔓 Periodo reabierto.")
                        st.rerun()
                    else:
                        st.error("Debe ingresar obligatoriamente un motivo para reabrir.")

    with col_aud:
        st.markdown("#### 🛡️ Registro de Auditoría y Trazabilidad")
        df_aud = core.read_db("SELECT * FROM public.auditoria ORDER BY id DESC LIMIT 300")
        if df_aud.empty:
            st.info("Sin registros de auditoría por el momento.")
        else:
            c_au1, c_au2 = st.columns(2)
            with c_au1:
                mods = ["Todos"] + sorted(list(df_aud["modulo"].dropna().unique()))
                f_mod = st.selectbox("Filtrar por Módulo:", mods)
            with c_au2:
                b_aud = st.text_input("Buscar en el Detalle:")

            df_aud_f = df_aud.copy()
            if f_mod != "Todos":
                df_aud_f = df_aud_f[df_aud_f["modulo"] == f_mod]
            if b_aud.strip():
                df_aud_f = df_aud_f[df_aud_f["descripcion"].str.contains(b_aud.strip(), case=False, na=False)]

            st.dataframe(
                df_aud_f[["fecha_hora", "modulo", "accion", "descripcion"]].rename(columns={
                    "fecha_hora": "Fecha / Hora", "modulo": "Módulo", "accion": "Acción", "descripcion": "Detalle de Operación"
                }), 
                use_container_width=True, 
                hide_index=True
            )

            out_aud = io.BytesIO()
            with pd.ExcelWriter(out_aud, engine='openpyxl') as w:
                df_aud_f.to_excel(w, index=False, sheet_name="Auditoria")
            st.download_button(
                label="📊 Exportar Auditoría a Excel (.xlsx)", 
                data=out_aud.getvalue(), 
                file_name=f"Auditoria_Nazareth_{date.today()}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ==============================================================================
# 3. RESPALDO Y BASE DE DATOS
# ==============================================================================
elif seccion_cfg == "🛡️ Respaldo y Base de Datos":
    c_b1, c_b2 = st.columns(2)

    with c_b1:
        st.markdown("#### 📦 Copia de Seguridad Integral a Excel (.xlsx)")
        st.caption("Descarga todas las tablas de tu base de datos en un único archivo Excel con pestañas independientes (Miembros, Diezmos, Movimientos, Fondos, Rubros, Cierres y Auditoría).")
        
        backup_excel_bytes = generar_backup_completo_excel()
        st.download_button(
            label="📊 Descargar Backup Completo de Base de Datos (.xlsx)",
            data=backup_excel_bytes,
            file_name=f"Backup_Total_Nazareth_{date.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )

        st.markdown("---")
        st.markdown("#### 📁 Copia de Archivos en la Nube (.ZIP)")
        st.caption("Empaqueta fotos de miembros y comprobantes almacenados en el servidor.")
        bk_bytes = crear_backup_archivos_zip()
        st.download_button(
            label="📦 Descargar Archivos Locales (.ZIP)",
            data=bk_bytes,
            file_name=f"Archivos_Nazareth_{date.today().strftime('%Y%m%d')}.zip",
            mime="application/zip",
            use_container_width=True
        )

        with st.expander("📤 Restaurar Archivos desde ZIP"):
            up_zip = st.file_uploader("Subir archivo ZIP para restaurar fotos y comprobantes:", type=["zip"])
            if up_zip is not None:
                if st.button("Confirmar Restauración de Archivos"):
                    try:
                        with zipfile.ZipFile(up_zip, "r") as z:
                            z.extractall(".")
                        core.registrar_log("Configuración", "Restauración", "Copia de archivos restaurada.")
                        st.success("✅ Archivos restaurados exitosamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al restaurar: {e}")

    with c_b2:
        st.markdown("#### ⚠️ Formateo de Cero / Reset de Fábrica")
        st.caption("Vacía por completo los datos de movimientos, diezmos y registros en Supabase, conservando intactos tus usuarios y configuración institucional.")
        st.error("Esta acción eliminará de forma irreversible movimientos, diezmos, actividades y compromisos en la base de datos.")

        chk_fmt = st.checkbox("Comprendo el riesgo y confirmo el vaciado definitivo del sistema.")
        txt_fmt = st.text_input("Escribe 'REINICIAR' en mayúsculas para desbloquear:", placeholder="REINICIAR")

        if st.button("💥 Formatear Sistema de Cero", type="primary", disabled=not chk_fmt):
            if txt_fmt.strip().upper() != "REINICIAR":
                st.error("Debes escribir exactamente la palabra 'REINICIAR'.")
            else:
                try:
                    tablas = [
                        "movimientos", "diezmos", "actividad_movimientos", 
                        "actividades", "pagos_programados", "cierres_mensuales", "miembros"
                    ]
                    with core.get_db() as conn:
                        with conn.cursor() as cur:
                            for tbl in tablas:
                                try:
                                    cur.execute(f"TRUNCATE TABLE public.{tbl} RESTART IDENTITY CASCADE;")
                                except Exception:
                                    pass
                        conn.commit()

                    core.registrar_log("Configuración", "RESET", "Sistema formateado de fábrica.")
                    st.success("🎉 Base de datos operativa reiniciada de fábrica con éxito.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error durante el reinicio: {e}")

# ==============================================================================
# 4. USUARIOS Y PERMISOS
# ==============================================================================
elif seccion_cfg == "👥 Usuarios y Permisos":
    rol_actual = st.session_state.get("usuario_actual", {}).get("rol", "")

    if rol_actual == "Administrador":
        st.markdown("#### 👥 Administración de Usuarios y Accesos")
        st.caption("Gestión exclusiva de credenciales y roles para el personal del sistema.")

        with st.expander("➕ Registrar Nuevo Usuario", expanded=False):
            with st.form("form_nuevo_usuario"):
                col1, col2 = st.columns(2)
                with col1:
                    nuevo_u = st.text_input("Usuario (ej: tesoreria, pastor):", placeholder="Sin espacios ni mayúsculas").strip().lower()
                    nuevo_nom = st.text_input("Nombre Completo (ej: Juan Pérez):")
                with col2:
                    nuevo_rol = st.selectbox("Rol en el Sistema:", ["Tesorero General", "Pastor Principal", "Secretaría", "Administrador"])
                    nuevo_pass = st.text_input("Contraseña Temporal:", type="password")

                btn_guardar_u = st.form_submit_button("Guardar Usuario", type="primary")

                if btn_guardar_u:
                    if not nuevo_u or not nuevo_nom or not nuevo_pass:
                        st.warning("⚠️ Debes completar todos los campos.")
                    else:
                        pass_hash = core.encriptar_clave(nuevo_pass)
                        try:
                            core.query_db("""
                                INSERT INTO public.usuarios_sistema (usuario, password_hash, nombre, rol, activo)
                                VALUES (%s, %s, %s, %s, TRUE)
                            """, (nuevo_u, pass_hash, nuevo_nom, nuevo_rol))
                            core.registrar_log("Usuarios", "Crear", f"Usuario '{nuevo_u}' registrado con rol '{nuevo_rol}'.")
                            st.success(f"✅ Usuario '{nuevo_u}' registrado exitosamente.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al registrar usuario (verifique si el usuario ya existe): {e}")

        st.markdown("##### Cuentas Registradas en el Sistema")
        try:
            df_usuarios = core.read_db("SELECT id, usuario, nombre, rol, activo, fecha_creacion FROM public.usuarios_sistema ORDER BY id ASC")

            if not df_usuarios.empty:
                st.dataframe(
                    df_usuarios.rename(columns={
                        "id": "ID", "usuario": "Usuario", "nombre": "Nombre",
                        "rol": "Rol", "activo": "Estado Activo", "fecha_creacion": "Fecha Creación"
                    }), 
                    use_container_width=True, 
                    hide_index=True
                )

                st.markdown("---")
                st.markdown("##### ⚙️ Gestionar Credenciales de Usuario Existente")
                
                usuarios_modificables = {
                    f"{r['usuario']} ({r['nombre']} - {r['rol']})": r["id"] 
                    for _, r in df_usuarios.iterrows()
                }
                
                u_sel_label = st.selectbox("Seleccione cuenta a modificar:", list(usuarios_modificables.keys()))
                id_u_sel = usuarios_modificables[u_sel_label]
                row_user = df_usuarios[df_usuarios["id"] == id_u_sel].iloc[0]

                c_u1, c_u2 = st.columns(2)
                with c_u1:
                    with st.form("form_cambiar_pass"):
                        st.caption(f"Actualizar clave para: **{row_user['usuario']}**")
                        nueva_clave = st.text_input("Nueva Contraseña:", type="password")
                        if st.form_submit_button("🔑 Actualizar Contraseña"):
                            if nueva_clave.strip():
                                n_hash = core.encriptar_clave(nueva_clave)
                                core.query_db("UPDATE public.usuarios_sistema SET password_hash=%s WHERE id=%s", (n_hash, id_u_sel))
                                core.registrar_log("Usuarios", "Seguridad", f"Actualizada contraseña del usuario {row_user['usuario']}")
                                st.success("✅ Contraseña actualizada.")
                            else:
                                st.warning("La contraseña no puede estar vacía.")

                with c_u2:
                    st.caption(f"Estado de la cuenta: **{'Activo' if row_user['activo'] else 'Inactivo'}**")
                    if row_user["usuario"] == "admin":
                        st.info("ℹ️ La cuenta de Administrador General 'admin' no puede desactivarse ni eliminarse.")
                    else:
                        nuevo_estado = not bool(row_user["activo"])
                        btn_txt = "🔴 Desactivar Acceso" if row_user["activo"] else "🟢 Habilitar Acceso"
                        if st.button(btn_txt):
                            core.query_db("UPDATE public.usuarios_sistema SET activo=%s WHERE id=%s", (nuevo_estado, id_u_sel))
                            core.registrar_log("Usuarios", "Estado", f"Cambiado estado de {row_user['usuario']} a {nuevo_estado}")
                            st.toast("✅ Estado de cuenta actualizado.")
                            st.rerun()

                        if st.button("🗑️ Eliminar Usuario Definitivamente", type="secondary"):
                            core.query_db("DELETE FROM public.usuarios_sistema WHERE id=%s", (id_u_sel,))
                            core.registrar_log("Usuarios", "Eliminación", f"Eliminado usuario {row_user['usuario']}")
                            st.toast("🗑️ Usuario eliminado.")
                            st.rerun()

        except Exception as e:
            st.error(f"Error al gestionar usuarios: {e}")

    else:
        st.info("ℹ️ **Acceso Restringido**: La creación y administración de usuarios está reservada exclusivamente para el Administrador General.")
