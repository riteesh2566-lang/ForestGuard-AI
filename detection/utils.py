# utils
import base64
import cv2
import numpy as np

def read_image_from_bytes(file_bytes):
    arr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img

def to_png_base64(img_bgr):
    _, buf = cv2.imencode('.png', img_bgr)
    return base64.b64encode(buf.tobytes()).decode('utf-8')
