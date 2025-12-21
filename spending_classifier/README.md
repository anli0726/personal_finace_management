# Spending Classifier Summarizer

This folder holds a lightweight statement summarizer plus a static dashboard.

## Generate dashboard data
```bash
python3 spending_classifier/summarizer.py
```

This scans `spending_classifier/statements/*.CSV` and writes
`spending_classifier/dashboard/data.json`.

## Open the dashboard
Open `spending_classifier/dashboard/index.html` in a browser.

## Options
```bash
python3 spending_classifier/summarizer.py --threshold 0.8 --out spending_classifier/dashboard/data.json
```
