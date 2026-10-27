from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

import aiosqlite

from database.sqlite import get_connection
from models.cart import Cart, CartItem
from utils.errors import DatabaseException, NotFoundException


class CartsRepository:
    async def create(self) -> Cart:
        cart_id = str(uuid4())
        async with get_connection() as connection:
            await connection.execute("INSERT INTO carts (cart_id) VALUES (?);", (cart_id,))
            await connection.commit()
        cart = await self.find_by_id(cart_id)
        if cart is None:
            raise DatabaseException("Failed to retrieve created Cart")
        return cart

    async def find_by_id(self, cart_id: str) -> Cart | None:
        async with get_connection() as connection:
            cursor = await connection.execute(
                "SELECT cart_id FROM carts WHERE cart_id = ?;",
                (cart_id,),
            )
            cart_row = await cursor.fetchone()
            if cart_row is None:
                return None

            cursor = await connection.execute(
                """
                SELECT p.product_id, p.name, p.description, p.sku, p.unit, p.img_name,
                       ci.quantity, p.price, COALESCE(p.discount, 0) AS discount
                FROM cart_items ci
                JOIN products p ON p.product_id = ci.product_id
                WHERE ci.cart_id = ?
                ORDER BY p.product_id;
                """,
                (cart_id,),
            )
            rows = await cursor.fetchall()

        items: list[CartItem] = []
        total = Decimal("0.00")
        for row in rows:
            unit_price = (
                Decimal(str(row["price"]))
                * (Decimal("1") - Decimal(str(row["discount"])))
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            line_total = (unit_price * row["quantity"]).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            total += line_total
            items.append(
                CartItem(
                    productId=row["product_id"],
                    name=row["name"],
                    description=row["description"],
                    sku=row["sku"],
                    unit=row["unit"],
                    imgName=row["img_name"],
                    quantity=row["quantity"],
                    unitPrice=float(unit_price),
                    lineTotal=float(line_total),
                )
            )

        return Cart(cartId=cart_id, items=items, total=float(total))

    async def add_item(self, cart_id: str, product_id: int, quantity: int) -> Cart:
        async with get_connection() as connection:
            await self._require_cart(connection, cart_id)
            await self._require_product(connection, product_id)
            await connection.execute(
                """
                INSERT INTO cart_items (cart_id, product_id, quantity)
                VALUES (?, ?, ?)
                ON CONFLICT (cart_id, product_id)
                DO UPDATE SET quantity = cart_items.quantity + excluded.quantity;
                """,
                (cart_id, product_id, quantity),
            )
            await connection.commit()
        cart = await self.find_by_id(cart_id)
        if cart is None:
            raise DatabaseException("Failed to retrieve updated Cart")
        return cart

    async def update_item(self, cart_id: str, product_id: int, quantity: int) -> Cart:
        async with get_connection() as connection:
            await self._require_cart(connection, cart_id)
            cursor = await connection.execute(
                """
                UPDATE cart_items SET quantity = ?
                WHERE cart_id = ? AND product_id = ?;
                """,
                (quantity, cart_id, product_id),
            )
            await connection.commit()
            if cursor.rowcount == 0:
                raise NotFoundException("Cart item", product_id)
        cart = await self.find_by_id(cart_id)
        if cart is None:
            raise DatabaseException("Failed to retrieve updated Cart")
        return cart

    async def remove_item(self, cart_id: str, product_id: int) -> None:
        async with get_connection() as connection:
            await self._require_cart(connection, cart_id)
            cursor = await connection.execute(
                "DELETE FROM cart_items WHERE cart_id = ? AND product_id = ?;",
                (cart_id, product_id),
            )
            await connection.commit()
            if cursor.rowcount == 0:
                raise NotFoundException("Cart item", product_id)

    @staticmethod
    async def _require_cart(connection: aiosqlite.Connection, cart_id: str) -> None:
        cursor = await connection.execute(
            "SELECT 1 FROM carts WHERE cart_id = ?;",
            (cart_id,),
        )
        if await cursor.fetchone() is None:
            raise NotFoundException("Cart", cart_id)

    @staticmethod
    async def _require_product(connection: aiosqlite.Connection, product_id: int) -> None:
        cursor = await connection.execute(
            "SELECT 1 FROM products WHERE product_id = ?;",
            (product_id,),
        )
        if await cursor.fetchone() is None:
            raise NotFoundException("Product", product_id)