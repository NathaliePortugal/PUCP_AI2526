import { useState, useEffect } from 'react'
import axios from 'axios'

export function useProducts() {
  const [products, setProducts]     = useState([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)
  const [category, setCategory]     = useState('todos')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    axios.get('/api/products/catalog')
      .then(r => setProducts(r.data.products))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = products.filter(p => {
    const matchCategory = category === 'todos' || p.category === category
    const q = searchQuery.toLowerCase()
    const matchSearch = !q ||
      p.name.toLowerCase().includes(q) ||
      p.brand.toLowerCase().includes(q) ||
      p.description.toLowerCase().includes(q)
    return matchCategory && matchSearch
  })

  return { products, filtered, loading, error, category, setCategory, searchQuery, setSearchQuery }
}
