# Embedded Temperature Monitoring & Real-Time Web Dashboard

This repository contains the complete implementation of the Embedded Temperature Monitoring and MQTT Telemetry System assignment.

---

## 📋 Project Requirements

* **Part 1: Temperature Reading & LCD Display**
  * Read temperature values using a DHT11 sensor on an Arduino Uno.
  * Display candidate name on the first row of a 16x2 LCD display (with horizontal scrolling if the name exceeds 16 characters).
  * Display the live temperature value on the second row of the LCD.
  * Send the temperature values from the Arduino Uno to the PC via USB Serial communication.
* **Part 2: PC Monitoring & MQTT Transmission**
  * Write a PC-side program to read temperature values from the Arduino serial port.
  * Display incoming values in real time on the PC terminal.
  * Publish the temperature values to an MQTT broker hosted on a Cloud VPS.
  * Retrieve values and serve a premium, real-time web dashboard hosted on the VPS.

---

## ⚙️ System Architecture

```text
 Temperature Sensor (DHT11)
            │
            ▼
       Arduino Uno ──(I2C)──► 16x2 LCD Display (Row 1: Scrolling Name, Row 2: Live Temp)
            │
            ▼ (USB Serial @ 9600 Baud)
     PC Client program (pc_monitor.py)
            │
            ▼ (MQTT Publish Port 1883)
    MQTT Mosquitto Broker (VPS)
            │
            ▼ (Local Subscribe)
   Flask Web Dashboard (vps_dashboard.py @ Port 24085)
            │
            ▼ (Server-Sent Events)
   Web Browser (Real-time Graph UI)
```

---

## 📂 Project Structure

* 📂 **[temperature_monitor.ino](temperature_monitor.ino)**: Arduino C++ source code handling sensor reading, I2C LCD drawing, scrolling, and Serial outputs.
* 📂 **[pc_monitor.py](pc_monitor.py)**: Python bridge script running locally on the PC to read Serial and publish to MQTT.
* 📂 **[vps_dashboard.py](vps_dashboard.py)**: Python Flask server and real-time frontend serving gauges and charts via Server-Sent Events (SSE).
* 📂 **[system_architecture.md](system_architecture.md)**: Extended architecture documentation and Mermaid diagrams.
* 📂 **[VPS_SETUP.md](VPS_SETUP.md)**: System administration guide for configuring Mosquitto and managing UFW firewalls on Ubuntu VPS.

---

## 🚀 How to Run the System

### 1. Arduino Setup
1. Open [temperature_monitor.ino](temperature_monitor.ino) in the Arduino IDE.
2. Verify the candidate name variable and upload the code to your Arduino Uno.

### 2. PC Setup
1. Install Python dependencies:
   ```cmd
   pip install pyserial paho-mqtt flask
   ```
2. Open [pc_monitor.py](pc_monitor.py) and change the `SERIAL_PORT` variable to match your connected Arduino COM port (e.g. `COM3`).
3. Run the PC serial monitor:
   ```cmd
   python pc_monitor.py
   ```

### 3. VPS Dashboard Setup
1. Log into your VPS and install dependencies:
   ```bash
   sudo apt update && sudo apt install -y mosquitto mosquitto-clients python3-flask
   pip3 install paho-mqtt
   ```
2. Enable public MQTT listener inside `/etc/mosquitto/conf.d/default.conf`:
   ```ini
   listener 1883 0.0.0.0
   allow_anonymous true
   ```
3. Restart Mosquitto:
   ```bash
   sudo systemctl restart mosquitto
   ```
4. Run the dashboard in the background (using port `24085` or your assigned port):
   ```bash
   nohup python3 vps_dashboard.py localhost 24085 > dashboard.log 2>&1 &
   ```

### 4. Verification
* Open your browser and navigate to **`http://<VPS_IP>:24085`** to view the live dashboard updating in real time.

---

## 📡 Protocol Specifications

| Interface | Protocol / Type | Connection Config | Format / Topic |
|---|---|---|---|
| **Arduino ↔ PC** | USB Serial | `9600 Baud`, `8-N-1` | `TEMP:<value>` (e.g. `TEMP:23.5`) |
| **PC ↔ Broker** | MQTT Publish | Host: `157.173.101.159:1883` | Topic: `exam/temperature` |
| **Broker ↔ Web** | MQTT Subscribe | Host: `localhost:1883` | Topic: `exam/temperature` |
| **Web ↔ Browser** | HTTP / SSE | Port: `24085` | Server-Sent Events `/stream` |
