import streamlit as st
import core
import os
import io
import pandas as pd
from datetime import date, datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Padrón de Miembros", page_icon="👥", layout="wide")
core.requerir_login()
core.inicializar_bd()
core.aplicar_estilos_base()

# ==============================================================================
# ASEGURAR ESTRUCTURA COMPLETA DE LA TABLA EN POSTGRESQL (AUTO-MIGRACIÓN)
# ==============================================================================
try:
    with core.get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS miembros (
                    id_miembro TEXT PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    telefono TEXT DEFAULT '',
                    direccion TEXT DEFAULT '',
                    fecha_nacimiento TEXT DEFAULT '',
                    estado_civil TEXT DEFAULT 'Soltero(a)',
                    bautizado TEXT DEFAULT 'No',
                    miembro_pleno TEXT DEFAULT 'No',
                    cargo_eclesiastico TEXT DEFAULT 'Miembro Activo',
                    foto TEXT DEFAULT '',
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            columnas_requeridas = [
                ("telefono", "TEXT DEFAULT ''"),
                ("direccion", "TEXT DEFAULT ''"),
                ("fecha_nacimiento", "TEXT DEFAULT ''"),
                ("estado_civil", "TEXT DEFAULT 'Soltero(a)'"),
                ("bautizado", "TEXT DEFAULT 'No'"),
                ("miembro_pleno", "TEXT DEFAULT 'No'"),
                ("cargo_eclesiastico", "TEXT DEFAULT 'Miembro Activo'"),
                ("foto", "TEXT DEFAULT ''"),
                ("fecha_registro", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            ]
            for col, tipo in columnas_requeridas:
                try:
                    cur.execute(f"ALTER TABLE miembros ADD COLUMN IF NOT EXISTS {col} {tipo};")
                except Exception:
                    pass
        conn.commit()
except Exception:
    pass

CARPETA_FOTOS = "fotos_miembros"
os.makedirs(CARPETA_FOTOS, exist_ok=True)

st.subheader("👥 Padrón General de Miembros")
opcion = st.radio(
    "Acción:", 
    ["Ver Miembros", "Registrar Miembro", "✏️ Editar Miembro", "📥 Carga Masiva (Excel)", "Eliminar Miembro"], 
    horizontal=True
)

# Obtener miembros ordenados; si fecha_registro es nula, ordena por id_miembro
df_m = core.read_db("""
    SELECT ROW_NUMBER() OVER(ORDER BY COALESCE(fecha_registro, '1970-01-01'::timestamp) ASC, id_miembro ASC) as nro_orden, * 
    FROM miembros 
    ORDER BY COALESCE(fecha_registro, '1970-01-01'::timestamp) ASC, id_miembro ASC
""")

LISTA_CARGOS = [
    "Miembro Activo", 
    "Pastor Principal", 
    "Copastor", 
    "Líder de Jóvenes", 
    "Líder de Damas", 
    "Líder de Varones", 
    "Diácono", 
    "Músico / Alabanza", 
    "Tesorero(a)", 
    "Secretario(a)", 
    "Maestro(a) Escuela Dominical"
]

def generar_pdf_padron(df_exportar, columnas_visibles):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=20, rightMargin=20, topMargin=25, bottomMargin=25)
    elementos = []

    t_header = Table([[
        Paragraph("<b>IGLESIA EVANGÉLICA \"NAZARETH\" — ASAMBLEAS DE DIOS DEL PERÚ</b><br/><font size=8.5 color='#334155'>PADRÓN OFICIAL DE MIEMBROS REGISTRADOS</font>",
                  ParagraphStyle('H1', fontName='Helvetica-Bold', fontSize=10.5, alignment=1))
    ]], colWidths=[752])
    t_header.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#EFF6FF")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#1D4ED8")),
        ('PADDING', (0,0), (-1,-1), 6)
    ]))
    elementos.append(t_header)
    elementos.append(Spacer(1, 10))

    encabezados = ["N°"] + columnas_visibles
    datos_tabla = [encabezados]

    for _, fila in df_exportar.iterrows():
        fila_datos = [str(fila["N°"])]
        for col in columnas_visibles:
            fila_datos.append(str(fila.get(col, ""))[:28])
        datos_tabla.append(fila_datos)

    ancho_disponible = 752
    ancho_nro = 30
    ancho_resto = (ancho_disponible - ancho_nro) / max(1, len(columnas_visibles))
    anchos = [ancho_nro] + [ancho_resto] * len(columnas_visibles)

    t_datos = Table(datos_tabla, colWidths=anchos)
    t_datos.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('PADDING', (0,0), (-1,-1), 3.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")])
    ]))
    elementos.append(t_datos)

    doc.build(elementos)
    return buf.getvalue()

