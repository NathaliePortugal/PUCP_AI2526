import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid,
} from 'recharts'
import { useMetrics } from '../hooks/useMetrics'

const INTENT_LABELS = {
  consulta_producto: 'Producto',
  recomendacion:     'Recomendacion',
  soporte:           'Soporte',
  queja:             'Queja',
  devolucion:        'Devolucion',
  envio:             'Envio',
  general:           'General',
}

// Tooltip personalizado para los graficos
function CustomTooltip({ active, payload, label, suffix = '' }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#1a1a2e', border: '1px solid #00e5ff', borderRadius: 6, padding: '8px 12px', fontSize: 12 }}>
      <p style={{ color: '#00e5ff', marginBottom: 4 }}>{label}</p>
      <p style={{ color: '#fff' }}>{payload[0].value}{suffix}</p>
    </div>
  )
}

export default function MetricsDashboard() {
  const { metrics, health, loading, refresh } = useMetrics()

  if (loading) return <div className="empty-state"><div className="spinner" /></div>

  const dotClass = health?.ollama_connected ? 'green' : health?.status === 'error' ? 'red' : 'yellow'
  const mins = Math.floor((metrics?.uptime_seconds || 0) / 60)
  const secs = Math.floor((metrics?.uptime_seconds || 0) % 60)

  // Datos para el grafico de intenciones
  const intentData = Object.entries(metrics?.queries_by_intent || {}).map(([key, value]) => ({
    name: INTENT_LABELS[key] || key,
    consultas: value,
  }))

  // Datos para el grafico de tiempos de respuesta
  const timeData = (metrics?.response_times_history || []).map((ms, i) => ({
    consulta: `#${i + 1}`,
    ms: Math.round(ms),
  }))

  const outOfScopePct = metrics?.total_queries > 0
    ? Math.round((metrics.out_of_scope / metrics.total_queries) * 100)
    : 0

  return (
    <div>
      {/* Health bar */}
      <div className="health-bar">
        <div className={`health-bar__dot health-bar__dot--${dotClass}`} />
        <strong>Ollama:</strong>
        {health?.ollama_connected
          ? <span style={{ color: '#00e5ff' }}>Conectado — {health.available_models?.join(', ')}</span>
          : <span style={{ color: '#ff4444' }}>No disponible — ejecuta: ollama pull llama3.2:3b</span>
        }
        <span className="health-bar__uptime">Uptime: {mins}m {secs}s</span>
      </div>

      {/* KPI cards */}
      <div className="metrics-grid">
        {[
          { value: metrics?.total_queries ?? 0,                            label: 'Consultas totales' },
          { value: metrics?.escalations ?? 0,                              label: 'Escalaciones' },
          { value: metrics?.tickets_created ?? 0,                          label: 'Tickets creados' },
          { value: `${metrics?.avg_response_time_ms?.toFixed(0) ?? '--'}ms`, label: 'Tiempo promedio' },
          { value: `${outOfScopePct}%`,                                    label: 'Fuera de alcance' },
          { value: metrics?.total_tokens_in ?? 0,                          label: 'Tokens entrada' },
          { value: metrics?.total_tokens_out ?? 0,                         label: 'Tokens salida' },
        ].map(({ value, label }) => (
          <div key={label} className="metric-card">
            <div className="metric-card__value">{value}</div>
            <div className="metric-card__label">{label}</div>
          </div>
        ))}
      </div>

      {/* Grafico de intenciones */}
      <div className="chart-card">
        <h3 className="chart-card__title">Consultas por intencion</h3>
        {intentData.length === 0
          ? <p className="chart-empty">Sin datos aun. Usa el chat primero.</p>
          : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={intentData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
                <XAxis dataKey="name" tick={{ fill: '#aaa', fontSize: 11 }} />
                <YAxis tick={{ fill: '#aaa', fontSize: 11 }} allowDecimals={false} />
                <Tooltip content={<CustomTooltip suffix=" consultas" />} />
                <Bar dataKey="consultas" fill="#00e5ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )
        }
      </div>

      {/* Grafico de tiempos de respuesta */}
      <div className="chart-card">
        <h3 className="chart-card__title">Tiempo de respuesta por consulta (ms)</h3>
        {timeData.length < 2
          ? <p className="chart-empty">Necesitas al menos 2 consultas para ver la linea.</p>
          : (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={timeData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3e" />
                <XAxis dataKey="consulta" tick={{ fill: '#aaa', fontSize: 11 }} />
                <YAxis tick={{ fill: '#aaa', fontSize: 11 }} />
                <Tooltip content={<CustomTooltip suffix="ms" />} />
                <Line
                  type="monotone"
                  dataKey="ms"
                  stroke="#f5ff00"
                  strokeWidth={2}
                  dot={{ fill: '#f5ff00', r: 3 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )
        }
      </div>

      <button className="btn-primary" onClick={refresh}>Actualizar</button>
    </div>
  )
}
