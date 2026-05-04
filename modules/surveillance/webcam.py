import cv2, os, base64, time

def capture_webcam(cam_index=0):
    """
    Captures a single frame from the webcam and returns it as a base64 string.
    """
    try:
        cap = cv2.VideoCapture(cam_index)
        if not cap.isOpened():
            return "Error: Could not open webcam."
        
        # Warm up the camera
        for _ in range(5): cap.read()
        
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return "Error: Could not capture image."
        
        # Encode to JPEG
        _, buffer = cv2.imencode('.jpg', frame)
        b64_data = base64.b64encode(buffer).decode('utf-8')
        return b64_data
    except Exception as e:
        return f"Error: {e}"