def generar_excel_bytes(df_a_exportar):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_a_exportar.to_excel(writer, index=False, sheet_name="Padron_Miembros")
    return output.getvalue()

def generar_plantilla_excel():
    columnas_plantilla = [
        "DNI_Codigo", "Nombres_y_Apellidos", "Telefono", "Direccion",
        "Fecha_Nacimiento", "Estado_Civil", "Bautizado", "Miembro_Pleno", "Cargo_Eclesiastico"
    ]
    ejemplos = [
        {
            "DNI_Codigo": "70123456",
            "Nombres_y_Apellidos": "Juan Carlos Pérez Morales",
            "Telefono": "987654321",
            "Direccion": "Av. Los Próceres 123",
            "Fecha_Nacimiento": "1990-05-15",
            "Estado_Civil": "Casado(a)",
            "Bautizado": "Sí",
            "Miembro_Pleno": "Sí",
            "Cargo_Eclesiastico": "Diácono"
        },
        {
            "DNI_Codigo": "75984123",
            "Nombres_y_Apellidos": "María Elena Gómez Ruiz",
            "Telefono": "912345678",
            "Direccion": "Jr. Trujillo 450",
            "Fecha_Nacimiento": "1995-10-22",
            "Estado_Civil": "Soltero(a)",
            "Bautizado": "Sí",
            "Miembro_Pleno": "No",
            "Cargo_Eclesiastico": "Líder de Jóvenes"
        }
    ]
    df_plantilla = pd.DataFrame(ejemplos, columns=columnas_plantilla)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_plantilla.to_excel(writer, index=False, sheet_name="Plantilla_Miembros")
    return output.getvalue()

