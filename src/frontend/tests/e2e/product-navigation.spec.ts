import { test, expect } from '@playwright/test';

/**
 * Product catalog discovery E2E tests
 * Implements: frontend/tests/features/product-navigation.feature
 *
 * Covers:
 * - Navigation from home page to product catalog
 * - Product search with valid matches
 * - Product search with no matches (empty state)
 */

test.describe('Product catalog discovery', () => {
  const suppliers = [
    { supplierId: 1, name: 'Feline Supply Co' },
    { supplierId: 2, name: 'Whisker Works' },
  ];
  const products = [
    {
      productId: 1,
      supplierId: 1,
      name: 'SmartFeeder One',
      description: 'AI-powered feeder learns nap cycles and mealtime habits.',
      price: 129.99,
      discount: 0.25,
      sku: 'CAT-FEED-001',
      unit: 'piece',
      imgName: 'feeder.png',
    },
    {
      productId: 2,
      supplierId: 2,
      name: 'SmartFeeder Mini',
      description: 'Compact feeder for small cats.',
      price: 89.99,
      discount: 0,
      sku: 'CAT-FEED-002',
      unit: 'piece',
      imgName: 'feeder.png',
    },
    {
      productId: 3,
      supplierId: 2,
      name: 'AutoClean Litter Dome',
      description: 'A self-cleaning litter box.',
      price: 199.99,
      discount: 0.25,
      sku: 'CAT-LITTER-001',
      unit: 'piece',
      imgName: 'litter-box.png',
    },
  ];

  test.beforeEach(async ({ page }) => {
    await page.route('**/api/suppliers', (route) => route.fulfill({ json: suppliers }));
    await page.route('**/api/products**', (route) => {
      const requestUrl = new URL(route.request().url());
      const search = requestUrl.searchParams.get('search')?.trim().toLowerCase() || '';
      const supplierId = requestUrl.searchParams.get('supplier_id');
      const filteredProducts = products.filter((product) => {
        const matchesSearch =
          !search ||
          product.name.toLowerCase().includes(search) ||
          product.sku.toLowerCase().includes(search);
        const matchesSupplier = !supplierId || product.supplierId === Number(supplierId);
        return matchesSearch && matchesSupplier;
      });
      return route.fulfill({ json: filteredProducts });
    });
    // Navigate away from about:blank so localStorage context is available
    await page.goto('/');
  });

  test('Navigate from the home page to the product catalog', async ({ page }) => {
    // Given I am on the home page
    await page.goto('/');
    await expect(page.locator('h1:has-text("Smart Cat Tech")')).toBeVisible();

    // When I select the Products navigation link
    await page.click('nav a:has-text("Products")');

    // Then I land on the product catalog page
    await expect(page).toHaveURL(/\/products/);

    // And I see the catalog header "Products"
    await expect(page.locator('h1:has-text("Products")')).toBeVisible();
  });

  test('Search by product name and SKU', async ({ page }) => {
    // Given I am viewing the product catalog
    await page.goto('/products');
    await expect(page.locator('h1:has-text("Products")')).toBeVisible();

    // And the catalog includes "SmartFeeder One"
    // Wait for product grid to load
    const productGrid = page.locator('div[class*="grid"]').filter({ hasText: 'SmartFeeder One' });
    await expect(productGrid).toBeVisible();

    // When I search for "SmartFeeder"
    const searchInput = page.locator('input[aria-label="Search products"]');
    await searchInput.fill('SmartFeeder');

    // Then the results list shows "SmartFeeder One"
    const productCard = page.locator('h3:has-text("SmartFeeder One")');
    await expect(productCard).toBeVisible();

    // And the product description is visible in the results
    const description = page.locator('text=/AI-powered feeder.*nap cycles/i').first();
    await expect(description).toBeVisible();

    await searchInput.fill('cat-feed-001');
    await expect(productCard).toBeVisible();
    await expect(page.locator('h3:has-text("SmartFeeder Mini")')).toHaveCount(0);
  });

  test('Filter by supplier, combine filters, and clear them', async ({ page }) => {
    await page.goto('/products');
    const supplierFilter = page.getByRole('combobox', { name: 'Filter by supplier' });
    await supplierFilter.selectOption('2');

    await expect(page.locator('h3:has-text("SmartFeeder Mini")')).toBeVisible();
    await expect(page.locator('h3:has-text("SmartFeeder One")')).toHaveCount(0);

    await page.getByRole('textbox', { name: 'Search products' }).fill('SmartFeeder');
    await expect(page.locator('h3:has-text("SmartFeeder Mini")')).toBeVisible();
    await expect(page.locator('h3:has-text("AutoClean Litter Dome")')).toHaveCount(0);

    await page.getByRole('button', { name: 'Clear filters' }).click();
    await expect(page.locator('h3:has-text("SmartFeeder One")')).toBeVisible();
    await expect(page.locator('h3:has-text("AutoClean Litter Dome")')).toBeVisible();
  });

  test('Product added from filtered results remains in the cart after filters clear', async ({
    page,
  }) => {
    type TestCartItem = {
      productId: number;
      name: string;
      description: string;
      sku: string;
      unit: string;
      imgName: string;
      quantity: number;
      unitPrice: number;
      lineTotal: number;
    };
    const cart = {
      cartId: 'filtered-search-cart',
      items: [] as TestCartItem[],
      total: 0,
    };

    await page.route('**/api/carts**', async (route) => {
      const request = route.request();
      const pathname = new URL(request.url()).pathname;

      if (request.method() === 'POST' && pathname === '/api/carts') {
        return route.fulfill({ status: 201, json: cart });
      }
      if (request.method() === 'GET' && pathname === `/api/carts/${cart.cartId}`) {
        return route.fulfill({ json: cart });
      }
      if (request.method() === 'POST' && pathname.endsWith('/items')) {
        const { productId, quantity } = request.postDataJSON() as {
          productId: number;
          quantity: number;
        };
        const product = products.find((candidate) => candidate.productId === productId);
        if (!product) {
          return route.fulfill({ status: 404 });
        }

        const existingItem = cart.items.find((item) => item.productId === productId);
        const nextQuantity = (existingItem?.quantity ?? 0) + quantity;
        const unitPrice = Math.round(product.price * (1 - product.discount) * 100) / 100;
        const nextItem: TestCartItem = {
          productId,
          name: product.name,
          description: product.description,
          sku: product.sku,
          unit: product.unit,
          imgName: product.imgName,
          quantity: nextQuantity,
          unitPrice,
          lineTotal: Math.round(unitPrice * nextQuantity * 100) / 100,
        };
        cart.items = [
          ...cart.items.filter((item) => item.productId !== productId),
          nextItem,
        ];
        cart.total = cart.items.reduce((total, item) => total + item.lineTotal, 0);
        return route.fulfill({ json: cart });
      }

      return route.fulfill({ status: 404 });
    });

    await page.goto('/products');
    await page.getByRole('combobox', { name: 'Filter by supplier' }).selectOption('2');
    await page.getByRole('textbox', { name: 'Search products' }).fill('SmartFeeder Mini');
    await expect(page.locator('h3:has-text("SmartFeeder Mini")')).toBeVisible();
    await expect(page.locator('h3:has-text("SmartFeeder One")')).toHaveCount(0);

    const productName = 'SmartFeeder Mini';
    await page.getByRole('button', { name: `Increase quantity of ${productName}` }).click();
    await page.getByRole('button', { name: `Increase quantity of ${productName}` }).click();
    await page.getByRole('button', { name: `Add 2 ${productName} to cart` }).click();
    await expect(page.getByRole('status')).toContainText('Product added to your cart.');

    await page.getByRole('button', { name: 'Clear filters' }).click();
    await expect(page.locator('h3:has-text("SmartFeeder One")')).toBeVisible();
    await expect(page.locator('h3:has-text("SmartFeeder Mini")')).toBeVisible();

    await page.locator('nav').getByRole('link', { name: 'Cart' }).click();
    await expect(page.getByTestId('cart-item-2')).toContainText(productName);
    await expect(page.getByTestId('cart-quantity-2')).toHaveText('2');
    await expect(page.getByTestId('cart-total')).toHaveText('$179.98');
  });

  test('Search for a product with no matches', async ({ page }) => {
    // Given I am viewing the product catalog
    await page.goto('/products');
    await expect(page.locator('h1:has-text("Products")')).toBeVisible();

    // When I search for "Space Tuna"
    const searchInput = page.locator('input[aria-label="Search products"]');
    await searchInput.fill('Space Tuna');

    // Then I see the empty state message "No products found"
    const emptyState = page.locator('[role="status"]');
    await expect(emptyState).toContainText('No products found');

    // And I am prompted to adjust the search filters
    await expect(emptyState).toContainText(/clearing.*changing.*search filters/i);
  });
});
