import cv2
from detection.fire_detector import detect_fire

cap = cv2.VideoCapture(0)  # webcam

while True:
    ok, frame = cap.read()
    if not ok:
        continue

    original, overlay, fire_pixels, flag, _, debug = detect_fire(frame)

    cv2.imshow("Fire Detection Test", overlay)
    print(flag, fire_pixels, debug)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
