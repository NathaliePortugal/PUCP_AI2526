import ChatWidget from './components/ChatWidget'
import ProductCard from './components/ProductCard'
import MetricsDashboard from './components/MetricsDashboard'
import { useProducts } from './hooks/useProducts'
import { useTicket } from './hooks/useTicket'
import { useState } from 'react'

const CATEGORIES = ['todos', 'electronica', 'computadores', 'celulares', 'audio', 'hogar', 'gaming', 'mascotas']

export default function App() {
  const [tab, setTab] = useState('tienda')

  const { filtered, loading, error, category, setCategory, searchQuery, setSearchQuery } = useProducts()
  const { form, update, tickets, error: ticketError, loading: ticketLoading, submit, addTicket } = useTicket()

  return (
    <div>
      <header className="header">
        <span className="header__logo">Retail<span>Genius</span></span>

        <div className="header__search">
          <input
            placeholder="Buscar productos..."
            value={searchQuery}
            onChange={e => { setSearchQuery(e.target.value); setTab('tienda') }}
            onKeyDown={e => e.key === 'Enter' && setTab('tienda')}
          />
          <button onClick={() => setTab('tienda')}>Buscar</button>
        </div>

        <nav className="header__nav">
          <button className={tab === 'tienda'   ? 'active' : ''} onClick={() => setTab('tienda')}>Tienda</button>
          <button className={tab === 'soporte'  ? 'active' : ''} onClick={() => setTab('soporte')}>Soporte</button>
          <button className={tab === 'metricas' ? 'active' : ''} onClick={() => setTab('metricas')}>Metricas</button>
        </nav>
      </header>

      <div className="main-content">

        {/* ── TIENDA ── */}
        {tab === 'tienda' && (
          <>
            {!searchQuery && (
              <div className="hero">
                <h1>Bienvenido a RetailGenius</h1>
                <p>
                  Tu asistente IA esta listo para ayudarte a encontrar el producto perfecto.<br />
                  Haz clic en "Chat" para hablar con RetailBot.
                </p>
                <button className="btn-primary" onClick={() => setTab('soporte')}>Ir a Soporte</button>
              </div>
            )}

            <div className="category-filter">
              {CATEGORIES.map(c => (
                <button
                  key={c}
                  className={`category-filter__btn${category === c ? ' category-filter__btn--active' : ''}`}
                  onClick={() => setCategory(c)}
                >
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </button>
              ))}
            </div>

            <span className="section-title">
              {searchQuery
                ? `Resultados para "${searchQuery}"`
                : category === 'todos' ? 'Todos los productos' : category.charAt(0).toUpperCase() + category.slice(1)
              }
              {' '}({filtered.length})
            </span>

            {loading && <div className="empty-state"><div className="spinner" /></div>}
            {error   && <div className="empty-state">Error cargando productos. El backend esta corriendo?</div>}

            {!loading && !error && filtered.length === 0 && (
              <div className="empty-state">
                No encontramos productos. Prueba otra busqueda o preguntale al chat.
              </div>
            )}

            {!loading && !error && filtered.length > 0 && (
              <div className="products-grid">
                {filtered.map(p => <ProductCard key={p.id} product={p} />)}
              </div>
            )}
          </>
        )}

        {/* ── SOPORTE ── */}
        {tab === 'soporte' && (
          <div className="ticket-form">
            <h2>Crear Ticket de Soporte</h2>
            <p className="subtitle">
              El asistente IA procesara tu caso y te dara una respuesta inmediata.
              Los casos graves se escalan automaticamente a un agente humano.
            </p>

            <form onSubmit={submit}>
              <div className="form-group">
                <label>Nombre completo *</label>
                <input required value={form.user_name} onChange={update('user_name')} placeholder="Maria Garcia" />
              </div>
              <div className="form-group">
                <label>Correo electronico *</label>
                <input required type="email" value={form.user_email} onChange={update('user_email')} placeholder="tucorreo@email.com" />
              </div>
              <div className="form-group">
                <label>Numero de orden (opcional)</label>
                <input value={form.order_id} onChange={update('order_id')} placeholder="ORD-2024-00000" />
              </div>
              <div className="form-group">
                <label>Descripcion del problema *</label>
                <textarea required value={form.issue_description} onChange={update('issue_description')} placeholder="Describe tu problema con el mayor detalle posible..." />
              </div>
              <button type="submit" className="btn-primary" disabled={ticketLoading}>
                {ticketLoading ? 'Procesando...' : 'Crear Ticket'}
              </button>
            </form>

            {/* Ultimo ticket creado */}
            {tickets[0] && (
              <div className="ticket-result ticket-result--success">
                <h3>
                  Ticket creado: {tickets[0].ticket_id}
                  <span className={`priority-badge priority-badge--${tickets[0].priority}`}>
                    {tickets[0].priority.toUpperCase()}
                  </span>
                </h3>
                <p style={{ fontSize: 13, marginBottom: 8 }}>
                  Estado: {tickets[0].status} | Resolucion: {tickets[0].estimated_resolution}
                  {tickets[0].escalated_to_human && ' — Escalado a agente humano'}
                </p>
                <p style={{ fontSize: 13, lineHeight: 1.6 }}>{tickets[0].ai_response}</p>
              </div>
            )}

            {ticketError && (
              <div className="ticket-result ticket-result--error">{ticketError}</div>
            )}

            {/* Historial de tickets de la sesion */}
            {tickets.length > 0 && (
              <div className="ticket-history">
                <h3>Tickets de esta sesion ({tickets.length})</h3>
                <div className="ticket-history__list">
                  {tickets.map(t => (
                    <div key={t.ticket_id} className="ticket-history__item">
                      <span className="ticket-history__item-id">{t.ticket_id}</span>
                      <span className="ticket-history__item-desc">{t.ai_response}</span>
                      <div className="ticket-history__item-meta">
                        <span className={`priority-badge priority-badge--${t.priority}`}>{t.priority}</span>
                        {t.escalated_to_human && <span style={{ color: '#c7511f' }}>Escalado</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── METRICAS ── */}
        {tab === 'metricas' && (
          <>
            <span className="section-title">Dashboard de Metricas</span>
            <MetricsDashboard />
          </>
        )}
      </div>

      <ChatWidget onAutoTicket={addTicket} />
    </div>
  )
}
