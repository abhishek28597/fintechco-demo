# FinTechCo Credit Risk Monitor

A demo financial analytics dashboard for **FinTechCo**, a hypothetical fintech that offers digital payments and traditional banking. It forecasts next quarter's U.S. credit card delinquency rate from macroeconomic indicators and compares three baseline machine-learning models.

> **Demo product.** FinTechCo is not a real company. The data is a static snapshot from [FRED](https://fred.stlouisfed.org/) taken on 2026-09-26, and nothing updates live. This isn't investment or credit advice.

Open `index.html` in any browser. It's a single self-contained page: the data and model results are embedded, and it makes no API calls when it loads.

## What the dashboard shows

- **Latest indicators:** summary cards for unemployment, CPI inflation, the fed funds rate, consumer sentiment and the card delinquency rate, each with a trend sparkline.
- **Actual vs. predicted:** historical delinquency (1991–today) plotted against each model's predictions. The held-out test period is shaded, and each model's next-quarter forecast is marked.
- **Model comparison:** R² and MAE for each model on the train and test periods, next-quarter forecasts, and a no-change benchmark.
- **Feature influence:** which inputs each model relies on.

## Data

All series come from FRED (Federal Reserve Bank of St. Louis). The raw CSVs are in `data/`.

| Series | Description | Frequency | Starts |
|---|---|---|---|
| `DRCCLACBS` | Delinquency rate on credit card loans, all commercial banks (SA, %) | Quarterly | 1991 Q1 |
| `UNRATE` | Unemployment rate (SA, %) | Monthly | 1948 |
| `CPIAUCSL` | Consumer Price Index, all urban consumers (SA, index) | Monthly | 1947 |
| `FEDFUNDS` | Effective federal funds rate (%) | Monthly | 1954 |
| `UMCSENT` | University of Michigan consumer sentiment (index) | Monthly | 1952 |

Monthly series are averaged to quarters, and CPI is converted to year-over-year inflation. The modeling window starts in 1991, where the delinquency series begins. FRED has no October 2025 value for CPI or unemployment, so Q4 2025 averages the two available months.

## The model

**Target:** the credit card delinquency rate in quarter *t + 1*.

**Features** (all measured at quarter *t*):

| Feature | Why it's included |
|---|---|
| Delinquency rate this quarter | Delinquency is highly persistent |
| Unemployment rate | Job loss is the main driver of missed payments |
| CPI inflation (YoY) | Squeezes household budgets |
| Fed funds rate | Drives card APRs and payment burden |
| Consumer sentiment | Household confidence |
| 4-quarter change in unemployment | Direction of the labor market |
| 4-quarter change in fed funds | Whether policy is tightening or easing |

**Models:**
- Linear regression on standardized features
- Ridge regression (α = 5) on standardized features
- Random forest (400 trees, max depth 4, at least 3 samples per leaf)

**Evaluation:** the split is chronological with no shuffling. The first 80% of quarters (1991 Q2 – 2019 Q1, 112 quarters) are used for training, and the last 20% (2019 Q2 – 2026 Q2, 29 quarters) are held out for testing. The reported metrics are on the test period. Each model's final forecast comes from a refit on all of history.

### Results

| Model | Test R² | Test MAE (pp) | 2026 Q3 forecast |
|---|---|---|---|
| Linear regression | 0.27 | 0.40 | 3.02% |
| Ridge regression | −0.75 | 0.57 | 3.05% |
| Random forest | **0.73** | **0.20** | 2.86% |
| *No-change benchmark* | *0.91* | *0.12* | *2.85%* |

### How to read these results

- **No-change benchmark:** the simplest possible forecast, which assumes next quarter equals this quarter. Delinquency moves slowly, so this is hard to beat, and a model is only useful if it does better. None of these baseline models beat it.
- **The COVID break:** in 2020 unemployment jumped to about 14.7%, but card delinquency fell to record lows. Stimulus checks, expanded unemployment benefits and payment forbearance let households pay down their cards. Models trained on 1991–2019 learned that rising unemployment means rising delinquency, so they predicted a spike that never happened.
- **Macro-only models:** trained without the current delinquency rate, all three models score a test R² between −13 and −20, which is worse than predicting the test-period average. These scores appear in the dashboard for transparency.

These are baselines for a demo, not production credit-risk models.

## Project structure

```
.
├── index.html          # Built dashboard (self-contained, open in a browser)
├── template.html       # Dashboard source; build.py injects the data here
├── train.py            # One-time training: FRED CSVs -> model_output.json
├── build.py            # Inlines model_output.json into template.html -> index.html
├── model_output.json   # Baked metrics, predictions and forecasts
├── data/               # FRED CSV snapshots
└── requirements.txt
```

## Rebuilding

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python train.py    # retrain the models, writes model_output.json
.venv/bin/python build.py    # regenerate index.html
```

To refresh the data, replace the CSVs in `data/` with new downloads from FRED that keep the same file names and `date,<SERIES_ID>` columns. Then run both scripts again.
