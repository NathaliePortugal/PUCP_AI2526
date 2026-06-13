import { useState, useRef, useEffect } from 'react'
import axios from 'axios'

const WELCOME = `Hola! Soy RetailBotito. Puedo ayudarte con:
- Buscar productos por precio o categoria
- Recomendar la mejor opcion para tu necesidad
- Resolver problemas con tu pedido

En que te puedo ayudar hoy?`

export function useChat(onAutoTicket) {
  const [messages, setMessages] = useState([{ role: 'bot', text: WELCOME }])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const sessionId = useRef(`ses-${Date.now()}`)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', text }])
    setLoading(true)

    try {
      const { data } = await axios.post('/api/assistant/query', {
        session_id: sessionId.current,
        message: text,
      })

      const msgs = [{ role: data.escalate_to_human ? 'escalated' : 'bot', text: data.response }]

      if (data.auto_ticket) {
        const t = data.auto_ticket
        onAutoTicket?.(t)
        msgs.push({
          role: 'ticket',
          text: `Ticket creado automaticamente\nID: ${t.ticket_id}\nPrioridad: ${t.priority.toUpperCase()}\nResolucion estimada: ${t.estimated_resolution}${t.escalated_to_human ? '\nEscalado a agente humano' : ''}`
        })
      }

      if (data.escalate_to_human && !data.auto_ticket) {
        msgs.push({ role: 'bot', text: 'Tu caso fue escalado a un agente humano. Pronto te contactaran.' })
      }

      setMessages(prev => [...prev, ...msgs])
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'bot', text: 'Tuve un problema al conectarme. Tienes Ollama corriendo? Ejecuta: ollama pull llama3.2:3b' }
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') sendMessage()
  }

  return { messages, input, setInput, loading, sendMessage, handleKeyDown, bottomRef }
}
