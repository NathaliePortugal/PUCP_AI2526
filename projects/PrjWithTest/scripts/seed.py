"""Carga el catalogo de productos y clientes de prueba en SQLite.

Uso: uv run python scripts/seed.py
"""

import csv
from pathlib import Path

from vendebot.config import get_settings
from vendebot.repo.sqlite import get_connection, init_db

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS_CSV = ROOT / "data" / "fixtures" / "products.csv"

# clientes de prueba con api_key fija: permiten probar la autenticacion
# por X-API-Key (Fase 3) sin necesitar un flujo de registro.
TEST_CUSTOMERS = [
    {"id": "C001", "name": "Ana Torres", "api_key": "dev-key-c001"},
    {"id": "C002", "name": "Luis Paredes", "api_key": "dev-key-c002"},
]


def load_products(conn, csv_path: Path) -> int:
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [(r["id"], r["nombre"], float(r["precio"]), int(r["stock"])) for r in reader]
    conn.executemany(
        "INSERT OR REPLACE INTO products (id, name, price, stock) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def load_customers(conn, customers: list[dict]) -> int:
    rows = [(c["id"], c["name"], c["api_key"]) for c in customers]
    conn.executemany(
        "INSERT OR REPLACE INTO customers (id, name, api_key) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def seed(db_path: str | Path, products_csv: Path = PRODUCTS_CSV, customers: list[dict] | None = None) -> dict:
    customers = customers if customers is not None else TEST_CUSTOMERS
    conn = get_connection(db_path)
    init_db(conn)
    n_products = load_products(conn, products_csv)
    n_customers = load_customers(conn, customers)
    conn.close()
    return {"products": n_products, "customers": n_customers}


def main() -> None:
    settings = get_settings()
    result = seed(settings.sqlite_path)
    print(f"Productos cargados: {result['products']}")
    print(f"Clientes cargados: {result['customers']}")


if __name__ == "__main__":
    main()
