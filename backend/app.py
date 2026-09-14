import os
import random
import string
import datetime
import bcrypt
import logging
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from datetime import timedelta
from db import DatabaseManager
# import face_recognition_helper # TEMPORARILY DISABLED to test if OpenCV is crashing Vercel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure absolute paths for Vercel deployment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "m3-elevator-secure-key-1893")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# Try importing RPi.GPIO for Raspberry Pi hardware control
try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except (ImportError, RuntimeError):
    HAS_GPIO = False
    logger.warning("RPi.GPIO not detected. Running in hardware simulation mode.")

# Hardware Pins configuration (REQ-52)
GREEN_LED_PIN = 18
RED_LED_PIN = 23
BUZZER_PIN = 24
RELAY_PINS = {
    1: 5,  # Floor 1 -> GPIO 5
    2: 6,  # Floor 2 -> GPIO 6
    3: 13, # Floor 3 -> GPIO 13
    4: 19, # Floor 4 -> GPIO 19
    5: 26  # Floor 5 -> GPIO 26
}

def init_hardware():
    if HAS_GPIO:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(GREEN_LED_PIN, GPIO.OUT)
        GPIO.setup(RED_LED_PIN, GPIO.OUT)
        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        for pin in RELAY_PINS.values():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        GPIO.output(GREEN_LED_PIN, GPIO.LOW)
        GPIO.output(RED_LED_PIN, GPIO.LOW)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        logger.info("Hardware GPIO pins initialized successfully.")

# Initialize Hardware
with app.app_context():
    init_hardware()
    
    # We remove init_db() and admin seeding from here to prevent Vercel Serverless Function 
    # timeouts on cold starts (Neon DB can take 3-5 seconds to wake up). 
    # The database has already been fully initialized and seeded!

# Loggers
def log_auth(username, method, result):
    DatabaseManager.execute_query(
        "INSERT INTO auth_logs (username, method, result) VALUES (%s, %s, %s)",
        (username, method, result)
    )

def log_access(username, floor, result):
    DatabaseManager.execute_query(
        "INSERT INTO access_logs (username, floor, result) VALUES (%s, %s, %s)",
        (username, floor, result)
    )

# Hardware Control Helpers
def trigger_access_granted(floor):
    logger.info(f"ACCESS GRANTED for floor {floor}. Triggering relay.")
    if HAS_GPIO:
        # Green LED on
        GPIO.output(GREEN_LED_PIN, GPIO.HIGH)
        # Pulse corresponding relay
        if floor in RELAY_PINS:
            relay_pin = RELAY_PINS[floor]
            GPIO.output(relay_pin, GPIO.HIGH)
            # Sleep 1s and set low
            import time
            time.sleep(1.0)
            GPIO.output(relay_pin, GPIO.LOW)
        GPIO.output(GREEN_LED_PIN, GPIO.LOW)

def trigger_access_denied():
    logger.warning("ACCESS DENIED. Triggering warning signals.")
    if HAS_GPIO:
        GPIO.output(RED_LED_PIN, GPIO.HIGH)
        # Beep buzzer
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        import time
        time.sleep(1.0)
        GPIO.output(RED_LED_PIN, GPIO.LOW)
        GPIO.output(BUZZER_PIN, GPIO.LOW)

# Security Checks
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

# Routes - UI Pages

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('elevator_panel'))
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    return render_template('signup.html')

@app.route('/admin')
@login_required
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('elevator_panel'))
    return render_template('admin.html')

@app.route('/elevator')
@login_required
def elevator_panel():
    return render_template('elevator.html')

# Authentication APIs

@app.route('/api/auth/signup', methods=['POST'])
def auth_signup():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    name = data.get('name')
    
    if not username or not password or not name:
        return jsonify({"error": "Username, password, and name are required"}), 400
        
    if len(password) < 8 or not any(c.isupper() for c in password) or not any(c.islower() for c in password) or not any(c.isdigit() for c in password):
        return jsonify({"error": "Password must be at least 8 characters long, contain an uppercase letter, lowercase letter, and a number."}), 400
        
    existing = DatabaseManager.execute_one("SELECT 1 FROM users WHERE username = %s", (username,))
    if existing:
        return jsonify({"error": "Username already exists"}), 409
        
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    DatabaseManager.execute_query(
        "INSERT INTO users (username, password_hash, name, role) VALUES (%s, %s, %s, 'resident')",
        (username, hashed, name)
    )
    
    log_auth(username, "signup", "success")
    return jsonify({"success": True, "redirect": url_for('login_page')})

