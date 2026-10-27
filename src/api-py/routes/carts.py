from __future__ import annotations

from fastapi import APIRouter, Response

from models.cart import AddCartItemRequest, Cart, UpdateCartItemRequest
from repositories.carts import CartsRepository
from utils.errors import NotFoundException, ValidationException

router = APIRouter(prefix="/api/carts", tags=["Carts"])
repository = CartsRepository()


@router.post("", response_model=Cart, status_code=201)
async def create() -> Cart:
    return await repository.create()


@router.get("/{cart_id}", response_model=Cart)
async def get_by_id(cart_id: str) -> Cart:
    cart = await repository.find_by_id(cart_id)
    if cart is None:
        raise NotFoundException("Cart", cart_id)
    return cart


@router.post("/{cart_id}/items", response_model=Cart)
async def add_item(cart_id: str, request: AddCartItemRequest) -> Cart:
    if request.productId <= 0 or request.quantity <= 0:
        raise ValidationException("productId and quantity must be positive integers")
    return await repository.add_item(cart_id, request.productId, request.quantity)


@router.put("/{cart_id}/items/{product_id}", response_model=Cart)
async def update_item(
    cart_id: str,
    product_id: int,
    request: UpdateCartItemRequest,
) -> Cart:
    if product_id <= 0 or request.quantity <= 0:
        raise ValidationException("productId and quantity must be positive integers")
    return await repository.update_item(cart_id, product_id, request.quantity)


@router.delete("/{cart_id}/items/{product_id}", status_code=204)
async def remove_item(cart_id: str, product_id: int) -> Response:
    await repository.remove_item(cart_id, product_id)
    return Response(status_code=204)