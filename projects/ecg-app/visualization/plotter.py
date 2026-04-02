import numpy as np
import plotly.graph_objects as go

from config import BACKGROUND_COLOR, GRID_COLOR_FINE, GRID_COLOR_THICK, SIGNAL_COLOR


def plot_lead(t, señal, lead_name, segundos=5.0):
    mask  = t <= segundos
    t_cut = t[mask]
    s_cut = señal[mask]

    y_min = float(np.nanmin(s_cut)) - 0.2
    y_max = float(np.nanmax(s_cut)) + 0.2

    fig = go.Figure()

    for x in np.arange(0, segundos, 0.04):
        fig.add_vline(x=round(x, 3), line_width=0.3, line_color=GRID_COLOR_FINE)
    for y in np.arange(round(y_min, 1), round(y_max, 1), 0.1):
        fig.add_hline(y=round(y, 2), line_width=0.3, line_color=GRID_COLOR_FINE)

    for x in np.arange(0, segundos, 0.20):
        fig.add_vline(x=round(x, 3), line_width=0.8, line_color=GRID_COLOR_THICK)
    for y in np.arange(round(y_min, 1), round(y_max, 1), 0.5):
        fig.add_hline(y=round(y, 2), line_width=0.8, line_color=GRID_COLOR_THICK)

    fig.add_trace(go.Scatter(
        x=t_cut,
        y=s_cut,
        mode='lines',
        line=dict(color=SIGNAL_COLOR, width=1.2),
        name=lead_name,
    ))

    fig.update_layout(
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=BACKGROUND_COLOR,
        height=220,
        margin=dict(l=50, r=10, t=25, b=25),
        xaxis=dict(title='Tiempo (s)', showgrid=False, range=[0, segundos]),
        yaxis=dict(title='mV',         showgrid=False, range=[y_min, y_max]),
        #title=dict(text=f"Derivación {lead_name}", font=dict(size=12)),
        title=dict(
            text=f"Derivada {lead_name}",
            font=dict(size=13, color="#aaaaaa"),
            x=0.01,
            xanchor="left",
        ),
        showlegend=False,
    )

    return fig
