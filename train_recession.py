"""One-time static training for the Recession Risk Signal dashboard.

Reads FRED CSV snapshots from data/, builds monthly features, trains three
baseline classifiers against the NBER recession indicator (USREC), and writes
everything the dashboard needs to recession_output.json.
"""
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

DATA = Path(__file__).parent / "data"
TEST_START = "2005-01-01"  # holds out the 2008-09 and 2020 recessions
THRESHOLD = 0.5
SEED = 42


def load(series_id):
    df = pd.read_csv(DATA / f"{series_id}.csv", na_values=["."])
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")[series_id].dropna()


raw = pd.DataFrame({s: load(s) for s in ["USREC", "T10Y2Y", "UNRATE", "UMCSENT", "INDPRO", "ICSA"]})
raw = raw[raw.index >= "1976-06-01"]  # first month of the yield-spread series
# FRED has no October 2025 unemployment reading (federal shutdown). Fill isolated
# one-month gaps by linear interpolation so rolling features don't break for a year.
indicators = raw.columns.drop("USREC")
filled_gaps = {c: [d.strftime("%Y-%m-%d") for d in raw.index[raw[c].isna()]
                   if raw[c].first_valid_index() < d < raw[c].last_valid_index() and d.year >= 1978] for c in indicators}
raw[indicators] = raw[indicators].interpolate(limit=1, limit_area="inside")

unrate_3m = raw["UNRATE"].rolling(3).mean()
df = pd.DataFrame({
    "spread": raw["T10Y2Y"],
    # Lowest spread in the past 12 months: inversions tend to lead recessions.
    "spread_min_12m": raw["T10Y2Y"].rolling(12).min(),
    # Sahm-style gap: 3-month average unemployment vs. its low over the prior 12 months.
    "unrate_gap": unrate_3m - unrate_3m.rolling(12).min(),
    "sentiment": raw["UMCSENT"],
    "indpro_yoy": raw["INDPRO"].pct_change(12, fill_method=None) * 100,
    "claims_yoy": raw["ICSA"].pct_change(12, fill_method=None) * 100,
    "usrec": raw["USREC"],
})

FEATURES = ["spread", "spread_min_12m", "unrate_gap", "sentiment", "indpro_yoy", "claims_yoy"]
FEATURE_LABELS = {
    "spread": "10Y–2Y yield spread",
    "spread_min_12m": "Lowest spread, past 12 months",
    "unrate_gap": "Unemployment rise vs. 12-month low",
    "sentiment": "Consumer sentiment",
    "indpro_yoy": "Industrial production, YoY",
    "claims_yoy": "Initial claims, YoY",
}

# Sentiment is only monthly from 1978; earlier months are sparse, so start there.
df = df[df.index >= "1978-01-01"]
labelled = df.dropna(subset=FEATURES + ["usrec"])
latest_row = df.dropna(subset=FEATURES).iloc[-1]
train = labelled[labelled.index < TEST_START]
test = labelled[labelled.index >= TEST_START]

MODELS = {
    "Logistic Regression": lambda: make_pipeline(
        StandardScaler(), LogisticRegression(class_weight="balanced", C=0.5, max_iter=2000)),
    "Random Forest": lambda: RandomForestClassifier(
        n_estimators=400, max_depth=4, min_samples_leaf=5, class_weight="balanced", random_state=SEED),
    "k-Nearest Neighbors": lambda: make_pipeline(
        StandardScaler(), KNeighborsClassifier(n_neighbors=15, weights="distance")),
}


def importance(model):
    est = model[-1] if hasattr(model, "steps") else model
    if hasattr(est, "coef_"):
        raw_imp = np.abs(est.coef_[0])
    elif hasattr(est, "feature_importances_"):
        raw_imp = est.feature_importances_
    else:
        return None  # kNN has no native feature importance
    raw_imp = raw_imp / raw_imp.sum()
    return {FEATURE_LABELS[f]: round(float(v), 4) for f, v in zip(FEATURES, raw_imp)}


