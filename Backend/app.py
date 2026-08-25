import os
import joblib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import openmeteo_requests
import requests_cache
from retry_requests import retry
import sqlite3
import json

# ------------------------------
# Initialization
# ------------------------------
app = Flask(__name__)
CORS(app)  # Allow frontend to call API

# Setup Open-Meteo client with cache
cache_session = requests_cache.CachedSession('.cache', expire_after=-1)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

# Load all models
MODEL_DIR = 'models'
model_temp = joblib.load(os.path.join(MODEL_DIR, 'model_temp.pkl'))
model_rain = joblib.load(os.path.join(MODEL_DIR, 'model_rain.pkl'))
model_sm = joblib.load(os.path.join(MODEL_DIR, 'model_sm.pkl'))
model_drought = joblib.load(os.path.join(MODEL_DIR, 'model_drought_classifier.pkl'))
model_stress = joblib.load(os.path.join(MODEL_DIR, 'model_crop_stress.pkl'))
model_inflow = joblib.load(os.path.join(MODEL_DIR, 'model_inflow.pkl'))

# District information (same points as training)
DISTRICTS = {
    "Srinagar": (34.08, 74.80),
    "Jammu": (32.73, 74.87),
    "Baramulla": (34.20, 74.35),
    "Anantnag": (33.75, 75.15),
    "Kupwara": (34.02, 74.35),
    "Udhampur": (32.93, 75.13),
    "Doda": (33.15, 75.55),
    "Leh": (34.15, 77.58)
}

