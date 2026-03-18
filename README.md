# AI-Based Traffic Prediction System — Bhopal
### JUET Guna | Mentor: Dr. Partha Sarathy Banerjee
### Students: Shraddha Verma · Tanu Kushwah · Mansi Dhakad

---

## Project Structure

```
trafficai/
│
├── backend/
│   ├── app.py               ← Flask API server (main backend)
│   ├── model.py             ← ML training: data gen, cleaning, RF, LR
│   └── routes.py            ← Route recommendation + GPS deviation logic
│
├── frontend/
│   ├── templates/
│   │   └── index.html       ← Main HTML shell (served by Flask)
│   └── static/
│       ├── css/
│       │   └── style.css    ← All styles
│       └── js/
│           ├── dashboard.js ← Charts & dashboard tab
│           ├── predictor.js ← Prediction form logic
│           ├── map.js       ← Leaflet live map + GPS simulation
│           └── app.js       ← Tab switching & shared utilities
│
├── data/
│   └── (bhopal_traffic_dataset.csv generated on first run)
│
├── models/
│   └── (traffic_model.pkl  generated on first run)
│
├── requirements.txt
├── README.md
└── run.py                   ← Entry point — just run this!
```

---

## Setup & Run (VS Code)

### Step 1 — Install Python packages
Open VS Code terminal and run:
```bash
pip install -r requirements.txt
```

### Step 2 — Train the model (first time only, ~60 seconds)
```bash
python backend/model.py
```
This generates:
- `data/bhopal_traffic_dataset.csv`  (105,120 rows)
- `models/traffic_model.pkl`         (trained Random Forest)

### Step 3 — Start the server
```bash
python run.py
```

### Step 4 — Open in browser
Visit: **http://localhost:5000**

---

## API Endpoints

| Method | Endpoint            | Description                        |
|--------|---------------------|------------------------------------|
| GET    | `/`                 | Serve frontend                     |
| GET    | `/api/status`       | Server health check                |
| POST   | `/api/predict`      | Predict traffic volume (RF model)  |
| POST   | `/api/forecast`     | 24-hour forecast for a junction    |
| GET    | `/api/junctions`    | All junction info + current volumes|
| POST   | `/api/routes`       | Route recommendations (3 routes)   |
| POST   | `/api/deviation`    | GPS deviation check (Haversine)    |
| GET    | `/api/metrics`      | Model performance metrics          |
| GET    | `/api/eda`          | EDA summary statistics             |

---

## Technologies Used

| Layer     | Technology              |
|-----------|-------------------------|
| Backend   | Python 3.10+, Flask 3.0 |
| ML Models | scikit-learn (LR + RF)  |
| Data      | pandas, numpy           |
| Frontend  | HTML5, CSS3, JavaScript |
| Charts    | Chart.js 4.4            |
| Map       | Leaflet.js 1.9          |
| Fonts     | Google Fonts (Outfit)   |
