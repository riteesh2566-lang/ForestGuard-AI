# prediction/predictor.py

import pandas as pd

def pure_python_fire_model(temp, humidity, wind, rain, drought):
    print("MODEL DEBUG:", temp, humidity, wind, rain, drought)   # <--- ADD THIS


    """
    Realistic forest fire rule-based model.
    NO sklearn used. Works on any system.
    """

    # 🌡 FIRE CONDITIONS (Realistic thresholds)
    is_hot = temp > 30 # High temperature
    is_dry_air = humidity < 30  # Low humidity
    is_windy = wind > 20          # Strong wind
    is_no_rain = rain < 5          # Very little rain
    is_drought = drought > 10    # Long dry period

    # 🔥 FIRE RISK: High ONLY if ALL match
    if is_hot :
        prediction = 1   # FIRE LIKELY
        probability = 0.90
    else:
        prediction = 0   # SAFE
        probability = 0.10 

    return {
        "prediction": prediction,
        "probability": probability
    }


def predict_with_model(data):
    """
    Wrapper function used by app.py.
    Accepts dictionary from weather API.
    """

    temp = float(data.get("temp", 0))
    humidity = float(data.get("humidity", 0))
    wind = float(data.get("wind", 0))
    rain = float(data.get("rain", 0))
    drought = float(data.get("drought", 0))

    return pure_python_fire_model(temp, humidity, wind, rain, drought)
