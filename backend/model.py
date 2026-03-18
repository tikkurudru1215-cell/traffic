"""
================================================================
  backend/model.py
  ML Pipeline: Data Generation → Cleaning → Feature Eng →
               Training (LR + RF) → Evaluation → Save
  Run standalone: python backend/model.py
================================================================
"""
import os, sys, math, pickle, json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from sklearn.model_selection import train_test_split
from sklearn.linear_model    import LinearRegression
from sklearn.ensemble        import RandomForestRegressor
from sklearn.preprocessing   import LabelEncoder
from sklearn.metrics         import mean_absolute_error, mean_squared_error, r2_score

import warnings
warnings.filterwarnings("ignore")
np.random.seed(42)

# ── Paths ────────────────────────────────────────────────────
ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(ROOT, "data")
MODEL_DIR  = os.path.join(ROOT, "models")
CSV_PATH   = os.path.join(DATA_DIR,  "bhopal_traffic_dataset.csv")
MODEL_PATH = os.path.join(MODEL_DIR, "traffic_model.pkl")
os.makedirs(DATA_DIR,  exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# ── Junction definitions ──────────────────────────────────────
JUNCTIONS = {
    "J01_DBMall":    {"lat": 23.2332, "lon": 77.4272, "mult": 1.25, "name": "DB Mall Chowk"},
    "J02_MPNagar":   {"lat": 23.2299, "lon": 77.4382, "mult": 1.15, "name": "MP Nagar Square"},
    "J03_NewMarket": {"lat": 23.2354, "lon": 77.4001, "mult": 1.10, "name": "New Market Chowk"},
    "J04_Karond":    {"lat": 23.2691, "lon": 77.4098, "mult": 0.90, "name": "Karond Square"},
    "J05_Ayodhya":   {"lat": 23.2019, "lon": 77.4465, "mult": 0.85, "name": "Ayodhya Bypass"},
    "J06_Bairagarh": {"lat": 23.2594, "lon": 77.3672, "mult": 0.80, "name": "Bairagarh Chowk"},
}

WEATHER_OPTIONS = ["Clear", "Clouds", "Rain", "Fog", "Thunderstorm", "Drizzle", "Haze"]
WEATHER_PROBS   = [0.45, 0.25, 0.10, 0.07, 0.04, 0.05, 0.04]
WEATHER_IMPACT  = {
    "Clear":1.00,"Clouds":0.97,"Drizzle":0.91,
    "Haze":0.94,"Rain":0.82,"Fog":0.72,"Thunderstorm":0.60
}
HOLIDAYS = {(1,26),(8,15),(10,2),(11,1),(12,25),(1,1),(3,25),(4,14),(10,24),(11,14)}

FEATURES = [
    "hour","day_of_week","month","is_weekend","is_holiday","is_peak_hour",
    "temperature_c","humidity_pct","rainfall_mm","visibility_km",
    "junction_enc","weather_enc",
    "hour_sin","hour_cos","month_sin","month_cos","dow_sin","dow_cos",
    "peak_weekday","holiday_weekend","rain_peak",
    "lag_1h","lag_24h","lag_168h","rolling_3h","rolling_6h",
]
TARGET = "traffic_volume"


# ════════════════════════════════════════════════════════════
#  STEP 1 — GENERATE DATASET
# ════════════════════════════════════════════════════════════
def generate_dataset():
    print("[1/7] Generating Bhopal traffic dataset (105,120 rows)...")
    rows = []
    start = datetime(2023, 1, 1)

    for day_off in range(730):
        date       = start + timedelta(days=day_off)
        dow        = date.weekday()
        month      = date.month
        is_weekend = int(dow >= 5)
        is_holiday = int((month, date.day) in HOLIDAYS)

        for hour in range(24):
            weather   = np.random.choice(WEATHER_OPTIONS, p=WEATHER_PROBS)
            temp_c    = 20 + 8*math.sin((month-3)*math.pi/6) + np.random.normal(0, 2.5)
            rainfall  = np.random.exponential(4) if weather in ["Rain","Thunderstorm","Drizzle"] else 0.0
            humidity  = np.clip(40 + 30*math.sin((month-4)*math.pi/6) + np.random.normal(0,8), 10, 100)
            is_peak   = int(hour in [7,8,9,17,18,19])
            vis       = {"Clear":10,"Clouds":8,"Drizzle":6,"Haze":5,"Rain":4,"Fog":1,"Thunderstorm":3}[weather]

            if is_holiday:
                base = 400*max(0, math.sin((hour-9)*math.pi/8)) + 100
            elif is_weekend:
                base = 550*max(0, math.sin((hour-10)*math.pi/10)) + 80
            else:
                base = (600*math.exp(-((hour-8)**2)/4)
                      + 750*math.exp(-((hour-18)**2)/3)
                      + 150*math.exp(-((hour-13)**2)/5) + 80)

            sf = 1.0 + 0.08*math.sin((month-6)*math.pi/6)
            wf = WEATHER_IMPACT[weather]
            tf = 0.95 if (temp_c < 8 or temp_c > 42) else 1.0

            for jid, jd in JUNCTIONS.items():
                vol = int(base * sf * wf * tf * jd["mult"] * np.random.uniform(0.91,1.09))
                vol = max(0, vol)
                lvl = ("LOW" if vol < 400 else "MODERATE" if vol < 900
                        else "HIGH" if vol < 1600 else "VERY HIGH")
                rows.append({
                    "datetime":      date.strftime("%Y-%m-%d") + f" {hour:02d}:00:00",
                    "date":          date.strftime("%Y-%m-%d"),
                    "hour":          hour,
                    "day_of_week":   dow,
                    "day_name":      date.strftime("%A"),
                    "month":         month,
                    "month_name":    date.strftime("%B"),
                    "year":          date.year,
                    "week_of_year":  date.isocalendar()[1],
                    "is_weekend":    is_weekend,
                    "is_holiday":    is_holiday,
                    "is_peak_hour":  is_peak,
                    "junction_id":   jid,
                    "junction_name": jd["name"],
                    "latitude":      jd["lat"],
                    "longitude":     jd["lon"],
                    "weather":       weather,
                    "temperature_c": round(temp_c, 1),
                    "humidity_pct":  round(humidity, 1),
                    "rainfall_mm":   round(rainfall, 2),
                    "visibility_km": vis,
                    "traffic_volume": vol,
                    "traffic_level": lvl,
                })

    df = pd.DataFrame(rows)
    df.to_csv(CSV_PATH, index=False)
    print(f"    ✓ Saved {len(df):,} rows → data/bhopal_traffic_dataset.csv")
    return df


# ════════════════════════════════════════════════════════════
#  STEP 2 — CLEAN
# ════════════════════════════════════════════════════════════
def clean_data(df):
    print("[2/7] Cleaning data...")
    # Inject + repair nulls
    idx = df.sample(frac=0.01, random_state=7).index
    n   = len(idx)
    df.loc[idx[:n//3],    "temperature_c"] = np.nan
    df.loc[idx[n//3:2*n//3], "humidity_pct"] = np.nan
    df.loc[idx[2*n//3:],  "rainfall_mm"]   = np.nan
    df["temperature_c"] = df.groupby("junction_id")["temperature_c"].transform(lambda x: x.fillna(x.median()))
    df["humidity_pct"]  = df.groupby("junction_id")["humidity_pct"].transform( lambda x: x.fillna(x.median()))
    df["rainfall_mm"]   = df["rainfall_mm"].fillna(0.0)
    # Outlier removal
    q1 = df["traffic_volume"].quantile(0.01)
    q3 = df["traffic_volume"].quantile(0.99)
    before = len(df)
    df = df[(df["traffic_volume"] >= q1) & (df["traffic_volume"] <= q3)].copy()
    df = df.drop_duplicates()
    df["datetime"] = pd.to_datetime(df["datetime"])
    print(f"    ✓ Clean: {len(df):,} rows  (removed {before-len(df)} outliers)")
    return df


# ════════════════════════════════════════════════════════════
#  STEP 3 — FEATURE ENGINEERING
# ════════════════════════════════════════════════════════════
def feature_engineering(df):
    print("[3/7] Engineering features...")
    le_junc = LabelEncoder(); df["junction_enc"] = le_junc.fit_transform(df["junction_id"])
    le_wthr = LabelEncoder(); df["weather_enc"]  = le_wthr.fit_transform(df["weather"])

    df["hour_sin"]  = np.sin(2*np.pi*df["hour"]/24)
    df["hour_cos"]  = np.cos(2*np.pi*df["hour"]/24)
    df["month_sin"] = np.sin(2*np.pi*df["month"]/12)
    df["month_cos"] = np.cos(2*np.pi*df["month"]/12)
    df["dow_sin"]   = np.sin(2*np.pi*df["day_of_week"]/7)
    df["dow_cos"]   = np.cos(2*np.pi*df["day_of_week"]/7)

    df["peak_weekday"]    = df["is_peak_hour"] * (1 - df["is_weekend"])
    df["holiday_weekend"] = df["is_holiday"]   * df["is_weekend"]
    df["rain_peak"]       = (df["weather"]=="Rain").astype(int) * df["is_peak_hour"]

    df = df.sort_values(["junction_id","datetime"]).reset_index(drop=True)
    for col, shift in [("lag_1h",1),("lag_24h",24),("lag_168h",168)]:
        df[col] = df.groupby("junction_id")[TARGET].shift(shift)
    df["rolling_3h"] = df.groupby("junction_id")[TARGET].transform(lambda x: x.rolling(3,  min_periods=1).mean())
    df["rolling_6h"] = df.groupby("junction_id")[TARGET].transform(lambda x: x.rolling(6,  min_periods=1).mean())
    df = df.dropna(subset=["lag_1h","lag_24h","lag_168h"]).reset_index(drop=True)
    print(f"    ✓ {len(FEATURES)} features ready  |  {len(df):,} rows remain")
    return df, le_junc, le_wthr


# ════════════════════════════════════════════════════════════
#  STEP 4-6 — SPLIT, TRAIN, EVALUATE
# ════════════════════════════════════════════════════════════
def train_and_evaluate(df):
    print("[4/7] Splitting 80/20...")
    X = df[FEATURES]; y = df[TARGET]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"    ✓ Train {len(X_train):,}  |  Test {len(X_test):,}")

    print("[5/7] Training Linear Regression (baseline)...")
    lr = LinearRegression(n_jobs=-1)
    lr.fit(X_train, y_train)
    yp_lr = np.maximum(0, lr.predict(X_test))
    lr_m  = {"mae": round(mean_absolute_error(y_test,yp_lr),1),
              "rmse":round(float(np.sqrt(mean_squared_error(y_test,yp_lr))),1),
              "r2":  round(r2_score(y_test,yp_lr),4)}
    print(f"    ✓ LR  →  R²={lr_m['r2']}  MAE={lr_m['mae']}")

    print("[6/7] Training Random Forest (200 trees)...")
    rf = RandomForestRegressor(n_estimators=200, max_depth=20,
                               min_samples_leaf=4, min_samples_split=8,
                               max_features="sqrt", random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    yp_rf = rf.predict(X_test)
    rf_m  = {"mae": round(mean_absolute_error(y_test,yp_rf),1),
              "rmse":round(float(np.sqrt(mean_squared_error(y_test,yp_rf))),1),
              "r2":  round(r2_score(y_test,yp_rf),4)}
    print(f"    ✓ RF  →  R²={rf_m['r2']}  MAE={rf_m['mae']}")

    feat_imp = {k: round(v,4) for k,v in
                sorted(zip(FEATURES, rf.feature_importances_), key=lambda x:-x[1])}
    return lr, rf, lr_m, rf_m, feat_imp


# ════════════════════════════════════════════════════════════
#  STEP 7 — SAVE
# ════════════════════════════════════════════════════════════
def save_model(lr, rf, le_junc, le_wthr, lr_m, rf_m, feat_imp, df):
    print("[7/7] Saving model...")
    # Pre-compute lag medians per junction (used for live prediction)
    lag_meds = {}
    for jid in df["junction_id"].unique():
        sub = df[df["junction_id"]==jid]
        lag_meds[jid] = {
            "lag_1h":   float(sub["lag_1h"].median()),
            "lag_24h":  float(sub["lag_24h"].median()),
            "lag_168h": float(sub["lag_168h"].median()),
            "rolling_3h": float(sub["rolling_3h"].median()),
            "rolling_6h": float(sub["rolling_6h"].median()),
            "temperature_c": float(sub["temperature_c"].median()),
            "humidity_pct":  float(sub["humidity_pct"].median()),
        }

    pkg = {
        "rf": rf, "lr": lr,
        "features": FEATURES, "target": TARGET,
        "encoders": {"junction": le_junc, "weather": le_wthr},
        "metrics": {"rf": rf_m, "lr": lr_m},
        "feat_imp": feat_imp,
        "lag_meds": lag_meds,
        "junctions": JUNCTIONS,
    }
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(pkg, f)
    print(f"    ✓ Saved → models/traffic_model.pkl")
    print("\n  ✅ Training complete!")
    print(f"     RF  R²={rf_m['r2']} | MAE={rf_m['mae']} veh/hr")
    print(f"     LR  R²={lr_m['r2']} | MAE={lr_m['mae']} veh/hr\n")


# ════════════════════════════════════════════════════════════
#  PREDICT HELPER  (used by Flask app)
# ════════════════════════════════════════════════════════════
def load_model():
    """Load and return the saved model package."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Model not found. Run: python backend/model.py")
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def make_prediction(pkg, hour, dow, month, weather, junction_id, is_holiday=0):
    """Make a single traffic volume prediction using the RF model."""
    le_j = pkg["encoders"]["junction"]
    le_w = pkg["encoders"]["weather"]
    lm   = pkg["lag_meds"].get(junction_id, list(pkg["lag_meds"].values())[0])

    jenc = (le_j.transform([junction_id])[0]
            if junction_id in le_j.classes_ else 0)
    wenc = (le_w.transform([weather])[0]
            if weather in le_w.classes_ else 0)

    is_peak   = int(hour in [7,8,9,17,18,19])
    is_weekend = int(dow >= 5)

    row = pd.DataFrame([[
        hour, dow, month, is_weekend, is_holiday, is_peak,
        lm["temperature_c"], lm["humidity_pct"], 0.0, 10,
        jenc, wenc,
        math.sin(2*math.pi*hour/24),  math.cos(2*math.pi*hour/24),
        math.sin(2*math.pi*month/12), math.cos(2*math.pi*month/12),
        math.sin(2*math.pi*dow/7),    math.cos(2*math.pi*dow/7),
        is_peak*(1-is_weekend), 0, 0,
        lm["lag_1h"], lm["lag_24h"], lm["lag_168h"],
        lm["rolling_3h"], lm["rolling_6h"],
    ]], columns=FEATURES)

    vol = max(0, int(pkg["rf"].predict(row)[0]))
    return vol


def classify_volume(v):
    if v < 400:  return "LOW",       "#10d97e"
    if v < 900:  return "MODERATE",  "#f5a623"
    if v < 1600: return "HIGH",      "#ff4d4d"
    return           "VERY HIGH", "#9b6dff"


# ── Run standalone ───────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  TrafficAI — Model Training Pipeline")
    print("=" * 55)
    df_raw           = generate_dataset()
    df_clean         = clean_data(df_raw)
    df_feat, le_j, le_w = feature_engineering(df_clean)
    lr, rf, lr_m, rf_m, feat_imp = train_and_evaluate(df_feat)
    save_model(lr, rf, le_j, le_w, lr_m, rf_m, feat_imp, df_feat)