@app.route('/api/auth/password', methods=['POST'])
def auth_password():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
        
    user = DatabaseManager.execute_one(
        "SELECT id, username, password_hash, name, role, is_active, approval_status FROM users WHERE username = %s", 
        (username,)
    )
    
    if not user:
        log_auth(username, "password", "fail_invalid_user")
        return jsonify({"error": "Invalid username or password"}), 401
        
    user_id, uname, pwd_hash, name, role, is_active, approval_status = user
    
    if approval_status == 'pending':
        log_auth(username, "password", "fail_user_pending")
        return jsonify({"error": "Account is pending admin approval."}), 403
        
    if not is_active:
        log_auth(username, "password", "fail_user_inactive")
        return jsonify({"error": "Account is deactivated"}), 403
        
    # Check failed login rate limits (REQ-55: 5 failed attempts locks account for 15 mins)
    recent_fails = DatabaseManager.execute_one(
        """SELECT COUNT(*) FROM auth_logs 
           WHERE username = %s AND timestamp > NOW() - INTERVAL '15 minutes' 
           AND result LIKE 'fail%%'""", (username,)
    )[0]
    
    if recent_fails >= 5:
        log_auth(username, "password", "fail_account_locked")
        return jsonify({"error": "Account is temporarily locked due to 5 consecutive failures. Try again in 15 minutes."}), 429
        
    if bcrypt.checkpw(password.encode('utf-8'), pwd_hash.encode('utf-8')):
        session.permanent = True
        session['user_id'] = user_id
        session['username'] = uname
        session['name'] = name
        session['role'] = role
        
        log_auth(username, "password", "success")
        return jsonify({"success": True, "redirect": url_for('admin_dashboard') if role == 'admin' else url_for('elevator_panel')})
    else:
        log_auth(username, "password", "fail_incorrect_password")
        return jsonify({"error": "Invalid username or password"}), 401

@app.route('/api/auth/signup', methods=['POST'])
def auth_signup():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    name = data.get('name')
    
    if not username or not password or not name:
        return jsonify({"error": "Username, password, and name are required."}), 400
        
    if len(password) < 8 or not any(c.isupper() for c in password) or not any(c.islower() for c in password) or not any(c.isdigit() for c in password):
        return jsonify({"error": "Password must be at least 8 characters long, contain an uppercase letter, lowercase letter, and a number."}), 400
        
    existing = DatabaseManager.execute_one("SELECT 1 FROM users WHERE username = %s", (username,))
    if existing:
        return jsonify({"error": "Username already exists."}), 409
        
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    with DatabaseManager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, name, role, approval_status) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (username, hashed, name, 'resident', 'pending')
            )
        conn.commit()
        
    return jsonify({"success": True, "message": "Account created successfully. Please wait for admin approval."})

@app.route('/api/auth/face', methods=['POST'])
def auth_face():
    # Receive captured frame (as base64 or raw file)
    if 'image' not in request.files:
        return jsonify({"error": "Image file required"}), 400
        
    img_file = request.files['image']
    img_bytes = img_file.read()
    
    face_box, decoded_img = face_recognition_helper.detect_face(img_bytes)
    if face_box is None:
        log_auth("unknown", "face", "fail_no_face_detected")
        return jsonify({"error": "No face detected in the frame. Please adjust the camera."}), 400
        
    live_encoding = face_recognition_helper.generate_encoding(decoded_img, face_box)
    
    # Query all active stored face encodings
    rows = DatabaseManager.execute_query(
        """SELECT u.id, u.username, fe.encoding FROM face_encodings fe 
           JOIN users u ON fe.user_id = u.id 
           WHERE u.is_active = TRUE""", fetch=True
    )
    
    stored_encodings = []
    for r in rows:
        stored_encodings.append((r[0], r[1], r[2]))
        
    matched_user, score = face_recognition_helper.match_face(live_encoding, stored_encodings, threshold=60.0)
    
    if matched_user:
        user = DatabaseManager.execute_one(
            "SELECT id, username, name, role FROM users WHERE username = %s", (matched_user,)
        )
        session.permanent = True
        session['user_id'] = user[0]
        session['username'] = user[1]
        session['name'] = user[2]
        session['role'] = user[3]
        
        log_auth(matched_user, "face", f"success_score_{score:.1f}")
        return jsonify({"success": True, "username": matched_user, "score": score, "redirect": url_for('elevator_panel')})
    else:
        log_auth("unknown", "face", f"fail_no_match_score_{score:.1f}")
        return jsonify({"error": "Face not recognized. Access Denied.", "score": score}), 401

