"""
Página de evaluación del sistema Sunatito.
Accesible desde el sidebar de Streamlit automáticamente.

Tabs:
  1. Clasificador de intenciones (sentence-transformers) — 30 casos
  2. Pipeline RAG — 40 casos (hit@1 y hit@3)
  3. Comparativa de clasificadores — IntentService vs ZeroShot sobre los mismos 30 casos
  4. Intent + Router — 20 casos con decisión de routing incluida
  5. Flujo de Chat — 6 turnos de la conversación de formalización
  6. Assertions de Tools — verifica el estado final tras completar el flujo
"""

import os
import sys
from collections import defaultdict
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from app.services.intent_service import IntentService
from app.services.intent_serviceZeroShot import IntentService as IntentServiceZeroShot
from app.services.rag_service import RagService
from app.services.router import ConversationRouter
from app.services.state_store import InMemoryStateStore
from app.data.test_cases.intent_test_cases import INTENT_TEST_CASES
from app.data.test_cases.rag_test_cases import RAG_TEST_CASES

# Casos del scratch_test_intent_router (20 casos: intent + decisión del router)
INTENT_ROUTER_CASES = [
    {"text": "Quiero saber qué necesito para formalizar mi negocio",      "expected_intent": "formalizacion_negocio"},
    {"text": "Cómo saco mi RUC para empezar mi negocio",                  "expected_intent": "formalizacion_negocio"},
    {"text": "Qué pasos debo seguir para formalizar una empresa pequeña", "expected_intent": "formalizacion_negocio"},
    {"text": "Qué debo hacer para registrar mi negocio ante SUNAT",       "expected_intent": "formalizacion_negocio"},
    {"text": "Me llegó una multa por declarar fuera de fecha",            "expected_intent": "multas_y_sanciones"},
    {"text": "Qué pasa si no presenté mi declaración a tiempo",           "expected_intent": "multas_y_sanciones"},
    {"text": "Quiero saber cuánto me pueden cobrar de multa por no declarar", "expected_intent": "multas_y_sanciones"},
    {"text": "Hay sanción si no cumplo con mis obligaciones tributarias",  "expected_intent": "multas_y_sanciones"},
    {"text": "Qué régimen tributario me conviene para una bodega pequeña","expected_intent": "regimenes_tributarios"},
    {"text": "Cuál es la diferencia entre NRUS y RER",                    "expected_intent": "regimenes_tributarios"},
    {"text": "Cómo saber en qué régimen tributario debería estar mi negocio", "expected_intent": "regimenes_tributarios"},
    {"text": "Qué régimen me conviene si recién empiezo a vender",        "expected_intent": "regimenes_tributarios"},
    {"text": "Cómo emito una boleta o factura",                           "expected_intent": "comprobantes_pago"},
    {"text": "Qué comprobante de pago debo entregar a mi cliente",        "expected_intent": "comprobantes_pago"},
    {"text": "Cuándo corresponde emitir factura y cuándo boleta",         "expected_intent": "comprobantes_pago"},
    {"text": "Quiero saber cómo generar comprobantes de pago",            "expected_intent": "comprobantes_pago"},
    {"text": "Cuándo vence mi declaración mensual",                       "expected_intent": "cronograma_obligaciones"},
    {"text": "Cuál es la fecha límite para declarar impuestos este mes",  "expected_intent": "cronograma_obligaciones"},
    {"text": "Dónde consulto el cronograma de vencimientos de SUNAT",     "expected_intent": "cronograma_obligaciones"},
    {"text": "Qué día me toca presentar mis obligaciones tributarias",    "expected_intent": "cronograma_obligaciones"},
]

# Flujo predefinido de formalización (scratch_test_chat_flow y scratch_test_tool_flow_assertions)
CHAT_FLOW_MESSAGES = [
    "Quiero formalizar mi negocio",
    "no",
    "natural",
    "servicios",
    "boletas",
    "sí",
]

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

tab_intent, tab_rag, tab_compare, tab_router, tab_flow, tab_assert = st.tabs([
    "🎯 Clasificador de Intenciones",
    "📚 Pipeline RAG",
    "⚖️ Comparativa de Clasificadores",
    "🔀 Intent + Router",
    "💬 Flujo de Chat",
    "✅ Assertions de Tools",
])


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


# ===========================================================================
# TAB 3 — Comparativa de Clasificadores
# ===========================================================================

