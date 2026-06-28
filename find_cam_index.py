import cv2

print("🔍 Scanning for available cameras...\n")

for i in range(0, 10):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        print(f"✅ Camera works at index: {i}")
    else:
        print(f"❌ No camera at index: {i}")
    cap.release()

print("\n✅ Scan complete!")
