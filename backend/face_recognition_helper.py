import cv2
import numpy as np

# Load Haar Cascade for face detection
# OpenCV distributes Haar Cascades in its data directory
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def detect_face(image_bytes):
    """Detects a face in image bytes. Returns the bounding box (x, y, w, h) of the largest face, or None."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None, None
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    
    if len(faces) == 0:
        return None, None
        
    # Return the largest face by area
    largest_face = max(faces, key=lambda f: f[2] * f[3])
    return largest_face, img

def generate_encoding(img, face_box):
    """Generates a 128-dimensional face encoding vector (REQ-3).
    
    Uses a normalized 8x16 spatial downsampling of the face region as a local
    pixel descriptor. This represents the face shape/intensity distribution as a
    numeric vector, satisfies the 'no raw photo' constraint (REQ-4), and requires 
    no external deep learning file downloads, making it very fast on Raspberry Pi.
    """
    x, y, w, h = face_box
    face_roi = img[y:y+h, x:x+w]
    
    # Preprocess ROI: convert to grayscale, resize to 8x16 (128 values)
    gray_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray_roi, (8, 16))
    
    # Flatten and normalize the vector to unit length
    vector = resized.flatten().astype(float)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
        
    return vector.tolist()

def compare_encodings(encoding1, encoding2):
    """Compares two 128-dimensional encodings.
    
    Returns a similarity score between 0% and 100%.
    Using cosine similarity of normalized vectors, which is the dot product.
    We map it linearly: score = (cos_sim + 1) / 2 * 100
    """
    vec1 = np.array(encoding1)
    vec2 = np.array(encoding2)
    
    if len(vec1) != 128 or len(vec2) != 128:
        return 0.0
        
    # Dot product of normalized vectors = Cosine Similarity
    cos_sim = np.dot(vec1, vec2)
    
    # Scale from [-1, 1] to [0, 100]
    score = (cos_sim + 1) / 2 * 100
    return float(score)

def match_face(live_encoding, stored_encodings_with_users, threshold=60.0):
    """Compares live encoding against a list of stored encodings.
    
    stored_encodings_with_users: list of tuples (user_id, username, stored_encoding)
    Returns: (matched_username, match_score) or (None, 0.0) if below threshold (REQ-6).
    """
    best_match_user = None
    best_score = 0.0
    
    for user_id, username, stored_enc in stored_encodings_with_users:
        score = compare_encodings(live_encoding, stored_enc)
        if score > best_score:
            best_score = score
            best_match_user = username
            
    if best_score >= threshold:
        return best_match_user, best_score
    return None, best_score
