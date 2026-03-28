"""
Página de evaluación del clasificador de intenciones.
Accesible desde el sidebar de Streamlit automáticamente.
"""

import os
import sys
from collections import defaultdict
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from app.services.intent_service import IntentService
from app.data.test_cases.intent_test_cases import INTENT_TEST_CASES

st.set_page_config(page_title="Evaluación · Sunatito", page_icon="🧪", layout="wide")

st.markdown(
    """
    <style>
        .eval-header {
            background-color: #003876;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }
        .eval-header h1 { color: white; font-size: 1.4rem; margin: 0; }
        .metric-good  { color: #1a7a1a; font-weight: 700; }
        .metric-ok    { color: #b38600; font-weight: 700; }
        .metric-bad   { color: #c0392b; font-weight: 700; }
    </style>
    <div class="eval-header">
        <h1>🧪 Evaluación del Clasificador de Intenciones</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    f"Evalúa el `IntentService` contra **{len(INTENT_TEST_CASES)} casos de prueba** "
    "independientes de los ejemplos de entrenamiento."
)


# ---------------------------------------------------------------------------
# Funciones de métricas (sin sklearn)
# ---------------------------------------------------------------------------

def calcular_metricas(y_true: List[str], y_pred: List[str]) -> Dict:
    intents = sorted(set(y_true))
    vp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)
    correctos = 0

    for real, pred in zip(y_true, y_pred):
        if real == pred:
            vp[real] += 1
            correctos += 1
        else:
            fp[pred] += 1
            fn[real] += 1

    accuracy = correctos / len(y_true) if y_true else 0
    por_clase = {}

    for intent in intents:
        precision = vp[intent] / (vp[intent] + fp[intent]) if (vp[intent] + fp[intent]) > 0 else 0.0
        recall    = vp[intent] / (vp[intent] + fn[intent]) if (vp[intent] + fn[intent]) > 0 else 0.0
        f1        = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        por_clase[intent] = {
            "precision": round(precision, 3),
            "recall":    round(recall, 3),
            "f1":        round(f1, 3),
            "soporte":   vp[intent] + fn[intent],
        }

    macro_f1 = sum(m["f1"] for m in por_clase.values()) / len(por_clase) if por_clase else 0
    return {"accuracy": round(accuracy, 4), "macro_f1": round(macro_f1, 4), "por_clase": por_clase}


def construir_matriz_confusion(y_true, y_pred, intents):
    matriz = {i: {j: 0 for j in intents} for i in intents}
    for real, pred in zip(y_true, y_pred):
        if real in matriz and pred in matriz:
            matriz[real][pred] += 1
    return matriz


# ---------------------------------------------------------------------------
# Botón de evaluación
# ---------------------------------------------------------------------------

if st.button("▶ Ejecutar evaluación", type="primary", use_container_width=False):
    with st.spinner("Cargando modelo y evaluando casos de prueba..."):

        @st.cache_resource
        def cargar_classifier():
            return IntentService()

        classifier = cargar_classifier()

        y_true, y_pred, scores, errores, detalle = [], [], [], [], []

        for caso in INTENT_TEST_CASES:
            resultado  = classifier.classify_topic(caso["text"])
            predicho   = resultado.intent
            esperado   = caso["expected_intent"]
            confianza  = resultado.confidence
            correcto   = predicho == esperado

            y_true.append(esperado)
            y_pred.append(predicho)
            scores.append(confianza)
            detalle.append({
                "texto":    caso["text"],
                "esperado": esperado,
                "predicho": predicho,
                "confianza": round(confianza, 3),
                "correcto": correcto,
            })
            if not correcto:
                errores.append(detalle[-1])

        metricas = calcular_metricas(y_true, y_pred)
        intents  = sorted(set(y_true))
        matriz   = construir_matriz_confusion(y_true, y_pred, intents)

    # -----------------------------------------------------------------------
    # Métricas globales
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("Resultados globales")

    acc    = metricas["accuracy"] * 100
    mf1    = metricas["macro_f1"] * 100
    n_ok   = len(INTENT_TEST_CASES) - len(errores)
    conf_m = sum(scores) / len(scores)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Accuracy",       f"{acc:.1f}%")
    c2.metric("Macro F1",       f"{mf1:.1f}%")
    c3.metric("Aciertos / Total", f"{n_ok} / {len(INTENT_TEST_CASES)}")
    c4.metric("Confianza media", f"{conf_m:.3f}")

    if acc >= 85:
        st.success(f"✅ Nivel BUENO — el clasificador funciona bien para producción académica.")
    elif acc >= 70:
        st.warning(f"⚠️ Nivel ACEPTABLE — considera agregar ejemplos a los intents con F1 bajo.")
    else:
        st.error(f"❌ Necesita mejora — revisa los intents confundidos y agrega más ejemplos.")

    # -----------------------------------------------------------------------
    # Gráficos
    # -----------------------------------------------------------------------
    import pandas as pd
    import plotly.graph_objects as go

    st.divider()
    st.subheader("📊 Visualización")

    graf_col1, graf_col2 = st.columns([1, 2])

    # Gráfico 1: Dona — aciertos vs errores
    with graf_col1:
        st.markdown("**¿Cuántos clasificó bien?**")
        st.caption("Verde = correctos · Rojo = errores")
        fig_dona = go.Figure(go.Pie(
            labels=["Correctos", "Errores"],
            values=[n_ok, len(errores)],
            hole=0.6,
            marker_colors=["#2ecc71", "#e74c3c"],
            textinfo="label+percent",
            textfont_size=13,
        ))
        fig_dona.update_layout(
            showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            height=260,
            annotations=[dict(
                text=f"<b>{acc:.0f}%</b>",
                x=0.5, y=0.5,
                font_size=22,
                showarrow=False,
            )],
        )
        st.plotly_chart(fig_dona, use_container_width=True)

    # Gráfico 2: Barras horizontales — Precision, Recall y F1 por intención
    with graf_col2:
        st.markdown("**Precision, Recall y F1 por intención**")
        st.caption(
            "**Precision** = de lo que predijo como X, ¿cuánto era X?  "
            "**Recall** = de todos los X reales, ¿cuántos encontró?  "
            "**F1** = balance entre ambos"
        )

        nombres   = [i.replace("_", " ") for i in sorted(metricas["por_clase"])]
        precision = [metricas["por_clase"][i]["precision"] * 100 for i in sorted(metricas["por_clase"])]
        recall    = [metricas["por_clase"][i]["recall"]    * 100 for i in sorted(metricas["por_clase"])]
        f1_vals   = [metricas["por_clase"][i]["f1"]        * 100 for i in sorted(metricas["por_clase"])]

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            name="Precision", y=nombres, x=precision,
            orientation="h", marker_color="#3498db",
            text=[f"{v:.0f}%" for v in precision], textposition="auto",
        ))
        fig_bar.add_trace(go.Bar(
            name="Recall", y=nombres, x=recall,
            orientation="h", marker_color="#f39c12",
            text=[f"{v:.0f}%" for v in recall], textposition="auto",
        ))
        fig_bar.add_trace(go.Bar(
            name="F1", y=nombres, x=f1_vals,
            orientation="h", marker_color="#2ecc71",
            text=[f"{v:.0f}%" for v in f1_vals], textposition="auto",
        ))
        fig_bar.update_layout(
            barmode="group",
            xaxis=dict(range=[0, 110], ticksuffix="%"),
            yaxis=dict(autorange="reversed"),
            legend=dict(orientation="h", y=1.1),
            margin=dict(t=30, b=10, l=10, r=10),
            height=300,
        )
        # Línea de referencia en 80%
        fig_bar.add_vline(
            x=80, line_dash="dash", line_color="#e74c3c",
            annotation_text="80% objetivo", annotation_position="top right",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # -----------------------------------------------------------------------
    # Métricas por intención
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("Métricas por intención")

    rows = []
    for intent, m in sorted(metricas["por_clase"].items()):
        icono = "✅" if m["f1"] >= 0.8 else ("⚠️" if m["f1"] >= 0.5 else "❌")
        rows.append({
            "": icono,
            "Intención":  intent,
            "Precision":  f"{m['precision']*100:.1f}%",
            "Recall":     f"{m['recall']*100:.1f}%",
            "F1":         f"{m['f1']*100:.1f}%",
            "Casos (N)":  m["soporte"],
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # -----------------------------------------------------------------------
    # Matriz de confusión
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("Matriz de confusión")
    st.caption("Filas = intención real · Columnas = intención predicha · Diagonal = aciertos")

    matriz_df = pd.DataFrame(
        [[matriz[r][c] for c in intents] for r in intents],
        index=intents,
        columns=intents,
    )

    # Resaltar la diagonal con colores
    def resaltar(val, es_diagonal):
        if es_diagonal and val > 0:
            return "background-color: #d4edda; font-weight: bold"
        elif not es_diagonal and val > 0:
            return "background-color: #f8d7da"
        return ""

    styled = matriz_df.style.apply(
        lambda col: [
            resaltar(v, col.name == intents[i])
            for i, v in enumerate(col)
        ],
        axis=0,
    )
    st.dataframe(styled, use_container_width=True)

    # -----------------------------------------------------------------------
    # Detalle de cada caso
    # -----------------------------------------------------------------------
    st.divider()
    col_ok, col_err = st.columns(2)

    with col_err:
        st.subheader(f"❌ Errores ({len(errores)})")
        if errores:
            for e in errores:
                with st.expander(f'"{e["texto"][:55]}..."'):
                    st.write(f"**Esperado:** `{e['esperado']}`")
                    st.write(f"**Predicho:** `{e['predicho']}`")
                    st.write(f"**Confianza:** {e['confianza']}")
        else:
            st.success("¡Sin errores!")

    with col_ok:
        st.subheader(f"✅ Aciertos ({n_ok})")
        aciertos = [d for d in detalle if d["correcto"]]
        for a in aciertos:
            with st.expander(f'"{a["texto"][:55]}..."'):
                st.write(f"**Intent:** `{a['predicho']}`")
                st.write(f"**Confianza:** {a['confianza']}")

else:
    st.info("Haz clic en **▶ Ejecutar evaluación** para correr los tests.")

    st.markdown("### ¿Qué mide esta evaluación?")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**Accuracy**
% de mensajes clasificados correctamente sobre el total.

**Macro F1**
Promedio del F1 de cada intención. Penaliza si alguna intención
funciona mal aunque el promedio global sea alto.
        """)
    with col2:
        st.markdown("""
**Precision** (por intención)
De los mensajes que el modelo clasificó como X, ¿cuántos eran realmente X?

**Recall** (por intención)
De todos los mensajes que eran X, ¿cuántos encontró el modelo?
        """)

    st.markdown("### Casos de prueba cargados")
    import pandas as pd
    import plotly.graph_objects as go
    df = pd.DataFrame([
        {"Texto": c["text"], "Intent esperado": c["expected_intent"]}
        for c in INTENT_TEST_CASES
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)
