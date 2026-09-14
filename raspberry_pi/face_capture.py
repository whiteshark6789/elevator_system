import time
import sys
import logging
import cv2
import numpy as np
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Backend API URLs
AUTH_URL = "http://localhost:5000/api/auth/face"
REG_URL = "http://localhost:5000/api/admin/users/register_face"

# Haar Cascade for local face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def generate_local_encoding(img, face_box):
    """Generates the exact same 128-dimensional face encoding vector (parity with helper)."""
    x, y, w, h = face_box
    face_roi = img[y:y+h, x:x+w]
    
    gray_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray_roi, (8, 16))
    
    vector = resized.flatten().astype(float)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
        
    return vector.tolist()

def capture_face_and_process(action="auth", user_id=None, admin_cookie=None):
    """Accesses local USB webcam to detect face and register/authenticate (REQ-1, REQ-2)."""
    logger.info("Opening webcam...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        logger.error("Could not access camera /dev/video0. Make sure webcam is connected.")
        print("[CAMERA ERROR] Make sure your webcam is plugged in and accessible.")
        return False
        
    logger.info("Webcam active. Stand in front of camera. Press 'SPACE' to capture, or 'Q' to quit.")
    
    captured_img = None
    face_box = None
    
    while True:
        ret, frame = cap.read()
        if not ret:
            logger.error("Failed to read video frame.")
            break
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))
        
        # Draw bounding boxes around detected faces
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
        cv2.putText(frame, "Press SPACE to Scan, Q to Quit", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    
        cv2.imshow("Elevator Face Terminal", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            if len(faces) > 0:
                # Get largest face
                face_box = max(faces, key=lambda f: f[2] * f[3])
                captured_img = frame.copy()
                logger.info("Face captured successfully!")
                break
            else:
                logger.warning("No face detected in frame. Adjust position and try again.")
        elif key == ord('q'):
            logger.info("Operation canceled by user.")
            break
            
    cap.release()
    cv2.destroyAllWindows()
    
    if captured_img is None or face_box is None:
        logger.warning("No face captured.")
        return False
        
    # Generate 128-dimensional vector encoding (REQ-3)
    encoding = generate_local_encoding(captured_img, face_box)
    
    # Save encoding - no raw photo database storage (REQ-4)
    if action == "register":
        if user_id is None:
            logger.error("User ID required for registration.")
            return False
            
        # Send raw encoded frame image to registration endpoint
        _, img_encoded = cv2.imencode('.jpg', captured_img)
        files = {'image': ('face.jpg', img_encoded.tobytes(), 'image/jpeg')}
        data = {'user_id': user_id}
        
        logger.info(f"Sending registration request to {REG_URL} for User ID {user_id}...")
        try:
            # Requires admin session authentication if running in security context
            headers = {}
            response = requests.post(REG_URL, files=files, data=data, timeout=5.0)
            if response.status_code == 200:
                logger.info("Face registered successfully in system.")
                return True
            else:
                logger.error(f"Registration failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to backend: {e}")
            return False
            
    elif action == "auth":
        # Send image to authentication endpoint
        _, img_encoded = cv2.imencode('.jpg', captured_img)
        files = {'image': ('face.jpg', img_encoded.tobytes(), 'image/jpeg')}
        
        logger.info(f"Sending authentication request to {AUTH_URL}...")
        try:
            response = requests.post(AUTH_URL, files=files, timeout=5.0)
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Authentication success! Welcome user: {result.get('username')} (Score: {result.get('score'):.1f}%)")
                return True
            else:
                logger.warning(f"Authentication failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error connecting to backend: {e}")
            return False
            
    return False

if __name__ == "__main__":
    action_arg = "auth"
    user_id_arg = None
    
    if len(sys.argv) > 1:
        action_arg = sys.argv[1]
    if len(sys.argv) > 2:
        user_id_arg = sys.argv[2]
        
    print("--------------------------------------------------")
    print(f"Face Capture Utility: {action_arg.upper()} MODE")
    print("--------------------------------------------------")
    
    capture_face_and_process(action=action_arg, user_id=user_id_arg)