with tab_compare:
    st.caption(
        f"Corre los mismos **{len(INTENT_TEST_CASES)} casos** con ambos clasificadores "
        "y compara accuracy, confianza media y errores lado a lado."
    )
    st.markdown(
        """
        | Clasificador | Técnica | Modelo base |
        |---|---|---|
        | **IntentService** | Sentence-transformers + similitud coseno híbrida | `paraphrase-multilingual-MiniLM-L12-v2` |
        | **IntentServiceZeroShot** | Zero-shot classification (NLI) | `mDeBERTa-v3-base-mnli-xnli` |
        """
    )

    st.warning(
        "⚠️ El modelo ZeroShot requiere `mDeBERTa-v3-base-mnli-xnli` descargado localmente "
        "(`local_files_only=True`). Si no está en caché, la carga fallará.",
        icon="⚠️",
    )

    if st.button("▶ Ejecutar comparativa", type="primary", key="btn_compare"):

        @st.cache_resource
        def cargar_embedding_service():
            return IntentService()

        @st.cache_resource
        def cargar_zeroshot_service():
            return IntentServiceZeroShot()

        # --- Correr embedding classifier ---
        with st.spinner("Evaluando IntentService (sentence-transformers)..."):
            clf_emb = cargar_embedding_service()
            y_true, pred_emb, conf_emb, det_emb = [], [], [], []
            for caso in INTENT_TEST_CASES:
                res = clf_emb.classify_topic(caso["text"])
                y_true.append(caso["expected_intent"])
                pred_emb.append(res.intent)
                conf_emb.append(res.confidence)
                det_emb.append({
                    "Texto": caso["text"],
                    "Esperado": caso["expected_intent"],
                    "Predicho (Emb)": res.intent,
                    "Conf (Emb)": round(res.confidence, 3),
                    "✓ Emb": "✅" if res.intent == caso["expected_intent"] else "❌",
                })

        # --- Correr zero-shot classifier ---
        zs_error = None
        pred_zs, conf_zs = [], []
        try:
            with st.spinner("Evaluando IntentServiceZeroShot (mDeBERTa)... puede tardar más."):
                clf_zs = cargar_zeroshot_service()
                for i, caso in enumerate(INTENT_TEST_CASES):
                    res = clf_zs.classify_topic(caso["text"])
                    pred_zs.append(res.intent)
                    conf_zs.append(res.confidence)
                    det_emb[i]["Predicho (ZS)"] = res.intent
                    det_emb[i]["Conf (ZS)"] = round(res.confidence, 3)
                    det_emb[i]["✓ ZS"] = "✅" if res.intent == caso["expected_intent"] else "❌"
        except Exception as e:
            zs_error = str(e)

        # --- Calcular métricas ---
        import pandas as pd
        import plotly.graph_objects as go

        def accuracy(y_true, y_pred):
            return sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true) * 100

        acc_emb = accuracy(y_true, pred_emb)
        avg_conf_emb = sum(conf_emb) / len(conf_emb)
        err_emb = sum(1 for t, p in zip(y_true, pred_emb) if t != p)

        # --- Métricas globales comparadas ---
        st.divider()
        st.subheader("Métricas globales")

        col_emb, col_zs = st.columns(2)

        with col_emb:
            st.markdown("#### 🔵 Sentence-Transformers")
            st.metric("Accuracy", f"{acc_emb:.1f}%")
            st.metric("Confianza media", f"{avg_conf_emb:.3f}")
            st.metric("Errores", str(err_emb))

        with col_zs:
            st.markdown("#### 🟠 Zero-Shot (mDeBERTa)")
            if zs_error:
                st.error(f"Error al cargar el modelo: {zs_error}")
            else:
                acc_zs = accuracy(y_true, pred_zs)
                avg_conf_zs = sum(conf_zs) / len(conf_zs)
                err_zs = sum(1 for t, p in zip(y_true, pred_zs) if t != p)
                st.metric("Accuracy", f"{acc_zs:.1f}%", delta=f"{acc_zs - acc_emb:+.1f}% vs Emb")
                st.metric("Confianza media", f"{avg_conf_zs:.3f}")
                st.metric("Errores", str(err_zs))

        if not zs_error:
            # --- Gráfico comparativo de accuracy por intent ---
            st.divider()
            st.subheader("📊 Accuracy por intención")

            intents_uniq = sorted(set(y_true))
            acc_emb_por_intent, acc_zs_por_intent = [], []

            for intent in intents_uniq:
                casos_intent = [(t, pe, pz) for t, pe, pz in zip(y_true, pred_emb, pred_zs) if t == intent]
                n = len(casos_intent)
                acc_emb_por_intent.append(sum(1 for t, pe, _ in casos_intent if t == pe) / n * 100)
                acc_zs_por_intent.append(sum(1 for t, _, pz in casos_intent if t == pz) / n * 100)

            nombres_intents = [i.replace("_", " ") for i in intents_uniq]
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(
                name="Sentence-Transformers", y=nombres_intents, x=acc_emb_por_intent,
                orientation="h", marker_color="#3498db",
                text=[f"{v:.0f}%" for v in acc_emb_por_intent], textposition="auto",
            ))
            fig_comp.add_trace(go.Bar(
                name="Zero-Shot mDeBERTa", y=nombres_intents, x=acc_zs_por_intent,
                orientation="h", marker_color="#e67e22",
                text=[f"{v:.0f}%" for v in acc_zs_por_intent], textposition="auto",
            ))
            fig_comp.update_layout(
                barmode="group",
                xaxis=dict(range=[0, 110], ticksuffix="%"),
                yaxis=dict(autorange="reversed"),
                legend=dict(orientation="h", y=1.1),
                margin=dict(t=30, b=10, l=10, r=10),
                height=320,
            )
            fig_comp.add_vline(
                x=80, line_dash="dash", line_color="#e74c3c",
                annotation_text="80% objetivo", annotation_position="top right",
            )
            st.plotly_chart(fig_comp, use_container_width=True)

        # --- Tabla caso por caso ---
        st.divider()
        st.subheader(f"Detalle caso por caso ({len(INTENT_TEST_CASES)} casos)")

        if zs_error:
            for d in det_emb:
                d.setdefault("Predicho (ZS)", "—")
                d.setdefault("Conf (ZS)", "—")
                d.setdefault("✓ ZS", "—")

        cols_order = ["✓ Emb", "✓ ZS", "Texto", "Esperado",
                      "Predicho (Emb)", "Conf (Emb)", "Predicho (ZS)", "Conf (ZS)"]
        st.dataframe(pd.DataFrame(det_emb)[cols_order], use_container_width=True, hide_index=True)

    else:
        st.info("Haz clic en **▶ Ejecutar comparativa** para correr ambos clasificadores.")

        st.markdown("### Casos que se usarán para la comparativa")
        import pandas as pd
        df_comp_preview = pd.DataFrame([
            {"#": i + 1, "Texto": c["text"], "Intent esperado": c["expected_intent"]}
            for i, c in enumerate(INTENT_TEST_CASES)
        ])
        st.dataframe(df_comp_preview, use_container_width=True, hide_index=True)


