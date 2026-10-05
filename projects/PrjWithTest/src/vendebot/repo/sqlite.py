"""Conexion y esquema de la base SQLite usada en local y en tests.

El esquema crece por fases. `chat_sessions` usa clave compuesta
(session_id, customer_id) a proposito: un session_id es solo un identificador
de conversacion elegido por el cliente, nunca una prueba de identidad, asi
que dos clientes pueden reutilizar el mismo valor sin pisarse el historial.
"""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    api_key TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    items_json TEXT NOT NULL,
    total REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    proposal_id TEXT NOT NULL,
    items_json TEXT NOT NULL,
    total REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed',
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    session_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    history_json TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (session_id, customer_id)
);

CREATE TABLE IF NOT EXISTS token_usage (
    customer_id TEXT NOT NULL,
    usage_date TEXT NOT NULL,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (customer_id, usage_date)
);

CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    label TEXT,
    motivo TEXT,
    evidencia TEXT,
    confianza REAL,
    updated_at TEXT
);
"""


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