# ==============================================================================
# VISTA 1: VER MIEMBROS (FILTROS, TABLA, PDF Y EXCEL)
# ==============================================================================
if opcion == "Ver Miembros":
    if df_m.empty:
        st.info("Aún no hay miembros inscritos en el padrón.")
    else:
        mapa_cols = {
            "id_miembro": "DNI / Código",
            "nombre": "Nombres y Apellidos",
            "telefono": "Teléfono",
            "direccion": "Dirección",
            "fecha_nacimiento": "F. Nacimiento",
            "estado_civil": "Estado Civil",
            "bautizado": "Bautizado",
            "miembro_pleno": "Miembro Pleno",
            "cargo_eclesiastico": "Cargo Eclesiástico"
        }
        df_mostrar = df_m.rename(columns=mapa_cols)
        df_mostrar["N°"] = df_mostrar["nro_orden"]

        with st.expander("🔍 **Filtros de Búsqueda y Columnas Personalizadas**", expanded=True):
            col_b1, col_b2, col_b3 = st.columns([3, 2, 2])
            with col_b1:
                buscar_txt = st.text_input("Buscar por Nombre, DNI o Dirección:", placeholder="Escribe para buscar...")
            with col_b2:
                filtro_baut = st.selectbox("Bautismo:", ["Todos", "Sí", "No"])
            with col_b3:
                filtro_cargo = st.selectbox("Cargo:", ["Todos"] + sorted(list(df_mostrar["Cargo Eclesiástico"].dropna().unique())))

            st.markdown("##### 🎛️ Columnas a mostrar en Pantalla, PDF y Excel:")
            opciones_columnas = list(mapa_cols.values())
            columnas_seleccionadas = st.multiselect(
                "Seleccione o quite columnas flotantes:",
                options=opciones_columnas,
                default=["DNI / Código", "Nombres y Apellidos", "Teléfono", "Estado Civil", "Bautizado", "Cargo Eclesiástico"]
            )

        df_filtrado = df_mostrar.copy()
        if buscar_txt.strip():
            df_filtrado = df_filtrado[
                df_filtrado["Nombres y Apellidos"].astype(str).str.contains(buscar_txt, case=False, na=False) |
                df_filtrado["DNI / Código"].astype(str).str.contains(buscar_txt, case=False, na=False) |
                df_filtrado["Dirección"].astype(str).str.contains(buscar_txt, case=False, na=False)
            ]
        if filtro_baut != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Bautizado"] == filtro_baut]
        if filtro_cargo != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Cargo Eclesiástico"] == filtro_cargo]

        cols_finales = ["N°"] + columnas_seleccionadas
        st.markdown(f"**Total Miembros encontrados:** `{len(df_filtrado)}`")
        st.dataframe(df_filtrado[cols_finales], use_container_width=True, hide_index=True)

        col_pdf, col_xls, _ = st.columns([3, 3, 4])
        with col_pdf:
            if columnas_seleccionadas:
                pdf_bytes = generar_pdf_padron(df_filtrado, columnas_seleccionadas)
                st.download_button(
                    label="📄 Descargar Padrón en PDF",
                    data=pdf_bytes,
                    file_name=f"Padron_Nazareth_{date.today()}.pdf",
                    mime="application/pdf"
                )
        with col_xls:
            if columnas_seleccionadas:
                excel_bytes = generar_excel_bytes(df_filtrado[cols_finales])
                st.download_button(
                    label="📊 Descargar Padrón en Excel (.xlsx)",
                    data=excel_bytes,
                    file_name=f"Padron_Miembros_Nazareth_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary"
                )

        st.markdown("---")
        st.subheader("👤 Ficha y Tarjeta Individual del Miembro")
        lista_nombres = df_filtrado["Nombres y Apellidos"].tolist() if not df_filtrado.empty else df_mostrar["Nombres y Apellidos"].tolist()
        
        miembro_sel = st.selectbox("Seleccione un Miembro para desplegar su ficha completa:", lista_nombres)
        if miembro_sel:
            datos_m = df_m[df_m["nombre"] == miembro_sel].iloc[0]
            with st.container():
                col_foto, col_info = st.columns([1, 3])
                with col_foto:
                    foto_path = str(datos_m.get("foto", ""))
                    if foto_path and (foto_path.startswith("http") or os.path.exists(foto_path)):
                        st.image(foto_path, width=180, caption=f"Registro N° {datos_m['nro_orden']}")
                    else:
                        st.info("Sin Fotografía\nRegistrada")
                with col_info:
                    st.markdown(f"### {datos_m['nombre']}")
                    c_i1, c_i2 = st.columns(2)
                    with c_i1:
                        st.write(f"🪪 **DNI / Código:** {datos_m['id_miembro']}")
                        st.write(f"📞 **Teléfono:** {datos_m.get('telefono', '') or 'No registrado'}")
                        st.write(f"🏠 **Dirección:** {datos_m.get('direccion', '') or 'No registrada'}")
                        st.write(f"🎂 **Fecha de Nacimiento:** {datos_m.get('fecha_nacimiento', '') or 'No registrada'}")
                    with c_i2:
                        st.write(f"💍 **Estado Civil:** {datos_m.get('estado_civil', 'Soltero(a)')}")
                        st.write(f"🌊 **Bautizado en Agua:** {datos_m.get('bautizado', 'No')}")
                        st.write(f"📜 **Miembro Pleno:** {datos_m.get('miembro_pleno', 'No')}")
                        st.write(f"✝️ **Cargo Eclesiástico:** {datos_m.get('cargo_eclesiastico', 'Miembro Activo')}")

