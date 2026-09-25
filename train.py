"""One-time static training for the FinTechCo demo dashboard.

Reads FRED CSV snapshots from data/, builds quarterly features, trains three
baseline models to predict next-quarter credit card delinquency (DRCCLACBS),
and writes everything the dashboard needs to model_output.json.
"""
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

DATA = Path(__file__).parent / "data"
TEST_FRACTION = 0.2
SEED = 42


def load(series_id):
    df = pd.read_csv(DATA / f"{series_id}.csv", na_values=["."])
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")[series_id].dropna()


monthly = {s: load(s) for s in ["UNRATE", "CPIAUCSL", "FEDFUNDS", "UMCSENT"]}
delinq = load("DRCCLACBS")

# CPI is an index; the economically meaningful feature is YoY inflation.
monthly["CPI_YOY"] = monthly["CPIAUCSL"].pct_change(12, fill_method=None) * 100

# Quarterly averages of the monthly macro series (quarter-start labels match DRCCLACBS).
q = pd.DataFrame({
    "unrate": monthly["UNRATE"].resample("QS").mean(),
    "cpi_yoy": monthly["CPI_YOY"].resample("QS").mean(),
    "fedfunds": monthly["FEDFUNDS"].resample("QS").mean(),
    "sentiment": monthly["UMCSENT"].resample("QS").mean(),
})
q["unrate_chg_4q"] = q["unrate"].diff(4)
q["fedfunds_chg_4q"] = q["fedfunds"].diff(4)
q["delinq"] = delinq
q["target_next_q"] = q["delinq"].shift(-1)

MACRO_FEATURES = ["unrate", "cpi_yoy", "fedfunds", "sentiment", "unrate_chg_4q", "fedfunds_chg_4q"]
# Current-quarter delinquency is included: delinquency is highly persistent, and
# macro-only models failed badly out of sample (reported as macro_only_test below).
FEATURES = ["delinq"] + MACRO_FEATURES
FEATURE_LABELS = {
    "delinq": "Delinquency rate (current Q)",
    "unrate": "Unemployment rate",
    "cpi_yoy": "CPI inflation (YoY)",
    "fedfunds": "Fed funds rate",
    "sentiment": "Consumer sentiment",
    "unrate_chg_4q": "Unemployment, 4Q change",
    "fedfunds_chg_4q": "Fed funds, 4Q change",
}

q = q[q.index >= delinq.index.min()]
train_rows = q.dropna(subset=FEATURES + ["target_next_q"])
latest_row = q.dropna(subset=FEATURES + ["delinq"]).iloc[-1]

# Chronological split: no shuffling, so the test set is genuinely out-of-sample.
split = int(len(train_rows) * (1 - TEST_FRACTION))
train, test = train_rows.iloc[:split], train_rows.iloc[split:]

MODELS = {
    "Linear Regression": lambda: make_pipeline(StandardScaler(), LinearRegression()),
    "Ridge Regression": lambda: make_pipeline(StandardScaler(), Ridge(alpha=5.0)),
    "Random Forest": lambda: RandomForestRegressor(
        n_estimators=400, max_depth=4, min_samples_leaf=3, random_state=SEED),
}


def importance(model):
    est = model[-1] if hasattr(model, "steps") else model
    raw = np.abs(est.coef_) if hasattr(est, "coef_") else est.feature_importances_
    raw = raw / raw.sum()
    return {FEATURE_LABELS[f]: round(float(v), 4) for f, v in zip(FEATURES, raw)}


results = []
for name, factory in MODELS.items():
    m = factory().fit(train[FEATURES], train["target_next_q"])
    pred_train = m.predict(train[FEATURES])
    pred_test = m.predict(test[FEATURES])

    # Final forecast: refit on all labelled history, predict from the latest quarter.
    full = factory().fit(train_rows[FEATURES], train_rows["target_next_q"])
    forecast = float(full.predict(latest_row[FEATURES].to_frame().T)[0])

    results.append({
        "name": name,
        "metrics": {
            "train_r2": round(r2_score(train["target_next_q"], pred_train), 4),
            "test_r2": round(r2_score(test["target_next_q"], pred_test), 4),
            "train_mae": round(mean_absolute_error(train["target_next_q"], pred_train), 4),
            "test_mae": round(mean_absolute_error(test["target_next_q"], pred_test), 4),
        },
        "forecast": round(forecast, 3),
        "importance": importance(full),
        # Predictions are aligned to the quarter being predicted (t+1).
        "predictions": [round(float(v), 3) for v in np.concatenate([pred_train, pred_test])],
    })

def macro_only_test(factory):
    m = factory().fit(train[MACRO_FEATURES], train["target_next_q"])
    p = m.predict(test[MACRO_FEATURES])
    return {"test_r2": round(r2_score(test["target_next_q"], p), 4),
            "test_mae": round(mean_absolute_error(test["target_next_q"], p), 4)}


for r in results:
    r["macro_only_test"] = macro_only_test(MODELS[r["name"]])

# Benchmark: "next quarter equals this quarter".
naive_test = test["delinq"]
benchmark = {
    "name": "Naive persistence",
    "test_r2": round(r2_score(test["target_next_q"], naive_test), 4),
    "test_mae": round(mean_absolute_error(test["target_next_q"], naive_test), 4),
    "forecast": round(float(latest_row["delinq"]), 3),
}

target_dates = [(d + pd.offsets.QuarterBegin(1, startingMonth=1)).strftime("%Y-%m-%d")
                for d in train_rows.index]
forecast_quarter = (latest_row.name + pd.offsets.QuarterBegin(1, startingMonth=1))


def latest(series, n=13):
    s = series.dropna()
    return {"date": s.index[-1].strftime("%Y-%m-%d"), "value": round(float(s.iloc[-1]), 3),
            "history": [round(float(v), 3) for v in s.iloc[-n:]]}


out = {
    "build_date": date.today().isoformat(),
    "cards": {
        "UNRATE": latest(monthly["UNRATE"]),
        "CPI_YOY": latest(monthly["CPI_YOY"]),
        "FEDFUNDS": latest(monthly["FEDFUNDS"]),
        "UMCSENT": latest(monthly["UMCSENT"]),
        "DRCCLACBS": latest(delinq, n=12),
    },
    "features": [FEATURE_LABELS[f] for f in FEATURES],
    "split": {
        "n_train": len(train), "n_test": len(test),
        "test_start": target_dates[split],
        "train_range": [target_dates[0], target_dates[split - 1]],
        "test_range": [target_dates[split], target_dates[-1]],
    },
    "forecast_quarter": f"{forecast_quarter.year} Q{forecast_quarter.quarter}",
    "forecast_input_quarter": f"{latest_row.name.year} Q{latest_row.name.quarter}",
    "actual": {"dates": target_dates,
               "values": [round(float(v), 3) for v in train_rows["target_next_q"]]},
    "models": results,
    "benchmark": benchmark,
}
(Path(__file__).parent / "model_output.json").write_text(json.dumps(out, indent=1))

print(f"rows={len(train_rows)} train={len(train)} test={len(test)} test_start={target_dates[split]}")
print(f"forecast {out['forecast_quarter']} from {out['forecast_input_quarter']}, latest actual {latest_row['delinq']}")
for r in results:
    print(r["name"], r["metrics"], "forecast", r["forecast"], "macro-only", r["macro_only_test"])
print(benchmark)
