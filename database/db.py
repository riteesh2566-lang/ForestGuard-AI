# database/db.py

from pymongo import MongoClient
from datetime import datetime
from bson import ObjectId
import os   # 👈 REQUIRED for delete function

# ==============================
# 1) DATABASE CONNECTION SETUP
# ==============================
def get_db():
    """
    Returns database connection.
    Helps prevent duplicate connections.
    """
    client = MongoClient("mongodb://localhost:27017/")
    db = client["forest_fire_project_v3"]  # ✔ Your correct DB name
    return db  # 👈 CRUCIAL: must return db

# Use single global DB reference
db = get_db()
recordings_col = db["recordings"]   # Collection to store all recordings


# ==============================
# 2) SAVE RECORDING DETAILS
# ==============================
def save_recording(filename, camera_source="webcam"):
    """
    Saves the recording file info to MongoDB.
    Only stores metadata (NOT the video file).
    """
    try:
        doc = {
            "filename": filename,         # e.g. webcam_20251121_140210.avi
            "camera": camera_source,      # 'webcam' or 'ip-rtsp-url'
            "timestamp": datetime.now()
        }
        recordings_col.insert_one(doc)
        print(f"[DB] Saved: {filename}")
    except Exception as e:
        print(f"[ERROR] Could not save recording: {e}")


# ==============================
# 3) FETCH ALL RECORDINGS
# ==============================
def get_all_recordings():
    """
    Returns all recorded videos sorted by latest.
    """
    try:
        return list(recordings_col.find().sort("timestamp", -1))
    except Exception as e:
        print(f"[ERROR] Could not read database: {e}")
        return []


# ==============================
# 4) FETCH ONE RECORD (OPTIONAL)
# ==============================
def get_recording_by_id(record_id):
    """
    Get details of one recording using MongoDB ObjectId.
    """
    try:
        return recordings_col.find_one({"_id": ObjectId(record_id)})
    except Exception as e:
        print(f"[ERROR] Could not retrieve recording: {e}")
        return None


# ==============================
# 5) DELETE RECORDING FILE + DB
# ==============================
def delete_recording(record_id):
    """
    Deletes video file from /recordings folder + DB data.
    """
    try:
        rec = recordings_col.find_one({"_id": ObjectId(record_id)})

        if rec:
            filepath = os.path.join("recordings", rec["filename"])
            if os.path.exists(filepath):
                os.remove(filepath)  # delete video

            recordings_col.delete_one({"_id": ObjectId(record_id)})
            print(f"[DB] Deleted: {record_id}")

    except Exception as e:
        print("[ERROR] Delete failed:", e)