@app.route('/api/auth/rfid', methods=['POST'])
def auth_rfid():
    data = request.json or {}
    card_uid = data.get('card_uid')
    
    if not card_uid:
        return jsonify({"error": "Card UID required"}), 400
        
    # Match card
    card = DatabaseManager.execute_one(
        """SELECT u.id, u.username, u.name, u.role, u.is_active FROM rfid_cards r 
           JOIN users u ON r.user_id = u.id 
           WHERE r.card_uid = %s""", (card_uid,)
    )
    
    if not card:
        log_auth("unknown_rfid", "rfid", f"fail_invalid_card_{card_uid}")
        return jsonify({"error": "RFID card not recognized"}), 401
        
    user_id, username, name, role, is_active = card
    
    if not is_active:
        log_auth(username, "rfid", "fail_user_inactive")
        return jsonify({"error": "User associated with this card is inactive"}), 403
        
    session.permanent = True
    session['user_id'] = user_id
    session['username'] = username
    session['name'] = name
    session['role'] = role
    
    log_auth(username, "rfid", "success")
    return jsonify({"success": True, "username": username, "redirect": url_for('elevator_panel')})

@app.route('/api/auth/otp', methods=['POST'])
def auth_otp():
    data = request.json or {}
    otp_code = data.get('otp_code')
    
    if not otp_code or len(otp_code) != 6:
        return jsonify({"error": "Valid 6-digit OTP required"}), 400
        
    # Find active non-expired OTP
    otp = DatabaseManager.execute_one(
        """SELECT id, allowed_floors, requested_by FROM visitor_otps 
           WHERE otp_code = %s AND expires_at > NOW() AND is_used = FALSE""", (otp_code,)
    )
    
    if not otp:
        log_auth("visitor", "otp", f"fail_invalid_or_expired_otp_{otp_code}")
        return jsonify({"error": "Invalid or expired OTP code"}), 401
        
    otp_id, allowed_floors, requested_by = otp
    
    # Log in as visitor
    session.permanent = True
    session['user_id'] = f"visitor_{otp_id}"
    session['username'] = f"visitor_{otp_code}"
    session['name'] = "Visitor"
    session['role'] = 'visitor'
    session['allowed_floors'] = allowed_floors
    session['otp_id'] = otp_id
    
    log_auth(f"visitor_{otp_code}", "otp", "success")
    return jsonify({"success": True, "redirect": url_for('elevator_panel')})

@app.route('/logout')
def logout():
    username = session.get('username', 'unknown')
    # If it was a visitor OTP session, invalidate the OTP immediately upon logout/use (REQ-17)
    if session.get('role') == 'visitor' and 'otp_id' in session:
        DatabaseManager.execute_query(
            "UPDATE visitor_otps SET is_used = TRUE WHERE id = %s", (session['otp_id'],)
        )
    session.clear()
    return redirect(url_for('login_page'))

# Elevator Access Control APIs

@app.route('/api/elevator/permissions', methods=['GET'])
@login_required
def get_elevator_permissions():
    """Returns the list of allowed floors for the currently logged-in user."""
    role = session.get('role')
    username = session.get('username')
    
    if role == 'visitor':
        # Visitor permissions are stored directly in session and tied to their OTP
        floors = session.get('allowed_floors', [])
        return jsonify({"username": username, "role": role, "allowed_floors": floors})
        
    # Query database for resident/admin permissions
    rows = DatabaseManager.execute_query(
        "SELECT floor FROM floor_permissions WHERE user_id = %s", (session['user_id'],), fetch=True
    )
    floors = [r[0] for r in rows]
    return jsonify({"username": username, "role": role, "allowed_floors": floors})

