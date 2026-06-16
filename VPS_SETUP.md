# VPS Deployment and Setup Guide

This guide describes how to configure the **Mosquitto MQTT Broker** and host the **Real-Time Web Dashboard** on your Cloud VPS (`157.173.101.159`).

---

## Step 1: Install Mosquitto MQTT Broker on VPS

SSH into your VPS and install Mosquitto and its command-line clients.

```bash
# Update package lists
sudo apt update

# Install Mosquitto broker and client tools
sudo apt install -y mosquitto mosquitto-clients
```

---

## Step 2: Configure Mosquitto for Public Access

By default, newer versions of Mosquitto (v2.x+) only listen on `localhost` and deny anonymous connections. We must configure it to listen on the public interface (port `1883`) and allow anonymous access for testing.

1. Create a configuration file in `/etc/mosquitto/conf.d/`:
   ```bash
   sudo nano /etc/mosquitto/conf.d/default.conf
   ```
2. Paste the following configuration lines into the file:
   ```ini
   listener 1883 0.0.0.0
   allow_anonymous true
   ```
3. Save and close the file (`Ctrl+O`, `Enter`, `Ctrl+X`).
4. Restart Mosquitto to apply the settings:
   ```bash
   sudo systemctl restart mosquitto
   ```
5. Verify that Mosquitto is active and running:
   ```bash
   sudo systemctl status mosquitto
   ```

---

## Step 3: Configure the VPS Firewall (Open Ports)

If your VPS uses `ufw` (Uncomplicated Firewall) or a cloud-provider security group, you must open the required ports:

```bash
# Allow MQTT Broker port
sudo ufw allow 1883/tcp

# Allow Web Dashboard port
sudo ufw allow 24073/tcp

# Reload firewall rules
sudo ufw reload
```

---

## Step 4: Transfer and Set Up the Web Dashboard

1. Install the required Python packages on the VPS:
   ```bash
   sudo apt install -y python3-pip python3-flask
   pip3 install paho-mqtt
   ```

2. Copy the dashboard code from your local machine to the VPS, or create the file on the VPS directly:
   ```bash
   nano ~/vps_dashboard.py
   ```
   *Paste the entire contents of [vps_dashboard.py](file:///c:/Users/HP/Music/embedded/vps_dashboard.py) and save the file.*

3. Run the dashboard. To keep it running persistently in the background after you close the SSH terminal, run it using `nohup`:
   ```bash
   nohup python3 ~/vps_dashboard.py > dashboard.log 2>&1 &
   ```
   This will run the dashboard in the background and redirect output to `dashboard.log`.

4. Check if the dashboard is running:
   ```bash
   ps aux | grep vps_dashboard.py
   ```

---

## Step 5: Verification Flow

### 1. Test MQTT Publishing locally on the VPS
Open a separate terminal window on the VPS and subscribe to the topic:
```bash
mosquitto_sub -t "exam/temperature" -v
```
Publish a dummy value from another SSH session on the VPS:
```bash
mosquitto_pub -t "exam/temperature" -m "25.4"
```
You should see the message `exam/temperature 25.4` appear in the subscriber window.

### 2. Verify PC Client and Arduino
1. Flash the Arduino Uno with `temperature_monitor.ino`. Ensure you update the I2C LCD address and the candidate name in the code if needed.
2. In your local PC command terminal, navigate to your workspace and install Python requirements:
   ```bash
   pip install pyserial paho-mqtt
   ```
3. Run the PC client:
   ```bash
   python pc_monitor.py
   ```
   *Note: Ensure your Arduino is plugged in and change `SERIAL_PORT` inside `pc_monitor.py` to match the exact COM port (e.g. `COM3`). Make sure the Arduino IDE Serial Monitor is closed.*
4. The console will print incoming temperature readings and show `Published` for the MQTT status.

### 3. Open the Dashboard in your Browser
Open your web browser and navigate to:
`http://157.173.101.159:24073`

You will see the premium Web UI. When your PC program publishes temperature readings, the dashboard gauge, chart, and logs will update instantly in real time.