# ===========================================================================
# TAB 4 — Intent + Router (scratch_test_intent_router)
# ===========================================================================

with tab_router:
    st.caption(
        f"Evalúa el `IntentService` + `ConversationRouter` en conjunto sobre "
        f"**{len(INTENT_ROUTER_CASES)} casos**. Muestra no solo si el intent fue correcto "
        "sino también qué acción decidió el router (RAG, tool, clarificación)."
    )

    if st.button("▶ Ejecutar Intent + Router", type="primary", key="btn_router"):
        with st.spinner("Clasificando intenciones y calculando decisiones de routing..."):

            @st.cache_resource
            def cargar_router_services():
                return IntentService(), ConversationRouter()

            clf, router = cargar_router_services()
            store = InMemoryStateStore()

            detalle_router = []
            y_true_r, y_pred_r = [], []

            for i, caso in enumerate(INTENT_ROUTER_CASES):
                state = store.get(f"eval-router-{i}")
                intent_result = clf.classify_topic(caso["text"])
                decision = router.decide(
                    message=caso["text"],
                    intent_result=intent_result,
                    state=state,
                )
                correcto = intent_result.intent == caso["expected_intent"]
                y_true_r.append(caso["expected_intent"])
                y_pred_r.append(intent_result.intent)

                top3 = " | ".join(
                    f"{r.label.split('consulta sobre ')[-1][:30]} ({r.score:.2f})"
                    for r in intent_result.ranked_labels[:3]
                )
                detalle_router.append({
                    "✓": "✅" if correcto else "❌",
                    "Texto": caso["text"],
                    "Esperado": caso["expected_intent"],
                    "Predicho": intent_result.intent,
                    "Confianza": round(intent_result.confidence, 3),
                    "Acción": decision.action,
                    "Tool": decision.tool_name or "—",
                    "Top-3 labels": top3,
                })

        import pandas as pd
        import plotly.graph_objects as go

        acc_r = sum(t == p for t, p in zip(y_true_r, y_pred_r)) / len(y_true_r) * 100
        err_r = sum(1 for t, p in zip(y_true_r, y_pred_r) if t != p)

        st.divider()
        st.subheader("Resultados globales")
        cr1, cr2, cr3 = st.columns(3)
        cr1.metric("Accuracy", f"{acc_r:.1f}%")
        cr2.metric("Errores", str(err_r))
        cr3.metric("Casos", str(len(INTENT_ROUTER_CASES)))

        if acc_r >= 85:
            st.success("✅ Clasificador + router funcionan correctamente.")
        elif acc_r >= 70:
            st.warning("⚠️ Hay intents que el router no resuelve bien.")
        else:
            st.error("❌ Revisar ejemplos de entrenamiento y patrones del router.")

        # Gráfico: accuracy por intent
        st.divider()
        st.subheader("📊 Accuracy por intención")

        intents_r = sorted(set(y_true_r))
        acc_por_intent_r = []
        for intent in intents_r:
            pares = [(t, p) for t, p in zip(y_true_r, y_pred_r) if t == intent]
            acc_por_intent_r.append(sum(1 for t, p in pares if t == p) / len(pares) * 100)

        fig_r = go.Figure(go.Bar(
            y=[i.replace("_", " ") for i in intents_r],
            x=acc_por_intent_r,
            orientation="h",
            marker_color=["#2ecc71" if v >= 80 else "#e74c3c" for v in acc_por_intent_r],
            text=[f"{v:.0f}%" for v in acc_por_intent_r],
            textposition="auto",
        ))
        fig_r.update_layout(
            xaxis=dict(range=[0, 110], ticksuffix="%"),
            yaxis=dict(autorange="reversed"),
            margin=dict(t=10, b=10, l=10, r=10),
            height=280,
            showlegend=False,
        )
        fig_r.add_vline(
            x=80, line_dash="dash", line_color="#e74c3c",
            annotation_text="80% objetivo", annotation_position="top right",
        )
        st.plotly_chart(fig_r, use_container_width=True)

        # Distribución de acciones del router
        st.divider()
        st.subheader("📊 Distribución de acciones del router")
        from collections import Counter
        acciones = Counter(d["Acción"] for d in detalle_router)
        fig_acc = go.Figure(go.Pie(
            labels=list(acciones.keys()),
            values=list(acciones.values()),
            hole=0.4,
            marker_colors=["#3498db", "#2ecc71", "#e74c3c", "#f39c12"],
            textinfo="label+percent+value",
        ))
        fig_acc.update_layout(
            showlegend=True,
            margin=dict(t=10, b=10, l=10, r=10),
            height=260,
        )
        st.plotly_chart(fig_acc, use_container_width=True)

        # Tabla completa
        st.divider()
        st.subheader(f"Detalle de los {len(INTENT_ROUTER_CASES)} casos")
        st.dataframe(pd.DataFrame(detalle_router), use_container_width=True, hide_index=True)

    else:
        st.info("Haz clic en **▶ Ejecutar Intent + Router** para correr los tests.")
        import pandas as pd
        st.dataframe(
            pd.DataFrame([
                {"#": i + 1, "Texto": c["text"], "Intent esperado": c["expected_intent"]}
                for i, c in enumerate(INTENT_ROUTER_CASES)
            ]),
            use_container_width=True,
            hide_index=True,
        )


