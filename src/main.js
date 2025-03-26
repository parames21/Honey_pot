import { createClient } from '@supabase/supabase-js'

// Initialize Supabase client
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseKey = import.meta.env.VITE_SUPABASE_ANON_KEY
const supabase = createClient(supabaseUrl, supabaseKey)

// Login form handler
document.getElementById('loginForm').addEventListener('submit', async (e) => {
  e.preventDefault()
  const email = document.getElementById('email').value
  const password = document.getElementById('password').value

  try {
    const { data, error } = await supabase.auth.signInWithPassword({
      email,
      password
    })

    if (error) throw error

    // Check user role and redirect
    const { data: profile } = await supabase
      .from('profiles')
      .select('role')
      .eq('id', data.user.id)
      .single()

    if (profile.role === 'admin') {
      window.location.href = '/dashboard.html'
    } else {
      window.location.href = '/buy.html'
    }
  } catch (error) {
    alert('Error logging in: ' + error.message)
  }
})

// Signup form handler
document.getElementById('signupForm').addEventListener('submit', async (e) => {
  e.preventDefault()
  const email = document.getElementById('signupEmail').value
  const password = document.getElementById('signupPassword').value

  try {
    const { data, error } = await supabase.auth.signUp({
      email,
      password
    })

    if (error) throw error

    // Create profile with default role 'customer'
    await supabase
      .from('profiles')
      .insert([
        {
          id: data.user.id,
          email,
          role: 'customer'
        }
      ])

    alert('Signup successful! Please check your email for verification.')
  } catch (error) {
    alert('Error signing up: ' + error.message)
  }
})