results = []
for name, factory in MODELS.items():
    m = factory().fit(train[FEATURES], train["usrec"])
    p_train = m.predict_proba(train[FEATURES])[:, 1]
    p_test = m.predict_proba(test[FEATURES])[:, 1]
    y_test = test["usrec"].astype(int)
    yhat = (p_test >= THRESHOLD).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, yhat, labels=[0, 1]).ravel()

    # Current reading: refit on all labelled history, score the latest month.
    full = factory().fit(labelled[FEATURES], labelled["usrec"])
    current = float(full.predict_proba(latest_row[FEATURES].to_frame().T)[0, 1])

    results.append({
        "name": name,
        "metrics": {
            "accuracy": round(accuracy_score(y_test, yhat), 4),
            "precision": round(precision_score(y_test, yhat, zero_division=0), 4),
            "recall": round(recall_score(y_test, yhat, zero_division=0), 4),
            "f1": round(f1_score(y_test, yhat, zero_division=0), 4),
            "roc_auc": round(roc_auc_score(y_test, p_test), 4),
            "train_accuracy": round(accuracy_score(train["usrec"], (p_train >= THRESHOLD).astype(int)), 4),
        },
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "current": round(current, 4),
        "importance": importance(full),
        "probabilities": [round(float(v), 4) for v in np.concatenate([p_train, p_test])],
    })

# Baseline: always predict "no recession".
y_test = test["usrec"].astype(int)
baseline = {"name": "Always 'no recession'", "accuracy": round(float((y_test == 0).mean()), 4),
            "precision": 0.0, "recall": 0.0, "f1": 0.0}


def card(series, n=13, dp=3):
    s = series.dropna()
    return {"date": s.index[-1].strftime("%Y-%m-%d"), "value": round(float(s.iloc[-1]), dp),
            "history": [round(float(v), dp) for v in s.iloc[-n:]]}


def periods(flags):
    out, start = [], None
    for d, v in flags.items():
        if v == 1 and start is None:
            start = d
        if v != 1 and start is not None:
            out.append([start.strftime("%Y-%m-%d"), prev.strftime("%Y-%m-%d")])
            start = None
        prev = d
    if start is not None:
        out.append([start.strftime("%Y-%m-%d"), prev.strftime("%Y-%m-%d")])
    return out


out = {
    "build_date": date.today().isoformat(),
    "cards": {
        "T10Y2Y": card(raw["T10Y2Y"]),
        "UNRATE": card(raw["UNRATE"]),
        "UMCSENT": card(raw["UMCSENT"]),
        "INDPRO_YOY": card(df["indpro_yoy"]),
        "ICSA": card(raw["ICSA"], dp=0),
        "USREC": card(raw["USREC"], dp=0),
    },
    "features": [FEATURE_LABELS[f] for f in FEATURES],
    "latest_features": {FEATURE_LABELS[f]: round(float(latest_row[f]), 3) for f in FEATURES},
    "filled_gaps": {k: v for k, v in filled_gaps.items() if v},
    "typical": {FEATURE_LABELS[f]: {
        "expansion": round(float(labelled.loc[labelled["usrec"] == 0, f].median()), 3),
        "recession": round(float(labelled.loc[labelled["usrec"] == 1, f].median()), 3)} for f in FEATURES},
    "current_month": latest_row.name.strftime("%Y-%m-%d"),
    "threshold": THRESHOLD,
    "split": {
        "train_range": [train.index[0].strftime("%Y-%m-%d"), train.index[-1].strftime("%Y-%m-%d")],
        "test_range": [test.index[0].strftime("%Y-%m-%d"), test.index[-1].strftime("%Y-%m-%d")],
        "n_train": len(train), "n_test": len(test),
        "train_recession_months": int(train["usrec"].sum()),
        "test_recession_months": int(test["usrec"].sum()),
    },
    "dates": [d.strftime("%Y-%m-%d") for d in labelled.index],
    "recessions": periods(labelled["usrec"]),
    "models": results,
    "baseline": baseline,
}
(Path(__file__).parent / "recession_output.json").write_text(json.dumps(out, indent=1))

print(f"train {out['split']}", "filled", out["filled_gaps"])
print(f"current month {out['current_month']}", out["latest_features"])
for r in results:
    print(r["name"], r["metrics"], r["confusion"], "current", r["current"])
print(baseline)
