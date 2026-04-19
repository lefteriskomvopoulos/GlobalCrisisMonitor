"""GDELT Crisis Monitor — multi-tab interactive dashboard.

Tabs:
    * Map          — global event map with severity coloring
    * Heatmap      — country x hour severity heatmap
    * Rankings     — country leaderboard + QuadClass breakdown
    * Anomalies    — flagged events from IsolationForest + KMeans
    * Models       — MLOps run history (MAE, RMSE, F1, precision, recall)
"""
from __future__ import annotations

import json
from pathlib import Path

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html

from config import DASHBOARD_DB, METRICS_DIR, QUAD_CLASS_LABELS

DARK_BG, DARK_FG, ACCENT = "#111111", "#eeeeee", "#ff4b4b"
LIGHT_BG, LIGHT_FG = "#f4f4f9", "#222222"


def _load_events() -> pd.DataFrame:
    if not Path(DASHBOARD_DB).exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(DASHBOARD_DB)
    except Exception as e:
        print(f"[dashboard] parquet read error: {e}")
        return pd.DataFrame()
    for col, default in (("SOURCEURL", None), ("IsAnomaly", 0),
                         ("IsKMeansAnomaly", 0), ("AnomalyCluster", -1),
                         ("PredictedLabel", -1), ("QuadClass", -1),
                         ("EventCount", 1)):
        if col not in df.columns:
            df[col] = default
    df["DateFormatted"] = pd.to_datetime(df["DateFormatted"])
    df["QuadLabel"] = df["QuadClass"].map(QUAD_CLASS_LABELS).fillna("Unknown")
    return df


def _load_runs() -> pd.DataFrame:
    path = METRICS_DIR / "runs.jsonl"
    if not path.exists():
        return pd.DataFrame()
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            flat = {"run_id": r["run_id"], "timestamp": r["timestamp"],
                    "model": r["model"], "stage": r["stage"]}
            flat.update(r.get("metrics", {}))
            rows.append(flat)
    return pd.DataFrame(rows)


def _load_summary() -> dict:
    path = METRICS_DIR / "pipeline_run.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Dash app
# ---------------------------------------------------------------------------
app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "GDELT Crisis Monitor"

TABS = [
    {"label": "Map",        "value": "map"},
    {"label": "Heatmap",    "value": "heatmap"},
    {"label": "Rankings",   "value": "rankings"},
    {"label": "Anomalies",  "value": "anomalies"},
    {"label": "Models",     "value": "models"},
]

app.layout = html.Div(id="main-container", style={"minHeight": "100vh"}, children=[
    # Header
    html.Div(style={"display": "flex", "justifyContent": "space-between",
                    "alignItems": "center", "padding": "14px 22px"}, children=[
        html.H1("⚡ GLOBAL CRISIS MONITOR", id="main-title",
                style={"color": ACCENT, "margin": "0", "fontSize": "26px"}),
        html.Div([
            html.Span(id="kpi-strip", style={"marginRight": "20px", "fontSize": "14px"}),
            html.Button("Theme", id="theme-toggle", n_clicks=0,
                        style={"padding": "8px 14px", "cursor": "pointer",
                               "borderRadius": "6px", "fontWeight": "bold",
                               "border": "1px solid #888", "background": "transparent",
                               "color": "inherit"}),
        ]),
    ]),

    # Tabs
    dcc.Tabs(id="tabs", value="map", children=[
        dcc.Tab(label=t["label"], value=t["value"]) for t in TABS
    ]),

    html.Div(id="tab-content", style={"padding": "14px 20px"}),

    # Auto refresh + theme store
    dcc.Interval(id="refresh", interval=60 * 1000, n_intervals=0),
    dcc.Store(id="theme-store", data="dark"),
])


