from pathlib import Path

from scripts.seed import TEST_CUSTOMERS, seed
from vendebot.repo.sqlite import get_connection

PRODUCTS_CSV = Path("data/fixtures/products.csv")


def test_seed_loads_products_and_customers(tmp_path):
    db_path = tmp_path / "test.db"

    result = seed(db_path, products_csv=PRODUCTS_CSV, customers=TEST_CUSTOMERS)

    assert result["products"] == 5
    assert result["customers"] == len(TEST_CUSTOMERS)

    conn = get_connection(db_path)
    product = conn.execute("SELECT * FROM products WHERE id = ?", ("P001",)).fetchone()
    customer = conn.execute("SELECT * FROM customers WHERE id = ?", ("C001",)).fetchone()
    conn.close()

    assert product is not None
    assert product["stock"] == 15
    assert customer is not None
    assert customer["api_key"] == "dev-key-c001"


def test_seed_is_idempotent(tmp_path):
    db_path = tmp_path / "test.db"

    seed(db_path, products_csv=PRODUCTS_CSV, customers=TEST_CUSTOMERS)
    result = seed(db_path, products_csv=PRODUCTS_CSV, customers=TEST_CUSTOMERS)

    conn = get_connection(db_path)
    total = conn.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"]
    conn.close()

    assert result["products"] == 5
    assert total == 5
