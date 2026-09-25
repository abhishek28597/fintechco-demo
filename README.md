# FinTechCo Analytics Demo

Two demo analytics dashboards for **FinTechCo**, a hypothetical fintech that offers digital payments and traditional banking:

1. **Credit Risk Monitor** (landing page, regression): forecasts next quarter's U.S. credit card delinquency rate.
2. **Recession Risk Signal** (classification): estimates how closely current conditions resemble months that NBER later dated as recessions.

Switch between them with the tabs in the top bar. You can also link straight to the second dashboard with `index.html#recession`.

> **Demo product.** FinTechCo is not a real company. The data is a static snapshot from [FRED](https://fred.stlouisfed.org/) taken on 2026-09-26, and nothing updates live. This isn't investment or credit advice.

Open `index.html` in any browser. It's a single self-contained page: the data and model results are embedded, and it makes no API calls when it loads.

# Dashboard 1: Credit Risk Monitor

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

# Dashboard 2: Recession Risk Signal

> **Early-warning signal, not an official recession call.** The target, `USREC`, is NBER's recession indicator. The dates are set by committee judgment across many indicators and announced 6 to 18 months after a recession starts. A high reading means current conditions resemble past recession months. It does not mean a recession has started or will start.

## What the dashboard shows

- **Latest leading indicators:** the yield spread, unemployment, consumer sentiment, industrial production, jobless claims, and the latest official NBER status.
- **Current risk by model:** each model's probability for the latest month, with a Low (under 20%), Elevated (20–50%) or High (50% and up) band. Each model also shows accuracy, precision, recall, F1, ROC AUC and a confusion matrix.
- **Probability timeline:** each model's recession probability since 1978, with NBER recessions shaded.
- **Today vs. history:** each input next to its typical expansion and recession values, plus each model's feature influence.

## Data

| Series | Description | Monthly treatment |
|---|---|---|
| `USREC` | NBER recession indicator, 1 = recession month (**target**) | as published |
| `T10Y2Y` | 10-year minus 2-year Treasury spread | daily, averaged to months |
| `UNRATE` | Unemployment rate | as published |
| `UMCSENT` | University of Michigan consumer sentiment | as published |
| `INDPRO` | Industrial production index | as published |
| `ICSA` | Initial unemployment claims | weekly, averaged to months |

The window starts in January 1978, when consumer sentiment becomes monthly. FRED has no October 2025 unemployment value because of the federal shutdown, so that one month is filled by linear interpolation.

## Features

| Feature | Rationale |
|---|---|
| 10Y–2Y spread | Shape of the yield curve |
| Lowest spread over the past 12 months | Inversions tend to lead recessions |
| Unemployment rise vs. 12-month low (3-month average) | Similar to the Sahm rule |
| Consumer sentiment | Household confidence |
| Industrial production, YoY % | Real activity |
| Initial claims, YoY % | Early labor-market stress |

## Models and evaluation

- Logistic regression (balanced class weights, standardized features)
- Random forest (400 trees, depth 4, balanced class weights)
- k-nearest neighbors (k = 15, distance-weighted, standardized features)

The split is chronological. The models train on 1978–2004 (324 months, 38 in recession) and are tested on Jan 2005 – Aug 2026 (260 months, 20 in recession), which holds out the 2008–09 and 2020 recessions. A month is classified as a recession month when its probability is 50% or higher. The current readings come from each model refit on all labelled history.

| Model | Accuracy | Precision | Recall | F1 | Aug 2026 risk |
|---|---|---|---|---|---|
| Logistic regression | 86% | 35% | 95% | 0.51 | 39% (Elevated) |
| Random forest | 93% | 53% | 85% | 0.65 | 1% (Low) |
| k-nearest neighbors | 93% | 53% | 85% | 0.65 | 0% (Low) |
| *Always "no recession"* | *92%* | *n/a* | *0%* | *0* | n/a |

**How to read these results:** accuracy alone is misleading, because always predicting "no recession" scores 92% and catches nothing. Recall and precision are more informative. Most false alarms fall in 2022–25, when the yield curve was deeply inverted and sentiment hit record lows, but no recession followed. The logistic model's current elevated reading comes mostly from consumer sentiment, which at 51.7 is below its typical recession-month level.

## Project structure

```
.
├── index.html              # Built page with both dashboards (self-contained)
├── template.html           # Page source; build.py injects both data files here
├── train.py                # Credit Risk Monitor training -> model_output.json
├── train_recession.py      # Recession Risk Signal training -> recession_output.json
├── build.py                # Inlines both JSON files into template.html -> index.html
├── model_output.json       # Baked delinquency results
├── recession_output.json   # Baked recession results
├── data/               # FRED CSV snapshots
└── requirements.txt
```

## Rebuilding

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python train.py             # delinquency models -> model_output.json
.venv/bin/python train_recession.py   # recession models -> recession_output.json
.venv/bin/python build.py             # regenerate index.html
```

To refresh the data, replace the CSVs in `data/` with new downloads from FRED that keep the same file names and `date,<SERIES_ID>` columns. Then run all three scripts again.
