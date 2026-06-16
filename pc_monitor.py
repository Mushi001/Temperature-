# ============================================================
# PC Temperature Monitor
# Reads serial data from Arduino, displays in real-time,
# and publishes to MQTT broker on VPS
# ============================================================
# Required libraries: pip install pyserial paho-mqtt
# ============================================================

import serial
import time
import sys
from datetime import datetime

# Try to import paho MQTT client
try:
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import CallbackAPIVersion
except ImportError:
    print("ERROR: paho-mqtt not installed. Run: pip install paho-mqtt")
    sys.exit(1)

# =============================================================
# CONFIGURATION - UPDATE THESE VALUES BEFORE RUNNING
# =============================================================

# Serial port settings (Arduino connection)
SERIAL_PORT = "COM3"          # Change to your Arduino's COM port
BAUD_RATE = 9600              # Must match Arduino's Serial.begin()

# MQTT Broker settings (VPS)
MQTT_BROKER = "157.173.101.159"  # VPS IP address
MQTT_PORT = 1883              # Default MQTT port (use 8883 for TLS)
MQTT_TOPIC = "exam/temperature"  # Topic to publish temperature values
MQTT_USERNAME = ""            # Leave empty if no authentication
MQTT_PASSWORD = ""            # Leave empty if no authentication

# =============================================================
# MQTT CALLBACKS
# =============================================================

def on_connect(client, userdata, flags, rc, properties=None):
    """Called when the client connects to the MQTT broker."""
    if rc == 0 or rc.value == 0:
        print("[MQTT] Connected to broker successfully!")
        print(f"[MQTT] Broker: {MQTT_BROKER}:{MQTT_PORT}")
        print(f"[MQTT] Topic:  {MQTT_TOPIC}")
    else:
        print(f"[MQTT] Connection failed with code: {rc}")
        connection_codes = {
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorised"
        }
        print(f"[MQTT] Reason: {connection_codes.get(rc, 'Unknown')}")


def on_publish(client, userdata, mid, rc=None, properties=None):
    """Called when a message is successfully published."""
    pass  # Silent - we print confirmation in the main loop


def on_disconnect(client, userdata, flags, rc, properties=None):
    """Called when the client disconnects from the broker."""
    if rc != 0:
        print("[MQTT] Unexpected disconnection. Attempting to reconnect...")


# =============================================================
# MAIN PROGRAM
# =============================================================

def main():
    print("=" * 55)
    print("   PC TEMPERATURE MONITOR")
    print("   Serial Reader + MQTT Publisher")
    print("=" * 55)
    print()

    # ----- Step 1: Connect to MQTT Broker -----
    print("[MQTT] Connecting to broker...")
    mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)

    # Set username/password if provided
    if MQTT_USERNAME and MQTT_PASSWORD:
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    # Set callbacks
    mqtt_client.on_connect = on_connect
    mqtt_client.on_publish = on_publish
    mqtt_client.on_disconnect = on_disconnect

    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()  # Start background thread for MQTT
    except Exception as e:
        print(f"[MQTT] ERROR: Could not connect to broker: {e}")
        print("[MQTT] The program will continue without MQTT.")
        print("[MQTT] Temperature values will still be displayed locally.")
        mqtt_client = None

    # ----- Step 2: Open Serial Port (Arduino) -----
    print()
    print(f"[SERIAL] Opening {SERIAL_PORT} at {BAUD_RATE} baud...")

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        time.sleep(2)  # Wait for Arduino to reset after serial connection
        print(f"[SERIAL] Connected to Arduino on {SERIAL_PORT}")
    except serial.SerialException as e:
        print(f"[SERIAL] ERROR: Could not open {SERIAL_PORT}: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Check that Arduino is plugged in via USB")
        print("  2. Close the Arduino IDE Serial Monitor (it locks the port)")
        print("  3. Verify the COM port number in Device Manager")
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        sys.exit(1)

    # ----- Step 3: Main Loop - Read, Display, Publish -----
    print()
    print("-" * 55)
    print("  Listening for temperature data...")
    print("  Press Ctrl+C to stop")
    print("-" * 55)
    print()
    print(f"  {'TIME':<12} {'TEMPERATURE':<15} {'MQTT STATUS'}")
    print(f"  {'----':<12} {'-----------':<15} {'-----------'}")

    reading_count = 0

    try:
        while True:
            # Read a line from the serial port
            if ser.in_waiting > 0:
                raw_line = ser.readline()

                try:
                    line = raw_line.decode('utf-8').strip()
                except UnicodeDecodeError:
                    continue  # Skip garbled data

                # Check if it's a temperature reading
                if line.startswith("TEMP:"):
                    reading_count += 1
                    value = line.split(":")[1]
                    timestamp = datetime.now().strftime("%H:%M:%S")

                    # Publish to MQTT broker
                    mqtt_status = "---"
                    if mqtt_client and mqtt_client.is_connected():
                        result = mqtt_client.publish(MQTT_TOPIC, payload=value)
                        if result.rc == 0:
                            mqtt_status = "Published"
                        else:
                            mqtt_status = "Failed"
                    else:
                        mqtt_status = "No connection"

                    # Display in real-time on PC
                    print(f"  {timestamp:<12} {value + ' °C':<15} {mqtt_status}")

                elif line.startswith("ERROR:"):
                    # Sensor error from Arduino
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"  {timestamp:<12} {'SENSOR ERROR':<15} {'---'}")

                elif line:
                    # Other messages from Arduino (e.g., startup message)
                    print(f"  [Arduino] {line}")

            time.sleep(0.1)  # Small delay to prevent CPU overuse

    except KeyboardInterrupt:
        print()
        print()
        print("=" * 55)
        print(f"  Stopped. Total readings received: {reading_count}")
        print("=" * 55)

    finally:
        # Clean up
        ser.close()
        print("[SERIAL] Port closed.")
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
            print("[MQTT] Disconnected from broker.")
        print("Goodbye!")


if __name__ == "__main__":
    main()
