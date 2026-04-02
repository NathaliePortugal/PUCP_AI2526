# Visualizador ECG 🫀

Aplicación web interactiva para visualizar registros ECG de 12 derivaciones y analizar la frecuencia cardiaca, construida con Streamlit.

## Características

### Fase 1 — Visualización ECG
- Visualización de señales ECG con cuadrícula médica estándar (papel milimetrado)
- Soporte para 12 derivaciones: I, II, III, aVR, aVL, aVF, V1–V6
- Control de ventana temporal (2–15 segundos)
- Selector de paciente y derivaciones desde el sidebar
- Etiqueta diagnóstica por registro
- Formato de datos: WFDB (`.hea` + `.mat`)

### Fase 2 — Análisis de Frecuencia Cardiaca
- Limpieza de señal y detección de picos R con NeuroKit2 (Derivada II)
- Cálculo de frecuencia cardiaca media (BPM) e intervalo RR
- Alerta clínica automática: bradicardia (<60 BPM), normal, taquicardia (>100 BPM)
- Gráfico comparativo de detección de picos R en derivadas I, II y III
- Tabla de métricas por derivada: BPM, picos R detectados, SNR aproximado

## Requisitos previos

- Python 3.9 o superior
- Git

## Instalación y ejecución local

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/TU_REPOSITORIO.git
cd TU_REPOSITORIO/ecg-app
```

### 2. Crear y activar entorno virtual

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Ejecutar la aplicación

```bash
streamlit run app.py
```

La app abrirá automáticamente en el navegador en `http://localhost:8501`.

## Datos de muestra

Los registros ECG de ejemplo se encuentran en `Muestra/`. La carpeta incluye archivos en formato WFDB (`.hea` + `.mat`):

```
Muestra/
├── JS00001.hea
├── JS00001.mat
├── JS00002.hea
├── JS00002.mat
└── ...
```

## Usar el dataset completo (opcional)

El dataset completo (CPSC 2018 / JS ECG Database, ~6 500 registros, 773 MB) no está incluido en el repositorio. Para usarlo:

1. Descarga el dataset desde [PhysioNet - CPSC 2018](https://physionet.org/content/cpsc2018/1.0.0/)
2. Coloca todos los archivos `.hea` y `.mat` en la carpeta `Muestra/` en la raíz del proyecto

## Estructura del proyecto

```
ecg-app/
├── app.py                  # Aplicación principal Streamlit
├── config.py               # Configuración (rutas, colores, derivaciones)
├── ecg_hr_analysis.py      # Fase 2: análisis de frecuencia cardiaca
├── requirements.txt        # Dependencias Python
├── Muestra/                # Registros ECG de ejemplo
├── data/
│   ├── __init__.py
│   └── loader.py           # Carga de registros WFDB
└── visualization/
    ├── __init__.py
    └── plotter.py          # Gráficas ECG con cuadrícula médica (Plotly)
```

## Dependencias principales

| Librería | Versión | Uso |
|----------|---------|-----|
| `streamlit` | 1.55.0 | Framework de la app web |
| `wfdb` | 4.3.1 | Lectura de registros en formato PhysioNet |
| `plotly` | 6.6.0 | Visualización interactiva |
| `neurokit2` | 0.2.13 | Limpieza de señal ECG y detección de picos R |
| `numpy` | 1.26.4 | Cómputo numérico |
| `pandas` | 2.3.3 | Manejo de datos tabulares |
| `scipy` | 1.15.3 | Procesamiento de señales (dependencia de NeuroKit2) |
