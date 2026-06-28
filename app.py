import os
import time
import threading
import logging
import cv2
import numpy as np
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, Response, jsonify
from detection.fire_detector import detect_fire
from prediction.predictor import predict_with_model
from dotenv import load_dotenv
from twilio.rest import Client
import os
import subprocess




load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))

# ------------------------------------------------
# Flask Setup
# ------------------------------------------------
app = Flask(__name__)

camera_source = 0
global_cap = None
use_url = False

# WEATHER
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
IPINFO_URL = "https://ipinfo.io/json"

# TWILIO
TWILIO_SID = os.environ.get("TWILIO_SID")
TWILIO_AUTH = os.environ.get("TWILIO_AUTH")
TWILIO_WHATSAPP = os.environ.get("TWILIO_WHATSAPP", "whatsapp:+14155238886")
MY_WHATSAPP = os.environ.get("MY_WHATSAPP")
TWILIO_CALL = os.environ.get("TWILIO_CALL")
MY_PHONE = os.environ.get("MY_PHONE")


# ALERT SETTINGS
PREDICT_ALERT_COOLDOWN = int(os.environ.get("PREDICT_ALERT_COOLDOWN", 300))
CAMERA_ALERT_COOLDOWN = int(os.environ.get("CAMERA_ALERT_COOLDOWN", 300))
CALL_REPEATS = int(os.environ.get("CALL_REPEATS", 3))
CALL_GAP_SECONDS = int(os.environ.get("CALL_GAP_SECONDS", 5))

_last_predict_alert_time = 0
_last_camera_alert_time = 0

client = Client(TWILIO_SID, TWILIO_AUTH) if TWILIO_SID and TWILIO_AUTH else None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fire-alerts")


# ------------------------------------------------
# WEATHER SYSTEM
# ------------------------------------------------
def fetch_auto_weather():
    """
    Auto-detect location using IP and fetch weather.
    Used for backend prediction route.
    """
    try:
        ip_data = requests.get(IPINFO_URL, timeout=5).json()
        loc = ip_data.get("loc", None)
        city = ip_data.get("city", "Unknown")
        region = ip_data.get("region", "")
        country = ip_data.get("country", "")

        if loc:
            lat, lon = loc.split(",")
        else:
            # Default: Bangalore
            lat, lon = "12.9716", "77.5946"

        w = requests.get(
            f"{WEATHER_URL}?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric",
            timeout=7,
        ).json()

        return {
            "status": "success",
            "city": city,
            "region": region,
            "country": country,
            "lat": float(lat),
            "lon": float(lon),
            "temp": float(w["main"]["temp"]),
            "humidity": float(w["main"]["humidity"]),
            "wind": float(w["wind"]["speed"]),
            "rain": float(w.get("rain", {}).get("1h", 0.0)),
            "drought": 0.0,
        }
    except Exception as e:
        logger.error(f"Auto weather failed: {e}")
        return {"status": "error"}


# ------------------------------------------------
# TWILIO ALERTS
# ------------------------------------------------
def send_whatsapp_alert(lat, lon, location, temp=None, humidity=None, wind=None, probability=None):
    if client is None or not MY_WHATSAPP:
        logger.warning("WhatsApp client not configured, skipping WhatsApp alert.")
        return

    body = (
        "🔥 *FOREST FIRE ALERT* 🔥\n\n"
        f"📍 Location: {location}\n"
        f"🌎 Lat: {lat}, Lon: {lon}\n"
        f"🗺 Maps: https://www.google.com/maps?q={lat},{lon}\n"
    )
    if temp is not None:
        body += f"\n🌡 Temp: {temp}°C"
    if humidity is not None:
        body += f"\n💧 Humidity: {humidity}%"
    if wind is not None:
        body += f"\n💨 Wind: {wind} km/h"
    if probability is not None:
        body += f"\n🔥 Risk: {probability}%"

    body += "\n\n⚠ Take action immediately!"

    try:
        client.messages.create(
            body=body,
            from_=TWILIO_WHATSAPP,
            to=MY_WHATSAPP,
        )
        logger.info("WhatsApp alert sent.")
    except Exception as e:
        logger.error(f"Failed to send WhatsApp alert: {e}")


