import streamlit as st
import core
from datetime import date, datetime, timedelta
import pandas as pd
import calendar
import re

st.set_page_config(page_title="Pagos Programados", page_icon="📅", layout="wide")
core.requerir_login()
core.aplicar_estilos_base()

# Constantes del módulo
CATEGORIAS = [
    "Servicios Básicos (Luz/Agua/Internet)", "Alquiler de Local / Templo",
    "Mantenimiento e Infraestructura", "Préstamos / Financiamiento",
    "Aportes Distritales / Nacionales", "Viáticos y Movilidad", "Otros Compromisos"
]
FONDOS = ["General", "Pro-Templo", "Misiones", "Jóvenes", "Damas", "Caballeros"]
MEDIOS = ["Efectivo", "Depósito / Transferencia", "Yape / Plin"]

# 1. Base de datos: asegurar tabla y columnas necesarias (Sintaxis PostgreSQL)
try:
    with core.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pagos_programados (
                    id SERIAL PRIMARY KEY,
                    codigo TEXT,
                    concepto TEXT,
                    categoria TEXT,
                    monto REAL DEFAULT 0.0,
                    fondo TEXT DEFAULT 'General',
                    fecha_vencimiento TEXT,
                    periodicidad TEXT DEFAULT 'Mensual',
                    estado TEXT DEFAULT 'Pendiente',
                    fecha_pago TEXT,
                    medio_pago TEXT,
                    tipo_comprobante TEXT DEFAULT 'Recibo',
                    serie_comprobante TEXT DEFAULT '',
                    numero_comprobante TEXT DEFAULT '',
                    num_operacion TEXT,
                    responsable TEXT,
                    observaciones TEXT
                )
            """)
            
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='pagos_programados'")
            cols_existentes = {row['column_name'] for row in cur.fetchall()}

            columnas_def = [
                ("codigo", "TEXT"), ("concepto", "TEXT"), ("categoria", "TEXT"),
                ("monto", "REAL DEFAULT 0.0"), ("fondo", "TEXT DEFAULT 'General'"),
                ("fecha_vencimiento", "TEXT"), ("periodicidad", "TEXT DEFAULT 'Mensual'"),
                ("estado", "TEXT DEFAULT 'Pendiente'"), ("fecha_pago", "TEXT"),
                ("medio_pago", "TEXT"), ("tipo_comprobante", "TEXT DEFAULT 'Recibo'"),
                ("serie_comprobante", "TEXT DEFAULT ''"), ("numero_comprobante", "TEXT DEFAULT ''"),
                ("num_operacion", "TEXT"), ("responsable", "TEXT"), ("observaciones", "TEXT")
            ]
            for nom, tipo in columnas_def:
                if nom not in cols_existentes:
                    try:
                        cur.execute(f"SAVEPOINT sp_{nom}")
                        cur.execute(f"ALTER TABLE pagos_programados ADD COLUMN {nom} {tipo}")
                        cur.execute(f"RELEASE SAVEPOINT sp_{nom}")
                    except Exception:
                        cur.execute(f"ROLLBACK TO SAVEPOINT sp_{nom}")
            
            if "fecha" in cols_existentes and "fecha_vencimiento" in cols_existentes:
                try:
                    cur.execute("UPDATE pagos_programados SET fecha_vencimiento = fecha WHERE fecha_vencimiento IS NULL OR fecha_vencimiento = ''")
                except Exception:
                    pass
        conn.commit()
except Exception as e:
    pass

def get_sig_codigo_prg():
    df_u = core.read_db("SELECT codigo FROM pagos_programados WHERE codigo LIKE ? ORDER BY id DESC LIMIT 1", ("PRG-%",))
    if df_u.empty:
        return "PRG-0001"
    try:
        num = int(df_u.iloc[0]["codigo"].split("-")[-1].strip())
        return f"PRG-{num + 1:04d}"
    except Exception:
        df_cant = core.read_db("SELECT COUNT(*) as t FROM pagos_programados")
        cant = df_cant.iloc[0]["t"] if not df_cant.empty else 0
        return f"PRG-{int(cant) + 1:04d}"

def obtener_folio_comprobante(serie, numero, codigo_prg, fecha_pago_obj=None):
    s = str(serie).strip().upper() if pd.notnull(serie) and str(serie).strip().lower() != "nan" else ""
    n = str(numero).strip() if pd.notnull(numero) and str(numero).strip().lower() != "nan" else ""
    
    if s and n:
        return f"{s}-{n}", s, n, "Personalizado"
    elif n:
        return f"REC-{n}", "REC", n, "Personalizado"
    else:
        f_ref = fecha_pago_obj if isinstance(fecha_pago_obj, (date, datetime)) else date.today()
        mes_anio = f_ref.strftime("%Y%m")
        num_clean = str(codigo_prg).replace("PRG-", "").strip()
        serie_gen = "GEN"
        num_gen = f"{mes_anio}-{num_clean}"
        return f"{serie_gen}-{num_gen}", serie_gen, num_gen, "Genérico"

def parsear_fecha_segura(valor, default=None):
    if default is None:
        default = date.today()
    if pd.isnull(valor) or str(valor).strip().lower() in ("nan", "none", ""):
        return default
    try:
        return datetime.strptime(str(valor).strip(), "%Y-%m-%d").date()
    except Exception:
        return default

def limpiar_concepto_raiz(concepto_str):
    """Extrae el nombre base quitando el mes entre paréntesis (ej: 'Servicio Luz (Dic)' -> 'Servicio Luz')"""
    return re.sub(r"\s*\([A-Za-z]{3,}\)$", "", str(concepto_str)).strip()

def _sincronizar_asiento_tesoreria(fecha, categoria, concepto, fondo, monto, medio, comprobante_final, detalle_extra, responsable, es_update=False, comprobante_anterior=""):
    detalle = f"Pago programado: {concepto} | {detalle_extra}"
    if es_update:
        clave = comprobante_anterior if comprobante_anterior else comprobante_final
        core.query_db("""
            UPDATE movimientos SET fecha = ?, monto = ?, medio = ?, responsable = ?, detalle = ?, fondo = ?, categoria = ?, comprobante = ?
            WHERE comprobante = ?
        """, (str(fecha), monto, medio, responsable, detalle, fondo, categoria, comprobante_final, clave))
    else:
        core.query_db("""
            INSERT INTO movimientos 
            (fecha, tipo, categoria, subcategoria, fondo, monto, medio, comprobante, detalle, responsable, archivo_foto, estado_credito)
            VALUES (?, 'Egreso', ?, ?, ?, ?, ?, ?, ?, ?, '', 'Cobrado')
        """, (str(fecha), categoria, concepto, fondo, monto, medio, comprobante_final, detalle, responsable))

def sumar_meses(fecha_origen, meses_a_sumar):
    anio = fecha_origen.year + (fecha_origen.month + meses_a_sumar - 1) // 12
    mes = (fecha_origen.month + meses_a_sumar - 1) % 12 + 1
    max_dias = calendar.monthrange(anio, mes)[1]
    dia = min(fecha_origen.day, max_dias)
    return date(anio, mes, dia)

st.subheader("📅 Control y Agenda de Pagos Programados")

tabs = st.tabs([
    "📆 Calendario y Cronograma",
    "➕ Programar Compromiso",
    "💳 Ejecutar Pago (Liquidar)",
    "⚙️ Modificar o Eliminar (con Filtros)"
])

# ==============================================================================
# PESTAÑA 1: CALENDARIO Y CRONOGRAMA INTERACTIVO (OPTIMIZADO PARA MÓVIL)
# ==============================================================================
with tabs[0]:
    st.markdown("#### 📆 Calendario Mensual de Vencimientos y Compromisos")
    df_todos = core.read_db("SELECT * FROM pagos_programados ORDER BY CAST(COALESCE(NULLIF(fecha_vencimiento, ''), '1970-01-01') AS DATE) ASC, id DESC")

    hoy = date.today()
    c_f1, c_f2 = st.columns(2)
    with c_f1:
        anio_sel = st.selectbox("Año a visualizar:", list(range(hoy.year - 3, hoy.year + 4)), index=3, key="cal_anio")
    with c_f2:
        mes_sel = st.selectbox("Mes a visualizar:", core.MESES, index=hoy.month - 1, key="cal_mes")

    mes_num = core.MESES.index(mes_sel) + 1

    pagos_este_mes = []
    if not df_todos.empty:
        for _, r in df_todos.iterrows():
            fv = parsear_fecha_segura(r.get("fecha_vencimiento"), None)
            if not fv:
                continue

            period = str(r.get("periodicidad") or "Mensual")
            s_comp = str(r.get("serie_comprobante") or "")
            n_comp = str(r.get("numero_comprobante") or "")
            s_comp = "" if s_comp.lower() == "nan" else s_comp
            n_comp = "" if n_comp.lower() == "nan" else n_comp
            folio_comp = f"{s_comp}-{n_comp}".strip("-") if (s_comp or n_comp) else "-"

            if fv.year == anio_sel and fv.month == mes_num:
                pagos_este_mes.append({
                    "id": r["id"], "codigo": r["codigo"], "concepto": r["concepto"],
                    "categoria": r["categoria"], "monto": r["monto"], "fondo": r["fondo"],
                    "dia": fv.day, "fecha_venc": fv, "estado": r["estado"],
                    "periodicidad": period, "comprobante": folio_comp
                })
            elif period == "Mensual" and (fv.year < anio_sel or (fv.year == anio_sel and fv.month < mes_num)):
                max_dias = calendar.monthrange(anio_sel, mes_num)[1]
                dia_calc = min(fv.day, max_dias)
                fv_proy = date(anio_sel, mes_num, dia_calc)
                pagos_este_mes.append({
                    "id": r["id"], "codigo": f"{r['codigo']} ({mes_sel[:3]})", "concepto": r["concepto"],
                    "categoria": r["categoria"], "monto": r["monto"], "fondo": r["fondo"],
                    "dia": dia_calc, "fecha_venc": fv_proy, "estado": "Pendiente",
                    "periodicidad": period, "comprobante": "-"
                })

    df_mes = pd.DataFrame(pagos_este_mes)

    tot_mes = df_mes["monto"].sum() if not df_mes.empty else 0.0
    tot_pag = df_mes[df_mes["estado"] == "Pagado"]["monto"].sum() if not df_mes.empty else 0.0
    tot_pen = tot_mes - tot_pag

    m1, m2, m3 = st.columns(3)
    m1.metric(f"Total Programado ({mes_sel} {anio_sel})", f"S/. {tot_mes:,.2f}")
    m2.metric("Total Liquidado", f"S/. {tot_pag:,.2f}")
    m3.metric("Pendiente por Cancelar", f"S/. {tot_pen:,.2f}")

    st.markdown("---")
    st.markdown(f"### 🗓️ Cuadrícula: {mes_sel} {anio_sel}")
    st.caption("📱 *Si estás en celular, puedes deslizar la cuadrícula horizontalmente con el dedo.*")

    cal_mes_matriz = calendar.monthcalendar(anio_sel, mes_num)

    # Renderizado responsivo en un único bloque HTML con scroll horizontal suave
    html_cal = """
    <div style="overflow-x: auto; -webkit-overflow-scrolling: touch; width: 100%; border: 1px solid #E2E8F0; border-radius: 12px; padding: 6px; background: #FFFFFF; box-shadow: 0 4px 12px rgba(15,23,42,0.03); margin-bottom: 20px;">
        <table style="width: 100%; min-width: 720px; border-collapse: separate; border-spacing: 6px; table-layout: fixed;">
            <thead>
                <tr>
    """
    for d in ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]:
        html_cal += f"<th style='background-color: #1E3A8A; color: white; padding: 8px 4px; border-radius: 6px; font-size: 13px; font-weight: 700; text-align: center; width: 14.28%;'>{d}</th>"
    html_cal += "</tr></thead><tbody>"

    for semana in cal_mes_matriz:
        html_cal += "<tr>"
        for dia_num in semana:
            if dia_num == 0:
                html_cal += "<td style='background-color: #F8FAFC; border-radius: 6px; height: 100px; vertical-align: top; border: 1px dashed #E2E8F0;'></td>"
            else:
                fecha_iter = date(anio_sel, mes_num, dia_num)
                es_hoy = (fecha_iter == hoy)
                bg_dia = "#FEF08A" if es_hoy else "#FFFFFF"
                borde = "2px solid #CA8A04" if es_hoy else "1px solid #CBD5E1"
                
                pagos_dia = df_mes[df_mes["dia"] == dia_num] if not df_mes.empty else pd.DataFrame()
                
                html_cal += f"<td style='background-color: {bg_dia}; border: {borde}; border-radius: 6px; height: 100px; vertical-align: top; padding: 6px; box-sizing: border-box;'>"
                html_cal += f"<div style='font-weight: 800; font-size: 12px; color: #1E293B; margin-bottom: 4px;'>{dia_num} {'<span style=\"font-size: 10px; color: #B45309;\">(Hoy)</span>' if es_hoy else ''}</div>"
                
                if not pagos_dia.empty:
                    for _, p in pagos_dia.iterrows():
                        if p["estado"] == "Pagado":
                            color_b = "#22C55E"
                            ico = "🟢"
                        elif fecha_iter < hoy:
                            color_b = "#EF4444"
                            ico = "🔴"
                        else:
                            color_b = "#F59E0B"
                            ico = "🟡"
                        concepto_txt = str(p['concepto'])[:15]
                        monto_txt = f"{p['monto']:,.2f}"
                        html_cal += f"""<div style='background-color: {color_b}15; border-left: 3px solid {color_b}; padding: 3px 5px; margin-top: 3px; border-radius: 4px; font-size: 11px; line-height: 1.2;'>
                            <b style='color: #0F172A;'>{ico} {concepto_txt}</b><br/>
                            <span style='color: #334155; font-weight: 600;'>S/. {monto_txt}</span>
                        </div>"""
                html_cal += "</td>"
        html_cal += "</tr>"
    html_cal += "</tbody></table></div>"

    st.markdown(html_cal, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"#### 📋 Lista de Vencimientos: {mes_sel} {anio_sel}")
    if df_mes.empty:
        st.info(f"No hay compromisos registrados para {mes_sel} {anio_sel}.")
    else:
        def calc_alerta(r):
            if r["estado"] == "Pagado":
                return "🟢 Pagado"
            fv = r["fecha_venc"]
            if fv < hoy:
                return "🔴 Vencido"
            diff = (fv - hoy).days
            return f"🟡 Vence en {diff} d" if diff <= 5 else "⚪ Programado"

        df_mes["Alerta"] = df_mes.apply(calc_alerta, axis=1)
        mapa = {
            "codigo": "Código", "Alerta": "Estado", "fecha_venc": "F. Vencimiento",
            "concepto": "Concepto", "categoria": "Categoría", "monto": "Monto (S/.)",
            "fondo": "Fondo", "comprobante": "Comprobante / Folio"
        }
        df_mostrar = df_mes[list(mapa.keys())].rename(columns=mapa)
        st.dataframe(df_mostrar.style.format({"Monto (S/.)": "S/. {:,.2f}"}), use_container_width=True, hide_index=True)

# ==============================================================================
# PESTAÑA 2: PROGRAMAR NUEVO COMPROMISO
# ==============================================================================
with tabs[1]:
    st.markdown("#### ➕ Agendar Nuevo Compromiso o Gasto Recurrente")
    sig_cod = get_sig_codigo_prg()
    st.info(f"🔖 **Código autogenerado para el compromiso:** `{sig_cod}` *(La serie y número del comprobante se asignarán al momento del pago)*")

    with st.form("form_nuevo_pago_prg"):
        c1, c2 = st.columns(2)
        with c1:
            concepto = st.text_input("Concepto / Servicio a Pagar:", placeholder="Ej. Servicio de Luz (Enel), Internet Templo, Cuota de Préstamo")
            categoria = st.selectbox("Categoría del Gasto:", CATEGORIAS)
            monto_previsto = st.number_input("Monto Estimado / Cuota (S/.):", min_value=1.0, value=150.0, step=10.0, format="%.2f")
            fondo_cargo = st.selectbox("Fondo de Salida:", FONDOS)
        with c2:
            fecha_venc = st.date_input("Fecha Límite / Vencimiento Inicial:", value=date.today())
            periodicidad = st.selectbox("Periodicidad:", ["Mensual", "Bimestral", "Único / Puntual", "Anual"])
            meses_a_generar = 1
            if periodicidad == "Mensual":
                meses_a_generar = st.slider("Meses consecutivos a programar en agenda:", min_value=1, max_value=12, value=6, help="Genera automáticamente los vencimientos mensuales para cada periodo consecutivo.")
            observaciones = st.text_area("Notas / Observaciones:", placeholder="Ej. N° de Suministro: 1284950...")

        btn_guardar_prg = st.form_submit_button(f"💾 Agendar Compromiso ({sig_cod})", type="primary")

    if btn_guardar_prg:
        if not concepto.strip():
            st.error("Debe ingresar el concepto o servicio a pagar.")
        else:
            if periodicidad == "Mensual" and meses_a_generar > 1:
                base_num = int(sig_cod.split("-")[-1].strip())
                for i in range(meses_a_generar):
                    cod_mes = f"PRG-{base_num + i:04d}"
                    f_calc = sumar_meses(fecha_venc, i)
                    nom_concepto = f"{concepto.strip()} ({core.MESES[f_calc.month - 1][:3]})"
                    core.query_db("""
                        INSERT INTO pagos_programados 
                        (codigo, concepto, categoria, monto, fondo, fecha_vencimiento, periodicidad, estado, serie_comprobante, numero_comprobante, observaciones)
                        VALUES (?, ?, ?, ?, ?, ?, 'Mensual', 'Pendiente', '', '', ?)
                    """, (cod_mes, nom_concepto, categoria, monto_previsto, fondo_cargo, str(f_calc), observaciones.strip()))
                st.toast(f"✅ Se programaron {meses_a_generar} meses consecutivos.")
            else:
                core.query_db("""
                    INSERT INTO pagos_programados 
                    (codigo, concepto, categoria, monto, fondo, fecha_vencimiento, periodicidad, estado, serie_comprobante, numero_comprobante, observaciones)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente', '', '', ?)
                """, (sig_cod, concepto.strip(), categoria, monto_previsto, fondo_cargo, str(fecha_venc), periodicidad, observaciones.strip()))
                st.toast(f"✅ Compromiso {sig_cod} agendado correctamente.")

            core.registrar_log("Pagos Programados", "Agendado", f"{concepto.strip()} por S/. {monto_previsto:,.2f}")
            st.rerun()

# ==============================================================================
# PESTAÑA 3: EJECUTAR PAGO (LIQUIDAR CON SERIE/NÚMERO O GENÉRICO)
# ==============================================================================
with tabs[2]:
    st.markdown("#### 💳 Liquidar Pago y Asignar Serie y Número de Comprobante")
    df_pendientes = core.read_db("SELECT * FROM pagos_programados WHERE estado != 'Pagado' ORDER BY CAST(COALESCE(NULLIF(fecha_vencimiento, ''), '1970-01-01') AS DATE) ASC")

    if df_pendientes.empty:
        st.success("🎉 ¡No hay pagos pendientes! Todos los compromisos están liquidados.")
    else:
        opciones_liq = {
            f"{r['codigo']} — {r['concepto']} (S/. {r['monto']:,.2f} | Vence: {r['fecha_vencimiento']})": r["id"]
            for _, r in df_pendientes.iterrows()
        }
        sel_pago = st.selectbox("Seleccione el compromiso a pagar:", list(opciones_liq.keys()))
        id_pago = opciones_liq[sel_pago]
        reg_pago = df_pendientes[df_pendientes["id"] == id_pago].iloc[0]

        st.warning(f"Liquidando: **{reg_pago['concepto']}** (`{reg_pago['codigo']}`). Al confirmar se creará el asiento de egreso en Tesorería.")

        with st.form("form_liquidar_pago"):
            c1, c2 = st.columns(2)
            with c1:
                f_real_pago = st.date_input("Fecha Real de Pago:", value=date.today())
                monto_pagado = st.number_input("Monto Pagado (S/.):", min_value=1.0, value=float(reg_pago["monto"]), step=5.0, format="%.2f")
                medio_pago = st.selectbox("Medio de Pago:", MEDIOS)
                idx_fondo = FONDOS.index(reg_pago["fondo"]) if reg_pago["fondo"] in FONDOS else 0
                fondo_real = st.selectbox("Fondo de Salida del Dinero:", FONDOS, index=idx_fondo)
                responsable_pago = st.text_input("Responsable del Pago:", value="Tesorero General")

            with c2:
                st.markdown("##### 🧾 Datos del Comprobante / Recibo")
                st.caption("Si cuentas con recibo, ingresa su serie y número. Si los dejas vacíos, se generará uno genérico automáticamente.")
                
                c_s1, c_s2 = st.columns(2)
                with c_s1:
                    serie_input = st.text_input("Serie:", placeholder="Ej. B001, F001, REC")
                with c_s2:
                    numero_input = st.text_input("Número Correlativo:", placeholder="Ej. 0004523, 1290")

                num_op_banco = st.text_input("N° Operación Bancaria / Voucher (Opcional):", placeholder="Ej. OP-481920 (Transferencia / Yape)")

            btn_liquidar = st.form_submit_button("✅ Confirmar Pago y Asentar en Tesorería", type="primary")

        if btn_liquidar:
            folio_final, serie_guardar, numero_guardar, tipo_asignado = obtener_folio_comprobante(
                serie_input, numero_input, reg_pago["codigo"], f_real_pago
            )

            core.query_db("""
                UPDATE pagos_programados SET
                    estado = 'Pagado',
                    fecha_pago = ?,
                    monto = ?,
                    fondo = ?,
                    medio_pago = ?,
                    tipo_comprobante = ?,
                    serie_comprobante = ?,
                    numero_comprobante = ?,
                    num_operacion = ?,
                    responsable = ?
                WHERE id = ?
            """, (str(f_real_pago), monto_pagado, fondo_real, medio_pago, tipo_asignado, serie_guardar, numero_guardar, num_op_banco.strip(), responsable_pago.strip(), id_pago))

            detalle_tes = f"Op: {num_op_banco.strip()}" if num_op_banco.strip() else f"Comp: {folio_final}"
            _sincronizar_asiento_tesoreria(
                f_real_pago, reg_pago["categoria"], reg_pago["concepto"], fondo_real,
                monto_pagado, medio_pago, folio_final, detalle_tes, responsable_pago.strip(), es_update=False
            )

            core.registrar_log("Pagos Programados", "Liquidación", f"Liquidado {reg_pago['codigo']} | Comprobante {folio_final} por S/. {monto_pagado:,.2f}")
            st.toast(f"✅ Pago liquidado con comprobante {folio_final} ({tipo_asignado}).")
            st.rerun()

# ==============================================================================
# PESTAÑA 4: MODIFICAR O ELIMINAR (INDIVIDUAL O EVENTO GENERAL)
# ==============================================================================
with tabs[3]:
    st.markdown("#### 🔍 Búsqueda y Gestión de Compromisos")
    df_todos_gest = core.read_db("SELECT * FROM pagos_programados ORDER BY CAST(COALESCE(NULLIF(fecha_vencimiento, ''), '1970-01-01') AS DATE) DESC, id DESC")

    if df_todos_gest.empty:
        st.info("No hay registros en la base de datos para gestionar.")
    else:
        df_todos_gest["dt_venc"] = pd.to_datetime(df_todos_gest["fecha_vencimiento"], errors="coerce")
        df_todos_gest["anio_venc"] = df_todos_gest["dt_venc"].dt.year
        df_todos_gest["mes_venc"] = df_todos_gest["dt_venc"].dt.month

        with st.expander("🔎 Panel de Filtros para Localizar Compromiso", expanded=True):
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                filtro_texto = st.text_input("Buscar por Concepto / Código / Responsable:", placeholder="Ej. Luz, Internet, PRG-0005, Enel...")
            with col_f2:
                anios_disp = ["Todos"] + sorted([int(a) for a in df_todos_gest["anio_venc"].dropna().unique()], reverse=True)
                filtro_anio = st.selectbox("Filtrar por Año de Vencimiento:", anios_disp, index=0)
            with col_f3:
                filtro_mes = st.selectbox("Filtrar por Mes de Vencimiento:", ["Todos"] + core.MESES, index=0)

            col_f4, col_f5, col_f6 = st.columns(3)
            with col_f4:
                filtro_estado = st.selectbox("Estado del Pago:", ["Todos", "Pendiente", "Pagado"], index=0)
            with col_f5:
                filtro_fondo = st.selectbox("Fondo de Origen:", ["Todos"] + FONDOS, index=0)
            with col_f6:
                filtro_categoria = st.selectbox("Categoría:", ["Todos"] + CATEGORIAS, index=0)

        df_filtrado = df_todos_gest.copy()

        if filtro_texto.strip():
            txt = filtro_texto.strip().lower()
            df_filtrado = df_filtrado[
                df_filtrado["concepto"].astype(str).str.lower().str.contains(txt) |
                df_filtrado["codigo"].astype(str).str.lower().str.contains(txt) |
                df_filtrado["responsable"].astype(str).str.lower().str.contains(txt) |
                df_filtrado["serie_comprobante"].astype(str).str.lower().str.contains(txt) |
                df_filtrado["numero_comprobante"].astype(str).str.lower().str.contains(txt)
            ]

        if filtro_anio != "Todos":
            df_filtrado = df_filtrado[df_filtrado["anio_venc"] == filtro_anio]

        if filtro_mes != "Todos":
            mes_n_filtro = core.MESES.index(filtro_mes) + 1
            df_filtrado = df_filtrado[df_filtrado["mes_venc"] == mes_n_filtro]

        if filtro_estado != "Todos":
            df_filtrado = df_filtrado[df_filtrado["estado"] == filtro_estado]

        if filtro_fondo != "Todos":
            df_filtrado = df_filtrado[df_filtrado["fondo"] == filtro_fondo]

        if filtro_categoria != "Todos":
            df_filtrado = df_filtrado[df_filtrado["categoria"] == filtro_categoria]

        st.caption(f"Coincidencias encontradas: **{len(df_filtrado)}** de {len(df_todos_gest)} registros totales.")

        if df_filtrado.empty:
            st.warning("⚠️ No se encontraron compromisos que coincidan con los filtros seleccionados.")
        else:
            def comp_label(r):
                s = str(r.get("serie_comprobante") or "")
                n = str(r.get("numero_comprobante") or "")
                s = "" if s.lower() == "nan" else s
                n = "" if n.lower() == "nan" else n
                folio = f" | Comp: {s}-{n}".strip("-") if (s or n) else ""
                f_v = str(r.get("fecha_vencimiento") or "Sin fecha")
                return f"{r['codigo']} — {r['concepto']} (S/. {r['monto']:,.2f} | Vence: {f_v} | {r['estado']}{folio})"

            opciones_mod = {comp_label(r): r["id"] for _, r in df_filtrado.iterrows()}

            st.markdown("---")
            sel_mod = st.selectbox("📌 Selecciona el registro que deseas gestionar:", list(opciones_mod.keys()))
            id_mod = opciones_mod[sel_mod]
            reg_mod = df_filtrado[df_filtrado["id"] == id_mod].iloc[0]

            # Raíz del concepto para identificar la serie recurrente
            concepto_raiz = limpiar_concepto_raiz(reg_mod["concepto"])

            accion = st.radio("Acción a realizar sobre el registro:", ["✏️ Editar Datos", "🗑️ Eliminar Compromiso"], horizontal=True)

            if accion == "✏️ Editar Datos":
                f_v_val = parsear_fecha_segura(reg_mod.get("fecha_vencimiento"))

                idx_cat = CATEGORIAS.index(reg_mod["categoria"]) if reg_mod["categoria"] in CATEGORIAS else 0
                idx_fon = FONDOS.index(reg_mod["fondo"]) if reg_mod["fondo"] in FONDOS else 0

                s_init = str(reg_mod["serie_comprobante"]) if pd.notnull(reg_mod["serie_comprobante"]) and str(reg_mod["serie_comprobante"]).lower() != "nan" else ""
                n_init = str(reg_mod["numero_comprobante"]) if pd.notnull(reg_mod["numero_comprobante"]) and str(reg_mod["numero_comprobante"]).lower() != "nan" else ""
                op_init = str(reg_mod["num_operacion"]) if pd.notnull(reg_mod["num_operacion"]) and str(reg_mod["num_operacion"]).lower() != "nan" else ""
                resp_init = str(reg_mod["responsable"]) if pd.notnull(reg_mod["responsable"]) and str(reg_mod["responsable"]).lower() != "nan" else "Tesorero General"
                obs_init = str(reg_mod["observaciones"]) if pd.notnull(reg_mod["observaciones"]) and str(reg_mod["observaciones"]).lower() != "nan" else ""

                with st.form("form_editar_prg"):
                    st.info(f"Modificando compromiso: **{reg_mod['codigo']}** — {reg_mod['concepto']}")
                    c1, c2 = st.columns(2)
                    with c1:
                        e_concepto = st.text_input("Concepto:", value=str(reg_mod["concepto"]))
                        e_categoria = st.selectbox("Categoría:", CATEGORIAS, index=idx_cat)
                        e_monto = st.number_input("Monto (S/.):", min_value=1.0, value=float(reg_mod["monto"]), step=5.0, format="%.2f")
                        e_fondo = st.selectbox("Fondo:", FONDOS, index=idx_fon)
                        e_venc = st.date_input("Fecha de Vencimiento:", value=f_v_val)
                        e_estado = st.selectbox("Estado:", ["Pendiente", "Pagado"], index=0 if reg_mod["estado"] != "Pagado" else 1)

                    with c2:
                        st.markdown("##### 🧾 Serie y Número del Comprobante")
                        e_serie = st.text_input("Serie:", value=s_init)
                        e_numero = st.text_input("Número Correlativo:", value=n_init)
                        e_op = st.text_input("N° Operación Bancaria:", value=op_init)
                        e_resp = st.text_input("Responsable:", value=resp_init)
                        e_obs = st.text_area("Observaciones:", value=obs_init)

                    btn_guardar_edit = st.form_submit_button("💾 Guardar Cambios y Actualizar Tesorería", type="primary")

                if btn_guardar_edit:
                    f_pago_obj = parsear_fecha_segura(reg_mod.get("fecha_pago"), date.today())

                    folio_anterior, _, _, _ = obtener_folio_comprobante(s_init, n_init, reg_mod["codigo"], f_pago_obj)
                    folio_nuevo, s_new, n_new, t_new = obtener_folio_comprobante(e_serie, e_numero, reg_mod["codigo"], f_pago_obj)

                    core.query_db("""
                        UPDATE pagos_programados SET
                            concepto = ?, categoria = ?, monto = ?, fondo = ?,
                            fecha_vencimiento = ?, estado = ?, serie_comprobante = ?,
                            numero_comprobante = ?, num_operacion = ?, responsable = ?, observaciones = ?
                        WHERE id = ?
                    """, (e_concepto.strip(), e_categoria, e_monto, e_fondo, str(e_venc), e_estado, s_new, n_new, e_op.strip(), e_resp.strip(), e_obs.strip(), id_mod))

                    if reg_mod["estado"] == "Pagado" or e_estado == "Pagado":
                        detalle_act = f"Op: {e_op.strip()}" if e_op.strip() else f"Comp: {folio_nuevo}"
                        f_real = reg_mod["fecha_pago"] if pd.notnull(reg_mod["fecha_pago"]) and str(reg_mod["fecha_pago"]).lower() != "nan" else str(e_venc)
                        med_real = reg_mod["medio_pago"] if pd.notnull(reg_mod["medio_pago"]) and str(reg_mod["medio_pago"]).lower() != "nan" else "Efectivo"
                        _sincronizar_asiento_tesoreria(
                            f_real, e_categoria, e_concepto.strip(), e_fondo,
                            e_monto, med_real, folio_nuevo, detalle_act,
                            e_resp.strip(), es_update=True, comprobante_anterior=folio_anterior
                        )

                    core.registrar_log("Pagos Programados", "Edición", f"Actualizado {reg_mod['codigo']} | Comprobante: {folio_nuevo}")
                    st.toast(f"✅ Cambios guardados y Tesorería sincronizada ({folio_nuevo}).")
                    st.rerun()

            elif accion == "🗑️ Eliminar Compromiso":
                st.markdown("#### 🗑️ Opciones de Eliminación")
                alcance_elim = st.radio(
                    "Selecciona el alcance de la eliminación:",
                    [
                        "📌 Eliminar sólo esta cuota / movimiento puntual",
                        f"📦 Eliminar la serie / evento general completo ('{concepto_raiz}')"
                    ]
                )

                if alcance_elim.startswith("📌"):
                    s_del = str(reg_mod.get("serie_comprobante") or "")
                    n_del = str(reg_mod.get("numero_comprobante") or "")
                    s_del = "" if s_del.lower() == "nan" else s_del
                    n_del = "" if n_del.lower() == "nan" else n_del
                    
                    f_pago_del = parsear_fecha_segura(reg_mod.get("fecha_pago"), date.today())
                    folio_del, _, _, _ = obtener_folio_comprobante(s_del, n_del, reg_mod["codigo"], f_pago_del)

                    st.warning(f"⚠️ Se eliminará **únicamente** la cuota **{reg_mod['codigo']}** ({reg_mod['concepto']}). Si ya estaba liquidada, su asiento contable se revertirá de Tesorería.")
                    if st.button("Confirmar Eliminación de Esta Cuota", type="primary"):
                        core.query_db("DELETE FROM pagos_programados WHERE id=?", (id_mod,))
                        core.query_db("DELETE FROM movimientos WHERE comprobante=? OR comprobante=?", (folio_del, reg_mod["codigo"]))
                        core.registrar_log("Pagos Programados", "Eliminación Puntual", f"Eliminada cuota {reg_mod['codigo']}")
                        st.toast(f"🗑️ Cuota {reg_mod['codigo']} eliminada correctamente.")
                        st.rerun()

                else:
                    df_serie = core.read_db(
                        "SELECT * FROM pagos_programados WHERE concepto LIKE ? OR concepto = ?",
                        (f"{concepto_raiz}%", concepto_raiz)
                    )
                    cant_serie = len(df_serie)
                    st.error(f"🚨 **¡ATENCIÓN!** Se eliminarán **todas las {cant_serie} cuotas** vinculadas a la serie **'{concepto_raiz}'** (tanto pendientes como pagadas).")
                    st.write(f"Cuotas incluidas en la serie: {', '.join(df_serie['codigo'].tolist())}")

                    if st.button(f"Confirmar Eliminación de la Serie Completa ({cant_serie} cuotas)", type="primary"):
                        for _, r_s in df_serie.iterrows():
                            s_s = str(r_s.get("serie_comprobante") or "")
                            n_s = str(r_s.get("numero_comprobante") or "")
                            s_s = "" if s_s.lower() == "nan" else s_s
                            n_s = "" if n_s.lower() == "nan" else n_s
                            f_pago_s = parsear_fecha_segura(r_s.get("fecha_pago"), date.today())
                            f_folio_s, _, _, _ = obtener_folio_comprobante(s_s, n_s, r_s["codigo"], f_pago_s)
                            
                            core.query_db("DELETE FROM movimientos WHERE comprobante=? OR comprobante=?", (f_folio_s, r_s["codigo"]))

                        core.query_db(
                            "DELETE FROM pagos_programados WHERE concepto LIKE ? OR concepto = ?",
                            (f"{concepto_raiz}%", concepto_raiz)
                        )

                        core.registrar_log("Pagos Programados", "Eliminación Serie General", f"Eliminada serie completa '{concepto_raiz}' ({cant_serie} registros)")
                        st.toast(f"🗑️ Serie '{concepto_raiz}' ({cant_serie} cuotas) y sus asientos contables eliminados.")
                        st.rerun()
