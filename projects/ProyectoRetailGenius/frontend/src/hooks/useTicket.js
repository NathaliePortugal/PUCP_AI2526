import { useState } from 'react'
import axios from 'axios'

const INITIAL_FORM = { user_name: '', user_email: '', issue_description: '', order_id: '' }

export function useTicket() {
  const [form, setForm]       = useState(INITIAL_FORM)
  const [tickets, setTickets] = useState([])   // historial de la sesion
  const [error, setError]     = useState(null)
  const [loading, setLoading] = useState(false)

  const update = (field) => (e) => setForm(prev => ({ ...prev, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const { data } = await axios.post('/api/support/ticket', {
        session_id: `ses-${Date.now()}`,
        user_name:          form.user_name,
        user_email:         form.user_email,
        issue_description:  form.issue_description,
        order_id:           form.order_id || null,
      })
      setTickets(prev => [data, ...prev])
      setForm(INITIAL_FORM)
    } catch (err) {
      const detail = err.response?.data?.detail
      const msg = Array.isArray(detail)
        ? detail.map(d => d.msg).join('. ')
        : (typeof detail === 'string' ? detail : 'Error al crear ticket')
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const addTicket = (ticket) => setTickets(prev => [ticket, ...prev])

  return { form, update, tickets, error, loading, submit, addTicket }
}