def send_repeated_call_alert():
    if client is None or not TWILIO_CALL or not MY_PHONE:
        logger.warning("Call client not configured, skipping calls.")
        return

    for i in range(CALL_REPEATS):
        try:
            client.calls.create(
                url="http://demo.twilio.com/docs/voice.xml",
                to=MY_PHONE,
                from_=TWILIO_CALL,
            )
            logger.info(f"Call {i+1}/{CALL_REPEATS} initiated.")
        except Exception as e:
            logger.error(f"Failed to make call: {e}")
        time.sleep(CALL_GAP_SECONDS)


# ------------------------------------------------
# HOME PAGE
# ------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")


# ------------------------------------------------
# IMPORTS  💡 ALWAYS KEEP IMPORTS AT TOP
# ------------------------------------------------
import os
import cv2
import subprocess   # REQUIRED FOR MP4 CONVERSION
from datetime import datetime
from flask import Response, render_template, redirect, url_for, send_from_directory, request
from database.db import save_recording, get_all_recordings
# other imports... (detect_fire imported already)

# ------------------------------------------------
# GLOBAL VARIABLES
# ------------------------------------------------
video_writer = None
current_filename = None
global_cap = None
last_fire_event = "NOFIRE" 
fire_counter = 0                  # 🆕 Added
FIRE_STABLE_THRESHOLD = 20        # 🆕 Added

# ------------------------------------------------
# CAMERA STREAM
# ------------------------------------------------
@app.route("/live", methods=["GET", "POST"])
def live():
    global camera_source, video_writer, current_filename

    if request.method == "POST":
        if request.form.get("source_type") == "webcam":
            camera_source = int(request.form["cam_index"])
        else:
            camera_source = request.form["cam_url"]

        start_camera(camera_source)
        start_new_recording()    # ✔ AUTO START RECORDING

        return render_template("live.html", stream=True)

    stop_camera()
    return render_template("live.html", stream=False)


def start_camera(source):
    global global_cap
    if global_cap:
        return global_cap
    cap = cv2.VideoCapture(source)
    if cap.isOpened():
        global_cap = cap
    return global_cap


def stop_camera():
    global global_cap, video_writer, current_filename

    if global_cap:
        global_cap.release()
        global_cap = None

    if video_writer:
        video_writer.release()
        video_writer = None

        # 🔥 MP4 CONVERSION AFTER RECORDING STOPS
        avi_path = os.path.join("recordings", current_filename)
        convert_to_mp4(avi_path)
        print("[INFO] Converted to MP4:", avi_path.replace(".avi", ".mp4"))


def start_new_recording():
    """Start a new recording file and save to MongoDB."""
    global video_writer, current_filename

    if not os.path.exists("recordings"):
        os.makedirs("recordings")

    current_filename = f"webcam_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
    filepath = os.path.join("recordings", current_filename)

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    video_writer = cv2.VideoWriter(filepath, fourcc, 20.0, (640, 480))

    save_recording(current_filename, camera_source="webcam")
    print("[INFO] Started recording:", filepath)


# ------------------------------------------------
# MP4 CONVERSION FUNCTION (GLOBAL ACCESS)
# ------------------------------------------------
def convert_to_mp4(input_file):
    output_file = input_file.replace(".avi", ".mp4")
    command = f'ffmpeg -i "{input_file}" -vcodec libx264 "{output_file}"'
    subprocess.call(command, shell=True)
    return output_file