@app.route('/api/elevator/request_floor', methods=['POST'])
@login_required
def request_floor():
    """Triggers the relay for a floor if the user has permission (REQ-33, REQ-34)."""
    data = request.json or {}
    floor = data.get('floor')
    
    if floor is None:
        return jsonify({"error": "Floor not specified"}), 400
        
    try:
        floor = int(floor)
    except ValueError:
        return jsonify({"error": "Invalid floor format"}), 400
        
    # Check permissions
    role = session.get('role')
    username = session.get('username')
    allowed = False
    
    if role == 'visitor':
        allowed = (floor in session.get('allowed_floors', []))
    else:
        # Check database permissions
        permission = DatabaseManager.execute_one(
            "SELECT 1 FROM floor_permissions WHERE user_id = %s AND floor = %s",
            (session['user_id'], floor)
        )
        allowed = (permission is not None)
        
    if allowed:
        log_access(username, floor, "granted")
        # Trigger Relay + Green LED (simulated or real hardware)
        trigger_access_granted(floor)
        
        # If visitor logs in, the OTP is invalidated immediately after floor access (REQ-17)
        if role == 'visitor' and 'otp_id' in session:
            DatabaseManager.execute_query(
                "UPDATE visitor_otps SET is_used = TRUE WHERE id = %s", (session['otp_id'],)
            )
            # Log visitor out right after triggering floor button
            session.clear()
            return jsonify({"success": True, "message": f"Floor {floor} requested. Visitor session ended.", "visitor_ended": True})
            
        return jsonify({"success": True, "message": f"Access granted to floor {floor}."})
    else:
        log_access(username, floor, "denied")
        # Trigger Red LED + Buzzer (simulated or real hardware)
        trigger_access_denied()
        return jsonify({"error": f"Access denied to floor {floor}."}), 403

# Admin Management APIs

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_users():
    rows = DatabaseManager.execute_query(
        """SELECT u.id, u.username, u.name, u.role, u.is_active, 
           (SELECT card_uid FROM rfid_cards r WHERE r.user_id = u.id) as rfid,
           (SELECT COUNT(*) FROM face_encodings fe WHERE fe.user_id = u.id) as has_face,
           ARRAY(SELECT floor FROM floor_permissions fp WHERE fp.user_id = u.id ORDER BY floor) as floors
           FROM users u ORDER BY u.id ASC""", fetch=True
    )
    users_list = []
    for r in rows:
        users_list.append({
            "id": r[0],
            "username": r[1],
            "name": r[2],
            "role": r[3],
            "is_active": r[4],
            "rfid_card": r[5],
            "has_face": r[6] > 0,
            "allowed_floors": r[7]
        })
    return jsonify(users_list)

@app.route('/api/admin/users/create', methods=['POST'])
@admin_required
def create_user():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    name = data.get('name')
    role = data.get('role', 'resident')
    floors = data.get('floors', []) # List of integers
    
    if not username or not password or not name:
        return jsonify({"error": "Username, password, and name are required."}), 400
        
    # Validate password complexity (Section 5.3 Security Requirements)
    if len(password) < 8 or not any(c.isupper() for c in password) or not any(c.islower() for c in password) or not any(c.isdigit() for c in password):
        return jsonify({"error": "Password must be at least 8 characters long, contain an uppercase letter, lowercase letter, and a number."}), 400
        
    # Check if username exists
    existing = DatabaseManager.execute_one("SELECT 1 FROM users WHERE username = %s", (username,))
    if existing:
        return jsonify({"error": "Username already exists."}), 409
        
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    with DatabaseManager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, name, role) VALUES (%s, %s, %s, %s) RETURNING id",
                (username, hashed, name, role)
            )
            user_id = cur.fetchone()[0]
            
            # Save permissions (REQ-19)
            for f in floors:
                cur.execute(
                    "INSERT INTO floor_permissions (user_id, floor) VALUES (%s, %s)",
                    (user_id, int(f))
                )
        conn.commit()
        
    # Log admin action
    DatabaseManager.execute_query(
        "INSERT INTO auth_logs (username, method, result) VALUES (%s, %s, %s)",
        (session.get('username'), "admin_action", f"created_user_{username}")
    )
    
    return jsonify({"success": True, "user_id": user_id})

