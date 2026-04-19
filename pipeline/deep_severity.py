"""PyTorch feed-forward regressor predicting event severity.

Severity is derived from GDELT features: a combination of negative tone,
Goldstein conflict score, and media volume. The network learns the
non-linear interaction between those features and is evaluated with
MAE/RMSE against a held-out test set, per the proposal's evaluation plan.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from config import FEATURE_COLS, MODELS_DIR
from pipeline.mlops import log_run

WEIGHTS = MODELS_DIR / "severity_net.pt"
SCALER = MODELS_DIR / "severity_scaler.pkl"
META = MODELS_DIR / "severity_meta.json"


def compute_severity(df: pd.DataFrame) -> pd.Series:
    """Engineered severity score in [0, 100].

    Combines absolute tone, inverted Goldstein scale (more negative = more
    conflict), and a log media-volume factor. Scaled per-batch to [0, 100].
    """
    tone = df["AvgTone"].abs().fillna(0)
    gold = (-df["GoldsteinScale"]).clip(lower=0).fillna(0)
    vol = np.log1p(df[["NumSources", "NumArticles", "NumMentions"]].fillna(0).sum(axis=1))
    raw = 0.5 * tone + 0.3 * gold + 0.2 * vol
    rng = raw.max() - raw.min()
    if rng < 1e-6:
        return pd.Series(np.zeros(len(df)), index=df.index)
    return ((raw - raw.min()) / rng * 100).round(2)


class SeverityNet(nn.Module):
    def __init__(self, n_features: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_features, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


def train(pdf: pd.DataFrame, epochs: int = 40, batch_size: int = 512,
          lr: float = 1e-3) -> dict:
    pdf = pdf.dropna(subset=FEATURE_COLS).copy()
    pdf["severity"] = compute_severity(pdf)
    X = pdf[FEATURE_COLS].to_numpy(dtype=np.float32)
    y = pdf["severity"].to_numpy(dtype=np.float32)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    scaler = StandardScaler().fit(X_train)
    X_train = scaler.transform(X_train).astype(np.float32)
    X_test = scaler.transform(X_test).astype(np.float32)

    device = torch.device("cuda" if torch.cuda.is_available()
                          else "mps" if torch.backends.mps.is_available()
                          else "cpu")
    model = SeverityNet(X_train.shape[1]).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    X_train_t = torch.from_numpy(X_train).to(device)
    y_train_t = torch.from_numpy(y_train).to(device)
    X_test_t = torch.from_numpy(X_test).to(device)
    y_test_t = torch.from_numpy(y_test).to(device)

    n = X_train_t.shape[0]
    history: list[dict] = []
    for epoch in range(epochs):
        model.train()
        perm = torch.randperm(n, device=device)
        total = 0.0
        for start in range(0, n, batch_size):
            idx = perm[start:start + batch_size]
            opt.zero_grad()
            pred = model(X_train_t[idx])
            loss = loss_fn(pred, y_train_t[idx])
            loss.backward()
            opt.step()
            total += loss.item() * idx.shape[0]
        train_loss = total / n

        model.eval()
        with torch.no_grad():
            val_pred = model(X_test_t).cpu().numpy()
        mae = float(mean_absolute_error(y_test, val_pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, val_pred)))
        history.append({"epoch": epoch, "train_loss": train_loss, "mae": mae, "rmse": rmse})
        if epoch % 10 == 0 or epoch == epochs - 1:
            print(f"[torch] epoch {epoch:02d} train_loss={train_loss:.3f} "
                  f"mae={mae:.3f} rmse={rmse:.3f}")

    # Save artifacts
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), WEIGHTS)
    joblib.dump(scaler, SCALER)
    meta = {
        "features": FEATURE_COLS,
        "epochs": epochs,
        "batch_size": batch_size,
        "lr": lr,
        "final_mae": history[-1]["mae"],
        "final_rmse": history[-1]["rmse"],
        "n_train": int(X_train.shape[0]),
        "n_test": int(X_test.shape[0]),
        "device": str(device),
    }
    META.write_text(json.dumps(meta, indent=2))
    log_run(
        model_name="pytorch_severity_net",
        params={k: meta[k] for k in ("epochs", "batch_size", "lr", "features", "device")},
        metrics={"mae": meta["final_mae"], "rmse": meta["final_rmse"]},
        stage="production",
    )
    return {"history": history, **meta}


def predict(df: pd.DataFrame) -> np.ndarray:
    if not WEIGHTS.exists():
        raise RuntimeError("Severity model not trained yet. Run the pipeline first.")
    scaler: StandardScaler = joblib.load(SCALER)
    X = scaler.transform(df[FEATURE_COLS].fillna(0).to_numpy(dtype=np.float32)).astype(np.float32)
    device = torch.device("cpu")
    model = SeverityNet(X.shape[1]).to(device)
    model.load_state_dict(torch.load(WEIGHTS, map_location=device))
    model.eval()
    with torch.no_grad():
        return model(torch.from_numpy(X)).cpu().numpy()