# ------------------------------------------------
# FRAME GENERATOR (FIRE DETECTION + EVENT SYSTEM)
# ------------------------------------------------
def gen_frames():
    global video_writer, last_fire_event, _last_camera_alert_time

    while global_cap:
        ok, frame = global_cap.read()
        if not ok:
            continue

        _, overlay, fire_pixels, flag, _, _ = detect_fire(frame)

        # 🟢 FIRE DETECTION FLAG
        if fire_pixels > 80:
            last_fire_event = "ALERT_FIRE"
        else:
            last_fire_event = "NOFIRE"

        # 🚨🚨🚨  ADD THIS PART FOR ALERT  🚨🚨🚨
        now = time.time()
        if fire_pixels > 80 and client is not None:
            if now - _last_camera_alert_time > CAMERA_ALERT_COOLDOWN:
                _last_camera_alert_time = now
                send_whatsapp_alert(
                    lat="12.9716",
                    lon="77.5946",
                    location="Webcam Live Detection ⚠"
                )
                threading.Thread(target=send_repeated_call_alert).start()
                print("🔥 WEBCAM ALERT SENT!!")
        # ------------------------------------------------------

        if video_writer:
            video_writer.write(overlay)

        ret, buffer = cv2.imencode(".jpg", overlay)
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )


@app.route("/live_stream")
def live_stream():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ------------------------------------------------
# FIRE ALERT EVENT STREAM (🔥 ALARM TRIGGER)
# ------------------------------------------------
@app.route("/live/events")
def live_events():
    def event_stream():
        global last_fire_event
        while True:
            yield f"data: {last_fire_event}\n\n"
    return Response(event_stream(), mimetype="text/event-stream")


# ------------------------------------------------
# DELETE RECORDING
# ------------------------------------------------
@app.route("/delete/<record_id>", methods=["POST"])
def delete_recording_route(record_id):
    from database.db import delete_recording
    delete_recording(record_id)
    return redirect(url_for("history_page"))


# ------------------------------------------------
# SERVE RECORDED FILES
# ------------------------------------------------
@app.route("/recordings/<path:filename>")
def get_recording(filename):
    return send_from_directory("recordings", filename)


# ------------------------------------------------
# HISTORY PAGE
# ------------------------------------------------
@app.route("/history")
def history_page():
    try:
        recordings = get_all_recordings()
        return render_template("history.html", recordings=recordings)
    except Exception as e:
        return f"Error loading history: {e}"


# ------------------------------------------------
# STOP CAMERA (ROUTE)  ✔ SAFE
# ------------------------------------------------
@app.route("/stop_camera")
def stop_camera_route():
    stop_camera()
    return redirect(url_for("live"))


@app.route("/")
def index():
    return render_template("index.html")  # or your home page



# ------------------------------------------------
# PREDICTION PAGE (BACKEND MODEL + AUTO WEATHER)
# ------------------------------------------------
@app.route("/predict")
def predict():
    """
    Renders predict.html.
    Backend still runs ML model using auto-weather for your project logic,
    but the frontend map + JS will handle live display and alerts.
    """
    global _last_predict_alert_time

    weather = fetch_auto_weather()

    prediction = None
    probability = None
    alert_sent = False

    if weather.get("status") == "success":
        # Run your ML model
        try:
            result = predict_with_model(weather)
        except Exception as e:
            logger.error(f"Model prediction failed: {e}")
            result = {}

        prediction = result.get("prediction")
        probability = result.get("probability")

        # Optional: backend auto alert based on temperature (cooldown)
        now = time.time()
        if weather["temp"] > 30 and now - _last_predict_alert_time > PREDICT_ALERT_COOLDOWN:
            _last_predict_alert_time = now
            alert_sent = True
            send_whatsapp_alert(
                weather["lat"],
                weather["lon"],
                "Prediction Page (Auto-Location)",
                temp=weather["temp"],
                humidity=weather["humidity"],
                wind=weather["wind"],
                probability=probability,
            )
            threading.Thread(target=send_repeated_call_alert).start()

    return render_template(
        "predict.html",
        prediction=prediction,
        probability=probability,
        alert_sent=alert_sent,
    )