# SQLite setup for recent data cache (last 30 days)
DB_FILE = 'cache.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS daily_weather
                 (date TEXT PRIMARY KEY, temp_mean REAL, precip REAL)''')
    conn.commit()
    conn.close()

init_db()

# ------------------------------
# Helper functions
# ------------------------------

def fetch_recent_data(days=7):
    """
    Fetch the latest observed daily weather for Srinagar (representative point).
    Returns a DataFrame with columns ds, temp_mean, precip.
    """
    # First try to get from cache
    conn = sqlite3.connect(DB_FILE)
    cache_df = pd.read_sql_query(
        f"SELECT date as ds, temp_mean, precip FROM daily_weather ORDER BY date DESC LIMIT {days}",
        conn, parse_dates=['ds']
    )
    conn.close()
    if len(cache_df) >= days:
        return cache_df.sort_values('ds')

    # If cache insufficient, fetch from Open-Meteo
    print("Fetching recent data from API...")
    params = {
        "latitude": DISTRICTS["Srinagar"][0],
        "longitude": DISTRICTS["Srinagar"][1],
        "daily": ["temperature_2m_mean", "precipitation_sum"],
        "past_days": days,
        "forecast_days": 0,
        "timezone": "Asia/Kolkata"
    }
    responses = openmeteo.weather_api("https://api.open-meteo.com/v1/forecast", params=params)
    response = responses[0]
    daily = response.Daily()
    temps = daily.Variables(0).ValuesAsNumpy()
    precips = daily.Variables(1).ValuesAsNumpy()
    dates = pd.date_range(
        start=pd.to_datetime(daily.Time(), unit="s"),
        periods=len(temps),
        freq="D"
    )
    new_df = pd.DataFrame({'ds': dates, 'temp_mean': temps, 'precip': precips})

    # Update cache
    conn = sqlite3.connect(DB_FILE)
    for _, row in new_df.iterrows():
        conn.execute("INSERT OR REPLACE INTO daily_weather (date, temp_mean, precip) VALUES (?, ?, ?)",
                     (row['ds'].strftime('%Y-%m-%d'), float(row['temp_mean']), float(row['precip'])))
    conn.commit()
    conn.close()
    return new_df.tail(days).reset_index(drop=True)

def compute_anomalies(recent_df):
    """
    Compute current anomalies vs 1981-2010 baseline for Srinagar point.
    """
    # Fetch baseline normals for the same days (we approximate by month for simplicity)
    # In production, you would have precomputed daily normals.
    # Here we'll use a fixed monthly baseline for J&K (state average).
    monthly_baseline = {
        1: {'temp': 2.5, 'precip': 60},
        2: {'temp': 4.0, 'precip': 70},
        3: {'temp': 9.0, 'precip': 80},
        4: {'temp': 14.0, 'precip': 60},
        5: {'temp': 18.0, 'precip': 50},
        6: {'temp': 22.0, 'precip': 40},
        7: {'temp': 24.0, 'precip': 80},
        8: {'temp': 23.0, 'precip': 80},
        9: {'temp': 20.0, 'precip': 60},
        10: {'temp': 14.0, 'precip': 30},
        11: {'temp': 8.0, 'precip': 20},
        12: {'temp': 3.0, 'precip': 40}
    }
    latest = recent_df.iloc[-1]
    month = latest['ds'].month
    temp_anomaly = latest['temp_mean'] - monthly_baseline[month]['temp']
    # Rainfall anomaly: compare last 30 days total to average monthly * 1
    precip_30 = recent_df['precip'].sum()  # if days=7, only 7 days; use cache for 30 days
    precip_anomaly_pct = ((precip_30 / (monthly_baseline[month]['precip'] * 4.3)) - 1) * 100
    # Simplified soil moisture from recent precipitation (0.3 base + precip factor)
    soil_moisture = min(1.0, 0.3 + precip_30 / 200.0)
    # Drought risk class (0-5) using simplified SPI of recent 30 days
    precip_30_total = recent_df['precip'].sum()
    mean_precip_30 = 100  # approximate long-term mean for 30 days
    std_precip_30 = 40
    spi = (precip_30_total - mean_precip_30) / std_precip_30
    if spi > -0.5:
        drought_class = 0
    elif spi > -0.8:
        drought_class = 1
    elif spi > -1.3:
        drought_class = 2
    elif spi > -1.6:
        drought_class = 3
    elif spi > -2.0:
        drought_class = 4
    else:
        drought_class = 5

    return {
        'rainfall_anomaly_pct': round(precip_anomaly_pct, 1),
        'temperature_anomaly_c': round(temp_anomaly, 2),
        'soil_moisture_index': round(soil_moisture, 3),
        'drought_risk_class': drought_class,
        'last_assimilation_timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    }

def get_latest_weather_features():
    """
    Build the 6-feature vector for Random Forest models using cached recent data.
    Features: precip, temp_mean, precip_7d, temp_7d, precip_30d, doy
    """
    # Fetch last 30 days from cache
    conn = sqlite3.connect(DB_FILE)
    df30 = pd.read_sql_query("SELECT date as ds, temp_mean, precip FROM daily_weather ORDER BY date DESC LIMIT 30",
                             conn, parse_dates=['ds'])
    conn.close()
    if len(df30) < 30:
        # If not enough, fetch 30 days from API
        df30 = fetch_recent_data(30)
    df30 = df30.sort_values('ds')

    latest = df30.iloc[-1]
    precip = latest['precip']
    temp_mean = latest['temp_mean']
    precip_7d = df30['precip'].tail(7).mean()
    temp_7d = df30['temp_mean'].tail(7).mean()
    precip_30d = df30['precip'].tail(30).sum()
    doy = latest['ds'].dayofyear

    return pd.DataFrame([[precip, temp_mean, precip_7d, temp_7d, precip_30d, doy]],
                        columns=['precip', 'temp_mean', 'precip_7d', 'temp_7d', 'precip_30d', 'doy'])

# ------------------------------
# API Routes
# ------------------------------

@app.route('/api/current-state', methods=['GET'])
def current_state():
    recent = fetch_recent_data(7)
    anomalies = compute_anomalies(recent)
    return jsonify(anomalies)

@app.route('/api/forecast/temperature', methods=['GET'])
def forecast_temperature():
    # Generate 14-day forecast using Prophet
    future = model_temp.make_future_dataframe(periods=14)
    forecast = model_temp.predict(future)
    # Get last 7 observed days
    observed = fetch_recent_data(7)
    observed_list = observed[['ds', 'temp_mean']].rename(columns={'temp_mean': 'observed'}).to_dict('records')
    predicted_list = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(14).to_dict('records')
    return jsonify({
        'observed': observed_list,
        'predicted': predicted_list,
        'units': '°C'
    })

@app.route('/api/forecast/rainfall', methods=['GET'])
def forecast_rainfall():
    future = model_rain.make_future_dataframe(periods=14)
    forecast = model_rain.predict(future)
    observed = fetch_recent_data(7)
    observed_list = observed[['ds', 'precip']].rename(columns={'precip': 'observed'}).to_dict('records')
    predicted_list = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(14).to_dict('records')
    return jsonify({
        'observed': observed_list,
        'predicted': predicted_list,
        'units': 'mm/day'
    })

@app.route('/api/forecast/soil-moisture', methods=['GET'])
def forecast_soil_moisture():
    future = model_sm.make_future_dataframe(periods=14)
    forecast = model_sm.predict(future)
    predicted_list = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(14).to_dict('records')
    return jsonify({'predicted': predicted_list, 'units': 'index (0-1)'})

@app.route('/api/what-if', methods=['POST'])
def what_if():
    data = request.get_json()
    rain_mult = float(data.get('rain_multiplier', 1.0))
    temp_offset = float(data.get('temp_offset', 0.0))

    # Get baseline current features
    base_features = get_latest_weather_features().iloc[0]
    # Apply perturbations
    new_features = base_features.copy()
    new_features['precip'] *= rain_mult
    new_features['precip_7d'] *= rain_mult
    new_features['precip_30d'] *= rain_mult
    new_features['temp_mean'] += temp_offset
    new_features['temp_7d'] += temp_offset

    # Create DataFrame for prediction
    X_new = pd.DataFrame([new_features])

    # Predict with models
    drought_class = int(model_drought.predict(X_new)[0])
    crop_stress = float(model_stress.predict(X_new)[0])
    inflow = float(model_inflow.predict(X_new)[0])

    # Map drought class to label
    drought_labels = ['Normal', 'D0', 'D1', 'D2', 'D3', 'D4']
    drought_label = drought_labels[drought_class]

    # Crop stress category
    if crop_stress < 0.33:
        crop_cat = 'Low'
    elif crop_stress < 0.66:
        crop_cat = 'Medium'
    else:
        crop_cat = 'High'

    # Reservoir inflow change (%)
    baseline_inflow = float(model_inflow.predict(pd.DataFrame([base_features]))[0])
    inflow_change_pct = ((inflow - baseline_inflow) / (baseline_inflow + 1e-6)) * 100

    return jsonify({
        'soil_moisture_index': round(float(new_features['precip_30d']) / 200 + 0.3, 3),  # simplified
        'drought_risk_score': drought_class,
        'drought_risk_label': drought_label,
        'crop_water_stress_category': crop_cat,
        'reservoir_inflow_change_pct': round(inflow_change_pct, 1)
    })

@app.route('/api/districts', methods=['GET'])
def district_data():
    layer = request.args.get('layer', 'rainfall_anomaly')  # or 'temperature_anomaly', 'soil_moisture'
    results = []
    # For each district, fetch current value and compare with baseline
    for district, (lat, lon) in DISTRICTS.items():
        # Fetch recent 7-day data for this point
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ["temperature_2m_mean", "precipitation_sum"],
            "past_days": 7,
            "forecast_days": 0,
            "timezone": "Asia/Kolkata"
        }
        resp = openmeteo.weather_api("https://api.open-meteo.com/v1/forecast", params=params)[0]
        daily = resp.Daily()
        temps = daily.Variables(0).ValuesAsNumpy()
        precips = daily.Variables(1).ValuesAsNumpy()
        # Approximate baseline values (long-term average for district, could be improved)
        # For simplicity, we use a fixed baseline per district (manually defined)
        # In production, load from precomputed CSVs.
        baseline_temp = {'Srinagar': 13.5, 'Jammu': 24.0, 'Baramulla': 13.0, 'Anantnag': 12.5,
                         'Kupwara': 12.0, 'Udhampur': 21.0, 'Doda': 16.0, 'Leh': 5.0}
        baseline_precip = {'Srinagar': 80, 'Jammu': 140, 'Baramulla': 70, 'Anantnag': 60,
                           'Kupwara': 60, 'Udhampur': 100, 'Doda': 80, 'Leh': 10}
        temp_anom = np.mean(temps) - baseline_temp[district]
        rain_anom_pct = ((np.sum(precips) / 7) / (baseline_precip[district]/30) - 1) * 100  # rough

        if layer == 'temperature_anomaly':
            value = round(temp_anom, 2)
        elif layer == 'rainfall_anomaly':
            value = round(rain_anom_pct, 1)
        elif layer == 'soil_moisture':
            # Use a simple proxy based on rainfall
            value = min(1.0, 0.3 + np.sum(precips)/200)
        else:
            value = 0

        results.append({'district': district, 'value': value})
    return jsonify(results)

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'models_loaded': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)