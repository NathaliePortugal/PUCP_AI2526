import { useState } from 'react'
import { useChat } from '../hooks/useChat'

export default function ChatWidget({ onAutoTicket }) {
  const [open, setOpen] = useState(false)
  const { messages, input, setInput, loading, sendMessage, handleKeyDown, bottomRef } = useChat(onAutoTicket)

  return (
    <>
      <button className="chat-fab" onClick={() => setOpen(o => !o)}>
        <div className="chat-fab__robot">
          {open ? '✕' : '🤖'}
        </div>
        {!open && (
          <div className="chat-fab__label">
            <strong>RetailBotito</strong>
            <span>Preguntame algo</span>
          </div>
        )}
      </button>

      {open && (
        <div className="chat-window">
          <div className="chat-window__header">
            <div className="status-dot" />
            <h3>RetailBotito - Asistente IA</h3>
            <button className="close-btn" onClick={() => setOpen(false)}>X</button>
          </div>

          <div className="chat-window__messages">
            {messages.map((m, i) => (
              <div key={i} className={`msg msg--${m.role}`} style={{ whiteSpace: 'pre-line' }}>{m.text}</div>
            ))}
            {loading && (
              <div className="typing-dots">
                <span /><span /><span />
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="chat-window__input-row">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Escribe tu consulta..."
              disabled={loading}
            />
            <button onClick={sendMessage} disabled={loading || !input.trim()}>
              Enviar
            </button>
          </div>
        </div>
      )}
    </>
  )
}
