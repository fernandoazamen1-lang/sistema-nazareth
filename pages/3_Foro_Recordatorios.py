import streamlit as st
import core
from datetime import date

st.set_page_config(page_title="Foro y Recordatorios", page_icon="💬", layout="wide")
core.aplicar_estilos_base()

st.subheader("💬 Foro Interno y Recordatorios")
opcion = st.radio("Acción:", ["Tablón de Notas", "Publicar Recordatorio"], horizontal=True)

if opcion == "Tablón de Notas":
    df_foro = core.read_db("SELECT * FROM foro_recordatorios ORDER BY id DESC")
    if df_foro.empty:
        st.info("No hay notas registradas.")
    else:
        for _, r in df_foro.iterrows():
            with st.container():
                c1, c2 = st.columns([6, 2])
                with c1:
                    st.markdown(f"**{r['titulo']}** `[{r['prioridad'].upper()}]`")
                    st.write(r["contenido"])
                    st.caption(f"Autor: {r['autor']} | Límite: {r['fecha_limite'] or 'Sin fecha'}")
                with c2:
                    if r["leido"] == 0:
                        if st.button("Marcar Leído", key=f"f_lei_{r['id']}"):
                            core.query_db("UPDATE foro_recordatorios SET leido=1 WHERE id=?", (r["id"],))
                            st.rerun()
                    else:
                        st.caption("✅ Atendido")
                    if st.button("🗑️ Eliminar", key=f"f_del_{r['id']}"):
                        core.query_db("DELETE FROM foro_recordatorios WHERE id=?", (r["id"],))
                        st.toast("Nota eliminada.")
                        st.rerun()
            st.divider()

elif opcion == "Publicar Recordatorio":
    df_resp = core.read_db("SELECT nombre FROM responsables_catalogo ORDER BY nombre ASC")
    lista_resp = df_resp["nombre"].tolist() if not df_resp.empty else ["Secretaría", "Pastor Principal"]
    
    with st.form("form_nuevo_foro", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            autor = st.selectbox("Autor:", lista_resp)
            titulo = st.text_input("Título:")
        with c2:
            prioridad = st.selectbox("Prioridad:", ["Alta", "Media", "Baja"])
            limite = st.date_input("Fecha Límite:", value=date.today())
        contenido = st.text_area("Contenido / Tarea:")
        if st.form_submit_button("Publicar"):
            if titulo.strip() and contenido.strip():
                core.query_db(
                    "INSERT INTO foro_recordatorios (fecha_creacion, autor, titulo, contenido, fecha_limite, prioridad, leido) VALUES (?, ?, ?, ?, ?, ?, 0)",
                    (str(date.today()), autor, titulo.strip(), contenido.strip(), str(limite), prioridad)
                )
                st.toast("✅ Publicado en el foro.")
                st.rerun()
