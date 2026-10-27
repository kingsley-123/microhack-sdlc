import { useMutation, useQuery, useQueryClient } from 'react-query';
import { fetchCart, removeCartItem, updateCartItem } from '../../api/cartApi';
import { useTheme } from '../../context/ThemeContext';

export default function Cart() {
  const { darkMode } = useTheme();
  const queryClient = useQueryClient();
  const { data: cart, isLoading, error } = useQuery('cart', fetchCart);
  const updateMutation = useMutation(updateCartItem, {
    onSuccess: (updatedCart) => {
      queryClient.setQueryData('cart', updatedCart);
    },
  });
  const removeMutation = useMutation(removeCartItem, {
    onSuccess: () => queryClient.invalidateQueries('cart'),
  });

  const textColor = darkMode ? 'text-light' : 'text-gray-800';

  return (
    <section
      className={`min-h-screen ${darkMode ? 'bg-dark' : 'bg-gray-100'} px-4 pb-16 pt-24 transition-colors duration-300`}
    >
      <div className="mx-auto max-w-4xl">
        <h1 className={`mb-6 text-3xl font-bold ${textColor}`}>Shopping Cart</h1>

        {isLoading && <p role="status">Loading your cart...</p>}
        {Boolean(error) && (
          <p role="alert" className="text-red-600">
            Could not load your cart. Please try again.
          </p>
        )}
        {updateMutation.isError || removeMutation.isError ? (
          <p role="alert" className="mb-4 text-red-600">
            Could not update your cart. Please try again.
          </p>
        ) : null}

        {cart && cart.items.length === 0 && !isLoading && (
          <p className={`${textColor} py-8`} role="status">
            Your cart is empty.
          </p>
        )}

        {cart && cart.items.length > 0 && (
          <>
            <div className="divide-y divide-gray-300 border-y border-gray-300">
              {cart.items.map((item) => (
                <article
                  key={item.productId}
                  className="flex flex-wrap items-center justify-between gap-4 py-5"
                  data-testid={`cart-item-${item.productId}`}
                >
                  <div className="min-w-48 flex-1">
                    <h2 className={`font-semibold ${textColor}`}>{item.name}</h2>
                    <p className="text-sm text-gray-500">${item.unitPrice.toFixed(2)} each</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      aria-label={`Decrease quantity of ${item.name}`}
                      disabled={item.quantity <= 1 || updateMutation.isLoading}
                      onClick={() =>
                        updateMutation.mutate({
                          productId: item.productId,
                          quantity: item.quantity - 1,
                        })
                      }
                      className="h-9 w-9 border border-gray-400 disabled:opacity-40"
                    >
                      -
                    </button>
                    <span
                      aria-label={`Quantity of ${item.name}`}
                      data-testid={`cart-quantity-${item.productId}`}
                    >
                      {item.quantity}
                    </span>
                    <button
                      type="button"
                      aria-label={`Increase quantity of ${item.name}`}
                      disabled={updateMutation.isLoading}
                      onClick={() =>
                        updateMutation.mutate({
                          productId: item.productId,
                          quantity: item.quantity + 1,
                        })
                      }
                      className="h-9 w-9 border border-gray-400 disabled:opacity-40"
                    >
                      +
                    </button>
                  </div>
                  <p className={`w-24 text-right font-semibold ${textColor}`}>
                    ${item.lineTotal.toFixed(2)}
                  </p>
                  <button
                    type="button"
                    onClick={() => removeMutation.mutate(item.productId)}
                    disabled={removeMutation.isLoading}
                    className="text-sm text-red-700 underline disabled:opacity-50"
                  >
                    Remove
                  </button>
                </article>
              ))}
            </div>
            <div className="flex justify-end gap-6 py-6">
              <span className={`font-semibold ${textColor}`}>Total</span>
              <span
                className={`w-24 text-right text-xl font-bold ${textColor}`}
                data-testid="cart-total"
              >
                ${cart.total.toFixed(2)}
              </span>
            </div>
          </>
        )}
      </div>
    </section>
  );
}