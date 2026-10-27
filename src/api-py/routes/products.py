from __future__ import annotations

from fastapi import APIRouter

from models.product import CreateProductRequest, Product, UpdateProductRequest
from repositories.products import ProductsRepository
from repositories.suppliers import SuppliersRepository
from utils.errors import NotFoundException, ValidationException

router = APIRouter(prefix="/api/products", tags=["Products"])
repository = ProductsRepository()
suppliers_repository = SuppliersRepository()


@router.get("", response_model=list[Product])
async def get_all(search: str | None = None, supplier_id: int | None = None) -> list[Product]:
    normalized_search = search.strip() if search else None
    if normalized_search == "":
        normalized_search = None

    if supplier_id is not None:
        if supplier_id <= 0:
            raise ValidationException("supplier_id must be a positive integer")
        supplier = await suppliers_repository.find_by_id(supplier_id)
        if supplier is None:
            raise NotFoundException("Supplier", supplier_id)

    return await repository.find_all(normalized_search, supplier_id)


@router.get("/{product_id}", response_model=Product)
async def get_by_id(product_id: int) -> Product:
    product = await repository.find_by_id(product_id)
    if product is None:
        raise NotFoundException("Product", product_id)
    return product


@router.post("", response_model=Product, status_code=201)
async def create(request: CreateProductRequest) -> Product:
    if not request.name.strip():
        raise ValidationException("name is required")
    return await repository.create(request)


@router.put("/{product_id}", response_model=Product)
async def update(product_id: int, request: UpdateProductRequest) -> Product:
    return await repository.update(product_id, request)


@router.delete("/{product_id}", status_code=204)
async def delete(product_id: int) -> None:
    await repository.delete(product_id)
