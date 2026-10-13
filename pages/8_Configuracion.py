import streamlit as st
import core
import os
import io
import zipfile
import pandas as pd
from datetime import date

st.set_page_config(page_title="Configuración General", page_icon="⚙️", layout="wide")
core.aplicar_estilos_base()

# Asegurar tablas e inicialización de columnas necesarias (Sintaxis PostgreSQL)
try:
    with core.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS config_iglesia (
                    clave TEXT PRIMARY KEY,
                    valor TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cierres_mensuales (
                    periodo TEXT PRIMARY KEY,
                    fecha_cierre TEXT,
                    estado TEXT DEFAULT 'Abierto'
                )
            """)
            
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='cierres_mensuales'")
            cols_exist = {row['column_name'] for row in cur.fetchall()}
            
            if "saldo_cierre" not in cols_exist:
                try:
                    cur.execute("SAVEPOINT sp_saldo")
                    cur.execute("ALTER TABLE cierres_mensuales ADD COLUMN saldo_cierre REAL DEFAULT 0.0")
                    cur.execute("RELEASE SAVEPOINT sp_saldo")
                except Exception:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_saldo")
            if "usuario" not in cols_exist:
                try:
                    cur.execute("SAVEPOINT sp_user")
                    cur.execute("ALTER TABLE cierres_mensuales ADD COLUMN usuario TEXT DEFAULT 'Tesorería General'")
                    cur.execute("RELEASE SAVEPOINT sp_user")
                except Exception:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_user")
        conn.commit()
except Exception:
    pass

def get_config(clave, default=""):
    df = core.read_db("SELECT valor FROM config_iglesia WHERE clave=?", (clave,))
    return df.iloc[0]["valor"] if not df.empty else default

def set_config(clave, valor):
    core.query_db("""
        INSERT INTO config_iglesia (clave, valor) VALUES (?, ?) 
        ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor
    """, (clave, str(valor).strip()))

def crear_backup_integral():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for carp in ["fotos_miembros", "comprobantes"]:
            if os.path.exists(carp):
                for r, _, files in os.walk(carp):
                    for f in files:
                        p = os.path.join(r, f)
                        z.write(p, arcname=p)
    return buf.getvalue()

st.subheader("⚙️ Configuración y Administración del Sistema")

tabs = st.tabs([
    "🏛️ Parámetros y Catálogos",
    "🔒 Cierres de Mes y Auditoría",
    "🛡️ Respaldo y Mantenimiento"
])

# ==============================================================================
# PESTAÑA 1: PARÁMETROS Y CATÁLOGOS
# ==============================================================================
with tabs[0]:
    col_izq, col_der = st.columns(2)

    with col_izq:
        st.markdown("#### 🏛️ Datos de la Iglesia y Firmas")
        with st.form("form_identidad"):
            c_a, c_b = st.columns(2)
            with c_a:
                nom_igl = st.text_input("Nombre Iglesia:", value=get_config("nombre_iglesia", "IGLESIA EVANGÉLICA NAZARETH"))
                den_igl = st.text_input("Denominación:", value=get_config("denominacion", "ASAMBLEAS DE DIOS DEL PERÚ"))
                ruc_igl = st.text_input("RUC / Reg. Religioso:", value=get_config("ruc_registro", "20549182910"))
                pas_igl = st.text_input("Pastor(a) Principal:", value=get_config("pastor_principal", "Pastor Titular"))
            with c_b:
                tes_igl = st.text_input("Tesorero(a) General:", value=get_config("tesorero_general", "Tesorero General"))
                dir_igl = st.text_input("Dirección Templo:", value=get_config("direccion", "Jr. Trujillo 450"))
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
                core.query_db("INSERT INTO auditoria (fecha_hora, modulo, accion, descripcion) VALUES (?, 'Config_Tesorero', 'Actualizar', ?)", (str(date.today()), tes_igl.strip()))
                core.registrar_log("Configuración", "Identidad", "Actualizados datos institucionales.")
                st.toast("✅ Datos guardados.")
                st.rerun()

        st.markdown("#### 👤 Catálogo de Responsables / Firmantes")
        df_resp = core.read_db("SELECT id, nombre FROM responsables_catalogo ORDER BY nombre ASC")
        st.dataframe(df_resp.rename(columns={"nombre": "Autoridades Registradas"}), use_container_width=True, hide_index=True)

        c_r1, c_r2 = st.columns(2)
        with c_r1:
            with st.form("form_add_resp_mini"):
                n_resp = st.text_input("Añadir Responsable:")
                if st.form_submit_button("➕ Añadir"):
                    if n_resp.strip():
                        core.query_db("INSERT INTO responsables_catalogo (nombre) VALUES (?) ON CONFLICT (nombre) DO NOTHING", (n_resp.strip(),))
                        st.toast("✅ Responsable añadido.")
                        st.rerun()
        with c_r2:
            if not df_resp.empty:
                r_del = st.selectbox("Eliminar:", df_resp["nombre"].tolist(), key="sel_resp_del")
                if st.button("🗑️ Eliminar Responsable"):
                    core.query_db("DELETE FROM responsables_catalogo WHERE nombre=?", (r_del,))
                    st.toast("🗑️ Eliminado.")
                    st.rerun()

    with col_der:
        st.markdown("#### 💼 Fondos de Tesorería y Saldos")
        df_f = core.read_db("SELECT id, nombre FROM fondos_catalogo ORDER BY id ASC")
        df_movs_f = core.read_db("SELECT fondo, tipo, monto FROM movimientos")
        saldos_f = {}
        for fn in df_f["nombre"].tolist():
            i = df_movs_f[(df_movs_f["fondo"] == fn) & (df_movs_f["tipo"] == "Ingreso")]["monto"].sum()
            e = df_movs_f[(df_movs_f["fondo"] == fn) & (df_movs_f["tipo"] == "Egreso")]["monto"].sum()
            saldos_f[fn] = i - e
        df_f["Saldo Actual (S/.)"] = df_f["nombre"].map(saldos_f).fillna(0.0)

        st.dataframe(df_f.rename(columns={"nombre": "Fondo"}).style.format({"Saldo Actual (S/.)": "S/. {:,.2f}"}), use_container_width=True, hide_index=True)

        c_f1, c_f2 = st.columns(2)
        with c_f1:
            with st.form("form_add_fnd_mini"):
                n_fnd = st.text_input("Nuevo Fondo:")
                if st.form_submit_button("➕ Añadir"):
                    if n_fnd.strip():
                        core.query_db("INSERT INTO fondos_catalogo (nombre) VALUES (?) ON CONFLICT (nombre) DO NOTHING", (n_fnd.strip(),))
                        st.toast("✅ Fondo creado.")
                        st.rerun()
        with c_f2:
            f_del_disp = [f for f in df_f["nombre"].tolist() if f != "General"]
            if f_del_disp:
                f_del = st.selectbox("Eliminar:", f_del_disp, key="sel_fnd_del")
                df_cant = core.read_db("SELECT COUNT(*) as t FROM movimientos WHERE fondo=?", (f_del,))
                cant_m = df_cant.iloc[0]["t"] if not df_cant.empty else 0
                if st.button("🗑️ Eliminar Fondo"):
                    if cant_m > 0:
                        st.error(f"No se puede borrar: tiene {cant_m} movimientos.")
                    else:
                        core.query_db("DELETE FROM fondos_catalogo WHERE nombre=?", (f_del,))
                        st.toast("🗑️ Fondo eliminado.")
                        st.rerun()

        st.markdown("#### 📑 Categorías y Rubros de Gasto/Ingreso")
        df_rub = core.read_db("SELECT id, tipo, categoria, subcategoria FROM rubros_catalogo ORDER BY tipo ASC, categoria ASC")
        st.dataframe(df_rub.rename(columns={"categoria": "Categoría", "subcategoria": "Rubro"}), use_container_width=True, hide_index=True)

        with st.form("form_add_rub_mini"):
            cr1, cr2, cr3 = st.columns(3)
            with cr1: t_rub = st.selectbox("Tipo:", ["Egreso", "Ingreso"])
            with cr2: c_rub = st.text_input("Categoría:", placeholder="Ej. Servicios")
            with cr3: s_rub = st.text_input("Rubro:", placeholder="Ej. Internet")
            if st.form_submit_button("➕ Añadir Rubro"):
                if c_rub.strip() and s_rub.strip():
                    core.query_db("INSERT INTO rubros_catalogo (tipo, categoria, subcategoria) VALUES (?, ?, ?)", (t_rub, c_rub.strip(), s_rub.strip()))
                    st.toast("✅ Rubro agregado.")
                    st.rerun()

# ==============================================================================
# PESTAÑA 2: CIERRES DE MES Y AUDITORÍA
# ==============================================================================
with tabs[1]:
    col_cierre, col_aud = st.columns([1, 1])

    with col_cierre:
        st.markdown("#### 🔒 Cierres Mensuales y Arqueo")
        anio_c, mes_c, num_m, _ = core.selector_periodo("cierre_master")
        per_str = f"{anio_c}-{num_m:02d}"

        # Cambio strftime a SUBSTRING para compatibilidad con PostgreSQL
        df_m_per = core.read_db("SELECT tipo, monto FROM movimientos WHERE SUBSTRING(fecha FROM 1 FOR 7) = ?", (per_str,))
        ing_p = df_m_per[df_m_per["tipo"] == "Ingreso"]["monto"].sum()
        egr_p = df_m_per[df_m_per["tipo"] == "Egreso"]["monto"].sum()
        sal_p = ing_p - egr_p

        cierre_act = core.read_db("SELECT * FROM cierres_mensuales WHERE periodo=?", (per_str,))
        esta_cerrado = not cierre_act.empty and cierre_act.iloc[0]["estado"] == "Cerrado"

        m1, m2, m3 = st.columns(3)
        m1.metric("Ingresos", f"S/. {ing_p:,.2f}")
        m2.metric("Egresos", f"S/. {egr_p:,.2f}")
        m3.metric("Saldo Neto", f"S/. {sal_p:,.2f}", delta="Superávit" if sal_p >= 0 else "Déficit")

        if not esta_cerrado:
            st.info(f"Estado: **🔓 ABIERTO** ({mes_c} {anio_c})")
            if st.button("🔒 Ejecutar Cierre y Congelar Mes", type="primary"):
                core.query_db("""
                    INSERT INTO cierres_mensuales (periodo, fecha_cierre, estado, saldo_cierre, usuario) 
                    VALUES (?, ?, 'Cerrado', ?, 'Tesorería General') 
                    ON CONFLICT (periodo) DO UPDATE SET 
                        fecha_cierre = EXCLUDED.fecha_cierre, 
                        estado = 'Cerrado', 
                        saldo_cierre = EXCLUDED.saldo_cierre, 
                        usuario = EXCLUDED.usuario
                """, (per_str, str(date.today()), sal_p))
                core.registrar_log("Cierres", "Bloqueo", f"Cierre mensual {per_str} por S/. {sal_p:,.2f}")
                st.toast("✅ Mes cerrado formalmente.")
                st.rerun()
        else:
            f_c = cierre_act.iloc[0].get("fecha_cierre", str(date.today()))
            st.success(f"Estado: **🔒 CERRADO** el {f_c}")
            with st.expander("Reapertura extraordinaria"):
                mot = st.text_input("Motivo de reapertura:")
                if st.button("Confirmar Reapertura"):
                    if mot.strip():
                        core.query_db("UPDATE cierres_mensuales SET estado='Abierto' WHERE periodo=?", (per_str,))
                        core.registrar_log("Cierres", "Reapertura", f"Reabierto {per_str}: {mot.strip()}")
                        st.toast("🔓 Mes reabierto.")
                        st.rerun()
                    else:
                        st.error("Ingrese el motivo.")

    with col_aud:
        st.markdown("#### 🛡️ Registro de Auditoría")
        df_aud = core.read_db("SELECT * FROM auditoria ORDER BY id DESC")
        if df_aud.empty:
            st.info("Sin registros de auditoría.")
        else:
            c_au1, c_au2 = st.columns(2)
            with c_au1:
                mods = ["Todos"] + sorted(list(df_aud["modulo"].dropna().unique()))
                f_mod = st.selectbox("Filtrar módulo:", mods)
            with c_au2:
                b_aud = st.text_input("Buscar en detalle:")

            df_aud_f = df_aud.copy()
            if f_mod != "Todos":
                df_aud_f = df_aud_f[df_aud_f["modulo"] == f_mod]
            if b_aud.strip():
                df_aud_f = df_aud_f[df_aud_f["descripcion"].str.contains(b_aud.strip(), case=False, na=False)]

            st.dataframe(df_aud_f[["fecha_hora", "modulo", "accion", "descripcion"]].rename(columns={"fecha_hora": "Fecha/Hora", "modulo": "Módulo", "accion": "Acción", "descripcion": "Detalle"}), use_container_width=True, hide_index=True)

            out_aud = io.BytesIO()
            with pd.ExcelWriter(out_aud, engine='openpyxl') as w:
                df_aud_f.to_excel(w, index=False, sheet_name="Auditoria")
            st.download_button("📊 Exportar Auditoría a Excel", out_aud.getvalue(), f"Auditoria_{date.today()}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ==============================================================================
# PESTAÑA 3: RESPALDO Y MANTENIMIENTO
# ==============================================================================
with tabs[2]:
    c_b1, c_b2 = st.columns(2)

    with c_b1:
        st.markdown("#### 📦 Copias de Seguridad de Archivos (.ZIP)")
        st.caption("Empaqueta todos los comprobantes y fotos guardados en las carpetas de tu servidor en la nube.")
        bk_bytes = crear_backup_integral()
        st.download_button(
            label="📦 Descargar Backup de Archivos (.ZIP)",
            data=bk_bytes,
            file_name=f"Archivos_Nazareth_{date.today().strftime('%Y%m%d')}.zip",
            mime="application/zip",
            type="primary"
        )

        st.markdown("---")
        st.markdown("##### 📤 Restaurar Backup (.ZIP)")
        up_zip = st.file_uploader("Subir archivo ZIP para restaurar fotos y comprobantes:", type=["zip"])
        if up_zip is not None:
            if st.button("Confirmar Restauración de Archivos", type="secondary"):
                try:
                    with zipfile.ZipFile(up_zip, "r") as z:
                        z.extractall(".")
                    core.registrar_log("Configuración", "Restauración", "Copia de archivos restaurada.")
                    st.success("✅ Archivos restaurados.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al restaurar: {e}")

    with c_b2:
        st.markdown("#### ⚠️ Formateo de Cero / Reset de Fábrica")
        st.caption("Vacía por completo todas las tablas de tu base de datos en Supabase (Ideal para limpiar datos de prueba antes de entregar el sistema).")
        st.warning("Borrará permanentemente movimientos, diezmos, actividades, compromisos y miembros en la nube.")

        chk_fmt = st.checkbox("Confirmo el vaciado definitivo del sistema en la Nube.")
        txt_fmt = st.text_input("Escribe 'REINICIAR' para habilitar el formateo:", placeholder="REINICIAR")

        if st.button("💥 Formatear Sistema de Cero", type="primary", disabled=not chk_fmt):
            if txt_fmt.strip().upper() != "REINICIAR":
                st.error("Escribe exactamente 'REINICIAR'.")
            else:
                try:
                    tablas = ["movimientos", "diezmos", "actividad_movimientos", "actividades", "pagos_programados", "cierres_mensuales", "miembros"]
                    with core.get_db() as conn:
                        with conn.cursor() as cur:
                            for tbl in tablas:
                                try:
                                    cur.execute(f"TRUNCATE TABLE {tbl} RESTART IDENTITY CASCADE")
                                except Exception:
                                    pass
                        conn.commit()

                    for carp in ["fotos_miembros", "comprobantes"]:
                        if os.path.exists(carp):
                            for arch in os.listdir(carp):
                                p = os.path.join(carp, arch)
                                if os.path.isfile(p):
                                    os.remove(p)

                    core.inicializar_bd()
                    core.registrar_log("Configuración", "RESET", "Sistema formateado de cero en la nube.")
                    st.success("🎉 Sistema reiniciado de fábrica con éxito. La base de datos en Supabase está vacía.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al reiniciar: {e}")
