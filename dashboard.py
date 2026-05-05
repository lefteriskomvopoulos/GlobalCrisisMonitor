"""GDELT Crisis Monitor — multi-tab interactive dashboard.

Tabs:
    * Map          — global event map with severity coloring
    * Heatmap      — country x hour severity heatmap
    * Rankings     — country leaderboard + QuadClass breakdown
    * Anomalies    — flagged events from IsolationForest + KMeans
    * Models       — MLOps run history (MAE, RMSE, F1, precision, recall)

A shared filter bar (date range, severity slider, country picker, QuadClass
checklist, anomaly toggle, top-N slider) feeds every tab so the user can
slice the warehouse interactively without rerunning the pipeline.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import date, timedelta

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html

from config import DASHBOARD_DB, METRICS_DIR, QUAD_CLASS_LABELS

DARK_BG, DARK_FG, ACCENT = "#111111", "#eeeeee", "#ff4b4b"
PANEL_DARK, PANEL_LIGHT = "#1c1c1c", "#ffffff"
LIGHT_BG, LIGHT_FG = "#f4f4f9", "#222222"

QUAD_OPTIONS = [{"label": v, "value": int(k)} for k, v in QUAD_CLASS_LABELS.items()]


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
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
# Filter helpers
# ---------------------------------------------------------------------------
def _country_options(df: pd.DataFrame, limit: int = 80) -> list[dict]:
    if df.empty or "CountryName" not in df.columns:
        return []
    counts = (df["CountryName"].dropna().value_counts().head(limit))
    return [{"label": f"{name}  ({n})", "value": name}
            for name, n in counts.items()]


def _apply_filters(df: pd.DataFrame, *, date_start, date_end, severity_range,
                   countries, quad_classes, anomalies_only) -> pd.DataFrame:
    if df.empty:
        return df
    out = df
    if date_start:
        out = out[out["DateFormatted"] >= pd.Timestamp(date_start)]
    if date_end:
        out = out[out["DateFormatted"] <= pd.Timestamp(date_end) + pd.Timedelta(days=1)]
    if severity_range and len(severity_range) == 2:
        lo, hi = severity_range
        out = out[(out["SeverityPct"] >= lo) & (out["SeverityPct"] <= hi)]
    if countries:
        out = out[out["CountryName"].isin(countries)]
    if quad_classes:
        out = out[out["QuadClass"].isin([int(q) for q in quad_classes])]
    if anomalies_only:
        out = out[out["IsAnomaly"] == 1]
    return out


# ---------------------------------------------------------------------------
# Initial data probe (for default slider/date bounds)
# ---------------------------------------------------------------------------
_BOOT = _load_events()
if not _BOOT.empty:
    _MIN_DATE = _BOOT["DateFormatted"].min().date()
    _MAX_DATE = _BOOT["DateFormatted"].max().date()
    _DEFAULT_COUNTRIES = _country_options(_BOOT)
else:
    _MAX_DATE = date.today()
    _MIN_DATE = _MAX_DATE - timedelta(days=7)
    _DEFAULT_COUNTRIES = []


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


def _control_label(text):
    return html.Label(text, className="filter-label",
                      style={"fontSize": "12px", "fontWeight": "600",
                             "marginBottom": "4px", "display": "block"})


filter_bar = html.Div(id="filter-bar", className="filter-bar", style={
    "padding": "12px 22px", "display": "grid",
    "gridTemplateColumns": "1.4fr 1.6fr 1.8fr 1.4fr 0.9fr 0.9fr",
    "gap": "16px", "alignItems": "end",
    "borderTop": "1px solid #333", "borderBottom": "1px solid #333",
}, children=[
    html.Div([
        _control_label("Date range"),
        dcc.DatePickerRange(
            id="filter-date",
            min_date_allowed=_MIN_DATE,
            max_date_allowed=_MAX_DATE,
            start_date=_MIN_DATE,
            end_date=_MAX_DATE,
            display_format="MMM D",
            style={"fontSize": "12px"},
        ),
    ]),
    html.Div([
        _control_label("Severity range (%)"),
        dcc.RangeSlider(
            id="filter-severity",
            min=0, max=100, step=1, value=[0, 100],
            marks={0: "0", 25: "25", 50: "50", 75: "75", 100: "100"},
            tooltip={"placement": "bottom", "always_visible": False},
        ),
    ]),
    html.Div([
        _control_label("Countries / locations"),
        dcc.Dropdown(
            id="filter-country",
            options=_DEFAULT_COUNTRIES,
            value=[],
            multi=True,
            placeholder="All countries (type to filter)",
            style={"fontSize": "13px", "color": "#111"},
        ),
    ]),
    html.Div([
        _control_label("CAMEO QuadClass"),
        dcc.Checklist(
            id="filter-quad",
            options=QUAD_OPTIONS,
            value=[1, 2, 3, 4],
            inline=True,
            inputStyle={"marginRight": "4px", "marginLeft": "10px"},
            style={"fontSize": "12px"},
        ),
    ]),
    html.Div([
        _control_label("Top-N (rankings)"),
        dcc.Slider(
            id="filter-topn",
            min=5, max=50, step=5, value=25,
            marks={5: "5", 25: "25", 50: "50"},
            tooltip={"placement": "bottom", "always_visible": False},
        ),
    ]),
    html.Div([
        _control_label("Anomalies only"),
        dcc.Checklist(
            id="filter-anomaly",
            options=[{"label": " on", "value": "on"}],
            value=[],
            inputStyle={"marginRight": "4px"},
            style={"fontSize": "13px"},
        ),
        html.Button("Reset filters", id="filter-reset", n_clicks=0,
                    style={"marginTop": "6px", "padding": "5px 10px",
                           "fontSize": "11px", "cursor": "pointer",
                           "borderRadius": "4px",
                           "border": "1px solid #888",
                           "background": "transparent",
                           "color": "inherit"}),
    ]),
])


app.layout = html.Div(id="main-container", className="theme-dark",
                      style={"minHeight": "100vh"}, children=[
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

    filter_bar,

    # Tabs
    dcc.Tabs(id="tabs", value="map", children=[
        dcc.Tab(label=t["label"], value=t["value"]) for t in TABS
    ]),

    html.Div(id="tab-content", style={"padding": "14px 20px"}),

    # Stores + interval
    dcc.Interval(id="refresh", interval=60 * 1000, n_intervals=0),
    dcc.Store(id="theme-store", data="dark"),
])


# ---------------------------------------------------------------------------
# Reset filters
# ---------------------------------------------------------------------------
@app.callback(
    [Output("filter-date", "start_date"),
     Output("filter-date", "end_date"),
     Output("filter-severity", "value"),
     Output("filter-country", "value"),
     Output("filter-quad", "value"),
     Output("filter-anomaly", "value"),
     Output("filter-topn", "value")],
    Input("filter-reset", "n_clicks"),
    prevent_initial_call=True,
)
def reset_filters(_n):
    return (_MIN_DATE, _MAX_DATE, [0, 100], [], [1, 2, 3, 4], [], 25)


# ---------------------------------------------------------------------------
# Theme + KPI strip
# ---------------------------------------------------------------------------
@app.callback(
    [Output("theme-store", "data"),
     Output("main-container", "style"),
     Output("main-container", "className"),
     Output("kpi-strip", "children"),
     Output("kpi-strip", "style"),
     Output("filter-bar", "style"),
     Output("filter-severity", "marks"),
     Output("filter-topn", "marks")],
    [Input("theme-toggle", "n_clicks"),
     Input("refresh", "n_intervals"),
     Input("filter-date", "start_date"),
     Input("filter-date", "end_date"),
     Input("filter-severity", "value"),
     Input("filter-country", "value"),
     Input("filter-quad", "value"),
     Input("filter-anomaly", "value")],
    State("theme-store", "data"),
)
def update_chrome(n_clicks, n_intervals, d_start, d_end, sev, countries,
                  quads, anomaly_only, current_theme):
    ctx = dash.callback_context
    trig = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None
    theme = ("light" if current_theme == "dark" else "dark") if trig == "theme-toggle" else current_theme
    bg, fg = (LIGHT_BG, LIGHT_FG) if theme == "light" else (DARK_BG, DARK_FG)
    panel = PANEL_LIGHT if theme == "light" else PANEL_DARK

    df = _load_events()
    summary = _load_summary()
    if df.empty:
        kpi = "No data loaded yet — run python run_pipeline.py"
    else:
        filtered = _apply_filters(
            df, date_start=d_start, date_end=d_end,
            severity_range=sev, countries=countries, quad_classes=quads,
            anomalies_only=("on" in (anomaly_only or [])),
        )
        total_warehouse = summary.get("row_count", len(df))
        total = len(filtered)
        anomalies = int(filtered["IsAnomaly"].sum()) if not filtered.empty else 0
        avg_sev = filtered["SeverityPct"].mean() if not filtered.empty else 0
        unique_countries = filtered["CountryName"].nunique() if not filtered.empty else 0
        kpi = (f"📊 warehouse: {total_warehouse:,}  |  "
               f"🌍 filtered: {total:,}  |  "
               f"🔥 anomalies: {anomalies:,}  |  "
               f"📈 avg severity: {avg_sev:.1f}%  |  "
               f"🗺 countries: {unique_countries}")

    container_style = {"minHeight": "100vh", "backgroundColor": bg, "color": fg,
                       "fontFamily": "system-ui, -apple-system, sans-serif"}
    container_class = f"theme-{theme}"
    kpi_style = {"marginRight": "20px", "fontSize": "14px", "color": fg}
    filter_style = {
        "padding": "12px 22px", "display": "grid",
        "gridTemplateColumns": "1.4fr 1.6fr 1.8fr 1.4fr 0.9fr 0.9fr",
        "gap": "16px", "alignItems": "end",
        "background": panel,
        "color": fg,
        "borderTop": "1px solid #333" if theme == "dark" else "1px solid #ddd",
        "borderBottom": "1px solid #333" if theme == "dark" else "1px solid #ddd",
    }
    
    mark_color = "#ffffff" if theme == "dark" else "#222222"
    sev_marks = {v: {"label": str(v), "style": {"color": mark_color}} for v in [0, 25, 50, 75, 100]}
    topn_marks = {v: {"label": str(v), "style": {"color": mark_color}} for v in [5, 25, 50]}
    
    return theme, container_style, container_class, kpi, kpi_style, filter_style, sev_marks, topn_marks


# ---------------------------------------------------------------------------
# Tab routing
# ---------------------------------------------------------------------------
@app.callback(
    Output("tab-content", "children"),
    [Input("tabs", "value"),
     Input("refresh", "n_intervals"),
     Input("theme-store", "data"),
     Input("filter-date", "start_date"),
     Input("filter-date", "end_date"),
     Input("filter-severity", "value"),
     Input("filter-country", "value"),
     Input("filter-quad", "value"),
     Input("filter-anomaly", "value"),
     Input("filter-topn", "value")],
)
def render_tab(tab, _n, theme, d_start, d_end, sev, countries, quads,
               anomaly_only, top_n):
    raw = _load_events()
    if raw.empty:
        return html.Div("⚠️ No dashboard data found. Run "
                        "python run_pipeline.py to populate it.",
                        style={"padding": "30px", "fontSize": "18px"})

    df = _apply_filters(
        raw, date_start=d_start, date_end=d_end,
        severity_range=sev, countries=countries, quad_classes=quads,
        anomalies_only=("on" in (anomaly_only or [])),
    )

    if df.empty and tab != "models":
        return html.Div("No events match the current filters. Loosen the "
                        "date range or severity slider.",
                        style={"padding": "30px", "fontSize": "16px"})

    map_style = "carto-darkmatter" if theme == "dark" else "carto-positron"
    bg, fg = (DARK_BG, DARK_FG) if theme == "dark" else (LIGHT_BG, LIGHT_FG)
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    top_n = top_n or 25

    if tab == "map":
        return _render_map(df, map_style, bg, fg, template)
    if tab == "heatmap":
        return _render_heatmap(df, bg, fg, template, top_n)
    if tab == "rankings":
        return _render_rankings(df, bg, fg, template, top_n)
    if tab == "anomalies":
        return _render_anomalies(df, map_style, bg, fg, template, top_n)
    if tab == "models":
        return _render_models(bg, fg, template)
    return html.Div()


# ---------------------------------------------------------------------------
# Country dropdown options reload (auto refresh keeps them current)
# ---------------------------------------------------------------------------
@app.callback(
    Output("filter-country", "options"),
    Input("refresh", "n_intervals"),
)
def refresh_country_options(_n):
    df = _load_events()
    return _country_options(df)


# ---------------------------------------------------------------------------
# Tab: map
# ---------------------------------------------------------------------------
MAP_MAX_POINTS = 10000


def _downsample_for_map(df: pd.DataFrame, cap: int = MAP_MAX_POINTS) -> pd.DataFrame:
    if len(df) <= cap:
        return df
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

    # Tiny per-render counter so the user knows the filter affected the map
    rendered_count = len(rendered)
    total_count = len(df)
    note = (f"Showing {rendered_count:,} of {total_count:,} matching events "
            f"(map capped at {MAP_MAX_POINTS:,} for performance).")

    return html.Div([
        dcc.Graph(id="live-map", figure=fig, style={"height": "65vh"},
                  config={"displayModeBar": True, "scrollZoom": True}),
        html.Div(note, style={"padding": "6px 4px 0", "fontSize": "12px",
                              "opacity": "0.75"}),
        html.Div(id="click-data-panel",
                 style={"padding": "8px 4px", "fontSize": "15px"},
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
def _render_heatmap(df, bg, fg, template, top_n):
    df = df.copy()
    df["Hour"] = df["DateFormatted"].dt.floor("h")
    top = (df.groupby("CountryName")["SeverityPct"].mean()
             .sort_values(ascending=False).head(top_n).index)
    pivot = (df[df["CountryName"].isin(top)]
             .pivot_table(index="CountryName", columns="Hour",
                          values="SeverityPct", aggfunc="mean"))
    if pivot.empty:
        return html.Div("Not enough data for a heatmap yet.")
    fig = px.imshow(
        pivot, color_continuous_scale="OrRd", aspect="auto",
        labels={"color": "Severity %", "x": "Hour", "y": "Country"},
        title=f"Top-{top_n} locations: severity by hour",
    )
    fig.update_layout(paper_bgcolor=bg, plot_bgcolor=bg, font=dict(color=fg),
                      template=template, height=650)

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
def _render_rankings(df, bg, fg, template, top_n):
    top_countries = (df.groupby("CountryName")
                       .agg(events=("SeverityPct", "size"),
                            avg_severity=("SeverityPct", "mean"),
                            avg_tone=("AvgTone", "mean"))
                       .sort_values("avg_severity", ascending=False)
                       .head(top_n).reset_index())
    fig_top = px.bar(top_countries, x="avg_severity", y="CountryName",
                     orientation="h", color="avg_severity",
                     color_continuous_scale="OrRd",
                     title=f"Top {top_n} locations by average severity",
                     hover_data={"events": True, "avg_tone": ":.2f"})
    fig_top.update_layout(paper_bgcolor=bg, plot_bgcolor=bg, font=dict(color=fg),
                          template=template,
                          height=max(400, 22 * top_n + 80),
                          yaxis={"autorange": "reversed"})

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
def _render_anomalies(df, map_style, bg, fg, template, top_n):
    anomalies = df[df["IsAnomaly"] == 1].copy()
    if anomalies.empty:
        return html.Div("No anomalies match the current filters. "
                        "Try widening the date range or unchecking "
                        "the Anomalies-only toggle.",
                        style={"padding": "20px", "fontSize": "15px"})

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
           .sort_values(ascending=False).head(top_n).reset_index(name="n"))
    fig_bar = px.bar(top, x="n", y="CountryName", orientation="h",
                     title=f"Top {top_n} anomaly locations",
                     color="n", color_continuous_scale="Reds")
    fig_bar.update_layout(paper_bgcolor=bg, plot_bgcolor=bg, font=dict(color=fg),
                          template=template,
                          height=max(360, 22 * top_n + 80),
                          yaxis={"autorange": "reversed"})

    table_rows_n = min(50, len(anomalies))
    table_df = anomalies.nlargest(table_rows_n, "SeverityPct")[[
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
        html.H3(f"Highest-severity anomalies (top {table_rows_n})",
                style={"marginTop": "24px"}),
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