# ---------------------------------------------------------------------------
# Theme + KPI strip
# ---------------------------------------------------------------------------
@app.callback(
    [Output("theme-store", "data"),
     Output("main-container", "style"),
     Output("kpi-strip", "children"),
     Output("kpi-strip", "style")],
    [Input("theme-toggle", "n_clicks"),
     Input("refresh", "n_intervals")],
    State("theme-store", "data"),
)
def update_chrome(n_clicks, n_intervals, current_theme):
    ctx = dash.callback_context
    trig = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
    theme = ("light" if current_theme == "dark" else "dark") if trig == "theme-toggle" else current_theme
    bg, fg = (LIGHT_BG, LIGHT_FG) if theme == "light" else (DARK_BG, DARK_FG)

    df = _load_events()
    summary = _load_summary()
    if df.empty:
        kpi = "No data loaded yet — run `python run_pipeline.py`"
    else:
        total = len(df)
        anomalies = int(df["IsAnomaly"].sum())
        avg_sev = df["SeverityPct"].mean() if "SeverityPct" in df else 0
        countries = df["CountryName"].nunique()
        row_count = summary.get("row_count", total)
        kpi = (f"📊 warehouse rows: {row_count:,}  |  "
               f"🌍 dashboard rows: {total:,}  |  "
               f"🔥 anomalies: {anomalies:,}  |  "
               f"📈 avg severity: {avg_sev:.1f}%  |  "
               f"🗺 countries: {countries}")

    container_style = {"minHeight": "100vh", "backgroundColor": bg, "color": fg,
                       "fontFamily": "system-ui, -apple-system, sans-serif"}
    kpi_style = {"marginRight": "20px", "fontSize": "14px", "color": fg}
    return theme, container_style, kpi, kpi_style


# ---------------------------------------------------------------------------
# Tab routing
# ---------------------------------------------------------------------------
@app.callback(
    Output("tab-content", "children"),
    [Input("tabs", "value"),
     Input("refresh", "n_intervals"),
     Input("theme-store", "data")],
)
def render_tab(tab, _n, theme):
    df = _load_events()
    if df.empty:
        return html.Div("⚠️ No dashboard data found. Run "
                        "`python run_pipeline.py` to populate it.",
                        style={"padding": "30px", "fontSize": "18px"})

    map_style = "carto-darkmatter" if theme == "dark" else "carto-positron"
    bg, fg = (DARK_BG, DARK_FG) if theme == "dark" else (LIGHT_BG, LIGHT_FG)
    template = "plotly_dark" if theme == "dark" else "plotly_white"

    if tab == "map":
        return _render_map(df, map_style, bg, fg, template)
    if tab == "heatmap":
        return _render_heatmap(df, bg, fg, template)
    if tab == "rankings":
        return _render_rankings(df, bg, fg, template)
    if tab == "anomalies":
        return _render_anomalies(df, map_style, bg, fg, template)
    if tab == "models":
        return _render_models(bg, fg, template)
    return html.Div()


# ---------------------------------------------------------------------------
# Tab: map
# ---------------------------------------------------------------------------
MAP_MAX_POINTS = 10000


def _downsample_for_map(df: pd.DataFrame, cap: int = MAP_MAX_POINTS) -> pd.DataFrame:
    if len(df) <= cap:
        return df
    # Keep the top-severity half deterministically, then random-sample the rest
    df = df.copy()
    top_n = cap // 2
    top = df.nlargest(top_n, "SeverityPct")
    rest = df.drop(top.index).sample(n=cap - top_n, random_state=42)
    return pd.concat([top, rest], ignore_index=True)


