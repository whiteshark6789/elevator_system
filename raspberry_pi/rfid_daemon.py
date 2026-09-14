import time
import sys
import logging
import requests
import hardware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Backend API server URL
API_URL = "http://localhost:5000/api/auth/rfid"

# Try importing the physical SPI RFID reader library
try:
    from mfrc522 import SimpleMFRC522
    reader = SimpleMFRC522()
    HAS_READER = True
    logger.info("MFRC522 hardware reader library loaded.")
except ImportError:
    HAS_READER = False
    logger.warning("mfrc522 library not found. Running in simulation mode (Input Card UID via command line).")

def authenticate_rfid_with_server(card_uid):
    """Sends card UID to the Flask backend for verification."""
    logger.info(f"Sending authentication request for Card UID: {card_uid}")
    try:
        response = requests.post(
            API_URL, 
            json={"card_uid": card_uid}, 
            timeout=3.0
        )
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Access GRANTED for user: {result.get('username')}")
            # Visual feedback on Pi hardware
            hardware.indicate_access_granted()
            return True
        else:
            logger.warning(f"Access DENIED: {response.text}")
            hardware.indicate_access_denied()
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to backend server at {API_URL}: {e}")
        hardware.indicate_access_denied()
        return False

def run_rfid_scanner():
    """Main scanning loop (REQ-8, REQ-9)."""
    hardware.setup_pins()
    logger.info("RFID Scanner daemon started. Ready to scan...")

    try:
        while True:
            if HAS_READER:
                try:
                    logger.info("Waiting for RFID card tap...")
                    # Blocks until a card is read
                    card_id, text = reader.read()
                    
                    # Convert integer card_id to hex string representation
                    card_uid_hex = hex(card_id).upper().replace("0X", "")
                    logger.info(f"Card scanned! UID: {card_uid_hex}")
                    
                    # Send authentication request
                    authenticate_rfid_with_server(card_uid_hex)
                    
                    # Avoid double scans by sleeping
                    time.sleep(3.0)
                except Exception as ex:
                    logger.error(f"Error reading card: {ex}")
                    time.sleep(1.0)
            else:
                # Simulation Mode (Interactive Console)
                print("\n[RFID SIMULATOR] Enter Card UID to simulate swipe (or press Ctrl+C to exit):")
                user_input = sys.stdin.readline().strip()
                if user_input:
                    logger.info(f"Simulating swipe for UID: {user_input}")
                    authenticate_rfid_with_server(user_input)
                time.sleep(0.5)
                
    except KeyboardInterrupt:
        logger.info("Scanner daemon stopped by user.")
    finally:
        hardware.cleanup()

if __name__ == "__main__":
    run_rfid_scanner()
