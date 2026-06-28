import cv2
import numpy as np
import time

prev_mask = None
last_fire_time = 0
ALERT_HOLD = 5

def detect_fire(frame):
    global prev_mask, last_fire_time

    frame = cv2.resize(frame, (640, 480))
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # 🔥 STRONG HSV RANGE (less false alarm)
    lower_fire = np.array([10, 160, 180])   # 🔐 sun/bulb/cloth removed
    upper_fire = np.array([30, 255, 255])

    fire_color = cv2.inRange(hsv, lower_fire, upper_fire)

    # 🔎 BOOST REAL FLAME SIGNAL
    blur = cv2.GaussianBlur(fire_color, (7, 7), 0)
    thresh = cv2.threshold(blur, 200, 255, cv2.THRESH_BINARY)[1]
    combined = cv2.bitwise_or(fire_color, thresh)

    # 🚫 BLOCK SKIN
    skin_lower = np.array([0, 40, 80])
    skin_upper = np.array([20, 200, 200])
    skin_mask = cv2.inRange(hsv, skin_lower, skin_upper)
    combined = cv2.bitwise_and(combined, cv2.bitwise_not(skin_mask))

    # 🧠 MOTION CHECK
    if prev_mask is None:
        prev_mask = combined
        motion = combined
    else:
        motion = cv2.absdiff(combined, prev_mask)
        prev_mask = combined.copy()

    moving_pixels = np.sum(motion > 25)
    fire_pixels = np.sum(combined > 0)

    overlay = frame.copy()

    # 🧠 SMART DECISION
    if fire_pixels > 2500:       # 🆕 bigger threshold = less false fire
        flag = "FIRE LIKELY"
    elif fire_pixels > 200 and moving_pixels > 20:
        flag = "FIRE LIKELY"
    else:
        flag = "SAFE"

    # 🔁 SHAPE CHECK (ONLY REAL FIRE)
    contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 120 < area < 3500:    # 🆕 larger area range
            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = h / float(w)
            if aspect_ratio > 1.3:    # 🆕 flame is tall
                cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 255), 2)
                flag = "FIRE LIKELY"

    # 🔥 HOLD ALERT
    if flag == "FIRE LIKELY":
        last_fire_time = time.time()

    if time.time() - last_fire_time < ALERT_HOLD:
        flag = "🔥 FIRE ALERT!"
        cv2.putText(overlay, "🔥 FIRE ALERT!", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

    debug = {
        "fire_pixels": int(fire_pixels),
        "movement": int(moving_pixels),
        "flag": flag
    }

    return frame, overlay, fire_pixels, flag, [], debug
