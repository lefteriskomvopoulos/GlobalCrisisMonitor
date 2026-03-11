import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, State

app = Dash(__name__)

# Initial empty layout structure
app.layout = html.Div(id='main-container', style={'minHeight': '100vh', 'transition': 'background-color 0.3s'}, children=[
    
    # Settings Bar
    html.Div(style={'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center', 'padding': '15px 20px'}, children=[
        html.H1("⚡ GLOBAL CRISIS MONITOR", id='main-title', style={'color': '#ff4b4b', 'margin': '0', 'fontSize': '28px'}),
        html.Button("Toggle Light/Dark Mode", id='theme-toggle', n_clicks=0, 
                    style={'padding': '10px 15px', 'cursor': 'pointer', 'borderRadius': '5px', 'fontWeight': 'bold'})
    ]),
    
    # News Link Panel
    html.Div(id='click-data-panel', style={'padding': '15px 20px', 'fontSize': '16px'}, children=[
        html.P("Click a marker on the map to view the related news source.", id='click-data-text')
    ]),

    # Map
    dcc.Graph(
        id='live-map', 
        style={'height': '65vh'},
        config={'displayModeBar': True, 'scrollZoom': True}
    ),
    
    # Trend Chart
    dcc.Graph(
        id='trend-chart', 
        style={'height': '35vh', 'marginTop': '10px', 'padding': '0 20px'},
        config={'displayModeBar': False}
    ),

    # Interval for Auto-refresh
    dcc.Interval(
        id='auto-refresh-interval',
        interval=60*1000, # 60 seconds
        n_intervals=0
    ),

    dcc.Store(id='theme-store', data='dark')
])

@app.callback(
    [Output('live-map', 'figure'),
     Output('trend-chart', 'figure'),
     Output('theme-store', 'data'),
     Output('main-container', 'style'),
     Output('click-data-text', 'style')],
    [Input('auto-refresh-interval', 'n_intervals'),
     Input('theme-toggle', 'n_clicks')],
    [State('theme-store', 'data'),
     State('live-map', 'relayoutData')]
)
def update_map(n_intervals, n_clicks, current_theme, relayoutData):
    # Determine theme
    import dash
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
    
    if triggered_id == 'theme-toggle':
        theme = 'light' if current_theme == 'dark' else 'dark'
    else:
        theme = current_theme

    map_style = "carto-positron" if theme == 'light' else "carto-darkmatter"
    bg_color = "#f4f4f9" if theme == 'light' else "#111111"
    text_color = "#333333" if theme == 'light' else "#eeeeee"
    plotly_template = "plotly_white" if theme == 'light' else "plotly_dark"

    # Reload Data
    try:
        df_viz = pd.read_parquet("dashboard_db")
        if 'SOURCEURL' not in df_viz.columns:
            df_viz['SOURCEURL'] = None
        if 'AnomalyCluster' not in df_viz.columns:
            df_viz['AnomalyCluster'] = -1
    except Exception:
        df_viz = pd.DataFrame(columns=["ActionGeo_Lat", "ActionGeo_Long", "SeverityPct", "CountryName", "DateFormatted", "SOURCEURL", "AnomalyCluster"])
    
    # Establish default map viewport
    center_lat, center_lon = 20, 0
    zoom_level = 1.5

    # Retain viewport from previous state if available
    if relayoutData:
        if 'mapbox.center' in relayoutData:
            center_lat = relayoutData['mapbox.center'].get('lat', center_lat)
            center_lon = relayoutData['mapbox.center'].get('lon', center_lon)
        if 'mapbox.zoom' in relayoutData:
            zoom_level = relayoutData['mapbox.zoom']

    # Default empty charts if no data
    if df_viz.empty:
        fig = px.scatter_mapbox(lat=[0], lon=[0], zoom=zoom_level, center={"lat": center_lat, "lon": center_lon})
        fig_trend = px.line(title="Awaiting Data...")
    else:
        df_viz["SeverityPct"] = df_viz["SeverityPct"].astype(float)
        
        # Determine size, ensuring no negative or NaN values break Plotly
        size_array = df_viz["SeverityPct"].fillna(0) + 5
        
        # 1. Map Figure
        fig = px.scatter_mapbox(
            df_viz, 
            lat="ActionGeo_Lat", 
            lon="ActionGeo_Long", 
            color="SeverityPct",
            size=size_array,
            color_continuous_scale="OrRd", 
            zoom=zoom_level,
            center={"lat": center_lat, "lon": center_lon},
            custom_data=["SeverityPct", "DateFormatted", "SOURCEURL", "AnomalyCluster"] 
        )

        fig.update_traces(
            hovertemplate="<br>".join([
                "<b>📍 Location:</b> %{hovertext}",
                "<b>🔥 Severity:</b> %{customdata[0]:.1f}%",
                "<b>🚨 Anomaly Cluster:</b> %{customdata[3]}",
                "<b>📅 Date:</b> %{customdata[1]|%b %d, %Y}",
                "<extra></extra>"
            ]),
            hovertext=df_viz["CountryName"],
        )
        
        # 2. Trend Line Chart
        # Group by hour to get the severity trend
        df_viz['Hour'] = pd.to_datetime(df_viz['DateFormatted']).dt.floor('h')
        df_trend = df_viz.groupby('Hour')['SeverityPct'].mean().reset_index()
        df_trend = df_trend.sort_values(by='Hour')
        
        fig_trend = px.line(
            df_trend, 
            x="Hour", 
            y="SeverityPct", 
            title="Global Average Severity Trend (Hourly)",
            labels={"Hour": "Time", "SeverityPct": "Avg Severity %"}
        )
        # Style trend chart
        fig_trend.update_traces(line_color="#ff4b4b", line_width=3)
        fig_trend.update_layout(
            template=plotly_template,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font=dict(color=text_color),
            margin={"r":20,"t":40,"l":20,"b":20}
        )

    # Style map
    fig.update_layout(
        mapbox_style=map_style,
        mapbox_bounds={"west": -180, "east": 180, "south": -90, "north": 90},
        margin={"r":0,"t":0,"l":0,"b":0},
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color=text_color),
        coloraxis_colorbar=dict(title="Severity %")
    )
    
    container_style = {'minHeight': '100vh', 'backgroundColor': bg_color, 'transition': 'background-color 0.3s'}
    text_style = {'color': text_color}

    return fig, fig_trend, theme, container_style, text_style

@app.callback(
    Output('click-data-panel', 'children'),
    [Input('live-map', 'clickData')],
    [State('theme-store', 'data')]
)
def display_click_data(clickData, theme):
    text_color = "#333333" if theme == 'light' else "#eeeeee"
    if clickData is None:
        return html.P("Click a marker on the map to view the related news source.", id='click-data-text', style={'color': text_color})
    
    point = clickData['points'][0]
    customdata = point.get('customdata', [])
    if len(customdata) > 2:
        source_url = customdata[2]
        location = point.get('hovertext', 'Unknown Location')
        if pd.isna(source_url) or source_url is None:
             return html.P(f"Latest Selection ({location}): No URL available.", id='click-data-text', style={'color': text_color, 'fontWeight': 'bold'})
        return html.Div([
            html.Span(f"Latest Selection ({location}): ", style={'color': text_color, 'fontWeight': 'bold'}),
            html.A(str(source_url), href=str(source_url), target="_blank", style={'color': '#ff4b4b', 'textDecoration': 'underline'})
        ], id='click-data-text')
        
    return html.P("No URL found for this event.", id='click-data-text', style={'color': text_color})

if __name__ == '__main__':
    app.run(debug=False, port=8050, dev_tools_ui=False)