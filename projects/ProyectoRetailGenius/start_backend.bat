@echo off
echo ========================================
echo   RetailGenius - Backend (FastAPI)
echo ========================================
echo.
echo Instalando dependencias...
pip install -r requirements.txt
echo.
echo Iniciando servidor en http://localhost:8000
echo Docs: http://localhost:8000/docs
echo.
echo IMPORTANTE: Asegurate de tener Ollama corriendo
echo   ollama pull llama3.2:3b
echo.
uvicorn backend.main:app --reload --port 8000
pause
