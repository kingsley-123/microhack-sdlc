import { test, expect } from '@playwright/test';

test('add, update, reload, and remove cart items', async ({ page }) => {
  const product = {
    productId: 41,
    supplierId: 1,
    name: 'Cart Test Feeder',
    description: 'A product for the cart test',
    price: 10,
    discount: 0,
    imgName: 'feeder.png',
    sku: 'CART-E2E-001',
    unit: 'piece',
  };
  let cart = { cartId: 'cart-e2e', items: [] as Array<Record<string, unknown>>, total: 0 };

  await page.route('**/api/products', (route) => route.fulfill({ json: [product] }));
  await page.route('**/api/carts**', async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;

    if (request.method() === 'POST' && pathname === '/api/carts') {
      return route.fulfill({ status: 201, json: cart });
    }
    if (request.method() === 'GET' && pathname === '/api/carts/cart-e2e') {
      return route.fulfill({ json: cart });
    }
    if (request.method() === 'POST' && pathname.endsWith('/items')) {
      const { productId, quantity } = request.postDataJSON() as {
        productId: number;
        quantity: number;
      };
      const existing = cart.items.find((item) => item.productId === productId);
      const nextQuantity = Number(existing?.quantity || 0) + quantity;
      cart.items = [
        {
          productId,
          name: product.name,
          description: product.description,
          sku: product.sku,
          unit: product.unit,
          imgName: product.imgName,
          quantity: nextQuantity,
          unitPrice: product.price,
          lineTotal: nextQuantity * product.price,
        },
      ];
      cart.total = nextQuantity * product.price;
      return route.fulfill({ json: cart });
    }
    if (request.method() === 'PUT' && pathname.includes('/items/')) {
      const quantity = (request.postDataJSON() as { quantity: number }).quantity;
      cart.items = cart.items.map((item) => ({
        ...item,
        quantity,
        lineTotal: quantity * product.price,
      }));
      cart.total = quantity * product.price;
      return route.fulfill({ json: cart });
    }
    if (request.method() === 'DELETE' && pathname.includes('/items/')) {
      cart = { cartId: cart.cartId, items: [], total: 0 };
      return route.fulfill({ status: 204 });
    }

    return route.fulfill({ status: 404 });
  });

  await page.goto('/products');
  await expect(page.getByRole('heading', { name: product.name })).toBeVisible();
  await page.getByRole('button', { name: `Increase quantity of ${product.name}` }).click();
  await page.getByRole('button', { name: `Increase quantity of ${product.name}` }).click();
  await page.getByRole('button', { name: /Add 2 .* to cart/ }).click();
  await expect(page.getByRole('status')).toContainText('Product added to your cart.');

  await page.locator('nav').getByRole('link', { name: 'Cart' }).click();
  await expect(page.getByTestId(`cart-quantity-${product.productId}`)).toHaveText('2');
  await expect(page.getByTestId('cart-total')).toHaveText('$20.00');

  await page.reload();
  await expect(page.getByTestId(`cart-quantity-${product.productId}`)).toHaveText('2');

  await page.getByRole('button', { name: `Increase quantity of ${product.name}` }).click();
  await expect(page.getByTestId(`cart-quantity-${product.productId}`)).toHaveText('3');
  await expect(page.getByTestId('cart-total')).toHaveText('$30.00');

  await page.getByRole('button', { name: 'Remove' }).click();
  await expect(page.getByRole('status')).toContainText('Your cart is empty.');
});

test('concurrent first-time adds share one cart creation', async ({ page }) => {
  const products = [
    {
      productId: 51,
      supplierId: 1,
      name: 'First Concurrent Product',
      description: 'First cart race test product',
      price: 10,
      discount: 0,
      imgName: 'feeder.png',
      sku: 'CART-RACE-001',
      unit: 'piece',
    },
    {
      productId: 52,
      supplierId: 1,
      name: 'Second Concurrent Product',
      description: 'Second cart race test product',
      price: 20,
      discount: 0,
      imgName: 'litter-box.png',
      sku: 'CART-RACE-002',
      unit: 'piece',
    },
  ];
  let cartCreationRequests = 0;
  const cartIdsUsedForAdds: string[] = [];

  await page.route('**/api/products', (route) => route.fulfill({ json: products }));
  await page.route('**/api/carts**', async (route) => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;

    if (request.method() === 'POST' && pathname === '/api/carts') {
      cartCreationRequests += 1;
      await new Promise((resolve) => setTimeout(resolve, 100));
      return route.fulfill({
        status: 201,
        json: { cartId: 'shared-cart', items: [], total: 0 },
      });
    }
    if (request.method() === 'POST' && pathname.endsWith('/items')) {
      cartIdsUsedForAdds.push(pathname.split('/')[3]);
      return route.fulfill({
        json: { cartId: 'shared-cart', items: [], total: 0 },
      });
    }

    return route.fulfill({ status: 404 });
  });

  await page.goto('/products');
  for (const product of products) {
    await page.getByRole('button', { name: `Increase quantity of ${product.name}` }).click();
  }

  await Promise.all(
    products.map((product) =>
      page.getByRole('button', { name: new RegExp(`Add 1 .*${product.name}.* to cart`) }).click(),
    ),
  );

  expect(cartCreationRequests).toBe(1);
  expect(cartIdsUsedForAdds).toEqual(['shared-cart', 'shared-cart']);
});