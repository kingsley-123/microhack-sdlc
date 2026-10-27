from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    migrations_dir = Path(__file__).resolve().parents[2] / "database" / "migrations"
    monkeypatch.setenv("DB_FILE", str(tmp_path / "product-search-tests.db"))
    monkeypatch.setenv("DB_MIGRATIONS_DIR", str(migrations_dir))
    with TestClient(app) as test_client:
        yield test_client


def create_supplier(client: TestClient, name: str) -> int:
    response = client.post("/api/suppliers", json={"name": name})
    assert response.status_code == 201
    return response.json()["supplierId"]


def create_product(
    client: TestClient,
    supplier_id: int,
    name: str,
    sku: str,
) -> int:
    response = client.post(
        "/api/products",
        json={
            "supplierId": supplier_id,
            "name": name,
            "price": 12.5,
            "sku": sku,
            "unit": "piece",
        },
    )
    assert response.status_code == 201
    return response.json()["productId"]


def test_search_matches_name_and_sku_case_insensitively(client: TestClient) -> None:
    supplier_id = create_supplier(client, "Search Supplier")
    name_match_id = create_product(
        client,
        supplier_id,
        "NameSearchCaseProbe",
        "CASE-PROBE-NAME-001",
    )
    sku_match_id = create_product(
        client,
        supplier_id,
        "SkuSearchCaseProbe",
        "SkuCaseProbe-002",
    )
    create_product(client, supplier_id, "HydroFlow Bowl", "CAT-WATER-003")

    name_response = client.get("/api/products", params={"search": "nAmEsEaRcHcAsEpRoBe"})
    sku_response = client.get("/api/products", params={"search": "sKuCaSePrObE"})

    assert [product["productId"] for product in name_response.json()] == [name_match_id]
    assert [product["productId"] for product in sku_response.json()] == [sku_match_id]


def test_search_and_supplier_filter_combine_and_blank_search_is_ignored(
    client: TestClient,
) -> None:
    first_supplier_id = create_supplier(client, "First Search Supplier")
    second_supplier_id = create_supplier(client, "Second Search Supplier")
    first_product_id = create_product(
        client,
        first_supplier_id,
        "SupplierFilterProbe First Edition",
        "FEED-FIRST",
    )
    second_product_id = create_product(
        client,
        second_supplier_id,
        "SupplierFilterProbe Second Edition",
        "FEED-SECOND",
    )

    combined_response = client.get(
        "/api/products",
        params={"search": "supplierfilterprobe", "supplier_id": second_supplier_id},
    )
    blank_search_response = client.get("/api/products", params={"search": "   "})
    unfiltered_response = client.get("/api/products")

    assert [product["productId"] for product in combined_response.json()] == [second_product_id]
    assert first_product_id in [product["productId"] for product in blank_search_response.json()]
    assert second_product_id in [product["productId"] for product in blank_search_response.json()]
    assert blank_search_response.json() == unfiltered_response.json()


def test_search_treats_wildcards_as_literal_characters(client: TestClient) -> None:
    supplier_id = create_supplier(client, "Wildcard Search Supplier")
    literal_match_id = create_product(client, supplier_id, "Discount 100%", "ITEM_100")
    create_product(client, supplier_id, "Discount 100 units", "ITEM-100")

    percent_response = client.get("/api/products", params={"search": "%"})
    underscore_response = client.get("/api/products", params={"search": "_"})

    assert [product["productId"] for product in percent_response.json()] == [literal_match_id]
    assert [product["productId"] for product in underscore_response.json()] == [literal_match_id]


def test_search_treats_backslashes_and_sql_looking_input_as_literals(
    client: TestClient,
) -> None:
    supplier_id = create_supplier(client, "Literal Search Supplier")
    backslash_match_id = create_product(
        client,
        supplier_id,
        "Backslash\\MarkerSearchProbe",
        "BACKSLASH-SEARCH-001",
    )
    sql_looking_match_id = create_product(
        client,
        supplier_id,
        "Literal ' OR 1=1 -- Search Probe",
        "SQL-LOOKING-002",
    )
    create_product(client, supplier_id, "Unrelated Search Product", "SAFE-003")

    backslash_response = client.get(
        "/api/products",
        params={"search": "\\MarkerSearchProbe"},
    )
    sql_looking_response = client.get(
        "/api/products",
        params={"search": "' OR 1=1 --"},
    )

    assert [product["productId"] for product in backslash_response.json()] == [backslash_match_id]
    assert [product["productId"] for product in sql_looking_response.json()] == [
        sql_looking_match_id
    ]


def test_no_matches_and_supplier_validation(client: TestClient) -> None:
    supplier_id = create_supplier(client, "Validation Search Supplier")

    no_matches_response = client.get("/api/products", params={"search": "no-such-product"})
    invalid_supplier_response = client.get("/api/products", params={"supplier_id": 0})
    negative_supplier_response = client.get("/api/products", params={"supplier_id": -1})
    malformed_supplier_response = client.get(
        "/api/products",
        params={"supplier_id": "not-an-integer"},
    )
    fractional_supplier_response = client.get("/api/products", params={"supplier_id": 1.5})
    missing_supplier_response = client.get("/api/products", params={"supplier_id": 9999})

    assert no_matches_response.status_code == 200
    assert no_matches_response.json() == []
    assert invalid_supplier_response.status_code == 400
    assert negative_supplier_response.status_code == 400
    assert malformed_supplier_response.status_code == 422
    assert fractional_supplier_response.status_code == 422
    assert missing_supplier_response.status_code == 404
    assert client.get("/api/products", params={"supplier_id": supplier_id}).json() == []