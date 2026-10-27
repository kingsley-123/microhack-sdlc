from __future__ import annotations

from pydantic import BaseModel


class AddCartItemRequest(BaseModel):
    productId: int
    quantity: int


class UpdateCartItemRequest(BaseModel):
    quantity: int


class CartItem(BaseModel):
    productId: int
    name: str
    description: str | None = None
    sku: str
    unit: str
    imgName: str | None = None
    quantity: int
    unitPrice: float
    lineTotal: float


class Cart(BaseModel):
    cartId: str
    items: list[CartItem]
    total: float