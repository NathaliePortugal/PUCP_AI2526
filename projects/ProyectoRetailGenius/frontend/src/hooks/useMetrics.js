import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

export function useMetrics() {
  const [metrics, setMetrics] = useState(null)
  const [health, setHealth]   = useState(null)
  const [loading, setLoading] = useState(true)

  const fetchAll = useCallback(async () => {
    try {
      const [m, h] = await Promise.all([
        axios.get('/api/metrics'),
        axios.get('/api/health'),
      ])
      setMetrics(m.data)
      setHealth(h.data)
    } catch {
      setHealth({ status: 'error', ollama_connected: false, available_models: [] })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, 10000)
    return () => clearInterval(id)
  }, [fetchAll])

  return { metrics, health, loading, refresh: fetchAll }
}
