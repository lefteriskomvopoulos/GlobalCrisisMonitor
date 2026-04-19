"""Static matplotlib/seaborn reports for the GDELT analysis.

Saves PNGs into reports/ that the dashboard embeds and the write-up can
reference. Covers: country severity leaderboard, tone distribution by
QuadClass, global heatmap, event-volume time series, anomaly breakdown.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from config import QUAD_CLASS_LABELS, REPORTS_DIR

sns.set_theme(style="whitegrid", palette="rocket")


def _save(fig, name: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / name
    fig.savefig(path, bbox_inches="tight", dpi=130)
    plt.close(fig)
    print(f"[report] wrote {path.name}")
    return path


def country_severity_bar(df: pd.DataFrame, top_n: int = 20) -> Path:
    grouped = (
        df.dropna(subset=["CountryName"])
          .groupby("CountryName")["SeverityPct"].mean()
          .sort_values(ascending=False).head(top_n).reset_index()
    )
    fig, ax = plt.subplots(figsize=(11, 7))
    sns.barplot(data=grouped, x="SeverityPct", y="CountryName", ax=ax,
                hue="CountryName", legend=False)
    ax.set_title(f"Top {top_n} Locations by Average Event Severity")
    ax.set_xlabel("Average Severity (0-100)")
    ax.set_ylabel("")
    return _save(fig, "country_severity.png")


def tone_by_quadclass(df: pd.DataFrame) -> Path:
    d = df.copy()
    d["QuadLabel"] = d["QuadClass"].map(QUAD_CLASS_LABELS).fillna("Unknown")
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.violinplot(data=d, x="QuadLabel", y="AvgTone", ax=ax, hue="QuadLabel",
                   palette="Set2", legend=False, inner="quartile")
    ax.set_title("Tone Distribution across CAMEO QuadClasses")
    ax.set_xlabel("")
    ax.set_ylabel("GDELT Average Tone")
    ax.axhline(0, linestyle="--", color="black", linewidth=0.8)
    return _save(fig, "tone_by_quadclass.png")


def volume_timeseries(df: pd.DataFrame) -> Path:
    d = df.copy()
    d["Hour"] = pd.to_datetime(d["DateFormatted"]).dt.floor("h")
    series = d.groupby("Hour").agg(
        events=("SeverityPct", "size"),
        avg_sev=("SeverityPct", "mean"),
    ).reset_index()

    fig, ax1 = plt.subplots(figsize=(11, 5))
    ax2 = ax1.twinx()
    ax1.plot(series["Hour"], series["events"], color="#4c72b0",
             label="Events / hour")
    ax2.plot(series["Hour"], series["avg_sev"], color="#dd8452",
             label="Mean severity")
    ax1.set_title("Global Event Volume vs. Mean Severity")
    ax1.set_ylabel("Events", color="#4c72b0")
    ax2.set_ylabel("Severity %", color="#dd8452")
    fig.autofmt_xdate()
    return _save(fig, "volume_timeseries.png")


def anomaly_breakdown(df: pd.DataFrame) -> Path | None:
    if "IsAnomaly" not in df.columns or df["IsAnomaly"].sum() == 0:
        return None
    anomalies = df[df["IsAnomaly"] == 1]
    top = (anomalies.groupby("CountryName").size()
           .sort_values(ascending=False).head(15).reset_index(name="n"))
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=top, x="n", y="CountryName", ax=ax, color="#c44e52")
    ax.set_title("Top Locations by Flagged Anomaly Count")
    ax.set_xlabel("Anomalies Detected")
    ax.set_ylabel("")
    return _save(fig, "anomaly_breakdown.png")


def feature_correlation(df: pd.DataFrame) -> Path:
    cols = ["AvgTone", "GoldsteinScale", "NumSources", "NumArticles",
            "NumMentions", "SeverityPct"]
    avail = [c for c in cols if c in df.columns]
    corr = df[avail].corr()
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm",
                vmin=-1, vmax=1, ax=ax)
    ax.set_title("Feature Correlation Heatmap")
    return _save(fig, "feature_correlation.png")


def generate_all(df: pd.DataFrame) -> list[Path]:
    outputs = [
        country_severity_bar(df),
        tone_by_quadclass(df),
        volume_timeseries(df),
        feature_correlation(df),
    ]
    a = anomaly_breakdown(df)
    if a is not None:
        outputs.append(a)
    return outputs
