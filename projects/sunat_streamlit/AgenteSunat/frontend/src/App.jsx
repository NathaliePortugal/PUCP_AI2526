// App.jsx — Componente principal del chatbot SUNAT

import { useState, useEffect, useRef } from "react";
import { sendMessage } from "./api";
import "./App.css";

// ---------------------------------------------------------------------------
// OPCIONES RÁPIDAS — botones de acceso directo a los temas principales
// ---------------------------------------------------------------------------
const QUICK_OPTIONS = [
  { label: "Formalizar negocio",       message: "Quiero formalizar mi negocio y sacar el RUC" },
  { label: "Regímenes tributarios",    message: "Quiero comparar los regímenes tributarios" },
  { label: "Multas y sanciones",       message: "Tengo dudas sobre multas y sanciones tributarias" },
  { label: "Comprobantes de pago",     message: "Quiero saber sobre comprobantes de pago, boletas y facturas" },
  { label: "Cronograma vencimientos",  message: "Cuándo vencen mis obligaciones tributarias" },
  { label: "Otra consulta",            message: "Tengo una consulta general sobre SUNAT" },
];

function generateSessionId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return "session-" + Math.random().toString(36).substring(2, 10);
}

// ---------------------------------------------------------------------------
// COMPONENTE PRINCIPAL
// ---------------------------------------------------------------------------
function App() {
  const [messages, setMessages]     = useState([]);
  const [input, setInput]           = useState("");
  const [isLoading, setIsLoading]   = useState(false);
  const [sessionId]                 = useState(() => generateSessionId());

  // Controla si el panel de opciones rápidas (chips) está expandido durante el chat
  const [showOptions, setShowOptions] = useState(false);

  const messagesEndRef = useRef(null);
  const inputRef       = useRef(null);

  // Scroll automático al último mensaje
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Cuando llega un nuevo mensaje del bot, colapsar las opciones rápidas automáticamente
  // para no distraer al usuario mientras lee la respuesta
  useEffect(() => {
    if (messages.length > 0) setShowOptions(false);
  }, [messages.length]);

  const handleSend = async (messageText) => {
    const text = messageText.trim();
    if (!text || isLoading) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setIsLoading(true);
    setShowOptions(false); // colapsar opciones al enviar

    try {
      const data = await sendMessage(text, sessionId);
      setMessages((prev) => [...prev, { role: "bot", text: data.response }]);
    } catch (error) {
      console.error("Error al contactar el backend:", error);
      setMessages((prev) => [...prev, {
        role: "bot",
        text: "Lo siento, ocurrió un error. Verifica que el servidor esté corriendo e intenta nuevamente.",
      }]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleQuickOption = (option) => {
    handleSend(option.message);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(input);
    }
  };

  const hayMensajes = messages.length > 0;

  return (
    <div className="chat-wrapper">

      {/* ---- HEADER ---- */}
      <header className="chat-header">
        <div className="chat-header-avatar">AS</div>
        <div className="chat-header-info">
          <span className="chat-header-title">Asistente Virtual SUNAT</span>
          <span className="chat-header-subtitle">Orientación tributaria para MYPES</span>
        </div>
        <div className="chat-header-status">
          <div className="status-dot"></div>
          En línea
        </div>
      </header>

      {/* ---- ÁREA DE MENSAJES ---- */}
      <main className="chat-messages">
        {!hayMensajes ? (
          // Pantalla de bienvenida con grid completo de opciones
          <WelcomeScreen onSelectOption={handleQuickOption} />
        ) : (
          <>
            {messages.map((msg, index) => (
              <MessageBubble key={index} role={msg.role} text={msg.text} />
            ))}
            {isLoading && <TypingIndicator />}
          </>
        )}
        <div ref={messagesEndRef} />
      </main>

      {/* ---- BARRA DE INPUT ---- */}
      <footer className="chat-input-area">

        {/*
          Panel de opciones rápidas colapsable — solo visible durante el chat.
          Aparece como chips horizontales justo encima del input cuando el
          usuario hace click en el botón " Temas".
          En la pantalla de bienvenida no se muestra (las opciones ya están arriba).
        */}
        {hayMensajes && (
          <div className={`chips-panel ${showOptions ? "chips-panel--open" : ""}`}>
            {showOptions && (
              <div className="chips-row">
                {QUICK_OPTIONS.map((opt, i) => (
                  <button
                    key={i}
                    className="chip-btn"
                    onClick={() => handleQuickOption(opt)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="chat-input-row">
          {/* Botón para mostrar/ocultar los temas rápidos (solo durante el chat) */}
          {hayMensajes && (
            <button
              className={`topics-btn ${showOptions ? "topics-btn--active" : ""}`}
              onClick={() => setShowOptions((v) => !v)}
              title="Temas frecuentes"
            >
              Temas
            </button>
          )}

          <textarea
            ref={inputRef}
            className="chat-input"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Escribe tu consulta aquí..."
            disabled={isLoading}
          />
          <button
            className="send-btn"
            onClick={() => handleSend(input)}
            disabled={isLoading || !input.trim()}
            title="Enviar mensaje"
          >
            &gt;
          </button>
        </div>

        <p className="chat-input-hint">Enter para enviar · Shift+Enter para nueva línea</p>
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SUBCOMPONENTES
// ---------------------------------------------------------------------------

function WelcomeScreen({ onSelectOption }) {
  return (
    <div className="welcome-screen">
      <div className="welcome-logo">SUNAT</div>
      <h2 className="welcome-title">Bienvenido al Asistente Virtual de SUNAT</h2>
      <p className="welcome-subtitle">
        Estoy aquí para orientarte sobre obligaciones tributarias, formalización
        de negocios y más. ¿En qué puedo ayudarte hoy?
      </p>
      <p className="quick-options-title">Consultas frecuentes</p>
      <div className="quick-options-grid">
        {QUICK_OPTIONS.map((opt, i) => (
          <button key={i} className="quick-option-btn" onClick={() => onSelectOption(opt)}>
            <span className="quick-option-label">{opt.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ role, text }) {
  return (
    <div className={`message-row ${role}`}>
      {role === "bot" && <div className="message-avatar">AS</div>}
      <div className="message-bubble">{text}</div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="message-row bot">
      <div className="message-avatar">AS</div>
      <div className="typing-indicator">
        <div className="typing-dot"></div>
        <div className="typing-dot"></div>
        <div className="typing-dot"></div>
      </div>
    </div>
  );
}

export default App;
