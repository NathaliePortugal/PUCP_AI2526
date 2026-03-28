------------------------------------------
------------Ejecutar BE------------------- (Aun falta)
------------------------------------------
cd sunat
pip install -r requirements.txt
uvicorn app.main:app --reload

------------------------------------------
------------Ejecutar FE------------------- (Aun falta)
------------------------------------------
cd frontend
npm install
npm run dev
FE disponible en --> http://localhost:5173

------------------------------------------
------------Ejecutar pruebas-------------- (Testeable pero instalar esas dependenciasgm)
------------------------------------------
pip install transformers torch pydantic
pip install sentence-transformers faiss-cpu
pip install sentence-transformers

Dentro de la carpeta sunat, Ejecutar:
python scratch_test_intent_router.py


--------------------------------------------------
-------- Indexar documentos (RAG) 1 sola vez -----
-------------------------------------------------
python scripts/ingest_documents.py --verbose

------------Verificar que quedo bien --------------
python scripts/inspect_chroma.py
python scripts/inspect_chroma.py --samples          # ver un chunk de cada archivo
python scripts/inspect_chroma.py --search "multas"  # probar una búsqueda real


-------------------------------------------------
---------   EVALUAR RESULTADOS	 ----------------
-------------------------------------------------
# 1. Evalúa el clasificador de intenciones
python scripts/evaluate_intent.py --verbose

# 2. Evalúa el RAG (necesita documentos indexados)
python scripts/evaluate_rag.py --verbose

# 3. Evalúa el routing end-to-end
python scripts/evaluate_routing.py --verbose

# Agrega --verbose para ver el detalle de cada caso
python scripts/evaluate_intent.py --verbose

---------------------------------------------------
---------  EJECUTAR O RE-PROCESAR RAG -------------
---------------------------------------------------
python scripts/ingest_documents.py --force