# ==============================================================================
# VISTA 2: REGISTRAR MIEMBRO CON FOTOGRAFÍA (NUBE)
# ==============================================================================
elif opcion == "Registrar Miembro":
    st.markdown("#### ➕ Formulario de Afiliación / Registro Eclesiástico")
    
    with st.form("form_registro_miembro_completo", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            d_id = st.text_input("DNI / Código de Identificación:", placeholder="Ej. 74859612")
            d_nom = st.text_input("Nombres y Apellidos Completos:", placeholder="Ej. Carlos Mendoza Ríos")
            d_tel = st.text_input("Teléfono / Celular:", placeholder="Ej. 987654321")
            d_dir = st.text_input("Dirección de Domicilio:", placeholder="Ej. Jr. Trujillo 450")
            d_fnac = st.date_input("Fecha de Nacimiento:", min_value=date(1920, 1, 1), max_value=date.today())

        with col_f2:
            d_civil = st.selectbox("Estado Civil:", ["Soltero(a)", "Casado(a)", "Viudo(a)", "Divorciado(a)"])
            d_baut = st.selectbox("¿Es Bautizado en Agua?:", ["Sí", "No"])
            d_pleno = st.selectbox("¿Condición de Miembro Pleno?:", ["Sí", "No"])
            d_cargo = st.selectbox("Cargo Eclesiástico / Ministerio:", LISTA_CARGOS)
            d_foto_file = st.file_uploader("Fotografía del Miembro (Opcional):", type=["jpg", "png", "jpeg"])

        if st.form_submit_button("💾 Guardar Miembro en Padrón", type="primary"):
            if not d_id.strip() or not d_nom.strip():
                st.error("El DNI/Código y el Nombre completo son obligatorios.")
            else:
                ruta_foto_guardada = ""
                if d_foto_file is not None:
                    ruta_foto_guardada = core.comprimir_y_subir_foto(d_foto_file, f"miembro_{d_id.strip()}")

                core.query_db("""
                    INSERT INTO miembros 
                    (id_miembro, nombre, telefono, direccion, fecha_nacimiento, estado_civil, bautizado, miembro_pleno, cargo_eclesiastico, foto)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (id_miembro) DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    telefono = EXCLUDED.telefono,
                    direccion = EXCLUDED.direccion,
                    fecha_nacimiento = EXCLUDED.fecha_nacimiento,
                    estado_civil = EXCLUDED.estado_civil,
                    bautizado = EXCLUDED.bautizado,
                    miembro_pleno = EXCLUDED.miembro_pleno,
                    cargo_eclesiastico = EXCLUDED.cargo_eclesiastico,
                    foto = CASE WHEN EXCLUDED.foto <> '' THEN EXCLUDED.foto ELSE miembros.foto END
                """, (
                    d_id.strip(), d_nom.strip(), d_tel.strip(), d_dir.strip(),
                    str(d_fnac), d_civil, d_baut, d_pleno, d_cargo, ruta_foto_guardada
                ))
                core.registrar_log("Miembros", "Registro", f"Inscrito {d_nom.strip()} (DNI: {d_id.strip()})")
                st.toast("✅ Miembro registrado exitosamente.")
                st.rerun()

# ==============================================================================
# VISTA 3: EDITAR / MODIFICAR MIEMBRO (NUBE)
# ==============================================================================
elif opcion == "✏️ Editar Miembro":
    st.markdown("#### ✏️ Modificar o Corregir Datos de un Miembro")
    
    if df_m.empty:
        st.info("No hay miembros registrados para editar.")
    else:
        miembros_opciones = {f"{r['nombre']} (DNI: {r['id_miembro']})": r['id_miembro'] for _, r in df_m.iterrows()}
        seleccion_label = st.selectbox("Seleccione el Miembro que desea modificar:", list(miembros_opciones.keys()))
        dni_actual = miembros_opciones[seleccion_label]
        
        datos_actuales = df_m[df_m["id_miembro"] == dni_actual].iloc[0]

        f_nac_val = date(1990, 1, 1)
        if datos_actuales.get("fecha_nacimiento"):
            try:
                f_nac_val = datetime.strptime(str(datos_actuales["fecha_nacimiento"]), "%Y-%m-%d").date()
            except Exception:
                pass

        estados_civiles = ["Soltero(a)", "Casado(a)", "Viudo(a)", "Divorciado(a)"]
        idx_civil = estados_civiles.index(datos_actuales.get("estado_civil", "Soltero(a)")) if datos_actuales.get("estado_civil") in estados_civiles else 0
        
        sino = ["Sí", "No"]
        idx_baut = sino.index(datos_actuales.get("bautizado", "No")) if datos_actuales.get("bautizado") in sino else 1
        idx_pleno = sino.index(datos_actuales.get("miembro_pleno", "No")) if datos_actuales.get("miembro_pleno") in sino else 1
        
        cargo_act = datos_actuales.get("cargo_eclesiastico", "Miembro Activo")
        idx_cargo = LISTA_CARGOS.index(cargo_act) if cargo_act in LISTA_CARGOS else 0

        col_prev_foto, col_prev_info = st.columns([1, 4])
        with col_prev_foto:
            foto_existente = str(datos_actuales.get("foto", ""))
            if foto_existente and (foto_existente.startswith("http") or os.path.exists(foto_existente)):
                st.image(foto_existente, width=130, caption="Foto actual")
            else:
                st.caption("📷 Sin foto actual")

        with st.form("form_editar_miembro"):
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                edit_id = st.text_input("DNI / Código:", value=str(datos_actuales["id_miembro"]))
                edit_nom = st.text_input("Nombres y Apellidos Completos:", value=str(datos_actuales["nombre"]))
                edit_tel = st.text_input("Teléfono / Celular:", value=str(datos_actuales.get("telefono", "") or ""))
                edit_dir = st.text_input("Dirección de Domicilio:", value=str(datos_actuales.get("direccion", "") or ""))
                edit_fnac = st.date_input("Fecha de Nacimiento:", value=f_nac_val, min_value=date(1920, 1, 1), max_value=date.today())

            with col_e2:
                edit_civil = st.selectbox("Estado Civil:", estados_civiles, index=idx_civil)
                edit_baut = st.selectbox("¿Es Bautizado en Agua?:", sino, index=idx_baut)
                edit_pleno = st.selectbox("¿Condición de Miembro Pleno?:", sino, index=idx_pleno)
                edit_cargo = st.selectbox("Cargo Eclesiástico / Ministerio:", LISTA_CARGOS, index=idx_cargo)
                edit_foto_file = st.file_uploader("Subir nueva fotografía (reemplazará la actual):", type=["jpg", "png", "jpeg"])

            if st.form_submit_button("💾 Guardar Cambios", type="primary"):
                if not edit_id.strip() or not edit_nom.strip():
                    st.error("El DNI/Código y el Nombre completo no pueden estar vacíos.")
                else:
                    ruta_foto_final = foto_existente
                    if edit_foto_file is not None:
                        nueva_ruta = core.comprimir_y_subir_foto(edit_foto_file, f"miembro_{edit_id.strip()}")
                        if nueva_ruta:
                            ruta_foto_final = nueva_ruta
                            if foto_existente and not foto_existente.startswith("http") and os.path.exists(foto_existente):
                                try: os.remove(foto_existente)
                                except Exception: pass

                    core.query_db("""
                        UPDATE miembros SET
                            id_miembro = ?,
                            nombre = ?,
                            telefono = ?,
                            direccion = ?,
                            fecha_nacimiento = ?,
                            estado_civil = ?,
                            bautizado = ?,
                            miembro_pleno = ?,
                            cargo_eclesiastico = ?,
                            foto = ?
                        WHERE id_miembro = ?
                    """, (
                        edit_id.strip(), edit_nom.strip(), edit_tel.strip(), edit_dir.strip(),
                        str(edit_fnac), edit_civil, edit_baut, edit_pleno, edit_cargo,
                        ruta_foto_final, dni_actual
                    ))

                    if dni_actual != edit_id.strip() or datos_actuales["nombre"] != edit_nom.strip():
                        core.query_db("""
                            UPDATE diezmos SET id_miembro = ?, nombre_miembro = ? WHERE id_miembro = ?
                        """, (edit_id.strip(), edit_nom.strip(), dni_actual))

                    core.registrar_log("Miembros", "Edición", f"Actualizado miembro {edit_nom.strip()} (DNI: {edit_id.strip()})")
                    st.toast("✅ Datos actualizados con éxito.")
                    st.rerun()

# ==============================================================================
# VISTA 4: CARGA MASIVA MEDIANTE EXCEL
# ==============================================================================
elif opcion == "📥 Carga Masiva (Excel)":
    st.markdown("#### 📥 Importación Masiva de Miembros desde Archivo Excel")
    st.info("Descarga la plantilla estandarizada, completa los datos de los hermanos de la congregación y súbela para ingresarlos o actualizarlos automáticamente.")

    col_desc_plan, _ = st.columns([3, 4])
    with col_desc_plan:
        plantilla_bytes = generar_plantilla_excel()
        st.download_button(
            label="📄 Descargar Plantilla Excel (.xlsx)",
            data=plantilla_bytes,
            file_name="plantilla_miembros_nazareth.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.markdown("---")
    archivo_excel = st.file_uploader("Selecciona el archivo Excel completado (.xlsx o .xls):", type=["xlsx", "xls"])

    if archivo_excel is not None:
        try:
            df_import = pd.read_excel(archivo_excel)
            df_import.columns = [str(c).strip().replace(" ", "_") for c in df_import.columns]

            mapa_import = {
                "DNI_Codigo": "id_miembro",
                "Nombres_y_Apellidos": "nombre",
                "Telefono": "telefono",
                "Direccion": "direccion",
                "Fecha_Nacimiento": "fecha_nacimiento",
                "Estado_Civil": "estado_civil",
                "Bautizado": "bautizado",
                "Miembro_Pleno": "miembro_pleno",
                "Cargo_Eclesiastico": "cargo_eclesiastico"
            }

            columnas_presentes = [c for c in mapa_import.keys() if c in df_import.columns]
            if "DNI_Codigo" not in columnas_presentes or "Nombres_y_Apellidos" not in columnas_presentes:
                st.error("❌ El archivo no contiene las columnas requeridas: `DNI_Codigo` y `Nombres_y_Apellidos`.")
            else:
                st.markdown(f"##### 📋 Vista Previa de Registros a Importar ({len(df_import)} filas):")
                st.dataframe(df_import, use_container_width=True)

                if st.button("🚀 Confirmar e Importar al Padrón", type="primary"):
                    registros_nuevos = 0
                    registros_omitidos = 0

                    for _, fila in df_import.iterrows():
                        d_id = str(fila.get("DNI_Codigo", "")).split(".")[0].strip()
                        d_nom = str(fila.get("Nombres_y_Apellidos", "")).strip()

                        if not d_id or d_id.lower() == "nan" or not d_nom or d_nom.lower() == "nan":
                            registros_omitidos += 1
                            continue

                        d_tel = str(fila.get("Telefono", "")).split(".")[0].strip()
                        d_tel = "" if d_tel.lower() == "nan" else d_tel
                        
                        d_dir = str(fila.get("Direccion", "")).strip()
                        d_dir = "" if d_dir.lower() == "nan" else d_dir

                        raw_fnac = fila.get("Fecha_Nacimiento")
                        if pd.notnull(raw_fnac) and str(raw_fnac).strip().lower() != "nan":
                            try:
                                d_fnac = pd.to_datetime(raw_fnac).strftime("%Y-%m-%d")
                            except Exception:
                                d_fnac = str(raw_fnac).strip()
                        else:
                            d_fnac = ""

                        d_civil = str(fila.get("Estado_Civil", "Soltero(a)")).strip()
                        d_civil = "Soltero(a)" if d_civil.lower() == "nan" or not d_civil else d_civil

                        d_baut = str(fila.get("Bautizado", "No")).strip()
                        d_baut = "Sí" if d_baut.lower() in ("si", "sí", "s", "yes", "true", "1") else "No"

                        d_pleno = str(fila.get("Miembro_Pleno", "No")).strip()
                        d_pleno = "Sí" if d_pleno.lower() in ("si", "sí", "s", "yes", "true", "1") else "No"

                        d_cargo = str(fila.get("Cargo_Eclesiastico", "Miembro Activo")).strip()
                        d_cargo = "Miembro Activo" if d_cargo.lower() == "nan" or not d_cargo else d_cargo

                        core.query_db("""
                            INSERT INTO miembros 
                            (id_miembro, nombre, telefono, direccion, fecha_nacimiento, estado_civil, bautizado, miembro_pleno, cargo_eclesiastico, foto)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT foto FROM miembros WHERE id_miembro = ?), ''))
                            ON CONFLICT (id_miembro) DO UPDATE SET
                            nombre = EXCLUDED.nombre,
                            telefono = EXCLUDED.telefono,
                            direccion = EXCLUDED.direccion,
                            fecha_nacimiento = EXCLUDED.fecha_nacimiento,
                            estado_civil = EXCLUDED.estado_civil,
                            bautizado = EXCLUDED.bautizado,
                            miembro_pleno = EXCLUDED.miembro_pleno,
                            cargo_eclesiastico = EXCLUDED.cargo_eclesiastico
                        """, (
                            d_id, d_nom, d_tel, d_dir, d_fnac, d_civil, d_baut, d_pleno, d_cargo, d_id
                        ))
                        registros_nuevos += 1

                    core.registrar_log("Miembros", "Carga Masiva", f"Importados/actualizados {registros_nuevos} miembros.")
                    st.success(f"✅ ¡Carga completada con éxito! Se procesaron {registros_nuevos} registros correctamente (Omitidos: {registros_omitidos}).")
                    st.rerun()
        except Exception as e:
            st.error(f"Error al leer el archivo Excel: {e}")

# ==============================================================================
# VISTA 5: ELIMINAR MIEMBRO
# ==============================================================================
elif opcion == "Eliminar Miembro":
    st.markdown("#### 🗑️ Eliminar Registro de Miembro")
    if df_m.empty:
        st.info("No hay miembros para eliminar.")
    else:
        m_del = st.selectbox("Seleccione el Miembro que desea retirar del padrón:", df_m["nombre"].tolist())
        datos_del = df_m[df_m["nombre"] == m_del].iloc[0]
        st.warning(f"¿Confirma retirar a **{m_del}** (DNI: {datos_del['id_miembro']}) del sistema?")
        if st.button("Eliminar Definitivamente", type="primary"):
            foto_del = str(datos_del.get("foto", ""))
            if foto_del and not foto_del.startswith("http") and os.path.exists(foto_del):
                try: os.remove(foto_del)
                except Exception: pass
            
            core.query_db("DELETE FROM miembros WHERE id_miembro=?", (datos_del["id_miembro"],))
            core.registrar_log("Miembros", "Eliminación", f"Retirado {m_del}")
            st.toast("🗑️ Miembro eliminado.")
            st.rerun()
