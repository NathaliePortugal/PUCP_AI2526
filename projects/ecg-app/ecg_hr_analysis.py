import neurokit2 as nk
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

FS = 500

LEAD_COLORS = {
    "I":   "#378ADD",
    "II":  "#D85A30",
    "III": "#3B6D11",
}


# ------------------------------------------------------------------
# 1. DETECCIÓN DE PICOS R Y HR
# ------------------------------------------------------------------
def analizar_derivada(signal: np.ndarray, nombre: str) -> dict:
    try:
        limpia  = nk.ecg_clean(signal, sampling_rate=FS)
        _, info = nk.ecg_peaks(limpia, sampling_rate=FS)
        r_peaks = info["ECG_R_Peaks"]

        if len(r_peaks) < 2:
            return {"nombre": nombre, "r_peaks": r_peaks,
                    "hr_media": None, "hr_serie": None, "error": "Pocos picos"}

        hr_serie = nk.ecg_rate(r_peaks, sampling_rate=FS, desired_length=len(signal))
        hr_media = float(np.mean(hr_serie))

        return {"nombre": nombre, "r_peaks": r_peaks,
                "hr_media": hr_media, "hr_serie": hr_serie, "error": None}

    except Exception as e:
        return {"nombre": nombre, "r_peaks": np.array([]),
                "hr_media": None, "hr_serie": None, "error": str(e)}


# ------------------------------------------------------------------
# 2. GRÁFICO: subplots separados por derivada
# ------------------------------------------------------------------
def grafico_comparativo(señales: dict, segundos: float) -> go.Figure:
    leads  = [l for l in ["I", "II", "III"] if l in señales]
    n      = int(segundos * FS)
    tiempo = np.linspace(0, segundos, n)

    # Títulos con color embebido en anotación — más visibles que subplot_titles
    fig = make_subplots(
        rows=len(leads), cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=[""] * len(leads),
    )

    for i, lead in enumerate(leads, start=1):
        signal    = señales[lead][:n]
        resultado = analizar_derivada(signal, lead)
        color     = LEAD_COLORS[lead]
        es_elegida = lead == "II"
        label     = f"Derivada {lead}" + ("  ✓ elegida" if es_elegida else "")

        fig.add_annotation(
            text=f"<b>{label}</b>",
            xref="paper", yref="paper",
            x=0.0,
            y=1 - (i - 1) / len(leads) + 0.02,
            xanchor="left", yanchor="bottom",
            showarrow=False,
            font=dict(size=13, color=color),
        )

        fig.add_trace(go.Scatter(
            x=tiempo, y=signal,
            line=dict(color=color, width=1.6),
            showlegend=False,
        ), row=i, col=1)

        if resultado["r_peaks"] is not None and len(resultado["r_peaks"]) > 0:
            picos = resultado["r_peaks"][resultado["r_peaks"] < n]
            fig.add_trace(go.Scatter(
                x=tiempo[picos], y=signal[picos],
                mode="markers",
                marker=dict(color=color, size=9, symbol="circle",
                            line=dict(width=1.5, color="white")),
                showlegend=False,
            ), row=i, col=1)

        fig.update_yaxes(
            row=i, col=1,
            title_text="mV",
            title_font=dict(size=11),
            showgrid=True,
            gridcolor="rgba(180,140,120,0.2)",
            gridwidth=0.5,
            linecolor=color if es_elegida else "rgba(255,255,255,0.15)",
            linewidth=2 if es_elegida else 1,
        )

    fig.update_xaxes(
        title_text="Tiempo (s)", row=len(leads), col=1,
        showgrid=True, gridcolor="rgba(180,140,120,0.2)", gridwidth=0.5,
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#fff8f5",
        height=300 * len(leads),
        margin=dict(l=50, r=20, t=50, b=40),
        font=dict(color="#cccccc", size=12),
    )
    return fig

# ------------------------------------------------------------------
# 3. TABLA COMPARATIVA
# ------------------------------------------------------------------
def tabla_comparativa(señales: dict, segundos: float) -> pd.DataFrame:
    n     = int(segundos * FS)
    filas = []

    for lead in ["I", "II", "III"]:
        if lead not in señales:
            continue

        signal = señales[lead][:n]
        r      = analizar_derivada(signal, lead)
        limpia = nk.ecg_clean(signal, sampling_rate=FS)
        snr    = np.max(np.abs(limpia)) / (np.std(limpia) + 1e-9)

        filas.append({
            "Derivada":     lead,
            "BPM medio":    f"{r['hr_media']:.1f}" if r["hr_media"] else "—",
            "Picos R det.": int(len(r["r_peaks"])),
            "SNR aprox.":   f"{snr:.1f}",
            "Elegida":      "✓" if lead == "II" else "",
        })

    return pd.DataFrame(filas)


# ------------------------------------------------------------------
# 4. SECCIÓN STREAMLIT PRINCIPAL
# ------------------------------------------------------------------
def mostrar_analisis_hr(señales: dict, segundos: float):
    st.markdown("---")
    st.subheader("📊 Análisis de Frecuencia Cardiaca — Fase 2")

    if "II" not in señales:
        st.error("La Derivada II no está disponible en este paciente.")
        return

    n         = int(segundos * FS)
    signal_II = señales["II"][:n]
    resultado = analizar_derivada(signal_II, "II")
    hr        = resultado["hr_media"]
    n_picos   = int(len(resultado["r_peaks"]))
    intervalo = round(60 / hr, 3) if hr else None

    # --- Métricas ---
    col1, col2, col3 = st.columns(3)
    col1.metric("❤️ Frec. Cardiaca (Deriv. II)", f"{hr:.1f} BPM" if hr else "N/A")
    col2.metric("Picos R detectados", n_picos)
    col3.metric("Intervalo RR medio", f"{intervalo} s" if intervalo else "N/A",
                help="RR = 60 / BPM  →  inverso de la frecuencia cardiaca")

    # --- Alerta clínica ---
    if hr is None:
        st.warning("⚠️ No se pudo calcular la frecuencia cardiaca.")
    elif hr < 60:
        st.warning(f"⚠️ **Bradicardia**: {hr:.1f} BPM — por debajo del rango normal (60–100 BPM).")
    elif hr > 100:
        st.error(f"🚨 **Taquicardia**: {hr:.1f} BPM — por encima del rango normal (60–100 BPM).")
    else:
        st.success(f"✅ Frecuencia normal: {hr:.1f} BPM  (rango 60–100 BPM).")

    # --- Gráfico ---
    st.markdown("#### Comparativa de detección por derivada")
    st.caption(
        "Cada derivada en su propia fila. Los puntos marcan los picos R detectados. "
        "Derivada II (coral) es la elegida por mayor amplitud de onda R."
    )
    st.plotly_chart(grafico_comparativo(señales, segundos), use_container_width=True)

    # --- Tabla ---
    st.markdown("#### Métricas por derivada")

    def highlight_elegida(row):
        color = "rgba(216,90,48,0.15)" if row["Elegida"] == "✓" else ""
        return [f"background-color: {color}"] * len(row)

    tabla = tabla_comparativa(señales, segundos)
    st.dataframe(
        tabla.style.apply(highlight_elegida, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "**SNR aprox.** = |pico máximo| / desviación estándar de la señal limpia.  "
        "Mayor valor → onda R más distinguible del ruido de fondo."
    )