def _render_map(df, map_style, bg, fg, template):
    df = df.copy()
    df["SeverityPct"] = df["SeverityPct"].fillna(0).astype(float)
    rendered = _downsample_for_map(df)
    fig = px.scatter_mapbox(
        rendered, lat="ActionGeo_Lat", lon="ActionGeo_Long",
        color="SeverityPct", size=rendered["SeverityPct"].clip(lower=3) + 3,
        color_continuous_scale="OrRd",
        zoom=1.4, center={"lat": 20, "lon": 0},
        hover_name="CountryName",
        custom_data=["SeverityPct", "DateFormatted", "SOURCEURL",
                     "AnomalyCluster", "QuadLabel", "IsAnomaly"],
    )
    fig.update_traces(hovertemplate="<br>".join([
        "<b>📍 %{hovertext}</b>",
        "🔥 Severity: %{customdata[0]:.1f}%",
        "🧭 QuadClass: %{customdata[4]}",
        "🚨 Cluster: %{customdata[3]} | Anomaly: %{customdata[5]}",
        "📅 %{customdata[1]|%b %d %H:%M}",
        "<extra></extra>",
    ]))
    fig.update_layout(
        mapbox_style=map_style, margin={"r": 0, "t": 0, "l": 0, "b": 0},
        paper_bgcolor=bg, font=dict(color=fg),
        coloraxis_colorbar=dict(title="Severity %"),
        template=template,
    )

    return html.Div([
        dcc.Graph(id="live-map", figure=fig, style={"height": "72vh"},
                  config={"displayModeBar": True, "scrollZoom": True}),
        html.Div(id="click-data-panel",
                 style={"padding": "12px 4px", "fontSize": "15px"},
                 children="Click a marker to view the source article."),
    ])


@app.callback(
    Output("click-data-panel", "children"),
    Input("live-map", "clickData"),
    State("theme-store", "data"),
    prevent_initial_call=True,
)
def show_click(clickData, theme):
    fg = DARK_FG if theme == "dark" else LIGHT_FG
    if not clickData:
        return "Click a marker to view the source article."
    p = clickData["points"][0]
    cd = p.get("customdata") or []
    loc = p.get("hovertext", "Unknown")
    if len(cd) > 2 and cd[2]:
        return html.Div([
            html.Span(f"📰 {loc} — ", style={"fontWeight": "bold", "color": fg}),
            html.A(str(cd[2]), href=str(cd[2]), target="_blank",
                   style={"color": ACCENT, "textDecoration": "underline",
                          "wordBreak": "break-all"}),
        ])
    return html.Span(f"{loc} — no source URL available.", style={"color": fg})


# ---------------------------------------------------------------------------
# Tab: heatmap
# ---------------------------------------------------------------------------
def _render_heatmap(df, bg, fg, template):
    df = df.copy()
    df["Hour"] = df["DateFormatted"].dt.floor("h")
    top = (df.groupby("CountryName")["SeverityPct"].mean()
             .sort_values(ascending=False).head(30).index)
    pivot = (df[df["CountryName"].isin(top)]
             .pivot_table(index="CountryName", columns="Hour",
                          values="SeverityPct", aggfunc="mean"))
    if pivot.empty:
        return html.Div("Not enough data for a heatmap yet.")
    fig = px.imshow(
        pivot, color_continuous_scale="OrRd", aspect="auto",
        labels={"color": "Severity %", "x": "Hour", "y": "Country"},
        title="Top-30 locations — severity by hour",
    )
    fig.update_layout(paper_bgcolor=bg, plot_bgcolor=bg, font=dict(color=fg),
                      template=template, height=650)

    # Also: global volume timeseries
    ts = df.groupby("Hour").agg(events=("SeverityPct", "size"),
                                avg_sev=("SeverityPct", "mean")).reset_index()
    fig_ts = go.Figure()
    fig_ts.add_trace(go.Scatter(x=ts["Hour"], y=ts["events"], name="Events/hr",
                                line=dict(color="#4c72b0", width=2)))
    fig_ts.add_trace(go.Scatter(x=ts["Hour"], y=ts["avg_sev"], name="Avg severity",
                                line=dict(color=ACCENT, width=2), yaxis="y2"))
    fig_ts.update_layout(
        paper_bgcolor=bg, plot_bgcolor=bg, font=dict(color=fg), template=template,
        title="Global volume vs severity", height=380,
        yaxis=dict(title="Events / hour", side="left"),
        yaxis2=dict(title="Severity %", overlaying="y", side="right"),
        legend=dict(orientation="h"),
    )
    return html.Div([dcc.Graph(figure=fig), dcc.Graph(figure=fig_ts)])


