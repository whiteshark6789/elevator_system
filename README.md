# Secure Elevator Access System

This is a comprehensive, secure elevator access system prototype designed for Raspberry Pi 4/5, integrating Face Recognition, RFID Authentication, One-Time Password (OTP) verification, and an Admin Management Dashboard.

## Architecture Layout

```
├── backend/                       # Python Flask server & core logic API
│   ├── app.py                     # Main Flask router & session coordinator
│   ├── db.py                      # Neon DB PostgreSQL interface & migration manager
│   ├── face_recognition_helper.py # Face recognition encoding and matcher
│   ├── requirements.txt           # Backend python dependencies
│   ├── static/                    # Material Design 3 CSS & styles
│   └── templates/                 # Jinja2 HTML user portal panels
├── database/                      # Neon DB (PostgreSQL) migrations folder
│   └── migrations/
│       ├── 01_init_schema.sql     # Database structure (users, logs, credentials)
│       └── 02_indexes.sql         # Logging tables optimization indexes
├── raspberry_pi/                  # Isolated hardware control scripts
│   ├── hardware.py                # GPIO pin mappings (LEDs, Buzzer, Relays)
│   ├── rfid_daemon.py             # Background RFID MFRC522 card reader daemon
│   └── face_capture.py            # Local OpenCV camera frame encoder
└── tests/                         # Automated unit tests
    └── test_auth.py               # Authentication, rate limit, and validation logic tests
```

---

## Installation & Setup

### 1. Set Up Neon Database (PostgreSQL)
Create a new serverless PostgreSQL project on [Neon](https://neon.tech/) (or use a local Postgres database). 
Once created, retrieve your database connection string.

### 2. Configure Local Environment
Initialize a Python virtual environment and install backend dependencies:

```bash
# Clone or enter project directory
cd "Actual Project"

# Create a virtual environment
python -m venv venv

# Activate virtual environment
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux / macOS:
source venv/bin/activate

# Install required dependencies
pip install -r backend/requirements.txt
```

### 3. Run Database Migrations & Start Server
Expose your Neon DB connection string as an environment variable and launch the Flask server:

```powershell
# On Windows PowerShell:
$env:DATABASE_URL="postgresql://[username]:[password]@[neon-host]/[dbname]?sslmode=require"
$env:FLASK_SECRET_KEY="your-custom-secure-key"
python backend/app.py

# On Linux / macOS:
export DATABASE_URL="postgresql://[username]:[password]@[neon-host]/[dbname]?sslmode=require"
export FLASK_SECRET_KEY="your-custom-secure-key"
python backend/app.py
```

*Note: The Flask application will automatically run migration scripts in `database/migrations/` on start to initialize all tables and indexes, and will seed the default admin account if it does not exist.*

Default Admin Account credentials (automatically seeded):
- **Username**: `admin`
- **Password**: `Admin123!`

---

## Running Automated Logic Tests

To execute the unit test suites (which mock database and hardware APIs to test authentication rules, rate limits, OTP validity, and permission exclusions):

```bash
python -m unittest tests/test_auth.py
```

---

## Running Raspberry Pi Hardware Daemons

On the physical Raspberry Pi, run the following background services to capture hardware events:

### RFID Daemon
Performs continuous SPI reads for MFRC522 card readers. Sends scan records to the local Flask backend.
```bash
python raspberry_pi/rfid_daemon.py
```
*Note: If run on a non-Pi developer device, the daemon automatically falls back to an interactive console prompt allowing you to input Card UIDs manually for verification.*

### Face Recognition Capture Daemon
Accesses the webcam via OpenCV to verify face encodings in real-time or register new faces:
```bash
# To run local authentication terminal:
python raspberry_pi/face_capture.py auth

# To register a face profile for User ID 3:
python raspberry_pi/face_capture.py register 3
```

---

## Design System: Material Design 3 (M3)
The frontend implements Google's **Material Design 3** philosophy:
- **Baseline Palette**: Rich dynamic layout using deep violet primary accents, subtle surface variations, outline containers, and designated green/red status markers.
- **Micro-interactions**: Ripple responses on action items, transitions, state switches, and circular loaders.
- **Audio Feedback**: The elevator terminal console uses the Web Audio API to play metallic keypad clicks, access-granted door chimes, and access-denied warnings (matching physical buzzer triggers).
