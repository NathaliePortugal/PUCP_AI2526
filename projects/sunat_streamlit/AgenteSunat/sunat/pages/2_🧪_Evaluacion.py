"""
Página de evaluación del sistema Sunatito.
Accesible desde el sidebar de Streamlit automáticamente.

Tabs:
  1. Clasificador de intenciones — evalúa IntentService contra 30 casos
  2. Pipeline RAG — evalúa RagService contra 40 casos (hit@1 y hit@3)
"""

import os
import sys
from collections import defaultdict
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from app.services.intent_service import IntentService
from app.services.rag_service import RagService
from app.data.test_cases.intent_test_cases import INTENT_TEST_CASES
from app.data.test_cases.rag_test_cases import RAG_TEST_CASES

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
    </style>
    <div class="eval-header">
        <h1>🧪 Evaluación del Sistema Sunatito</h1>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Helpers de métricas (sin sklearn)
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
# Tabs principales
# ---------------------------------------------------------------------------

tab_intent, tab_rag = st.tabs(["🎯 Clasificador de Intenciones", "📚 Pipeline RAG"])


# ===========================================================================
# TAB 1 — Clasificador de Intenciones
# ===========================================================================

with tab_intent:
    st.caption(
        f"Evalúa el `IntentService` contra **{len(INTENT_TEST_CASES)} casos de prueba** "
        "distintos a los ejemplos de entrenamiento."
    )

    if st.button("▶ Ejecutar evaluación de intenciones", type="primary", key="btn_intent"):
        with st.spinner("Cargando modelo y clasificando casos..."):

            @st.cache_resource
            def cargar_intent_service():
                return IntentService()

            classifier = cargar_intent_service()

            y_true, y_pred, scores, detalle = [], [], [], []

            for caso in INTENT_TEST_CASES:
                resultado = classifier.classify_topic(caso["text"])
                predicho  = resultado.intent
                esperado  = caso["expected_intent"]
                confianza = resultado.confidence
                correcto  = predicho == esperado

                y_true.append(esperado)
                y_pred.append(predicho)
                scores.append(confianza)
                detalle.append({
                    "✓": "✅" if correcto else "❌",
                    "Texto": caso["text"],
                    "Esperado": esperado,
                    "Predicho": predicho,
                    "Confianza": round(confianza, 3),
                })

        metricas = calcular_metricas(y_true, y_pred)
        intents  = sorted(set(y_true))
        matriz   = construir_matriz_confusion(y_true, y_pred, intents)
        errores  = [d for d in detalle if d["✓"] == "❌"]
        n_ok     = len(INTENT_TEST_CASES) - len(errores)
        conf_m   = sum(scores) / len(scores)
        acc      = metricas["accuracy"] * 100
        mf1      = metricas["macro_f1"] * 100

        # --- Métricas globales ---
        st.divider()
        st.subheader("Resultados globales")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Accuracy",          f"{acc:.1f}%")
        c2.metric("Macro F1",          f"{mf1:.1f}%")
        c3.metric("Aciertos / Total",  f"{n_ok} / {len(INTENT_TEST_CASES)}")
        c4.metric("Confianza media",   f"{conf_m:.3f}")

        if acc >= 85:
            st.success("✅ Nivel BUENO — el clasificador funciona bien para producción académica.")
        elif acc >= 70:
            st.warning("⚠️ Nivel ACEPTABLE — considera agregar ejemplos a los intents con F1 bajo.")
        else:
            st.error("❌ Necesita mejora — revisa los intents confundidos y agrega más ejemplos.")

        # --- Gráficos ---
        import pandas as pd
        import plotly.graph_objects as go

        st.divider()
        st.subheader("📊 Visualización")

        graf_col1, graf_col2 = st.columns([1, 2])

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
            fig_bar.add_vline(
                x=80, line_dash="dash", line_color="#e74c3c",
                annotation_text="80% objetivo", annotation_position="top right",
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # --- Métricas por intención ---
        st.divider()
        st.subheader("Métricas por intención")

        rows_m = []
        for intent, m in sorted(metricas["por_clase"].items()):
            icono = "✅" if m["f1"] >= 0.8 else ("⚠️" if m["f1"] >= 0.5 else "❌")
            rows_m.append({
                "": icono,
                "Intención":  intent,
                "Precision":  f"{m['precision']*100:.1f}%",
                "Recall":     f"{m['recall']*100:.1f}%",
                "F1":         f"{m['f1']*100:.1f}%",
                "Casos (N)":  m["soporte"],
            })
        st.dataframe(pd.DataFrame(rows_m), use_container_width=True, hide_index=True)

        # --- Matriz de confusión ---
        st.divider()
        st.subheader("Matriz de confusión")
        st.caption("Filas = intención real · Columnas = intención predicha · Diagonal = aciertos")

        matriz_df = pd.DataFrame(
            [[matriz[r][c] for c in intents] for r in intents],
            index=intents,
            columns=intents,
        )

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

        # --- Tabla completa de casos ejecutados ---
        st.divider()
        st.subheader(f"Detalle de los {len(INTENT_TEST_CASES)} casos ejecutados")
        st.caption("Cada fila muestra si el clasificador acertó, el texto ingresado, el intent esperado vs predicho y la confianza.")

        df_detalle = pd.DataFrame(detalle)
        st.dataframe(df_detalle, use_container_width=True, hide_index=True)

    else:
        st.info("Haz clic en **▶ Ejecutar evaluación de intenciones** para correr los tests.")

        st.markdown("### Casos de prueba cargados")
        import pandas as pd
        df_preview = pd.DataFrame([
            {"#": i + 1, "Texto": c["text"], "Intent esperado": c["expected_intent"]}
            for i, c in enumerate(INTENT_TEST_CASES)
        ])
        st.dataframe(df_preview, use_container_width=True, hide_index=True)


# ===========================================================================
# TAB 2 — Pipeline RAG
# ===========================================================================

with tab_rag:
    st.caption(
        f"Evalúa el `RagService` contra **{len(RAG_TEST_CASES)} casos de prueba**. "
        "Para cada consulta verifica si el documento esperado aparece en los resultados recuperados."
    )

    st.markdown(
        """
        **¿Cómo se mide?**
        - **Hit@1** — el documento correcto es el resultado nº 1 (el más parecido)
        - **Hit@3** — el documento correcto aparece entre los 3 primeros resultados
        - Un caso puede tener varios documentos esperados; se considera acierto si *cualquiera* aparece
        """
    )

    if st.button("▶ Ejecutar evaluación RAG", type="primary", key="btn_rag"):
        with st.spinner("Conectando con ChromaDB y evaluando consultas..."):

            @st.cache_resource
            def cargar_rag_service():
                return RagService()

            rag = cargar_rag_service()

            if not rag.is_indexed():
                st.error("ChromaDB está vacío. Levanta la app principal primero para que se indexen los documentos.")
                st.stop()

            hit1_total = 0
            hit3_total = 0
            detalle_rag = []

            for caso in RAG_TEST_CASES:
                resultados = rag.search(caso["query"], n_results=5)
                fuentes_recuperadas = [r["source"] for r in resultados]
                esperadas = set(caso["expected_sources"])

                hit1 = bool(fuentes_recuperadas) and fuentes_recuperadas[0] in esperadas
                hit3 = any(f in esperadas for f in fuentes_recuperadas[:3])

                if hit1:
                    hit1_total += 1
                if hit3:
                    hit3_total += 1

                detalle_rag.append({
                    "Hit@1": "✅" if hit1 else "❌",
                    "Hit@3": "✅" if hit3 else "❌",
                    "Consulta": caso["query"],
                    "Top-1 recuperado": fuentes_recuperadas[0] if fuentes_recuperadas else "—",
                    "Top-3 recuperados": " | ".join(fuentes_recuperadas[:3]),
                    "Fuentes esperadas": " | ".join(sorted(esperadas)),
                })

        n_casos = len(RAG_TEST_CASES)
        pct_h1  = hit1_total / n_casos * 100
        pct_h3  = hit3_total / n_casos * 100

        # --- Métricas globales RAG ---
        st.divider()
        st.subheader("Resultados globales")

        r1, r2, r3 = st.columns(3)
        r1.metric("Hit@1", f"{pct_h1:.1f}%", help="El primer resultado era el documento correcto")
        r2.metric("Hit@3", f"{pct_h3:.1f}%", help="El doc correcto aparece entre los 3 primeros")
        r3.metric("Casos evaluados", str(n_casos))

        if pct_h3 >= 80:
            st.success("✅ El RAG recupera bien los documentos relevantes.")
        elif pct_h3 >= 60:
            st.warning("⚠️ Recuperación aceptable. Revisar casos con Hit@3 = ❌.")
        else:
            st.error("❌ El RAG falla en muchos casos. Revisar chunking, embeddings o índice.")

        # --- Gráfico: Hit@1 vs Hit@3 ---
        import pandas as pd
        import plotly.graph_objects as go

        st.divider()
        st.subheader("📊 Hit@1 vs Hit@3")

        fig_rag = go.Figure()
        fig_rag.add_trace(go.Bar(
            name="Hit@1", x=["Hit@1"], y=[pct_h1],
            marker_color="#3498db",
            text=[f"{pct_h1:.1f}%"], textposition="auto",
            width=0.3,
        ))
        fig_rag.add_trace(go.Bar(
            name="Hit@3", x=["Hit@3"], y=[pct_h3],
            marker_color="#2ecc71",
            text=[f"{pct_h3:.1f}%"], textposition="auto",
            width=0.3,
        ))
        fig_rag.update_layout(
            yaxis=dict(range=[0, 110], ticksuffix="%"),
            showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            height=250,
        )
        fig_rag.add_hline(
            y=80, line_dash="dash", line_color="#e74c3c",
            annotation_text="80% objetivo", annotation_position="top right",
        )
        st.plotly_chart(fig_rag, use_container_width=True)

        # --- Tabla completa de casos RAG ---
        st.divider()
        st.subheader(f"Detalle de los {n_casos} casos ejecutados")
        st.caption(
            "Top-1 = documento más cercano por similitud coseno. "
            "Top-3 = los 3 primeros resultados separados por |."
        )

        df_rag = pd.DataFrame(detalle_rag)
        st.dataframe(df_rag, use_container_width=True, hide_index=True)

    else:
        st.info("Haz clic en **▶ Ejecutar evaluación RAG** para correr los tests.")

        st.markdown("### Casos de prueba cargados")
        import pandas as pd
        df_rag_preview = pd.DataFrame([
            {
                "#": i + 1,
                "Consulta": c["query"],
                "Fuentes esperadas": " | ".join(c["expected_sources"]),
            }
            for i, c in enumerate(RAG_TEST_CASES)
        ])
        st.dataframe(df_rag_preview, use_container_width=True, hide_index=True)
