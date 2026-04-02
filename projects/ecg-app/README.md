# Visualizador ECG 🫀

Aplicación web interactiva para visualizar registros ECG de 12 derivaciones, construida con Streamlit.

## Características

- Visualización de señales ECG con cuadrícula médica estándar (papel milimetrado)
- Soporte para 12 derivaciones: I, II, III, aVR, aVL, aVF, V1–V6
- Control de ventana temporal (2–15 segundos)
- Etiqueta diagnóstica por registro
- Formato de datos: WFDB (`.hea` + `.mat`)

## Requisitos previos

- Python 3.9 o superior
- Git

## Instalación y ejecución local

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/TU_REPOSITORIO.git
cd TU_REPOSITORIO
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

El repositorio incluye 3 registros ECG de ejemplo en `sample_data/` para que la app funcione de inmediato:

```
sample_data/
├── JS00001.hea
├── JS00001.mat
├── JS00002.hea
├── JS00002.mat
├── JS00004.hea
└── JS00004.mat
```

## Usar el dataset completo (opcional)

El dataset completo (CPSC 2018 / JS ECG Database, ~6,500 registros, 773 MB) no está incluido en el repositorio. Para usarlo:

1. Descarga el dataset desde [PhysioNet - CPSC 2018](https://physionet.org/content/cpsc2018/1.0.0/)
2. Coloca todos los archivos `.hea` y `.mat` en una carpeta llamada `Muestra/` en la raíz del proyecto
3. Edita `config.py` y cambia:
   ```python
   DATA_DIR = "Muestra"
   ```

## Estructura del proyecto

```
ecg-app/
├── app.py                  # Aplicación principal Streamlit
├── config.py               # Configuración (rutas, colores, derivaciones)
├── requirements.txt        # Dependencias Python
├── sample_data/            # Registros ECG de ejemplo (incluidos en el repo)
├── data/
│   ├── __init__.py
│   └── loader.py           # Carga de registros WFDB
└── visualization/
    ├── __init__.py
    └── plotter.py          # Generación de gráficas ECG con Plotly
```

## Dependencias principales

| Librería | Uso |
|----------|-----|
| `streamlit` | Framework de la app web |
| `wfdb` | Lectura de registros en formato PhysioNet |
| `plotly` | Visualización interactiva |
| `neurokit2` | Procesamiento de señales biomédicas |
| `numpy` / `pandas` | Cómputo numérico y manejo de datos |