@app.route('/api/admin/users/update_permissions', methods=['POST'])
@admin_required
def update_permissions():
    data = request.json or {}
    user_id = data.get('user_id')
    floors = data.get('floors', []) # List of integers
    
    if user_id is None:
        return jsonify({"error": "User ID required"}), 400
        
    # Validate database constraints: Floor permissions cannot be edited for a user who is mid-authentication (REQ-20 / Section 5.5 Business Rules)
    # We can check if the user had a recent login in the last 10 seconds.
    recent_auth = DatabaseManager.execute_one(
        """SELECT 1 FROM auth_logs JOIN users u ON auth_logs.username = u.username 
           WHERE u.id = %s AND auth_logs.timestamp > NOW() - INTERVAL '10 seconds'""", (user_id,)
    )
    if recent_auth:
        return jsonify({"error": "Cannot update permissions. User is currently authenticating."}), 423
        
    with DatabaseManager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM floor_permissions WHERE user_id = %s", (user_id,))
            for f in floors:
                cur.execute(
                    "INSERT INTO floor_permissions (user_id, floor) VALUES (%s, %s)",
                    (user_id, int(f))
                )
        conn.commit()
        
    # Retrieve username for log
    username = DatabaseManager.execute_one("SELECT username FROM users WHERE id = %s", (user_id,))
    if username:
        DatabaseManager.execute_query(
            "INSERT INTO auth_logs (username, method, result) VALUES (%s, %s, %s)",
            (session.get('username'), "admin_action", f"updated_perms_{username[0]}")
        )
        
    return jsonify({"success": True})

@app.route('/api/admin/users/toggle_active', methods=['POST'])
@admin_required
def toggle_active():
    data = request.json or {}
    user_id = data.get('user_id')
    
    if user_id is None:
        return jsonify({"error": "User ID required"}), 400
        
    user = DatabaseManager.execute_one("SELECT is_active, username FROM users WHERE id = %s", (user_id,))
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    new_state = not user[0]
    DatabaseManager.execute_query("UPDATE users SET is_active = %s WHERE id = %s", (new_state, user_id))
    
    # Log admin action
    DatabaseManager.execute_query(
        "INSERT INTO auth_logs (username, method, result) VALUES (%s, %s, %s)",
        (session.get('username'), "admin_action", f"toggle_active_{user[1]}_to_{new_state}")
    )
    
    return jsonify({"success": True, "is_active": new_state})

@app.route('/api/admin/users/delete', methods=['POST'])
@admin_required
def delete_user():
    data = request.json or {}
    user_id = data.get('user_id')
    
    if user_id is None:
        return jsonify({"error": "User ID required"}), 400
        
    user = DatabaseManager.execute_one("SELECT username FROM users WHERE id = %s", (user_id,))
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    if user[0] == "admin":
        return jsonify({"error": "Cannot delete default admin account"}), 400
        
    DatabaseManager.execute_query("DELETE FROM users WHERE id = %s", (user_id,))
    
    # Log admin action
    DatabaseManager.execute_query(
        "INSERT INTO auth_logs (username, method, result) VALUES (%s, %s, %s)",
        (session.get('username'), "admin_action", f"deleted_user_{user[0]}")
    )
    
    return jsonify({"success": True})

@app.route('/api/admin/users/register_rfid', methods=['POST'])
@admin_required
def register_rfid():
    data = request.json or {}
    user_id = data.get('user_id')
    card_uid = data.get('card_uid')
    
    if user_id is None or not card_uid:
        return jsonify({"error": "User ID and Card UID required"}), 400
        
    # Check if card exists
    exists = DatabaseManager.execute_one("SELECT u.username FROM rfid_cards r JOIN users u ON r.user_id = u.id WHERE r.card_uid = %s", (card_uid,))
    if exists:
        return jsonify({"error": f"Card already assigned to user {exists[0]}."}), 409
        
    with DatabaseManager.get_connection() as conn:
        with conn.cursor() as cur:
            # Delete old card if exists
            cur.execute("DELETE FROM rfid_cards WHERE user_id = %s", (user_id,))
            cur.execute("INSERT INTO rfid_cards (user_id, card_uid) VALUES (%s, %s)", (user_id, card_uid))
        conn.commit()
        
    # Log action
    username = DatabaseManager.execute_one("SELECT username FROM users WHERE id = %s", (user_id,))
    if username:
        DatabaseManager.execute_query(
            "INSERT INTO auth_logs (username, method, result) VALUES (%s, %s, %s)",
            (session.get('username'), "admin_action", f"register_rfid_{username[0]}_card_{card_uid}")
        )
        
    return jsonify({"success": True})

