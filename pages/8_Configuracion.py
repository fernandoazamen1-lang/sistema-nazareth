import streamlit as st
import core
import os
import io
import zipfile
import calendar
import pandas as pd
from datetime import date

st.set_page_config(
    page_title="Configuración General", 
    page_icon="⚙️", 
    layout="wide"
)

# 1. Seguridad: Verificar que el usuario tenga acceso a Configuración
core.verificar_acceso_pagina("Configuración")
core.aplicar_estilos_base()

# LISTA COMPLETA Y EXACTA DE TODOS TUS MÓDULOS
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

# 2. Estructura de tablas y permisos en PostgreSQL
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
# 2. CIERRES DE MES CON ASIENTOS DE APERTURA AUTOMÁTICOS
# ==============================================================================
elif seccion_cfg == "🔒 Cierres de Mes y Auditoría":
    col_cierre, col_aud = st.columns([1, 1])

    with col_cierre:
        st.markdown("#### 🔒 Cierres Mensuales y Apertura de Siguiente Mes")
        anio_c, mes_c, num_m, _ = core.selector_periodo("cierre_master")
        per_str = f"{anio_c}-{num_m:02d}"
        u_dia = calendar.monthrange(anio_c, num_m)[1]
        f_fin_per = f"{anio_c}-{num_m:02d}-{u_dia:02d}"

        if num_m == 12:
            anio_sig = anio_c + 1
            num_m_sig = 1
        else:
            anio_sig = anio_c
            num_m_sig = num_m + 1

        sig_per = f"{anio_sig}-{num_m_sig:02d}"
        fecha_apertura_sig = f"{anio_sig}-{num_m_sig:02d}-01"
        nombre_mes_sig = core.MESES[num_m_sig - 1]
        c_efe_sig = f"ASIENTO-APERTURA-EFE-{sig_per}"
        c_ban_sig = f"ASIENTO-APERTURA-BAN-{sig_per}"

        df_m_per = core.read_db("""
            SELECT tipo, monto, medio, comprobante 
            FROM public.movimientos 
            WHERE SUBSTRING(fecha::text FROM 1 FOR 7) = ?
        """, (per_str,))

        c_efe_propio = f"ASIENTO-APERTURA-EFE-{per_str}"
        c_ban_propio = f"ASIENTO-APERTURA-BAN-{per_str}"
        tiene_apertura_propia = not df_m_per.empty and df_m_per["comprobante"].isin([c_efe_propio, c_ban_propio]).any()

        if tiene_apertura_propia:
            ing_efe = float(df_m_per[(df_m_per["medio"] == "Efectivo") & (df_m_per["tipo"] == "Ingreso")]["monto"].sum())
            egr_efe = float(df_m_per[(df_m_per["medio"] == "Efectivo") & (df_m_per["tipo"] == "Egreso")]["monto"].sum())
            sal_efe = ing_efe - egr_efe

            ing_ban = float(df_m_per[(df_m_per["medio"] != "Efectivo") & (df_m_per["tipo"] == "Ingreso")]["monto"].sum())
            egr_ban = float(df_m_per[(df_m_per["medio"] != "Efectivo") & (df_m_per["tipo"] == "Egreso")]["monto"].sum())
            sal_ban = ing_ban - egr_ban
        else:
            df_hist = core.read_db("""
                SELECT tipo, monto, medio 
                FROM public.movimientos 
                WHERE fecha <= ? AND comprobante NOT LIKE ?
            """, (f_fin_per, 'ASIENTO-APERTURA%'))

            ing_efe = float(df_hist[(df_hist["medio"] == "Efectivo") & (df_hist["tipo"] == "Ingreso")]["monto"].sum()) if not df_hist.empty else 0.0
            egr_efe = float(df_hist[(df_hist["medio"] == "Efectivo") & (df_hist["tipo"] == "Egreso")]["monto"].sum()) if not df_hist.empty else 0.0
            sal_efe = ing_efe - egr_efe

            ing_ban = float(df_hist[(df_hist["medio"] != "Efectivo") & (df_hist["tipo"] == "Ingreso")]["monto"].sum()) if not df_hist.empty else 0.0
            egr_ban = float(df_hist[(df_hist["medio"] != "Efectivo") & (df_hist["tipo"] == "Egreso")]["monto"].sum()) if not df_hist.empty else 0.0
            sal_ban = ing_ban - egr_ban

        sal_total = sal_efe + sal_ban

        df_op_mes = df_m_per[~df_m_per["comprobante"].astype(str).str.startswith("ASIENTO-APERTURA")] if not df_m_per.empty else pd.DataFrame()
        ing_op = float(df_op_mes[df_op_mes["tipo"] == "Ingreso"]["monto"].sum()) if not df_op_mes.empty else 0.0
        egr_op = float(df_op_mes[df_op_mes["tipo"] == "Egreso"]["monto"].sum()) if not df_op_mes.empty else 0.0

        cierre_act = core.read_db("SELECT * FROM public.cierres_mensuales WHERE periodo=?", (per_str,))
        esta_cerrado = not cierre_act.empty and cierre_act.iloc[0]["estado"] == "Cerrado"

        m1, m2 = st.columns(2)
        m1.metric("Ingresos Operativos", f"S/. {ing_op:,.2f}")
        m2.metric("Egresos del Mes", f"S/. {egr_op:,.2f}")

        st.markdown("##### 💰 Arqueo de Saldos al Cierre (a trasladar al mes siguiente):")
        c_s1, c_s2, c_s3 = st.columns(3)
        c_s1.metric("💵 Saldo en Efectivo", f"S/. {sal_efe:,.2f}")
        c_s2.metric("🏦 Saldo en Bancos", f"S/. {sal_ban:,.2f}")
        c_s3.metric("🪙 Saldo Neto Total", f"S/. {sal_total:,.2f}", delta="Superávit" if sal_total >= 0 else "Déficit")

        st.markdown("---")

        if not esta_cerrado:
            st.info(f"Estado del Periodo: **🔓 ABIERTO** ({mes_c} {anio_c})")
            st.caption(
                f"Al congelar el mes, se crearán automáticamente los **2 Asientos de Apertura** "
                f"(Efectivo: S/. {sal_efe:,.2f} y Bancos: S/. {sal_ban:,.2f}) el primer día de **{nombre_mes_sig} {anio_sig}**."
            )
            if st.button("🔒 Ejecutar Cierre y Crear Asientos de Apertura", type="primary", use_container_width=True):
                user_ejecutor = st.session_state.get("usuario_actual", {}).get("nombre", "Tesorería General")

                core.query_db("""
                    INSERT INTO public.cierres_mensuales (periodo, fecha_cierre, estado, saldo_cierre, usuario) 
                    VALUES (?, ?, 'Cerrado', ?, ?) 
                    ON CONFLICT (periodo) DO UPDATE SET 
                        fecha_cierre = EXCLUDED.fecha_cierre, 
                        estado = 'Cerrado', 
                        saldo_cierre = EXCLUDED.saldo_cierre, 
                        usuario = EXCLUDED.usuario
                """, (per_str, str(date.today()), sal_total, user_ejecutor))

                core.query_db("DELETE FROM public.movimientos WHERE comprobante IN (?, ?)", (c_efe_sig, c_ban_sig))

                tipo_efe = 'Ingreso' if sal_efe >= 0 else 'Egreso'
                core.query_db("""
                    INSERT INTO public.movimientos (
                        fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable, archivo_foto, estado_credito
                    ) VALUES (
                        ?, ?, 'Saldo Inicial / Apertura', 'Apertura en Efectivo', 'General', ?, 'Efectivo', ?, ?, ?, '', 'Cobrado'
                    )
                """, (
                    fecha_apertura_sig,
                    tipo_efe,
                    round(abs(float(sal_efe)), 2),
                    c_efe_sig,
                    f"Saldo inicial de apertura mes {nombre_mes_sig} {anio_sig} (Remanente Efectivo {mes_c} {anio_c})",
                    user_ejecutor
                ))

                tipo_ban = 'Ingreso' if sal_ban >= 0 else 'Egreso'
                core.query_db("""
                    INSERT INTO public.movimientos (
                        fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable, archivo_foto, estado_credito
                    ) VALUES (
                        ?, ?, 'Saldo Inicial / Apertura', 'Apertura en Banco / Transferencia', 'General', ?, 'Depósito / Transferencia', ?, ?, ?, '', 'Cobrado'
                    )
                """, (
                    fecha_apertura_sig,
                    tipo_ban,
                    round(abs(float(sal_ban)), 2),
                    c_ban_sig,
                    f"Saldo inicial de apertura mes {nombre_mes_sig} {anio_sig} (Remanente Banco {mes_c} {anio_c})",
                    user_ejecutor
                ))

                core.registrar_log(
                    "Cierres", "Bloqueo", 
                    f"Cierre {per_str}. Aperturas creadas para {sig_per}: Efectivo S/. {sal_efe:,.2f}, Bancos S/. {sal_ban:,.2f}"
                )
                st.success(f"🎉 Periodo {per_str} cerrado. Se generaron los 2 asientos de apertura para el 01/{num_m_sig:02d}/{anio_sig}.")
                st.rerun()
        else:
            f_c = cierre_act.iloc[0].get("fecha_cierre", str(date.today()))
            u_c = cierre_act.iloc[0].get("usuario", "Tesorería")
            st.success(f"Estado del Periodo: **🔒 CERRADO** el {f_c} por {u_c}")
            st.info(f"Asientos de apertura vigentes en Tesorería para **{fecha_apertura_sig}**:\n- 💵 Efectivo: `{c_efe_sig}`\n- 🏦 Bancos: `{c_ban_sig}`")

            with st.expander("🔓 Reapertura Extraordinaria del Periodo"):
                st.warning("⚠️ Al reabrir este periodo, los asientos de apertura generados en el mes siguiente se eliminarán temporalmente para evitar inconsistencias.")
                mot = st.text_input("Motivo fundamentado para reabrir el mes:")
                if st.button("Confirmar Reapertura y Eliminar Aperturas Siguientes", type="secondary"):
                    if mot.strip():
                        core.query_db("DELETE FROM public.movimientos WHERE comprobante IN (?, ?)", (c_efe_sig, c_ban_sig))
                        core.query_db("UPDATE public.cierres_mensuales SET estado='Abierto' WHERE periodo=?", (per_str,))
                        core.registrar_log("Cierres", "Reapertura", f"Reabierto {per_str}: {mot.strip()} (Eliminados {c_efe_sig} y {c_ban_sig})")
                        st.toast("🔓 Periodo reabierto y asientos de apertura revertidos.")
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
# 3. RESPALDO Y BASE DE DATOS (SOLO ADMINISTRADOR)
# ==============================================================================
elif seccion_cfg == "🛡️ Respaldo y Base de Datos" and es_administrador:
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
# 4. GESTIÓN DE USUARIOS Y ASIGNACIÓN DE MÓDULOS (SOLO ADMINISTRADOR)
# ==============================================================================
elif seccion_cfg == "👥 Usuarios y Permisos" and es_administrador:
    st.markdown("#### 👥 Administración de Usuarios y Asignación de Módulos")
    st.caption("Marca con exactitud a qué módulos de la aplicación tendrá acceso cada cuenta. Las páginas no seleccionadas no se verán en su menú lateral.")

    with st.expander("➕ Registrar Nuevo Usuario y Asignar Módulos", expanded=False):
        with st.form("form_nuevo_usuario_modulos"):
            col1, col2 = st.columns(2)
            with col1:
                nuevo_u = st.text_input("Usuario (ej: tesoreria, secretaria):", placeholder="Sin espacios ni mayúsculas").strip().lower()
                nuevo_nom = st.text_input("Nombre Completo (ej: Juan Pérez):")
            with col2:
                nuevo_rol = st.selectbox("Rol del Usuario:", ["Tesorero General", "Pastor Principal", "Secretaría", "Administrador"])
                nuevo_pass = st.text_input("Contraseña Temporal:", type="password")

            st.markdown("---")
            st.markdown("##### 📌 Módulos (Páginas) autorizadas para este usuario:")
            modulos_autorizados = st.multiselect(
                "Selecciona los módulos a los que tendrá acceso:",
                options=TODOS_LOS_MODULOS,
                default=["Panel Principal", "Diezmos", "Tesorería"]
            )
            
            st.info("🔒 **Seguridad estricta**: Si seleccionas 'Configuración', el usuario NO tendrá acceso a las pestañas de 'Respaldo' ni de 'Usuarios'. Esas secciones están reservadas única y exclusivamente para el Administrador.")

            btn_guardar_u = st.form_submit_button("Guardar Usuario con Módulos", type="primary")

            if btn_guardar_u:
                if not nuevo_u or not nuevo_nom or not nuevo_pass:
                    st.warning("⚠️ Debes completar los campos obligatorios de usuario, nombre y contraseña.")
                elif not modulos_autorizados:
                    st.warning("⚠️ Debes asignar al menos un módulo permitido.")
                else:
                    pass_hash = core.encriptar_clave(nuevo_pass)
                    cadena_permisos = ",".join(modulos_autorizados)
                    try:
                        core.query_db("""
                            INSERT INTO public.usuarios_sistema (usuario, password_hash, nombre, rol, activo, permisos)
                            VALUES (%s, %s, %s, %s, TRUE, %s)
                        """, (nuevo_u, pass_hash, nuevo_nom, nuevo_rol, cadena_permisos))
                        core.registrar_log("Usuarios", "Crear", f"Usuario '{nuevo_u}' registrado con módulos: {cadena_permisos}")
                        st.success(f"✅ Usuario '{nuevo_u}' registrado exitosamente con sus módulos permitidos.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar usuario: {e}")

    st.markdown("##### Cuentas Registradas en el Sistema")
    try:
        df_usuarios = core.read_db("SELECT id, usuario, nombre, rol, activo, permisos, fecha_creacion FROM public.usuarios_sistema ORDER BY id ASC")

        if not df_usuarios.empty:
            st.dataframe(
                df_usuarios.rename(columns={
                    "id": "ID", "usuario": "Usuario", "nombre": "Nombre",
                    "rol": "Rol", "activo": "Estado Activo", "permisos": "Módulos Autorizados", "fecha_creacion": "Fecha Creación"
                }), 
                use_container_width=True, 
                hide_index=True
            )

            st.markdown("---")
            st.markdown("##### ⚙️ Modificar Módulos Permitidos y Contraseña")

            usuarios_dict = {
                f"{r['usuario']} ({r['nombre']} - {r['rol']})": r["id"] 
                for _, r in df_usuarios.iterrows()
            }
            
            u_sel_label = st.selectbox("Seleccione la cuenta a configurar:", list(usuarios_dict.keys()))
            id_u_sel = usuarios_dict[u_sel_label]
            row_user = df_usuarios[df_usuarios["id"] == id_u_sel].iloc[0]

            perms_raw = str(row_user.get("permisos", "") or "")
            perms_lista = [p.strip() for p in perms_raw.split(",") if p.strip()]

            with st.form("form_editar_permisos_modulos"):
                st.caption(f"Configurando acceso para: **{row_user['usuario']}** ({row_user['nombre']})")

                def_modulos = [m for m in TODOS_LOS_MODULOS if m in perms_lista] if "TODOS" not in perms_raw.upper() else TODOS_LOS_MODULOS
                nuevos_modulos = st.multiselect(
                    "Módulos a los que puede acceder en la barra lateral:",
                    options=TODOS_LOS_MODULOS,
                    default=def_modulos
                )

                st.markdown("---")
                nueva_clave = st.text_input("Nueva Contraseña (dejar en blanco para no modificar):", type="password")

                if st.form_submit_button("💾 Guardar Cambios de Módulos y Clave", type="primary"):
                    cadena_nueva = ",".join(nuevos_modulos) if nuevos_modulos else "NINGUNO"

                    if nueva_clave.strip():
                        n_hash = core.encriptar_clave(nueva_clave)
                        core.query_db("UPDATE public.usuarios_sistema SET password_hash=%s, permisos=%s WHERE id=%s", (n_hash, cadena_nueva, id_u_sel))
                        core.registrar_log("Usuarios", "Seguridad", f"Actualizada clave y módulos de {row_user['usuario']}: {cadena_nueva}")
                        st.success("✅ Módulos y contraseña actualizados exitosamente.")
                    else:
                        core.query_db("UPDATE public.usuarios_sistema SET permisos=%s WHERE id=%s", (cadena_nueva, id_u_sel))
                        core.registrar_log("Usuarios", "Seguridad", f"Actualizados módulos de {row_user['usuario']}: {cadena_nueva}")
                        st.success("✅ Módulos autorizados actualizados exitosamente.")
                    st.rerun()

            col_est1, col_est2 = st.columns(2)
            with col_est1:
                st.caption(f"Estado de la cuenta: **{'Activo' if row_user['activo'] else 'Inactivo'}**")
                if row_user["usuario"] == "admin":
                    st.info("ℹ️ La cuenta 'admin' cuenta con acceso irrestricto y no puede ser desactivada ni eliminada.")
                else:
                    nuevo_estado = not bool(row_user["activo"])
                    btn_txt = "🔴 Desactivar Cuenta" if row_user["activo"] else "🟢 Habilitar Cuenta"
                    if st.button(btn_txt):
                        core.query_db("UPDATE public.usuarios_sistema SET activo=%s WHERE id=%s", (nuevo_estado, id_u_sel))
                        core.registrar_log("Usuarios", "Estado", f"Estado de {row_user['usuario']} cambiado a {nuevo_estado}")
                        st.toast("✅ Estado actualizado.")
                        st.rerun()

                    if st.button("🗑️ Eliminar Usuario Definitivamente", type="secondary"):
                        core.query_db("DELETE FROM public.usuarios_sistema WHERE id=%s", (id_u_sel,))
                        core.registrar_log("Usuarios", "Eliminación", f"Eliminado usuario {row_user['usuario']}")
                        st.toast("🗑️ Usuario eliminado.")
                        st.rerun()

    except Exception as e:
        st.error(f"Error al gestionar usuarios: {e}")