# ===========================================================================
# TAB 5 — Flujo de Chat (scratch_test_chat_flow)
# ===========================================================================

with tab_flow:
    st.caption(
        "Simula el flujo completo de formalización de negocio en **6 turnos** y muestra "
        "la respuesta del bot junto con el intent detectado y la decisión del router en cada turno."
    )
    st.markdown(
        "**Mensajes del flujo:**  \n" +
        "  →  ".join([f"`{m}`" for m in CHAT_FLOW_MESSAGES])
    )
    st.warning(
        "Este test usa el orquestador completo. Si ChromaDB no está indexado, "
        "el último turno puede responder con el fallback de RAG.",
        icon="⚠️",
    )

    if st.button("▶ Ejecutar flujo de chat", type="primary", key="btn_flow"):
        from app.services.chat_orchestrator import ChatOrchestrator
        from app.services.rag_executor import RagExecutor
        from app.services.tool_executor import ToolExecutor
        from app.services.llm_service import LLMService

        with st.spinner("Inicializando servicios y ejecutando flujo..."):

            @st.cache_resource
            def cargar_rag_para_flujo():
                return RagService()

            @st.cache_resource
            def cargar_orquestador_flujo():
                rag = cargar_rag_para_flujo()
                llm = LLMService()
                return ChatOrchestrator(
                    state_store=InMemoryStateStore(),
                    intent_classifier=IntentService(),
                    router=ConversationRouter(),
                    tool_executor=ToolExecutor(rag_service=rag, llm_service=llm),
                    rag_executor=RagExecutor(rag_service=rag, llm_service=llm),
                )

            orch = cargar_orquestador_flujo()
            session_id = "eval-chat-flow"
            resultados_flujo = []
            for msg in CHAT_FLOW_MESSAGES:
                r = orch.handle_message(session_id=session_id, message=msg)
                resultados_flujo.append(r)

        st.divider()
        st.subheader("Conversación turno por turno")

        for i, (msg, result) in enumerate(zip(CHAT_FLOW_MESSAGES, resultados_flujo), start=1):
            with st.expander(f"Turno {i} — usuario: \"{msg}\"", expanded=(i <= 2)):
                c_msg, c_bot = st.columns([1, 2])
                with c_msg:
                    st.markdown("**Mensaje**")
                    st.info(msg)
                    st.markdown(f"**Intent:** `{result['intent_result']['intent']}`")
                    st.markdown(f"**Confianza:** `{result['intent_result']['confidence']:.3f}`")
                    st.markdown(f"**Acción:** `{result['route_decision']['action']}`")
                    tool = result['route_decision'].get('tool_name') or "—"
                    st.markdown(f"**Tool:** `{tool}`")
                with c_bot:
                    st.markdown("**Respuesta del bot**")
                    st.success(result["response"])

        st.divider()
        st.subheader("Estado final de la sesión")
        import pandas as pd
        estado_final = resultados_flujo[-1]["state"]
        rows_estado = [
            {"Campo": k, "Valor": str(v)}
            for k, v in estado_final.items()
            if k != "entities"
        ]
        st.dataframe(pd.DataFrame(rows_estado), use_container_width=True, hide_index=True)

        if estado_final.get("entities"):
            st.json(estado_final["entities"])

    else:
        st.info("Haz clic en **▶ Ejecutar flujo de chat** para simular la conversación.")


