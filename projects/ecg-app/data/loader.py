import glob
import os

import numpy as np
import streamlit as st
import wfdb

from config import DATA_DIR


def get_registros_disponibles():
    archivos = sorted(glob.glob(os.path.join(DATA_DIR, "*.hea")))
    return [os.path.splitext(os.path.basename(a))[0] for a in archivos]


@st.cache_data(show_spinner="Cargando registro...")
def cargar(rid):
    path   = os.path.join(DATA_DIR, rid)
    record = wfdb.rdrecord(path)

    t = np.arange(record.sig_len) / record.fs

    señales = {
        lead: record.p_signal[:, i]
        for i, lead in enumerate(record.sig_name)
    }

    etiqueta = " | ".join(record.comments) if record.comments else "Sin etiqueta"

    return t, señales, etiqueta, record.fs
