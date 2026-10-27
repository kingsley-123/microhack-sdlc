import axios from 'axios';
import { api } from './config';

export interface CartItem {
  productId: number;
  name: string;
  description: string | null;
  sku: string;
  unit: string;
  imgName: string | null;
  quantity: number;
  unitPrice: number;
  lineTotal: number;
}

export interface Cart {
  cartId: string;
  items: CartItem[];
  total: number;
}

const CART_ID_STORAGE_KEY = 'octocat-supply-cart-id';
let cartCreationPromise: Promise<string> | null = null;

async function createCart(): Promise<string> {
  const { data } = await axios.post<Cart>(`${api.baseURL}${api.endpoints.carts}`);
  window.localStorage.setItem(CART_ID_STORAGE_KEY, data.cartId);
  return data.cartId;
}

async function getCartId(): Promise<string> {
  const cartId = window.localStorage.getItem(CART_ID_STORAGE_KEY);
  if (cartId) {
    return cartId;
  }

  if (!cartCreationPromise) {
    cartCreationPromise = createCart().finally(() => {
      cartCreationPromise = null;
    });
  }
  return cartCreationPromise;
}

export async function fetchCart(): Promise<Cart> {
  const cartId = await getCartId();
  try {
    const { data } = await axios.get<Cart>(`${api.baseURL}${api.endpoints.carts}/${cartId}`);
    return data;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      window.localStorage.removeItem(CART_ID_STORAGE_KEY);
      const newCartId = await getCartId();
      const { data } = await axios.get<Cart>(`${api.baseURL}${api.endpoints.carts}/${newCartId}`);
      return data;
    }
    throw error;
  }
}

export async function addCartItem(input: {
  productId: number;
  quantity: number;
}): Promise<Cart> {
  const cartId = await getCartId();
  const { data } = await axios.post<Cart>(
    `${api.baseURL}${api.endpoints.carts}/${cartId}/items`,
    input,
  );
  return data;
}

export async function updateCartItem(input: {
  productId: number;
  quantity: number;
}): Promise<Cart> {
  const cartId = await getCartId();
  const { data } = await axios.put<Cart>(
    `${api.baseURL}${api.endpoints.carts}/${cartId}/items/${input.productId}`,
    { quantity: input.quantity },
  );
  return data;
}

export async function removeCartItem(productId: number): Promise<void> {
  const cartId = await getCartId();
  await axios.delete(
    `${api.baseURL}${api.endpoints.carts}/${cartId}/items/${productId}`,
  );
}