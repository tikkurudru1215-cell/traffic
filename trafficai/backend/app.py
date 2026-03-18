"""
================================================================
  backend/app.py
  Flask REST API — All endpoints for the TrafficAI frontend
================================================================
  Endpoints:
    GET  /                    → serve frontend
    GET  /api/status          → health check
    POST /api/predict         → RF prediction for given inputs
    POST /api/forecast        → 24-hour forecast array
    GET  /api/junctions       → all junctions + current volumes
    POST /api/routes          → route recommendations
    POST /api/deviation       → GPS deviation check
    GET  /api/metrics         → model performance numbers
    GET  /api/eda             → EDA summary data for charts
================================================================
"""
import os, json, math
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS

from backend.model  import load_model, make_prediction, classify_volume, JUNCTIONS
from backend.routes import get_route_recommendations, check_deviation, WEATHER_IMPACT

# ── Cached model (loaded once on startup) ────────────────────
_MODEL_PKG = None

def get_model():
    global _MODEL_PKG
    if _MODEL_PKG is None:
        _MODEL_PKG = load_model()
    return _MODEL_PKG


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "templates"),
        static_folder   =os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "static"),
    )
    CORS(app)

    # ── Serve frontend ────────────────────────────────────────
    @app.route("/")
    def index():
        return render_template("index.html")

    # ── Health check ──────────────────────────────────────────
    @app.get("/api/status")
    def status():
        pkg = get_model()
        return jsonify({
            "status":  "ok",
            "model":   "Random Forest 200 trees",
            "r2":      pkg["metrics"]["rf"]["r2"],
            "mae":     pkg["metrics"]["rf"]["mae"],
            "dataset": "Bhopal Traffic — 105,120 rows",
        })

    # ── Single prediction ─────────────────────────────────────
    @app.post("/api/predict")
    def predict():
        """
        Body: { hour, day_of_week, month, weather, junction_id, is_holiday? }
        Returns: { volume, level, color, is_peak, inputs }
        """
        d = request.get_json()
        hour       = int(d.get("hour", 8))
        dow        = int(d.get("day_of_week", 0))
        month      = int(d.get("month", 3))
        weather    = d.get("weather", "Clear")
        junction   = d.get("junction_id", "J01_DBMall")
        is_holiday = int(d.get("is_holiday", 0))

        pkg = get_model()
        vol = make_prediction(pkg, hour, dow, month, weather, junction, is_holiday)
        lvl, color = classify_volume(vol)

        return jsonify({
            "volume":     vol,
            "level":      lvl,
            "color":      color,
            "is_peak":    hour in [7,8,9,17,18,19],
            "pct_of_max": round(min(100, vol/2000*100), 1),
            "inputs": {
                "hour": hour, "day_of_week": dow, "month": month,
                "weather": weather, "junction_id": junction,
            }
        })

    # ── 24-hour forecast ──────────────────────────────────────
    @app.post("/api/forecast")
    def forecast():
        """
        Body: { day_of_week, month, weather, junction_id }
        Returns: { hours: [{hour, volume, level, color}] }
        """
        d       = request.get_json()
        dow     = int(d.get("day_of_week", 0))
        month   = int(d.get("month", 3))
        weather = d.get("weather", "Clear")
        junc    = d.get("junction_id", "J01_DBMall")

        pkg   = get_model()
        hours = []
        for h in range(24):
            vol = make_prediction(pkg, h, dow, month, weather, junc)
            lvl, color = classify_volume(vol)
            hours.append({"hour": h, "volume": vol, "level": lvl, "color": color})

        return jsonify({"junction_id": junc, "hours": hours})

    # ── All junctions + live volumes ──────────────────────────
    @app.get("/api/junctions")
    def junctions():
        """
        Query params: hour, day_of_week, month, weather
        Returns all 6 junctions with predicted current volume.
        """
        hour    = int(request.args.get("hour",    8))
        dow     = int(request.args.get("day_of_week", 0))
        month   = int(request.args.get("month",   3))
        weather = request.args.get("weather", "Clear")

        pkg    = get_model()
        result = []
        for jid, jdata in JUNCTIONS.items():
            vol = make_prediction(pkg, hour, dow, month, weather, jid)
            lvl, color = classify_volume(vol)
            result.append({
                "id":     jid,
                "name":   jdata["name"],
                "lat":    jdata["lat"],
                "lon":    jdata["lon"],
                "volume": vol,
                "level":  lvl,
                "color":  color,
            })
        return jsonify({"junctions": result})

    # ── Route recommendations ─────────────────────────────────
    @app.post("/api/routes")
    def routes():
        """
        Body: { hour, day_of_week, month, weather }
        Returns: sorted list of 3 routes with scores.
        """
        d       = request.get_json()
        hour    = int(d.get("hour", 8))
        dow     = int(d.get("day_of_week", 0))
        month   = int(d.get("month", 3))
        weather = d.get("weather", "Clear")

        pkg = get_model()
        def rf_predict(h, dw, mo, wt, jid):
            return make_prediction(pkg, h, dw, mo, wt, jid)

        scored = get_route_recommendations(hour, dow, month, weather, predict_fn=rf_predict)
        return jsonify({"routes": scored})

    # ── GPS deviation check ───────────────────────────────────
    @app.post("/api/deviation")
    def deviation():
        """
        Body: { lat, lon, route_id? }
        Returns: { distance_m, level, message, color, reroute }
        """
        d        = request.get_json()
        lat      = float(d.get("lat", 23.235))
        lon      = float(d.get("lon", 77.42))
        route_id = d.get("route_id", "A")

        result = check_deviation(lat, lon, route_id)
        return jsonify(result)

    # ── Model metrics ─────────────────────────────────────────
    @app.get("/api/metrics")
    def metrics():
        pkg = get_model()
        return jsonify({
            "rf":           pkg["metrics"]["rf"],
            "lr":           pkg["metrics"]["lr"],
            "feat_imp":     pkg["feat_imp"],
            "improvement":  round(pkg["metrics"]["lr"]["mae"] / pkg["metrics"]["rf"]["mae"], 1),
        })

    # ── EDA summary for charts ────────────────────────────────
    @app.get("/api/eda")
    def eda():
        """Pre-computed EDA summary data for all dashboard charts."""
        wi = WEATHER_IMPACT

        def bv(h, dow, mon):
            s = 1 + 0.08*math.sin((mon-6)*math.pi/6)
            if dow >= 5:
                b = 550*max(0, math.sin((h-10)*math.pi/10)) + 80
            else:
                b = (600*math.exp(-((h-8)**2)/4)
                   + 750*math.exp(-((h-18)**2)/3)
                   + 150*math.exp(-((h-13)**2)/5) + 80)
            return round(b*s)

        return jsonify({
            "hourly_weekday": [bv(h, 0, 3) for h in range(24)],
            "hourly_weekend": [bv(h, 6, 3) for h in range(24)],
            "junction_avg":   {jid: round(jd["mult"]*780) for jid,jd in JUNCTIONS.items()},
            "junction_names": {jid: jd["name"]            for jid,jd in JUNCTIONS.items()},
            "weather_avg":    {w: round(wi[w]*960) for w in wi},
            "monthly":        [810,820,880,920,950,990,1010,1000,960,930,900,860],
            "dow_avg":        [1050,980,990,1010,1120,720,680],
            "dist_labels":    ["0–200","200–400","400–600","600–800","800–1k","1k–1.2k","1.2k+"],
            "dist_counts":    [8,12,18,22,20,12,8],
        })

    return app