# ---------------------------------------------------------------------------
# Tab: rankings
# ---------------------------------------------------------------------------
def _render_rankings(df, bg, fg, template):
    top_countries = (df.groupby("CountryName")
                       .agg(events=("SeverityPct", "size"),
                            avg_severity=("SeverityPct", "mean"),
                            avg_tone=("AvgTone", "mean"))
                       .sort_values("avg_severity", ascending=False)
                       .head(25).reset_index())
    fig_top = px.bar(top_countries, x="avg_severity", y="CountryName",
                     orientation="h", color="avg_severity",
                     color_continuous_scale="OrRd",
                     title="Top 25 locations by average severity",
                     hover_data={"events": True, "avg_tone": ":.2f"})
    fig_top.update_layout(paper_bgcolor=bg, plot_bgcolor=bg, font=dict(color=fg),
                          template=template, height=600, yaxis={"autorange": "reversed"})

    quad_counts = df.groupby("QuadLabel").size().reset_index(name="count")
    fig_quad = px.pie(quad_counts, values="count", names="QuadLabel",
                      title="CAMEO QuadClass distribution",
                      color_discrete_sequence=px.colors.sequential.OrRd)
    fig_quad.update_layout(paper_bgcolor=bg, font=dict(color=fg),
                           template=template, height=420)

    return html.Div([
        dcc.Graph(figure=fig_top),
        dcc.Graph(figure=fig_quad),
    ])


# ---------------------------------------------------------------------------
# Tab: anomalies
# ---------------------------------------------------------------------------
def _render_anomalies(df, map_style, bg, fg, template):
    anomalies = df[df["IsAnomaly"] == 1].copy()
    if anomalies.empty:
        return html.Div("No anomalies flagged in the current dataset.")

    rendered = _downsample_for_map(anomalies, cap=6000)
    fig_map = px.scatter_mapbox(
        rendered, lat="ActionGeo_Lat", lon="ActionGeo_Long",
        size=rendered["SeverityPct"].clip(lower=4) + 4,
        color="SeverityPct", color_continuous_scale="Reds",
        zoom=1.4, center={"lat": 20, "lon": 0},
        hover_name="CountryName",
        custom_data=["SeverityPct", "DateFormatted", "SOURCEURL", "QuadLabel"],
    )
    fig_map.update_traces(hovertemplate="<br>".join([
        "<b>📍 %{hovertext}</b>",
        "🔥 Severity: %{customdata[0]:.1f}%",
        "🧭 %{customdata[3]}",
        "📅 %{customdata[1]|%b %d %H:%M}",
        "<extra></extra>",
    ]))
    fig_map.update_layout(mapbox_style=map_style, paper_bgcolor=bg,
                          font=dict(color=fg), margin={"r": 0, "t": 0, "l": 0, "b": 0},
                          height=500, template=template)

    top = (anomalies.groupby("CountryName").size()
           .sort_values(ascending=False).head(15).reset_index(name="n"))
    fig_bar = px.bar(top, x="n", y="CountryName", orientation="h",
                     title="Top anomaly locations", color="n",
                     color_continuous_scale="Reds")
    fig_bar.update_layout(paper_bgcolor=bg, plot_bgcolor=bg, font=dict(color=fg),
                          template=template, height=450,
                          yaxis={"autorange": "reversed"})

    table_df = anomalies.nlargest(25, "SeverityPct")[[
        "DateFormatted", "CountryName", "SeverityPct", "AvgTone",
        "GoldsteinScale", "QuadLabel", "SOURCEURL",
    ]]
    table_rows = [html.Tr([html.Th(c) for c in table_df.columns])]
    for _, row in table_df.iterrows():
        cells = []
        for col in table_df.columns:
            v = row[col]
            if col == "SOURCEURL" and pd.notna(v):
                cells.append(html.Td(html.A(str(v)[:60] + "…", href=str(v),
                                            target="_blank",
                                            style={"color": ACCENT})))
            elif col == "DateFormatted":
                cells.append(html.Td(str(v)))
            elif isinstance(v, float):
                cells.append(html.Td(f"{v:.2f}"))
            else:
                cells.append(html.Td(str(v)))
        table_rows.append(html.Tr(cells))

    return html.Div([
        dcc.Graph(figure=fig_map),
        dcc.Graph(figure=fig_bar),
        html.H3("Highest-severity anomalies", style={"marginTop": "24px"}),
        html.Div(html.Table(table_rows, style={
            "width": "100%", "borderCollapse": "collapse",
            "fontSize": "13px"}),
            style={"overflowX": "auto"},
        ),
    ])


