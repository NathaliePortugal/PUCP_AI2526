import streamlit as st

from config import LEADS
from data.loader import get_registros_disponibles, cargar
from visualization.plotter import plot_lead

st.set_page_config(page_title="ECG Viewer", layout="wide", page_icon="🫀")
st.title("🫀 Visualizador ECG")

registros = get_registros_disponibles()

if not registros:
    st.error("No se encontraron archivos .hea en la carpeta 'Muestra'.")
    st.stop()

with st.sidebar:
    st.header("⚙️ Configuración")
    rid_sel   = st.selectbox("Paciente", registros)
    segundos  = st.slider("Segundos a mostrar", 2.0, 15.0, 5.0, 0.5)
    leads_sel = st.multiselect("Derivaciones", LEADS, default=['I', 'II', 'III'])
    st.caption(f"Total pacientes: {len(registros)}")

t, señales, etiqueta, fs = cargar(rid_sel)

col1, col2, col3 = st.columns(3)
col1.metric("Paciente",   rid_sel)
col2.metric("Duración",   f"{t[-1]:.1f} s")
col3.metric("Frecuencia", f"{fs} Hz")

st.markdown(f"**Diagnóstico:** `{etiqueta}`")
st.divider()

if not leads_sel:
    st.warning("Selecciona al menos una derivación en el sidebar.")
else:
    for lead in leads_sel:
        if lead in señales:
            fig = plot_lead(t, señales[lead], lead, segundos)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"Derivación {lead} no disponible en este registro.")
