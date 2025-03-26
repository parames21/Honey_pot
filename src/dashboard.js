import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)

// Load products
async function loadProducts() {
  const { data: products, error } = await supabase
    .from('products')
    .select('*')
    .order('name')

  if (error) {
    alert('Error loading products: ' + error.message)
    return
  }

  const productsTable = document.getElementById('productsTable')
  productsTable.innerHTML = products.map(product => `
    <tr>
      <td>${product.name}</td>
      <td>$${product.price.toFixed(2)}</td>
      <td>${product.stock}</td>
      <td>
        <button class="btn btn-sm btn-primary me-2" onclick="editProduct('${product.id}')">Edit</button>
        <button class="btn btn-sm btn-danger" onclick="deleteProduct('${product.id}')">Delete</button>
      </td>
    </tr>
  `).join('')
}

// Handle form submission
const productForm = document.getElementById('productForm')
productForm.addEventListener('submit', async (e) => {
  e.preventDefault()
  
  const formData = {
    name: document.getElementById('name').value,
    price: parseFloat(document.getElementById('price').value),
    stock: parseInt(document.getElementById('stock').value)
  }

  const productId = document.getElementById('productId').value

  try {
    if (productId) {
      // Update existing product
      const { error } = await supabase
        .from('products')
        .update(formData)
        .eq('id', productId)

      if (error) throw error
    } else {
      // Create new product
      const { error } = await supabase
        .from('products')
        .insert([formData])

      if (error) throw error
    }

    resetForm()
    loadProducts()
  } catch (error) {
    alert('Error saving product: ' + error.message)
  }
})

// Edit product
window.editProduct = async (id) => {
  const { data: product, error } = await supabase
    .from('products')
    .select('*')
    .eq('id', id)
    .single()

  if (error) {
    alert('Error loading product: ' + error.message)
    return
  }

  document.getElementById('productId').value = product.id
  document.getElementById('name').value = product.name
  document.getElementById('price').value = product.price
  document.getElementById('stock').value = product.stock
  document.getElementById('formTitle').textContent = 'Edit Product'
}

// Delete product
window.deleteProduct = async (id) => {
  if (!confirm('Are you sure you want to delete this product?')) return

  const { error } = await supabase
    .from('products')
    .delete()
    .eq('id', id)

  if (error) {
    alert('Error deleting product: ' + error.message)
    return
  }

  loadProducts()
}

// Reset form
function resetForm() {
  productForm.reset()
  document.getElementById('productId').value = ''
  document.getElementById('formTitle').textContent = 'Add New Product'
}

document.getElementById('resetForm').addEventListener('click', resetForm)

// Logout
document.getElementById('logoutBtn').addEventListener('click', async () => {
  await supabase.auth.signOut()
  window.location.href = '/'
})

// Check if user is admin
async function checkAdmin() {
  const { data: { user } } = await supabase.auth.getUser()
  
  if (!user) {
    window.location.href = '/'
    return
  }

  const { data: profile } = await supabase
    .from('profiles')
    .select('role')
    .eq('id', user.id)
    .single()

  if (!profile || profile.role !== 'admin') {
    window.location.href = '/'
  }
}

// Initial load
checkAdmin()
loadProducts()