# ---------------------------------------------------------------------------
# Tab: models
# ---------------------------------------------------------------------------
def _render_models(bg, fg, template):
    runs = _load_runs()
    if runs.empty:
        return html.Div("No MLOps runs logged yet.")
    runs = runs.sort_values("timestamp")

    # History chart: F1 over runs (classification)
    cls = runs[runs["model"].str.contains("spark_", na=False)].copy()
    figs = []
    if not cls.empty and "f1" in cls.columns:
        f = px.line(cls, x="timestamp", y="f1", color="model",
                    markers=True, title="Spark classifier F1 across runs")
        f.update_layout(paper_bgcolor=bg, plot_bgcolor=bg, font=dict(color=fg),
                        template=template, height=360)
        figs.append(dcc.Graph(figure=f))

    reg = runs[runs["model"].isin(
        ["pytorch_severity_net", "gbr_tone_forecaster"])].copy()
    if not reg.empty:
        melted_cols = [c for c in ["mae", "rmse"] if c in reg.columns]
        if melted_cols:
            reg_long = reg.melt(
                id_vars=["timestamp", "model"], value_vars=melted_cols,
                var_name="metric", value_name="value",
            ).dropna()
            f = px.line(reg_long, x="timestamp", y="value",
                        color="model", line_dash="metric", markers=True,
                        title="Regressor MAE / RMSE across runs")
            f.update_layout(paper_bgcolor=bg, plot_bgcolor=bg, font=dict(color=fg),
                            template=template, height=360)
            figs.append(dcc.Graph(figure=f))

    iso = runs[runs["model"] == "isolation_forest"].copy()
    if not iso.empty and "precision" in iso.columns:
        iso_long = iso.melt(
            id_vars=["timestamp"],
            value_vars=[c for c in ["precision", "recall", "f1"] if c in iso.columns],
            var_name="metric", value_name="value",
        ).dropna()
        f = px.line(iso_long, x="timestamp", y="value", color="metric",
                    markers=True, title="IsolationForest precision / recall / F1")
        f.update_layout(paper_bgcolor=bg, plot_bgcolor=bg, font=dict(color=fg),
                        template=template, height=360)
        figs.append(dcc.Graph(figure=f))

    latest = runs.tail(12)[::-1]
    header_cols = ["timestamp", "model", "stage"] + [
        c for c in ["accuracy", "f1", "weightedPrecision", "weightedRecall",
                    "mae", "rmse", "precision", "recall"] if c in latest.columns]
    table_rows = [html.Tr([html.Th(c) for c in header_cols])]
    for _, r in latest.iterrows():
        cells = []
        for c in header_cols:
            v = r.get(c)
            if isinstance(v, float):
                cells.append(html.Td(f"{v:.3f}"))
            else:
                cells.append(html.Td(str(v) if pd.notna(v) else ""))
        table_rows.append(html.Tr(cells))

    figs.append(html.H3("Recent runs", style={"marginTop": "20px"}))
    figs.append(html.Div(html.Table(table_rows, style={
        "width": "100%", "borderCollapse": "collapse", "fontSize": "13px"}),
        style={"overflowX": "auto"}))
    return html.Div(figs)


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=8050, dev_tools_ui=False)
