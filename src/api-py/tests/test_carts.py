from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    migrations_dir = Path(__file__).resolve().parents[2] / "database" / "migrations"
    monkeypatch.setenv("DB_FILE", str(tmp_path / "cart-tests.db"))
    monkeypatch.setenv("DB_MIGRATIONS_DIR", str(migrations_dir))
    with TestClient(app) as test_client:
        yield test_client


def create_product(client: TestClient) -> int:
    supplier_response = client.post("/api/suppliers", json={"name": "Cart Test Supplier"})
    assert supplier_response.status_code == 201
    product_response = client.post(
        "/api/products",
        json={
            "supplierId": supplier_response.json()["supplierId"],
            "name": "Cart Test Product",
            "price": 19.99,
            "sku": "CART-TEST-001",
            "unit": "piece",
            "discount": 0.1,
        },
    )
    assert product_response.status_code == 201
    return product_response.json()["productId"]


def test_cart_persists_items_and_calculates_discounted_total(client: TestClient) -> None:
    product_id = create_product(client)
    cart_response = client.post("/api/carts")
    assert cart_response.status_code == 201
    cart_id = cart_response.json()["cartId"]
    assert cart_response.json()["items"] == []

    add_response = client.post(
        f"/api/carts/{cart_id}/items",
        json={"productId": product_id, "quantity": 2},
    )
    assert add_response.status_code == 200
    assert add_response.json()["items"][0]["quantity"] == 2
    assert add_response.json()["items"][0]["unitPrice"] == 17.99
    assert add_response.json()["items"][0]["lineTotal"] == 35.98
    assert add_response.json()["total"] == 35.98

    add_again_response = client.post(
        f"/api/carts/{cart_id}/items",
        json={"productId": product_id, "quantity": 1},
    )
    assert add_again_response.json()["items"][0]["quantity"] == 3

    persisted_response = client.get(f"/api/carts/{cart_id}")
    assert persisted_response.status_code == 200
    assert persisted_response.json()["total"] == 53.97


def test_cart_item_quantity_can_be_updated_and_removed(client: TestClient) -> None:
    product_id = create_product(client)
    cart_id = client.post("/api/carts").json()["cartId"]
    client.post(
        f"/api/carts/{cart_id}/items",
        json={"productId": product_id, "quantity": 2},
    )

    update_response = client.put(
        f"/api/carts/{cart_id}/items/{product_id}",
        json={"quantity": 4},
    )
    assert update_response.status_code == 200
    assert update_response.json()["items"][0]["quantity"] == 4
    assert update_response.json()["total"] == 71.96

    remove_response = client.delete(f"/api/carts/{cart_id}/items/{product_id}")
    assert remove_response.status_code == 204
    empty_cart = client.get(f"/api/carts/{cart_id}").json()
    assert empty_cart["items"] == []
    assert empty_cart["total"] == 0.0


def test_cart_rejects_invalid_or_missing_resources(client: TestClient) -> None:
    cart_id = client.post("/api/carts").json()["cartId"]

    invalid_quantity = client.post(
        f"/api/carts/{cart_id}/items",
        json={"productId": 1, "quantity": 0},
    )
    assert invalid_quantity.status_code == 400

    missing_product = client.post(
        f"/api/carts/{cart_id}/items",
        json={"productId": 9999, "quantity": 1},
    )
    assert missing_product.status_code == 404

    missing_cart = client.get("/api/carts/not-a-cart")
    assert missing_cart.status_code == 404