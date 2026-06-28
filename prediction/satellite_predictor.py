import tensorflow as tf
import numpy as np
from tensorflow.keras.preprocessing.image import load_img, img_to_array

MODEL_PATH = "models/satellite_fire_model.h5"
model = tf.keras.models.load_model(MODEL_PATH)  # Load once here

IMG_SIZE = (224, 224)

def predict_satellite_image(image_path):
    img = load_img(image_path, target_size=IMG_SIZE)
    img_array = img_to_array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)

    prob = model.predict(img_array)[0][0]  # float
    confidence = round(prob * 100, 2)

    if prob > 0.5:
        return "🔥 Wildfire Detected!", confidence
    else:
        return "🟢 No Fire Detected", confidence