# ------------------------------------------------
# API FOR PREDICTION PAGE (USED BY YOUR JS)
# ------------------------------------------------
@app.route("/reverse_geocode")
def reverse_geocode():
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    print("Received reverse geocode request:", lat, lon)  # 🔍 debug

    if not lat or not lon:
        return jsonify({"name": "Unknown Location"})

    try:
        url = f"https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "zoom": 10,          # more accurate
            "addressdetails": 1  # return city, state, country
        }

        headers = {
            "User-Agent": "ForestFireDetectionSystem/1.0"  # REQUIRED OR API REJECTS
        }

        response = requests.get(url, params=params, headers=headers, timeout=8)
        data = response.json()

        # BEST SAFE NAME SELECTION
        name = data.get("display_name") or "Unknown Location"

    except Exception as e:
        print("Reverse geocode error:", e)  # debug error
        name = "Unknown Location"

    return jsonify({"name": name})


@app.route("/get_weather")
def get_weather_route():
    """
    Used by predict.html JS: /get_weather?lat=..&lon=..
    Returns temperature, humidity, wind, rain, drought.
    """
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if not lat or not lon:
        return jsonify({"error": "missing_lat_lon"}), 400

    try:
        w = requests.get(
            f"{WEATHER_URL}?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric",
            timeout=7,
        ).json()

        data = {
            "temperature": w["main"]["temp"],
            "humidity": w["main"]["humidity"],
            "wind": w["wind"]["speed"],
            "rain": w.get("rain", {}).get("1h", 0.0),
            "drought": 0,
        }
        return jsonify(data)
    except Exception as e:
        logger.error(f"/get_weather failed: {e}")
        return jsonify({"error": "weather_fetch_failed"}), 500


@app.route("/trigger_alert", methods=["POST"])
def trigger_alert():
    """
    Called from predict.html JS when frontend detects temp > 30°C.
    Triggers WhatsApp + repeated call (with cooldown).
    """
    global _last_predict_alert_time

    data = request.get_json() or {}
    lat = data.get("lat")
    lon = data.get("lon")
    temp = data.get("temp")
    humidity = data.get("humidity")
    wind = data.get("wind")

    now = time.time()
    if now - _last_predict_alert_time < PREDICT_ALERT_COOLDOWN:
        logger.info("Alert cooldown active, skipping new alert.")
        return jsonify({"status": "cooldown_active"})

    _last_predict_alert_time = now

    send_whatsapp_alert(
        lat,
        lon,
        "Prediction Page (Map Selected Area)",
        temp=temp,
        humidity=humidity,
        wind=wind,
    )
    threading.Thread(target=send_repeated_call_alert).start()

    return jsonify({"status": "alert_sent"})








# ------------------------------------------------
# SATELLITE PAGE (THIS WAS MISSING!)
# ------------------------------------------------
@app.route("/satellite")
def satellite_page():
    return render_template("satellite.html")  # or satellite.html

# ------------------------------------------------
# SATELLITE PAGE
# ------------------------------------------------


import os, random
from flask import request, jsonify
from prediction.satellite_predictor import model, predict_satellite_image



# Directly use your dataset
DATASET = "static/satellite_dataset/train/"
WILDFIRE_DIR = DATASET + "wildfire/"
NONWILDFIRE_DIR = DATASET + "nowildfire/"

@app.route("/get_wildfire_image")
def get_wildfire_image():
    img = random.choice(os.listdir(WILDFIRE_DIR))
    return jsonify({"image": WILDFIRE_DIR + img})

@app.route("/get_nonwildfire_image")
def get_nonwildfire_image():
    img = random.choice(os.listdir(NONWILDFIRE_DIR))
    return jsonify({"image": NONWILDFIRE_DIR + img})

@app.route("/predict_satellite", methods=["POST"])
def predict_satellite():
    data = request.get_json()
    image_path = data["image"]

    result, confidence = predict_satellite_image(image_path)  # returns both

    return jsonify({"result": result, "confidence": confidence})



# ------------------------------------------------
# RUN
# ------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
