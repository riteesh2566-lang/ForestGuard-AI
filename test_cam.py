import cv2

def test_camera(index=0):
    print(f"🎥 Opening camera index {index} ...")
    cap = cv2.VideoCapture(index)

    if not cap.isOpened():
        print("❌ Failed to open camera. Try a different index (1, 2, etc.)")
        return

    print("✅ Camera opened successfully. Press 'q' to quit window.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("⚠️ Failed to grab frame.")
            break

        cv2.imshow("Camera Test - Press 'q' to close", frame)

        # Press q to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Camera closed successfully.")

if __name__ == "__main__":
    test_camera(0)
