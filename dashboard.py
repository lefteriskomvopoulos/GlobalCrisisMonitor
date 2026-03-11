import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html

# 1. LOAD DATA
df_viz = pd.read_parquet("dashboard_db")

# 2. CREATE ENHANCED MAP
fig = px.scatter_mapbox(
    df_viz, 
    lat="ActionGeo_Lat", 
    lon="ActionGeo_Long", 
    color="SeverityPct",
    size=df_viz["SeverityPct"] + 5,
    color_continuous_scale="OrRd", 
    zoom=1.5,
    center={"lat": 20, "lon": 0}
)

### ENHANCE HOVER WITH PERCENTAGE
fig.update_traces(
    hovertemplate="<br>".join([
        "<b>📍 Location:</b> %{hovertext}",
        "<b>🔥 Severity:</b> %{customdata[0]:.1f}%",
        "<b>📅 Date:</b> %{customdata[1]|%b %d, %Y}",
        "<extra></extra>"
    ]),
    hovertext=df_viz["CountryName"],
    customdata=df_viz[["SeverityPct", "DateFormatted"]]
)

fig.update_layout(
    mapbox_style="carto-darkmatter",
    mapbox_bounds={"west": -180, "east": 180, "south": -90, "north": 90},
    margin={"r":0,"t":0,"l":0,"b":0},
    paper_bgcolor="#111111",
    coloraxis_colorbar=dict(title="Severity %")
)

# 3. DASH UI
app = Dash(__name__)

app.layout = html.Div(style={'backgroundColor': '#111111', 'minHeight': '100vh'}, children=[
    html.H1("⚡ GLOBAL CRISIS MONITOR", 
            style={'textAlign': 'center', 'color': '#ff4b4b', 'padding': '20px', 'margin': '0'}),
    dcc.Graph(
        id='live-map', 
        figure=fig, 
        style={'height': '85vh'},
        config={'displayModeBar': False}
    )
])

if __name__ == '__main__':
    app.run(debug=False, port=8050, dev_tools_ui=False)