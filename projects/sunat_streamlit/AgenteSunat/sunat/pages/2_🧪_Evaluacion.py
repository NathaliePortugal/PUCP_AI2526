"""
Página de evaluación del sistema Sunatito.
Accesible desde el sidebar de Streamlit automáticamente.

Tabs:
  1. Clasificador de intenciones (sentence-transformers) — 30 casos
  2. Pipeline RAG — 40 casos (hit@1 y hit@3)
  3. Comparativa de clasificadores — IntentService vs ZeroShot sobre los mismos 30 casos
  4. Tests de Integración — Intent+Router (20 casos) · Flujos de Chat (3) · Assertions (14)
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
    {"text": "Quiero saber qué necesito para formalizar mi negocio",          "expected_intent": "formalizacion_negocio"},
    {"text": "Cómo saco mi RUC para empezar mi negocio",                      "expected_intent": "formalizacion_negocio"},
    {"text": "Qué pasos debo seguir para formalizar una empresa pequeña",     "expected_intent": "formalizacion_negocio"},
    {"text": "Qué debo hacer para registrar mi negocio ante SUNAT",           "expected_intent": "formalizacion_negocio"},
    {"text": "Me llegó una multa por declarar fuera de fecha",                "expected_intent": "multas_y_sanciones"},
    {"text": "Qué pasa si no presenté mi declaración a tiempo",               "expected_intent": "multas_y_sanciones"},
    {"text": "Quiero saber cuánto me pueden cobrar de multa por no declarar", "expected_intent": "multas_y_sanciones"},
    {"text": "Hay sanción si no cumplo con mis obligaciones tributarias",      "expected_intent": "multas_y_sanciones"},
    {"text": "Qué régimen tributario me conviene para una bodega pequeña",    "expected_intent": "regimenes_tributarios"},
    {"text": "Cuál es la diferencia entre NRUS y RER",                        "expected_intent": "regimenes_tributarios"},
    {"text": "Cómo saber en qué régimen tributario debería estar mi negocio", "expected_intent": "regimenes_tributarios"},
    {"text": "Qué régimen me conviene si recién empiezo a vender",            "expected_intent": "regimenes_tributarios"},
    {"text": "Cómo emito una boleta o factura",                               "expected_intent": "comprobantes_pago"},
    {"text": "Qué comprobante de pago debo entregar a mi cliente",            "expected_intent": "comprobantes_pago"},
    {"text": "Cuándo corresponde emitir factura y cuándo boleta",             "expected_intent": "comprobantes_pago"},
    {"text": "Quiero saber cómo generar comprobantes de pago",                "expected_intent": "comprobantes_pago"},
    {"text": "Cuándo vence mi declaración mensual",                           "expected_intent": "cronograma_obligaciones"},
    {"text": "Cuál es la fecha límite para declarar impuestos este mes",      "expected_intent": "cronograma_obligaciones"},
    {"text": "Dónde consulto el cronograma de vencimientos de SUNAT",         "expected_intent": "cronograma_obligaciones"},
    {"text": "Qué día me toca presentar mis obligaciones tributarias",        "expected_intent": "cronograma_obligaciones"},
]

# Los 3 flujos de conversación completos
CHAT_FLOWS = [
    {
        "nombre": "Formalización de negocio",
        "icono": "🏢",
        "descripcion": "5 preguntas guiadas → checklist personalizado (build_formalization_checklist)",
        "session_id": "eval-formalizacion",
        "mensajes": ["Quiero formalizar mi negocio", "no", "natural", "servicios", "boletas", "sí"],
    },
    {
        "nombre": "Regímenes tributarios",
        "icono": "📊",
        "descripcion": "3 preguntas → recomendación de régimen ideal (compare_tax_regimes)",
        "session_id": "eval-regimenes",
        "mensajes": [
            "Ayúdame a elegir el régimen tributario ideal para mi negocio",
            "a",   # ventas: menos de S/5,000
            "no",  # no necesita facturas
            "a",   # trabaja solo
        ],
    },
    {
        "nombre": "Multas y sanciones",
        "icono": "⚠️",
        "descripcion": "1 turno one-shot → orientación inmediata (handle_fines_guidance)",
        "session_id": "eval-multas",
        "mensajes": ["Tengo una multa de SUNAT"],
    },
]

# Assertions agrupadas por flujo
FLOW_ASSERTIONS = [
    {
        "flujo": "Formalización de negocio",
        "session_id": "assert-formalizacion",
        "mensajes": ["Quiero formalizar mi negocio", "no", "natural", "servicios", "boletas", "sí"],
        "checks": [
            {"nombre": "active_tool es None al finalizar",
             "fn": lambda s, r: s["active_tool"] is None},
            {"nombre": "has_ruc guardado como 'no'",
             "fn": lambda s, r: s["entities"].get("formalization_result", {}).get("has_ruc") == "no"},
            {"nombre": "person_type guardado como 'natural'",
             "fn": lambda s, r: s["entities"].get("formalization_result", {}).get("person_type") == "natural"},
            {"nombre": "economic_activity capturado",
             "fn": lambda s, r: s["entities"].get("formalization_result", {}).get("economic_activity") == "servicios"},
            {"nombre": "voucher_type guardado como 'boletas'",
             "fn": lambda s, r: s["entities"].get("formalization_result", {}).get("voucher_type") == "boletas"},
            {"nombre": "has_employees guardado como 'sí'",
             "fn": lambda s, r: s["entities"].get("formalization_result", {}).get("has_employees") == "sí"},
            {"nombre": "formalization_flow eliminado del estado",
             "fn": lambda s, r: "formalization_flow" not in s["entities"]},
        ],
    },
    {
        "flujo": "Regímenes tributarios",
        "session_id": "assert-regimenes",
        "mensajes": ["Ayúdame a elegir el régimen tributario ideal para mi negocio", "a", "no", "a"],
        "checks": [
            {"nombre": "active_tool es None al finalizar",
             "fn": lambda s, r: s["active_tool"] is None},
            {"nombre": "monthly_sales capturado",
             "fn": lambda s, r: s["entities"].get("tax_regime_result", {}).get("monthly_sales") is not None},
            {"nombre": "needs_invoices guardado como 'no'",
             "fn": lambda s, r: s["entities"].get("tax_regime_result", {}).get("needs_invoices") == "no"},
            {"nombre": "worker_count capturado",
             "fn": lambda s, r: s["entities"].get("tax_regime_result", {}).get("worker_count") is not None},
            {"nombre": "tax_regime_flow eliminado del estado",
             "fn": lambda s, r: "tax_regime_flow" not in s["entities"]},
        ],
    },
    {
        "flujo": "Multas y sanciones",
        "session_id": "assert-multas",
        "mensajes": ["Tengo una multa de SUNAT"],
        "checks": [
            {"nombre": "active_tool es None tras turno one-shot",
             "fn": lambda s, r: s["active_tool"] is None},
            {"nombre": "La respuesta tiene contenido real (> 50 chars)",
             "fn": lambda s, r: len(r) > 50},
        ],
    },
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
# Tabs
# ---------------------------------------------------------------------------

tab_intent, tab_rag, tab_compare, tab_integration = st.tabs([
    "🎯 Clasificador de Intenciones",
    "📚 Pipeline RAG",
    "⚖️ Comparativa de Clasificadores",
    "🧩 Tests de Integración",
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

        st.divider()
        st.subheader("Resultados globales")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Accuracy",         f"{acc:.1f}%")
        c2.metric("Macro F1",         f"{mf1:.1f}%")
        c3.metric("Aciertos / Total", f"{n_ok} / {len(INTENT_TEST_CASES)}")
        c4.metric("Confianza media",  f"{conf_m:.3f}")

        if acc >= 85:
            st.success("✅ Nivel BUENO — el clasificador funciona correctamente para producción.")
        elif acc >= 70:
            st.warning("⚠️ Nivel ACEPTABLE — se recomienda agregar ejemplos a los intents con F1 bajo.")
        else:
            st.error("❌ Necesita mejora — se recomienda revisar los intents confundidos y agregar más ejemplos.")

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
                annotations=[dict(text=f"<b>{acc:.0f}%</b>", x=0.5, y=0.5,
                                  font_size=22, showarrow=False)],
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
            fig_bar.add_trace(go.Bar(name="Precision", y=nombres, x=precision, orientation="h",
                                     marker_color="#3498db", text=[f"{v:.0f}%" for v in precision], textposition="auto"))
            fig_bar.add_trace(go.Bar(name="Recall", y=nombres, x=recall, orientation="h",
                                     marker_color="#f39c12", text=[f"{v:.0f}%" for v in recall], textposition="auto"))
            fig_bar.add_trace(go.Bar(name="F1", y=nombres, x=f1_vals, orientation="h",
                                     marker_color="#2ecc71", text=[f"{v:.0f}%" for v in f1_vals], textposition="auto"))
            fig_bar.update_layout(barmode="group", xaxis=dict(range=[0, 110], ticksuffix="%"),
                                  yaxis=dict(autorange="reversed"), legend=dict(orientation="h", y=1.1),
                                  margin=dict(t=30, b=10, l=10, r=10), height=300)
            fig_bar.add_vline(x=80, line_dash="dash", line_color="#e74c3c",
                              annotation_text="80% objetivo", annotation_position="top right")
            st.plotly_chart(fig_bar, use_container_width=True)

        st.divider()
        st.subheader("Métricas por intención")
        rows_m = []
        for intent, m in sorted(metricas["por_clase"].items()):
            icono = "✅" if m["f1"] >= 0.8 else ("⚠️" if m["f1"] >= 0.5 else "❌")
            rows_m.append({"": icono, "Intención": intent,
                           "Precision": f"{m['precision']*100:.1f}%",
                           "Recall": f"{m['recall']*100:.1f}%",
                           "F1": f"{m['f1']*100:.1f}%",
                           "Casos (N)": m["soporte"]})
        st.dataframe(pd.DataFrame(rows_m), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("Matriz de confusión")
        st.caption("Filas = intención real · Columnas = intención predicha · Diagonal = aciertos")
        matriz_df = pd.DataFrame(
            [[matriz[r][c] for c in intents] for r in intents],
            index=intents, columns=intents,
        )

        def resaltar(val, es_diagonal):
            if es_diagonal and val > 0:
                return "background-color: #d4edda; font-weight: bold"
            elif not es_diagonal and val > 0:
                return "background-color: #f8d7da"
            return ""

        styled = matriz_df.style.apply(
            lambda col: [resaltar(v, col.name == intents[i]) for i, v in enumerate(col)], axis=0)
        st.dataframe(styled, use_container_width=True)

        st.divider()
        st.subheader(f"Detalle de los {len(INTENT_TEST_CASES)} casos ejecutados")
        st.caption("Cada fila muestra si el clasificador acertó, el texto, el intent esperado vs predicho y la confianza.")
        st.dataframe(pd.DataFrame(detalle), use_container_width=True, hide_index=True)

    else:
        st.info("Haz clic en **▶ Ejecutar evaluación de intenciones** para correr los tests.")
        st.markdown("### Casos de prueba cargados")
        import pandas as pd
        st.dataframe(
            pd.DataFrame([{"#": i+1, "Texto": c["text"], "Intent esperado": c["expected_intent"]}
                          for i, c in enumerate(INTENT_TEST_CASES)]),
            use_container_width=True, hide_index=True,
        )


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

        import pandas as pd
        import plotly.graph_objects as go

        n_casos = len(RAG_TEST_CASES)
        pct_h1  = hit1_total / n_casos * 100
        pct_h3  = hit3_total / n_casos * 100

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

        st.divider()
        st.subheader("📊 Hit@1 vs Hit@3")
        fig_rag = go.Figure()
        fig_rag.add_trace(go.Bar(name="Hit@1", x=["Hit@1"], y=[pct_h1], marker_color="#3498db",
                                 text=[f"{pct_h1:.1f}%"], textposition="auto", width=0.3))
        fig_rag.add_trace(go.Bar(name="Hit@3", x=["Hit@3"], y=[pct_h3], marker_color="#2ecc71",
                                 text=[f"{pct_h3:.1f}%"], textposition="auto", width=0.3))
        fig_rag.update_layout(yaxis=dict(range=[0, 110], ticksuffix="%"), showlegend=False,
                              margin=dict(t=10, b=10, l=10, r=10), height=250)
        fig_rag.add_hline(y=80, line_dash="dash", line_color="#e74c3c",
                          annotation_text="80% objetivo", annotation_position="top right")
        st.plotly_chart(fig_rag, use_container_width=True)

        st.divider()
        st.subheader(f"Detalle de los {n_casos} casos ejecutados")
        st.caption("Top-1 = documento más cercano por similitud coseno. Top-3 = los 3 primeros separados por |.")
        st.dataframe(pd.DataFrame(detalle_rag), use_container_width=True, hide_index=True)

    else:
        st.info("Haz clic en **▶ Ejecutar evaluación RAG** para correr los tests.")
        st.markdown("### Casos de prueba cargados")
        import pandas as pd
        st.dataframe(
            pd.DataFrame([{"#": i+1, "Consulta": c["query"],
                           "Fuentes esperadas": " | ".join(c["expected_sources"])}
                          for i, c in enumerate(RAG_TEST_CASES)]),
            use_container_width=True, hide_index=True,
        )


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
        "El modelo ZeroShot se descarga de HuggingFace (~550 MB) la primera vez. "
        "En Streamlit Cloud puede tardar 1-3 minutos.",
        icon="⚠️",
    )

    if st.button("▶ Ejecutar comparativa", type="primary", key="btn_compare"):

        @st.cache_resource
        def cargar_embedding_service():
            return IntentService()

        @st.cache_resource
        def cargar_zeroshot_service():
            return IntentServiceZeroShot()

        with st.spinner("Evaluando IntentService (sentence-transformers)..."):
            clf_emb = cargar_embedding_service()
            y_true, pred_emb, conf_emb, det_emb = [], [], [], []
            for caso in INTENT_TEST_CASES:
                res = clf_emb.classify_topic(caso["text"])
                y_true.append(caso["expected_intent"])
                pred_emb.append(res.intent)
                conf_emb.append(res.confidence)
                det_emb.append({
                    "Texto": caso["text"], "Esperado": caso["expected_intent"],
                    "Predicho (Emb)": res.intent, "Conf (Emb)": round(res.confidence, 3),
                    "✓ Emb": "✅" if res.intent == caso["expected_intent"] else "❌",
                })

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

        import pandas as pd
        import plotly.graph_objects as go

        def accuracy(y_true, y_pred):
            return sum(t == p for t, p in zip(y_true, y_pred)) / len(y_true) * 100

        acc_emb      = accuracy(y_true, pred_emb)
        avg_conf_emb = sum(conf_emb) / len(conf_emb)
        err_emb      = sum(1 for t, p in zip(y_true, pred_emb) if t != p)

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
                acc_zs      = accuracy(y_true, pred_zs)
                avg_conf_zs = sum(conf_zs) / len(conf_zs)
                err_zs      = sum(1 for t, p in zip(y_true, pred_zs) if t != p)
                st.metric("Accuracy", f"{acc_zs:.1f}%", delta=f"{acc_zs - acc_emb:+.1f}% vs Emb")
                st.metric("Confianza media", f"{avg_conf_zs:.3f}")
                st.metric("Errores", str(err_zs))

        if not zs_error:
            st.divider()
            st.subheader("📊 Accuracy por intención")
            intents_uniq = sorted(set(y_true))
            acc_emb_pi, acc_zs_pi = [], []
            for intent in intents_uniq:
                casos_i = [(t, pe, pz) for t, pe, pz in zip(y_true, pred_emb, pred_zs) if t == intent]
                n = len(casos_i)
                acc_emb_pi.append(sum(1 for t, pe, _ in casos_i if t == pe) / n * 100)
                acc_zs_pi.append(sum(1 for t, _, pz in casos_i if t == pz) / n * 100)

            nombres_i = [i.replace("_", " ") for i in intents_uniq]
            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(name="Sentence-Transformers", y=nombres_i, x=acc_emb_pi,
                                      orientation="h", marker_color="#3498db",
                                      text=[f"{v:.0f}%" for v in acc_emb_pi], textposition="auto"))
            fig_comp.add_trace(go.Bar(name="Zero-Shot mDeBERTa", y=nombres_i, x=acc_zs_pi,
                                      orientation="h", marker_color="#e67e22",
                                      text=[f"{v:.0f}%" for v in acc_zs_pi], textposition="auto"))
            fig_comp.update_layout(barmode="group", xaxis=dict(range=[0, 110], ticksuffix="%"),
                                   yaxis=dict(autorange="reversed"), legend=dict(orientation="h", y=1.1),
                                   margin=dict(t=30, b=10, l=10, r=10), height=320)
            fig_comp.add_vline(x=80, line_dash="dash", line_color="#e74c3c",
                               annotation_text="80% objetivo", annotation_position="top right")
            st.plotly_chart(fig_comp, use_container_width=True)

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
        st.dataframe(
            pd.DataFrame([{"#": i+1, "Texto": c["text"], "Intent esperado": c["expected_intent"]}
                          for i, c in enumerate(INTENT_TEST_CASES)]),
            use_container_width=True, hide_index=True,
        )


# ===========================================================================
# TAB 4 — Tests de Integración (Intent+Router · Flujos de Chat · Assertions)
# ===========================================================================

with tab_integration:
    total_checks_all = sum(len(f["checks"]) for f in FLOW_ASSERTIONS)
    st.caption(
        f"Ejecuta **{len(INTENT_ROUTER_CASES)} casos** de intent+routing, "
        f"**{len(CHAT_FLOWS)} flujos** de conversación y "
        f"**{total_checks_all} assertions** sobre el estado final — todo en un solo botón."
    )
    st.warning(
        "Usa el orquestador completo. Si ChromaDB no está indexado, los flujos que "
        "terminan en RAG devolverán el fallback.",
        icon="⚠️",
    )

    if st.button("▶ Ejecutar todos los tests de integración", type="primary", key="btn_integration"):
        from app.services.chat_orchestrator import ChatOrchestrator
        from app.services.rag_executor import RagExecutor
        from app.services.tool_executor import ToolExecutor
        from app.services.llm_service import LLMService
        from collections import Counter
        import pandas as pd
        import plotly.graph_objects as go

        @st.cache_resource
        def cargar_rag_integracion():
            return RagService()

        @st.cache_resource
        def cargar_llm_integracion():
            return LLMService()

        rag_i = cargar_rag_integracion()
        llm_i = cargar_llm_integracion()

        def build_orch():
            return ChatOrchestrator(
                state_store=InMemoryStateStore(),
                intent_classifier=IntentService(),
                router=ConversationRouter(),
                tool_executor=ToolExecutor(rag_service=rag_i, llm_service=llm_i),
                rag_executor=RagExecutor(rag_service=rag_i, llm_service=llm_i),
            )

        # -------------------------------------------------------------------
        # SECCIÓN 1 — Intent + Router
        # -------------------------------------------------------------------
        st.divider()
        st.subheader("🔀 Sección 1: Intent + Router")
        st.caption(f"{len(INTENT_ROUTER_CASES)} casos — verifica intent clasificado y acción del router")

        with st.spinner("Clasificando intenciones y decisiones de routing..."):
            clf_r = IntentService()
            router_r = ConversationRouter()
            store_r = InMemoryStateStore()
            y_true_r, y_pred_r, det_router = [], [], []

            for i, caso in enumerate(INTENT_ROUTER_CASES):
                state_r = store_r.get(f"integ-router-{i}")
                ir = clf_r.classify_topic(caso["text"])
                dec = router_r.decide(message=caso["text"], intent_result=ir, state=state_r)
                correcto = ir.intent == caso["expected_intent"]
                y_true_r.append(caso["expected_intent"])
                y_pred_r.append(ir.intent)
                top3 = " | ".join(
                    f"{r.label.split('consulta sobre ')[-1][:28]} ({r.score:.2f})"
                    for r in ir.ranked_labels[:3]
                )
                det_router.append({
                    "✓": "✅" if correcto else "❌",
                    "Texto": caso["text"],
                    "Esperado": caso["expected_intent"],
                    "Predicho": ir.intent,
                    "Conf": round(ir.confidence, 3),
                    "Acción": dec.action,
                    "Tool": dec.tool_name or "—",
                    "Top-3": top3,
                })

        acc_r = sum(t == p for t, p in zip(y_true_r, y_pred_r)) / len(y_true_r) * 100
        cr1, cr2, cr3 = st.columns(3)
        cr1.metric("Accuracy", f"{acc_r:.1f}%")
        cr2.metric("Errores", str(sum(1 for t, p in zip(y_true_r, y_pred_r) if t != p)))
        cr3.metric("Casos", str(len(INTENT_ROUTER_CASES)))

        intents_r = sorted(set(y_true_r))
        acc_por_r = []
        for intent in intents_r:
            pares = [(t, p) for t, p in zip(y_true_r, y_pred_r) if t == intent]
            acc_por_r.append(sum(1 for t, p in pares if t == p) / len(pares) * 100)

        col_r1, col_r2 = st.columns([2, 1])
        with col_r1:
            fig_r = go.Figure(go.Bar(
                y=[i.replace("_", " ") for i in intents_r], x=acc_por_r, orientation="h",
                marker_color=["#2ecc71" if v >= 80 else "#e74c3c" for v in acc_por_r],
                text=[f"{v:.0f}%" for v in acc_por_r], textposition="auto",
            ))
            fig_r.update_layout(xaxis=dict(range=[0, 110], ticksuffix="%"),
                                 yaxis=dict(autorange="reversed"),
                                 margin=dict(t=10, b=10, l=10, r=10), height=240, showlegend=False)
            fig_r.add_vline(x=80, line_dash="dash", line_color="#e74c3c",
                            annotation_text="80%", annotation_position="top right")
            st.plotly_chart(fig_r, use_container_width=True)

        with col_r2:
            acciones = Counter(d["Acción"] for d in det_router)
            fig_acc = go.Figure(go.Pie(
                labels=list(acciones.keys()), values=list(acciones.values()),
                hole=0.4, textinfo="label+value",
                marker_colors=["#3498db", "#2ecc71", "#e74c3c", "#f39c12"],
            ))
            fig_acc.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=240)
            st.plotly_chart(fig_acc, use_container_width=True)

        with st.expander(f"Ver los {len(INTENT_ROUTER_CASES)} casos detallados"):
            st.dataframe(pd.DataFrame(det_router), use_container_width=True, hide_index=True)

        # -------------------------------------------------------------------
        # SECCIÓN 2 — Flujos de Chat
        # -------------------------------------------------------------------
        st.divider()
        st.subheader("💬 Sección 2: Flujos de Chat")
        st.caption(f"{len(CHAT_FLOWS)} flujos — conversaciones completas turno a turno")

        for flujo in CHAT_FLOWS:
            with st.spinner(f"Ejecutando flujo '{flujo['nombre']}'..."):
                orch_f = build_orch()
                resultados_f = [orch_f.handle_message(flujo["session_id"], m) for m in flujo["mensajes"]]

            with st.expander(f"{flujo['icono']} {flujo['nombre']} — {len(flujo['mensajes'])} turnos"):
                st.caption(flujo["descripcion"])
                for i, (msg, res) in enumerate(zip(flujo["mensajes"], resultados_f), start=1):
                    c_left, c_right = st.columns([1, 2])
                    with c_left:
                        st.markdown(f"**Turno {i}** — `{msg}`")
                        st.markdown(f"Intent: `{res['intent_result']['intent']}` · conf: `{res['intent_result']['confidence']:.2f}`")
                        st.markdown(f"Acción: `{res['route_decision']['action']}` · tool: `{res['route_decision'].get('tool_name') or '—'}`")
                    with c_right:
                        st.info(res["response"])
                estado_f = resultados_f[-1]["state"]
                if estado_f.get("entities"):
                    st.json(estado_f["entities"])

        # -------------------------------------------------------------------
        # SECCIÓN 3 — Assertions
        # -------------------------------------------------------------------
        st.divider()
        st.subheader("✅ Sección 3: Assertions de estado final")
        st.caption(f"{total_checks_all} assertions sobre {len(FLOW_ASSERTIONS)} flujos")

        total_pass = 0
        resumen_assert = []

        for flujo_def in FLOW_ASSERTIONS:
            with st.spinner(f"Assertions '{flujo_def['flujo']}'..."):
                orch_a = build_orch()
                last_a = {}
                for msg in flujo_def["mensajes"]:
                    last_a = orch_a.handle_message(flujo_def["session_id"], msg)

            state_a = last_a["state"]
            resp_a  = last_a["response"]
            rows_a  = []
            flujo_pass = 0

            for check in flujo_def["checks"]:
                try:
                    paso = bool(check["fn"](state_a, resp_a))
                    err_txt = ""
                except Exception as e:
                    paso = False
                    err_txt = str(e)
                if paso:
                    flujo_pass += 1
                    total_pass += 1
                rows_a.append({
                    "": "✅" if paso else "❌",
                    "Assertion": check["nombre"],
                    "Resultado": "PASS" if paso else f"FAIL{' — ' + err_txt if err_txt else ''}",
                })
            resumen_assert.append({"flujo": flujo_def["flujo"], "pass": flujo_pass,
                                   "total": len(flujo_def["checks"]), "rows": rows_a,
                                   "state": state_a})

        pct_assert = total_pass / total_checks_all * 100
        ca1, ca2 = st.columns(2)
        ca1.metric("PASS total", f"{total_pass} / {total_checks_all}")
        ca2.metric("Tasa global", f"{pct_assert:.0f}%")

        if total_pass == total_checks_all:
            st.success("✅ Todas las assertions pasaron.")
        else:
            st.error(f"❌ {total_checks_all - total_pass} assertion(s) fallaron.")

        fig_pa = go.Figure(go.Bar(
            x=[r["flujo"] for r in resumen_assert],
            y=[r["pass"] / r["total"] * 100 for r in resumen_assert],
            marker_color=["#2ecc71" if r["pass"] == r["total"] else "#e74c3c" for r in resumen_assert],
            text=[f"{r['pass']}/{r['total']}" for r in resumen_assert],
            textposition="auto",
        ))
        fig_pa.update_layout(yaxis=dict(range=[0, 110], ticksuffix="%"),
                             margin=dict(t=10, b=10, l=10, r=10), height=240, showlegend=False)
        fig_pa.add_hline(y=100, line_dash="dash", line_color="#2ecc71")
        st.plotly_chart(fig_pa, use_container_width=True)

        for r in resumen_assert:
            icono = "✅" if r["pass"] == r["total"] else "❌"
            with st.expander(f"{icono} {r['flujo']} — {r['pass']}/{r['total']} assertions"):
                st.dataframe(pd.DataFrame(r["rows"]), use_container_width=True, hide_index=True)
                with st.expander("Estado final"):
                    st.json(r["state"])

    else:
        st.info("Haz clic en **▶ Ejecutar todos los tests de integración** para correr las 3 secciones.")
        st.markdown("### ¿Qué corre este tab?")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.markdown("**🔀 Intent + Router**")
            st.markdown(f"{len(INTENT_ROUTER_CASES)} casos — verifica que el clasificador y el router toman las decisiones correctas juntos.")
        with col_s2:
            st.markdown("**💬 Flujos de Chat**")
            for f in CHAT_FLOWS:
                st.markdown(f"- {f['icono']} {f['nombre']} ({len(f['mensajes'])} turnos)")
        with col_s3:
            st.markdown("**✅ Assertions**")
            for f in FLOW_ASSERTIONS:
                st.markdown(f"- {f['flujo']}: {len(f['checks'])} checks")
