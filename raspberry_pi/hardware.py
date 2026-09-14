import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except (ImportError, RuntimeError):
    HAS_GPIO = False
    logger.warning("RPi.GPIO not detected. Running hardware in simulation mode.")

# Physical GPIO mapping (REQ-52)
GREEN_LED_PIN = 18
RED_LED_PIN = 23
BUZZER_PIN = 24
RELAY_PINS = {
    1: 5,   # Floor 1
    2: 6,   # Floor 2
    3: 13,  # Floor 3
    4: 19,  # Floor 4
    5: 26   # Floor 5
}

def setup_pins():
    """Initializes pin modes and default outputs."""
    if HAS_GPIO:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(GREEN_LED_PIN, GPIO.OUT)
        GPIO.setup(RED_LED_PIN, GPIO.OUT)
        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        
        # Turn off all indicator outputs initially
        GPIO.output(GREEN_LED_PIN, GPIO.LOW)
        GPIO.output(RED_LED_PIN, GPIO.LOW)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        
        # Relays are active-low or active-high depending on relay modules
        # Usually, active-low relays need to start HIGH. We will set LOW as off by default.
        for floor, pin in RELAY_PINS.items():
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
            
        logger.info("GPIO configuration complete.")
    else:
        logger.info("[Simulated] GPIO pins initialized.")

def pulse_relay(floor, duration=1.0):
    """Simulates a button press on the physical elevator panel (REQ-33, REQ-34)."""
    if floor not in RELAY_PINS:
        logger.error(f"Invalid floor number: {floor}")
        return False
        
    pin = RELAY_PINS[floor]
    
    if HAS_GPIO:
        logger.info(f"Pulsing relay on GPIO {pin} for Floor {floor} (Duration: {duration}s)")
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(pin, GPIO.LOW)
    else:
        logger.info(f"[Simulated] Pulsed relay on pin {pin} for Floor {floor} for {duration} seconds.")
    return True

def indicate_access_granted():
    """Turns on Green LED for 2 seconds to signal access granted (REQ-35)."""
    if HAS_GPIO:
        logger.info("LED State: Green LED ON")
        GPIO.output(GREEN_LED_PIN, GPIO.HIGH)
        time.sleep(2.0)
        GPIO.output(GREEN_LED_PIN, GPIO.LOW)
        logger.info("LED State: Green LED OFF")
    else:
        logger.info("[Simulated] Green LED ON for 2.0s")

def indicate_access_denied():
    """Turns on Red LED and sounds Buzzer warning tones to signal access denied (REQ-36)."""
    if HAS_GPIO:
        logger.info("Warning State: Red LED and Buzzer ON")
        GPIO.output(RED_LED_PIN, GPIO.HIGH)
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        
        # Double beep
        time.sleep(0.4)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        time.sleep(0.1)
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(0.4)
        
        GPIO.output(RED_LED_PIN, GPIO.LOW)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        logger.info("Warning State: OFF")
    else:
        logger.info("[Simulated] Red LED + Buzzer warning active for 1.0s")

def cleanup():
    """Cleans up GPIO settings on program close."""
    if HAS_GPIO:
        GPIO.cleanup()
        logger.info("GPIO settings cleaned up.")
    else:
        logger.info("[Simulated] GPIO cleanup complete.")

if __name__ == "__main__":
    # Test script locally
    setup_pins()
    indicate_access_granted()
    time.sleep(0.5)
    indicate_access_denied()
    time.sleep(0.5)
    pulse_relay(1)
    cleanup()
