# DefectDesk — Defect Management Application

A local Flask + SQLite web application for the Defect Management assignment.

## Assignment coverage

1. **Defect prevention:** configurable pre-release checklist for reviews, static analysis, unit tests and release checks.
2. **Defect discovery:** defect capture form records discovery date, component, description and reproduction steps.
3. **Recording and reporting:** persistent SQLite register, search/filter, activity history and summary reports.
4. **Classification:** severity, priority and component fields.
5. **Resolution:** enforced lifecycle transitions: `NEW → ASSIGNED → RESOLVED → VERIFIED → CLOSED`; `RESOLVED → REOPENED → ASSIGNED` is also supported. Invalid transitions are rejected.
6. **Prediction:** transparent baseline estimate using the average number of defects discovered per day over the last seven days. It is a simple trend estimate, not a trained ML model.

## Requirements

- Python 3.9+
- Flask

## Run on Ubuntu / Linux

```bash
cd defect_management_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` in your browser. The SQLite database `defect_tracker.db` is created automatically and remains in this folder.

## Run on Windows

```powershell
cd defect_management_app
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py app.py
```

Open `http://127.0.0.1:5000`.

## Notes

- This is intended as an educational local assignment project, not a production issue tracker.
- For a classroom demo, create a defect, assign it, resolve it, reopen it, reassign it, resolve it again, verify it, and close it to demonstrate the lifecycle.
- The prediction is based on a seven-day average. More historical data and a defined prediction target would be needed for a more advanced forecasting model.
- Before deployment beyond localhost, replace the demo secret key, disable Flask debug mode, add authentication/authorization, and run submitted code (if added later) in an isolated environment.
