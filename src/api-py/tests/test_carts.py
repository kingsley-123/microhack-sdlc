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


def create_product(
    client: TestClient,
    name: str = "Cart Test Product",
    price: float = 19.99,
    discount: float = 0.1,
) -> int:
    supplier_response = client.post("/api/suppliers", json={"name": "Cart Test Supplier"})
    assert supplier_response.status_code == 201
    product_response = client.post(
        "/api/products",
        json={
            "supplierId": supplier_response.json()["supplierId"],
            "name": name,
            "price": price,
            "sku": "CART-TEST-001",
            "unit": "piece",
            "discount": discount,
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


def test_cart_totals_multiple_items_and_persists_across_clients(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    discounted_product_id = create_product(client)
    regular_product_id = create_product(
        client,
        name="Cart Test Product Without Discount",
        price=10.0,
        discount=0.0,
    )
    cart_id = client.post("/api/carts").json()["cartId"]

    client.post(
        f"/api/carts/{cart_id}/items",
        json={"productId": discounted_product_id, "quantity": 2},
    )
    client.post(
        f"/api/carts/{cart_id}/items",
        json={"productId": regular_product_id, "quantity": 3},
    )

    cart_response = client.get(f"/api/carts/{cart_id}")
    assert cart_response.status_code == 200
    cart = cart_response.json()
    items_by_product = {item["productId"]: item for item in cart["items"]}
    assert items_by_product[discounted_product_id]["unitPrice"] == 17.99
    assert items_by_product[discounted_product_id]["lineTotal"] == 35.98
    assert items_by_product[regular_product_id]["unitPrice"] == 10.0
    assert items_by_product[regular_product_id]["lineTotal"] == 30.0
    assert cart["total"] == 65.98

    monkeypatch.setenv("DB_FILE", str(tmp_path / "cart-tests.db"))
    with TestClient(app) as reopened_client:
        reopened_response = reopened_client.get(f"/api/carts/{cart_id}")

    assert reopened_response.status_code == 200
    assert reopened_response.json() == cart


def test_failed_cart_operations_leave_contents_and_totals_unchanged(
    client: TestClient,
) -> None:
    product_id = create_product(client)
    cart_id = client.post("/api/carts").json()["cartId"]
    add_response = client.post(
        f"/api/carts/{cart_id}/items",
        json={"productId": product_id, "quantity": 2},
    )
    assert add_response.status_code == 200
    original_cart = add_response.json()

    invalid_adds = [
        ({"productId": product_id, "quantity": 0}, 400),
        ({"productId": product_id, "quantity": -1}, 400),
        ({"productId": product_id, "quantity": "not-an-integer"}, 422),
        ({"productId": product_id}, 422),
        ({"productId": 9999, "quantity": 1}, 404),
    ]
    for payload, expected_status in invalid_adds:
        response = client.post(f"/api/carts/{cart_id}/items", json=payload)
        assert response.status_code == expected_status
        assert client.get(f"/api/carts/{cart_id}").json() == original_cart

    invalid_update = client.put(
        f"/api/carts/{cart_id}/items/{product_id}",
        json={"quantity": 0},
    )
    assert invalid_update.status_code == 400
    assert client.get(f"/api/carts/{cart_id}").json() == original_cart

    missing_item_update = client.put(
        f"/api/carts/{cart_id}/items/9999",
        json={"quantity": 1},
    )
    missing_item_remove = client.delete(f"/api/carts/{cart_id}/items/9999")
    assert missing_item_update.status_code == 404
    assert missing_item_remove.status_code == 404
    assert client.get(f"/api/carts/{cart_id}").json() == original_cart

    missing_cart_get = client.get("/api/carts/not-a-cart")
    missing_cart_add = client.post(
        "/api/carts/not-a-cart/items",
        json={"productId": product_id, "quantity": 1},
    )
    missing_cart_update = client.put(
        f"/api/carts/not-a-cart/items/{product_id}",
        json={"quantity": 1},
    )
    missing_cart_remove = client.delete(f"/api/carts/not-a-cart/items/{product_id}")
    assert missing_cart_get.status_code == 404
    assert missing_cart_add.status_code == 404
    assert missing_cart_update.status_code == 404
    assert missing_cart_remove.status_code == 404
    assert client.get(f"/api/carts/{cart_id}").json() == original_cart