@app.route('/api/admin/users/register_face', methods=['POST'])
@admin_required
def register_face():
    # Capture webcam photo, extract encoding, and register it for the user
    user_id = request.form.get('user_id')
    if 'image' not in request.files or user_id is None:
        return jsonify({"error": "User ID and image file required"}), 400
        
    img_file = request.files['image']
    img_bytes = img_file.read()
    
    face_box, decoded_img = face_recognition_helper.detect_face(img_bytes)
    if face_box is None:
        return jsonify({"error": "No face detected in the photo. Please check camera alignment."}), 400
        
    live_encoding = face_recognition_helper.generate_encoding(decoded_img, face_box)
    
    with DatabaseManager.get_connection() as conn:
        with conn.cursor() as cur:
            # Remove any existing face encodings for this user
            cur.execute("DELETE FROM face_encodings WHERE user_id = %s", (user_id,))
            # Save new encoding
            cur.execute("INSERT INTO face_encodings (user_id, encoding) VALUES (%s, %s)", (user_id, live_encoding))
        conn.commit()
        
    username = DatabaseManager.execute_one("SELECT username FROM users WHERE id = %s", (user_id,))
    if username:
        DatabaseManager.execute_query(
            "INSERT INTO auth_logs (username, method, result) VALUES (%s, %s, %s)",
            (session.get('username'), "admin_action", f"register_face_{username[0]}")
        )
        
    return jsonify({"success": True, "message": "Face registration complete."})

@app.route('/api/admin/otp/generate', methods=['POST'])
@admin_required
def generate_visitor_otp():
    """Generates a random 6-digit OTP code with a 30-minute expiry (REQ-13, REQ-14)."""
    data = request.json or {}
    floors = data.get('floors', [])
    
    if not floors:
        return jsonify({"error": "At least one floor must be selected"}), 400
        
    # Convert floors list to integers
    try:
        floors = [int(f) for f in floors]
    except ValueError:
        return jsonify({"error": "Invalid floor list format"}), 400
        
    # Generate 6 digit numeric code
    otp_code = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.datetime.now() + datetime.timedelta(minutes=30)
    
    DatabaseManager.execute_query(
        """INSERT INTO visitor_otps (otp_code, requested_by, allowed_floors, expires_at) 
           VALUES (%s, %s, %s, %s)""",
        (otp_code, session['user_id'], floors, expires_at)
    )
    
    # Log action
    DatabaseManager.execute_query(
        "INSERT INTO auth_logs (username, method, result) VALUES (%s, %s, %s)",
        (session.get('username'), "admin_action", f"generate_otp_{otp_code}_floors_{floors}")
    )
    
    return jsonify({"success": True, "otp_code": otp_code, "expires_at": expires_at.isoformat()})

@app.route('/api/admin/logs/auth', methods=['GET'])
@admin_required
def get_auth_logs():
    # Filtering queries (REQ-42, REQ-44)
    username = request.args.get('username')
    method = request.args.get('method')
    date_str = request.args.get('date') # YYYY-MM-DD
    
    query = "SELECT timestamp, username, method, result FROM auth_logs WHERE 1=1"
    params = []
    
    if username:
        query += " AND username ILIKE %s"
        params.append(f"%{username}%")
    if method:
        query += " AND method = %s"
        params.append(method)
    if date_str:
        query += " AND DATE(timestamp) = %s"
        params.append(date_str)
        
    query += " ORDER BY timestamp DESC LIMIT 200"
    
    rows = DatabaseManager.execute_query(query, params, fetch=True)
    logs = [{"timestamp": r[0].isoformat(), "username": r[1], "method": r[2], "result": r[3]} for r in rows]
    return jsonify(logs)

@app.route('/api/admin/logs/access', methods=['GET'])
@admin_required
def get_access_logs():
    # Filtering queries (REQ-43, REQ-44)
    username = request.args.get('username')
    floor = request.args.get('floor')
    date_str = request.args.get('date') # YYYY-MM-DD
    
    query = "SELECT timestamp, username, floor, result FROM access_logs WHERE 1=1"
    params = []
    
    if username:
        query += " AND username ILIKE %s"
        params.append(f"%{username}%")
    if floor:
        try:
            query += " AND floor = %s"
            params.append(int(floor))
        except ValueError:
            pass
    if date_str:
        query += " AND DATE(timestamp) = %s"
        params.append(date_str)
        
    query += " ORDER BY timestamp DESC LIMIT 200"
    
    rows = DatabaseManager.execute_query(query, params, fetch=True)
    logs = [{"timestamp": r[0].isoformat(), "username": r[1], "floor": r[2], "result": r[3]} for r in rows]
    return jsonify(logs)

if __name__ == '__main__':
    # Start the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)