# ===========================================================================
# TAB 6 — Assertions de Tools (scratch_test_tool_flow_assertions)
# ===========================================================================

with tab_assert:
    st.caption(
        "Corre el flujo de formalización y verifica programáticamente que el estado final "
        "contiene los valores esperados. Equivale a un test unitario con asserts."
    )

    ASSERTIONS = [
        {
            "nombre": "active_tool es None al finalizar",
            "descripcion": "Tras completar el flujo, el orquestador no debe quedar esperando respuesta de ninguna tool.",
            "fn": lambda state, resp: state["active_tool"] is None,
        },
        {
            "nombre": "has_ruc guardado como 'no'",
            "descripcion": "El usuario respondió 'no' a la pregunta de RUC → debe quedar normalizado como 'no'.",
            "fn": lambda state, resp: state["entities"].get("formalization_result", {}).get("has_ruc") == "no",
        },
        {
            "nombre": "person_type guardado como 'natural'",
            "descripcion": "El usuario respondió 'natural' → debe quedar normalizado.",
            "fn": lambda state, resp: state["entities"].get("formalization_result", {}).get("person_type") == "natural",
        },
        {
            "nombre": "economic_activity capturado",
            "descripcion": "La actividad económica 'servicios' debe haber sido registrada.",
            "fn": lambda state, resp: state["entities"].get("formalization_result", {}).get("economic_activity") == "servicios",
        },
        {
            "nombre": "voucher_type capturado",
            "descripcion": "El tipo de comprobante 'boletas' debe haber sido normalizado.",
            "fn": lambda state, resp: state["entities"].get("formalization_result", {}).get("voucher_type") == "boletas",
        },
        {
            "nombre": "has_employees capturado como 'sí'",
            "descripcion": "El usuario respondió 'sí' a trabajadores → debe quedar como 'sí'.",
            "fn": lambda state, resp: state["entities"].get("formalization_result", {}).get("has_employees") == "sí",
        },
        {
            "nombre": "formalization_flow eliminado del estado",
            "descripcion": "El flujo en curso debe limpiarse de entities para no repetirse en el siguiente turno.",
            "fn": lambda state, resp: "formalization_flow" not in state["entities"],
        },
    ]

    if st.button("▶ Ejecutar assertions", type="primary", key="btn_assert"):
        from app.services.chat_orchestrator import ChatOrchestrator
        from app.services.rag_executor import RagExecutor
        from app.services.tool_executor import ToolExecutor
        from app.services.llm_service import LLMService
        import pandas as pd
        import plotly.graph_objects as go

        with st.spinner("Ejecutando flujo de formalización..."):

            @st.cache_resource
            def cargar_rag_para_assert():
                return RagService()

            rag_a = cargar_rag_para_assert()
            llm_a = LLMService()
            orch_a = ChatOrchestrator(
                state_store=InMemoryStateStore(),
                intent_classifier=IntentService(),
                router=ConversationRouter(),
                tool_executor=ToolExecutor(rag_service=rag_a, llm_service=llm_a),
                rag_executor=RagExecutor(rag_service=rag_a, llm_service=llm_a),
            )
            sid = "eval-assertions"
            for msg in CHAT_FLOW_MESSAGES:
                last = orch_a.handle_message(session_id=sid, message=msg)

        final_state = last["state"]
        final_response = last["response"]

        # Evaluar cada assertion
        resultados_assert = []
        pasaron = 0
        for a in ASSERTIONS:
            try:
                paso = bool(a["fn"](final_state, final_response))
                error_msg = ""
            except Exception as e:
                paso = False
                error_msg = str(e)
            if paso:
                pasaron += 1
            resultados_assert.append({
                "": "✅" if paso else "❌",
                "Assertion": a["nombre"],
                "Descripción": a["descripcion"],
                "Resultado": "PASS" if paso else f"FAIL{' — ' + error_msg if error_msg else ''}",
            })

        total_a = len(ASSERTIONS)
        pct_a = pasaron / total_a * 100

        st.divider()
        st.subheader("Resultados")

        ca1, ca2 = st.columns(2)
        ca1.metric("Assertions PASS", f"{pasaron} / {total_a}")
        ca2.metric("Tasa de éxito", f"{pct_a:.0f}%")

        if pasaron == total_a:
            st.success("✅ Todas las assertions pasaron. El flujo de formalización funciona correctamente.")
        else:
            st.error(f"❌ {total_a - pasaron} assertion(s) fallaron. Revisar la tabla de detalle.")

        # Gráfico dona pass/fail
        st.divider()
        fig_a = go.Figure(go.Pie(
            labels=["PASS", "FAIL"],
            values=[pasaron, total_a - pasaron],
            hole=0.55,
            marker_colors=["#2ecc71", "#e74c3c"],
            textinfo="label+value",
            textfont_size=13,
        ))
        fig_a.update_layout(
            showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            height=220,
            annotations=[dict(
                text=f"<b>{pct_a:.0f}%</b>",
                x=0.5, y=0.5, font_size=20, showarrow=False,
            )],
        )
        st.plotly_chart(fig_a, use_container_width=True)

        # Tabla de assertions
        st.subheader("Detalle de assertions")
        st.dataframe(pd.DataFrame(resultados_assert), use_container_width=True, hide_index=True)

        # Estado final completo
        with st.expander("Ver estado final completo"):
            st.json(final_state)

    else:
        st.info("Haz clic en **▶ Ejecutar assertions** para verificar el flujo.")
        st.markdown("### Assertions que se verificarán")
        import pandas as pd
        st.dataframe(
            pd.DataFrame([
                {"#": i + 1, "Assertion": a["nombre"], "Descripción": a["descripcion"]}
                for i, a in enumerate(ASSERTIONS)
            ]),
            use_container_width=True,
            hide_index=True,
        )
