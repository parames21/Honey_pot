import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)

let cart = []

// Load products
async function loadProducts() {
  const { data: products, error } = await supabase
    .from('products')
    .select('*')
    .gt('stock', 0)

  if (error) {
    alert('Error loading products: ' + error.message)
    return
  }

  const productsList = document.getElementById('productsList')
  productsList.innerHTML = products.map(product => `
    <div class="col-md-6 mb-4">
      <div class="card">
        <div class="card-body">
          <h5 class="card-title">${product.name}</h5>
          <p class="card-text">
            Price: $${product.price.toFixed(2)}<br>
            Available: ${product.stock}
          </p>
          <button class="btn btn-primary" onclick="addToCart('${product.id}', '${product.name}', ${product.price}, ${product.stock})">
            Add to Cart
          </button>
        </div>
      </div>
    </div>
  `).join('')
}

// Add to cart
window.addToCart = (id, name, price, maxStock) => {
  const existingItem = cart.find(item => item.id === id)
  
  if (existingItem) {
    if (existingItem.quantity < maxStock) {
      existingItem.quantity++
    } else {
      alert('Maximum stock reached!')
      return
    }
  } else {
    cart.push({ id, name, price, quantity: 1 })
  }
  
  updateCartDisplay()
}

// Update cart display
function updateCartDisplay() {
  const cartItems = document.getElementById('cartItems')
  const cartTotal = document.getElementById('cartTotal')
  
  cartItems.innerHTML = cart.map(item => `
    <div class="d-flex justify-content-between align-items-center mb-2">
      <div>
        ${item.name} x ${item.quantity}
        <br>
        <small>$${(item.price * item.quantity).toFixed(2)}</small>
      </div>
      <div>
        <button class="btn btn-sm btn-danger" onclick="removeFromCart('${item.id}')">Remove</button>
      </div>
    </div>
  `).join('')
  
  const total = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0)
  cartTotal.textContent = `$${total.toFixed(2)}`
}

// Remove from cart
window.removeFromCart = (id) => {
  cart = cart.filter(item => item.id !== id)
  updateCartDisplay()
}

// Checkout
document.getElementById('checkoutBtn').addEventListener('click', async () => {
  if (cart.length === 0) {
    alert('Your cart is empty!')
    return
  }

  try {
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) {
      alert('Please log in to checkout')
      return
    }

    // Create order
    const { data: order, error: orderError } = await supabase
      .from('orders')
      .insert([{
        user_id: user.id,
        total_amount: cart.reduce((sum, item) => sum + (item.price * item.quantity), 0)
      }])
      .select()
      .single()

    if (orderError) throw orderError

    // Create order items and update stock
    for (const item of cart) {
      // Add order item
      await supabase
        .from('order_items')
        .insert([{
          order_id: order.id,
          product_id: item.id,
          quantity: item.quantity,
          price: item.price
        }])

      // Update stock
      await supabase
        .from('products')
        .update({ 
          stock: supabase.raw(`stock - ${item.quantity}`)
        })
        .eq('id', item.id)
    }

    cart = []
    updateCartDisplay()
    alert('Order placed successfully!')
    loadProducts() // Reload products to update stock
  } catch (error) {
    alert('Error placing order: ' + error.message)
  }
})

// Logout
document.getElementById('logoutBtn').addEventListener('click', async () => {
  await supabase.auth.signOut()
  window.location.href = '/'
})

// Initial load
loadProducts()