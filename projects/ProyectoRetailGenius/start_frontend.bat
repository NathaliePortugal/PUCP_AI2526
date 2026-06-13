@echo off
echo ========================================
echo   RetailGenius - Frontend (React)
echo ========================================
echo.

cd /d "%~dp0frontend"
if %errorlevel% neq 0 (
    echo ERROR: No se encontro la carpeta frontend en %~dp0
    pause
    exit /b 1
)

echo Carpeta: %cd%
echo.

where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: npm no encontrado.
    echo Instala Node.js desde https://nodejs.org y vuelve a intentar.
    pause
    exit /b 1
)

echo npm encontrado en:
where npm
echo.

echo Instalando dependencias...
call npm install
if %errorlevel% neq 0 (
    echo.
    echo ERROR: npm install fallo. Revisa los mensajes de arriba.
    pause
    exit /b 1
)

echo.
echo Iniciando servidor en http://localhost:3000
echo Para detener presiona Ctrl+C
echo.
call npm run dev

echo.
echo El servidor se detuvo.
pause
