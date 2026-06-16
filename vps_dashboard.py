# ============================================================
# VPS Temperature Dashboard
# Subscribes to MQTT broker on VPS, serves a premium web UI
# ============================================================

import os
import sys
import json
import time
import queue
import threading
from datetime import datetime
from collections import deque
from flask import Flask, Response, render_template_string, jsonify

# Try to import paho-mqtt
try:
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import CallbackAPIVersion
except ImportError:
    print("ERROR: paho-mqtt is required. Run: pip install paho-mqtt")
    sys.exit(1)

# Try to import flask
try:
    from flask import Flask
except ImportError:
    print("ERROR: flask is required. Run: pip install Flask")
    sys.exit(1)

# =============================================================
# CONFIGURATION
# =============================================================
MQTT_BROKER = "localhost"      # Default: Dashboard runs on VPS, connects to local broker
if len(sys.argv) > 1:
    MQTT_BROKER = sys.argv[1]

MQTT_PORT = 1883
MQTT_TOPIC = "exam/temperature"
DASHBOARD_HOST = "0.0.0.0"     # Listen on all interfaces to be accessible publicly
DASHBOARD_PORT = 24073
if len(sys.argv) > 2:
    try:
        DASHBOARD_PORT = int(sys.argv[2])
    except ValueError:
        print("[Warning] Invalid port argument. Defaulting to 24073.")

# =============================================================
# STATE MANAGEMENT
# =============================================================
app = Flask(__name__)
data_lock = threading.Lock()
temperature_history = deque(maxlen=50)  # Stores last 50 readings
sse_listeners = []
broker_connected = False

# =============================================================
# MQTT CALLBACKS
# =============================================================
def on_connect(client, userdata, flags, rc, properties=None):
    global broker_connected
    if rc == 0 or rc.value == 0:
        print(f"[MQTT] Dashboard connected to broker on port {MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        broker_connected = True
    else:
        print(f"[MQTT] Connection failed with code: {rc}")
        broker_connected = False

def on_disconnect(client, userdata, flags, rc, properties=None):
    global broker_connected
    print("[MQTT] Disconnected from broker. Reconnecting...")
    broker_connected = False

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        temp_val = float(payload)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        data_point = {
            "timestamp": timestamp,
            "value": temp_val,
            "raw_time": time.time()
        }
        
        # Add to local history and stream to browsers
        with data_lock:
            temperature_history.append(data_point)
            # Broadcast to all active browser SSE streams
            for q in sse_listeners:
                q.put(data_point)
                
        print(f"[MQTT] Broadcasted reading: {temp_val} °C at {timestamp}")
    except ValueError:
        print(f"[MQTT] Warning: Received invalid non-numeric payload: {msg.payload}")
    except Exception as e:
        print(f"[MQTT] Error handling message: {e}")

# Start MQTT Client in a background thread
def start_mqtt_client():
    mqtt_client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message
    
    while True:
        try:
            print(f"[MQTT] Connecting to broker at {MQTT_BROKER}:{MQTT_PORT}...")
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            mqtt_client.loop_forever()
        except Exception as e:
            global broker_connected
            broker_connected = False
            print(f"[MQTT] Connection failed: {e}. Retrying in 5 seconds...")
            time.sleep(5)

# =============================================================
# WEB SERVER ROUTES
# =============================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Embedded Temp Monitor | VPS Dashboard</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
    <!-- Chart.js -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(20, 26, 43, 0.65);
            --card-border: rgba(255, 255, 255, 0.07);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-cyan: #00f2fe;
            --accent-blue: #4facfe;
            --accent-purple: #8b5cf6;
            --state-online: #10b981;
            --state-offline: #ef4444;
            --glow-color: rgba(79, 172, 254, 0.15);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
            background-image: 
                radial-gradient(at 10% 20%, rgba(30, 41, 59, 0.5) 0px, transparent 50%),
                radial-gradient(at 90% 80%, rgba(139, 92, 246, 0.1) 0px, transparent 50%);
        }

        header {
            padding: 2rem 2rem 1.5rem;
            max-width: 1400px;
            width: 100%;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1.5rem;
            border-bottom: 1px solid var(--card-border);
        }

        .header-title h1 {
            font-size: 1.8rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }

        .header-title p {
            color: var(--text-secondary);
            font-size: 0.95rem;
            margin-top: 0.25rem;
        }

        .status-panel {
            display: flex;
            gap: 1rem;
        }

        .status-badge {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            padding: 0.6rem 1rem;
            border-radius: 12px;
            font-size: 0.85rem;
            display: flex;
            align-items: center;
            gap: 0.6rem;
            backdrop-filter: blur(8px);
            font-weight: 500;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }

        .status-dot.online {
            background-color: var(--state-online);
            box-shadow: 0 0 10px var(--state-online);
            animation: pulse 2s infinite;
        }

        .status-dot.offline {
            background-color: var(--state-offline);
            box-shadow: 0 0 10px var(--state-offline);
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        main {
            flex: 1;
            padding: 2rem;
            max-width: 1400px;
            width: 100%;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 2rem;
        }

        @media (max-width: 1024px) {
            main {
                grid-template-columns: 1fr;
            }
        }

        .left-column {
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }

        .right-column {
            display: flex;
            flex-direction: column;
            gap: 2rem;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 1.8rem;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 40px 0 rgba(0, 242, 254, 0.05);
            border-color: rgba(79, 172, 254, 0.2);
        }

        .card-title {
            font-size: 1rem;
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* Gauge Styling */
        .gauge-container {
            position: relative;
            width: 200px;
            height: 200px;
            margin: 0 auto;
        }

        .gauge-svg {
            transform: rotate(-90deg);
        }

        .gauge-bg {
            fill: none;
            stroke: rgba(255, 255, 255, 0.05);
            stroke-width: 16;
        }

        .gauge-fill {
            fill: none;
            stroke: url(#gauge-grad);
            stroke-width: 16;
            stroke-linecap: round;
            stroke-dasharray: 565.48; /* 2 * PI * r (r=90) */
            stroke-dashoffset: 565.48; /* Starts empty */
            transition: stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .gauge-value-box {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
        }

        .gauge-num {
            font-size: 2.8rem;
            font-weight: 800;
            color: var(--text-primary);
            line-height: 1;
            letter-spacing: -1px;
            font-family: 'Outfit', sans-serif;
        }

        .gauge-unit {
            font-size: 1rem;
            color: var(--accent-cyan);
            font-weight: 600;
            margin-top: 0.1rem;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1.2rem;
            margin-top: 1rem;
        }

        .stat-item {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.03);
            border-radius: 12px;
            padding: 1rem;
            text-align: center;
        }

        .stat-label {
            font-size: 0.8rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 0.4rem;
        }

        .stat-val {
            font-size: 1.4rem;
            font-weight: 700;
            font-family: 'Space Mono', monospace;
            background: linear-gradient(135deg, #fff, var(--text-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .stat-val.highlight-cyan {
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        /* Config Table Details */
        .metadata-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
        }

        .metadata-item {
            display: flex;
            justify-content: space-between;
            padding-bottom: 0.8rem;
            border-bottom: 1px dashed rgba(255, 255, 255, 0.05);
            font-size: 0.9rem;
        }

        .metadata-item:last-child {
            border-bottom: none;
            padding-bottom: 0;
        }

        .metadata-key {
            color: var(--text-secondary);
        }

        .metadata-val {
            font-family: 'Space Mono', monospace;
            font-weight: 700;
            color: var(--text-primary);
        }

        /* Chart Canvas wrapper */
        .chart-container {
            position: relative;
            width: 100%;
            height: 320px;
        }

        /* Live Feed Logger */
        .log-container {
            max-height: 180px;
            overflow-y: auto;
            font-family: 'Space Mono', monospace;
            font-size: 0.8rem;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            padding-right: 0.5rem;
        }

        .log-container::-webkit-scrollbar {
            width: 6px;
        }

        .log-container::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.02);
            border-radius: 3px;
        }

        .log-container::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 3px;
        }

        .log-entry {
            display: flex;
            justify-content: space-between;
            background: rgba(255, 255, 255, 0.02);
            padding: 0.6rem 0.8rem;
            border-radius: 8px;
            border-left: 3px solid var(--accent-cyan);
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .log-time {
            color: var(--text-secondary);
        }

        .log-val {
            color: var(--accent-cyan);
            font-weight: 700;
        }

        footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.85rem;
            border-top: 1px solid var(--card-border);
            margin-top: auto;
        }
        
        .footer-logo {
            font-weight: 700;
            color: var(--text-primary);
            letter-spacing: -0.5px;
            margin-bottom: 0.25rem;
        }
    </style>
</head>
<body>

    <header>
        <div class="header-title">
            <h1>EVALUATOR MONITORING PORTAL</h1>
            <p>Verification dashboard for embedded system & MQTT integration</p>
        </div>
        <div class="status-panel">
            <div class="status-badge" title="Status of MQTT broker connection on VPS">
                <span id="broker-dot" class="status-dot offline"></span>
                <span>MQTT Broker: <strong id="broker-status">Checking...</strong></span>
            </div>
            <div class="status-badge" title="Status of SSE stream connection from VPS dashboard to this page">
                <span id="sse-dot" class="status-dot offline"></span>
                <span>Live Stream: <strong id="sse-status">Offline</strong></span>
            </div>
        </div>
    </header>

    <main>
        <!-- Left Column: Gauges, Metadata, Stats -->
        <div class="left-column">
            <!-- Current Value Card -->
            <div class="card">
                <div class="card-title">
                    <span>Live Temperature</span>
                    <span style="color: var(--accent-cyan); font-size: 1.2rem;">⏱️</span>
                </div>
                <div class="gauge-container">
                    <svg class="gauge-svg" width="200" height="200" viewBox="0 0 200 200">
                        <defs>
                            <linearGradient id="gauge-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                                <stop offset="0%" stop-color="var(--accent-cyan)" />
                                <stop offset="100%" stop-color="var(--accent-purple)" />
                            </linearGradient>
                        </defs>
                        <circle class="gauge-bg" cx="100" cy="100" r="90" />
                        <circle id="gauge-progress" class="gauge-fill" cx="100" cy="100" r="90" />
                    </svg>
                    <div class="gauge-value-box">
                        <div id="temp-display" class="gauge-num">--.-</div>
                        <div class="gauge-unit">CELSIUS</div>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-label">Min Temp</div>
                        <div id="stat-min" class="stat-val">--.-</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Max Temp</div>
                        <div id="stat-max" class="stat-val">--.-</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Average</div>
                        <div id="stat-avg" class="stat-val">--.-</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-label">Readings</div>
                        <div id="stat-count" class="stat-val highlight-cyan">0</div>
                    </div>
                </div>
            </div>

            <!-- Architecture Info Card -->
            <div class="card">
                <div class="card-title">Communication Specs</div>
                <ul class="metadata-list">
                    <li class="metadata-item">
                        <span class="metadata-key">Serial Config</span>
                        <span class="metadata-val">COM3 @ 9600 Baud</span>
                    </li>
                    <li class="metadata-item">
                        <span class="metadata-key">Serial Format</span>
                        <span class="metadata-val">TEMP:&lt;val&gt;</span>
                    </li>
                    <li class="metadata-item">
                        <span class="metadata-key">MQTT Host</span>
                        <span class="metadata-val">157.173.101.159</span>
                    </li>
                    <li class="metadata-item">
                        <span class="metadata-key">MQTT Port</span>
                        <span class="metadata-val">1883</span>
                    </li>
                    <li class="metadata-item">
                        <span class="metadata-key">MQTT Topic</span>
                        <span class="metadata-val">exam/temperature</span>
                    </li>
                </ul>
            </div>
        </div>

        <!-- Right Column: Graphs, Log feed -->
        <div class="right-column">
            <!-- Real-Time History Graph -->
            <div class="card" style="flex: 1; display: flex; flex-direction: column;">
                <div class="card-title">Real-Time Temperature Plot</div>
                <div class="chart-container" style="flex: 1;">
                    <canvas id="tempChart"></canvas>
                </div>
            </div>

            <!-- Live MQTT Message Log -->
            <div class="card">
                <div class="card-title">Live Message Stream logs</div>
                <div id="log-feed" class="log-container">
                    <div class="log-entry" style="border-left-color: var(--text-secondary);">
                        <span class="log-time">System Ready</span>
                        <span>Awaiting connection stream...</span>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <footer>
        <div class="footer-logo">Embedded Systems Lab Verification</div>
        <p>VPS Hosted Platform &bull; Real-time MQTT telemetry</p>
    </footer>

    <!-- Frontend Scripting -->
    <script>
        // Init state variables
        let temperatures = [];
        let labels = [];
        let maxSamples = 20;

        // Stat trackers
        let tempSum = 0;
        let tempMin = Infinity;
        let tempMax = -Infinity;
        let tempCount = 0;

        // Initialize Chart.js
        const ctx = document.getElementById('tempChart').getContext('2d');
        
        // Create subtle gradient under chart line
        const chartGradient = ctx.createLinearGradient(0, 0, 0, 300);
        chartGradient.addColorStop(0, 'rgba(0, 242, 254, 0.25)');
        chartGradient.addColorStop(1, 'rgba(139, 92, 246, 0.01)');

        const tempChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Temperature (°C)',
                    data: temperatures,
                    borderColor: '#00f2fe',
                    borderWidth: 3,
                    pointBackgroundColor: '#4facfe',
                    pointBorderColor: '#fff',
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: '#8b5cf6',
                    fill: true,
                    backgroundColor: chartGradient,
                    tension: 0.35
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.03)' },
                        ticks: { color: '#94a3b8', font: { family: 'Space Mono' } }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.03)' },
                        ticks: { color: '#94a3b8', font: { family: 'Space Mono' } },
                        suggestedMin: 15,
                        suggestedMax: 40
                    }
                }
            }
        });

        // Set up I2C style Gauge Value Range (0°C to 50°C)
        // 565.48 stroke-dasharray corresponds to the full circle perimeter (r=90)
        function updateGauge(value) {
            const maxTempRange = 50.0;
            const minTempRange = 0.0;
            
            // Constrain value between min and max range
            let constrainedVal = Math.max(minTempRange, Math.min(maxTempRange, value));
            let percentage = (constrainedVal - minTempRange) / (maxTempRange - minTempRange);
            
            // Full perimeter is 565.48, offset controls how much is hidden.
            // When percentage = 1.0 (50°C), offset is 0. When percentage = 0.0, offset is 565.48.
            let offset = 565.48 * (1.0 - percentage);
            document.getElementById('gauge-progress').style.strokeDashoffset = offset;
        }

        // Add log entry to the log panel
        function addLog(time, val) {
            const container = document.getElementById('log-feed');
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.innerHTML = `
                <span class="log-time">[${time}] exam/temperature publish</span>
                <span class="log-val">${val} °C</span>
            `;
            // Keep container clean by pruning logs > 15
            if (container.children.length >= 15) {
                container.removeChild(container.lastChild);
            }
            container.insertBefore(entry, container.firstChild);
        }

        // Process new incoming reading
        function handleNewReading(value, timeStr) {
            const val = parseFloat(value);
            if (isNaN(val)) return;

            // Update gauge UI
            document.getElementById('temp-display').innerText = val.toFixed(1);
            updateGauge(val);

            // Update numerical stats
            tempCount++;
            tempSum += val;
            if (val < tempMin) tempMin = val;
            if (val > tempMax) tempMax = val;
            
            document.getElementById('stat-count').innerText = tempCount;
            document.getElementById('stat-min').innerText = tempMin.toFixed(1) + ' °C';
            document.getElementById('stat-max').innerText = tempMax.toFixed(1) + ' °C';
            document.getElementById('stat-avg').innerText = (tempSum / tempCount).toFixed(1) + ' °C';

            // Update Log
            addLog(timeStr, val.toFixed(1));

            // Update Chart.js dataset
            labels.push(timeStr);
            temperatures.push(val);
            
            if (labels.length > maxSamples) {
                labels.shift();
                temperatures.shift();
            }

            tempChart.update();
        }

        // Fetch Broker and Stream updates via SSE
        function initRealtimeStream() {
            const sseStatusDot = document.getElementById('sse-dot');
            const sseStatusText = document.getElementById('sse-status');
            const brokerStatusDot = document.getElementById('broker-dot');
            const brokerStatusText = document.getElementById('broker-status');

            // Establish SSE Connection to Flask
            const source = new EventSource('/stream');

            source.onopen = function() {
                sseStatusText.innerText = "Active";
                sseStatusDot.className = "status-dot online";
            };

            source.onerror = function() {
                sseStatusText.innerText = "Offline";
                sseStatusDot.className = "status-dot offline";
            };

            source.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.keep_alive) {
                    // Check broker status regularly
                    fetch('/api/broker_status')
                        .then(res => res.json())
                        .then(status => {
                            if (status.connected) {
                                brokerStatusText.innerText = "Online";
                                brokerStatusDot.className = "status-dot online";
                            } else {
                                brokerStatusText.innerText = "Offline";
                                brokerStatusDot.className = "status-dot offline";
                            }
                        });
                    return;
                }
                
                // Process temperature values
                handleNewReading(data.value, data.timestamp);
            };
        }

        // Preload historical data
        function loadHistoricalData() {
            fetch('/api/history')
                .then(res => res.json())
                .then(history => {
                    // Populate from oldest to newest
                    history.forEach(pt => {
                        handleNewReading(pt.value, pt.timestamp);
                    });
                })
                .catch(err => console.error("Error fetching historical data:", err));
        }

        // Page load
        window.addEventListener('DOMContentLoaded', () => {
            loadHistoricalData();
            initRealtimeStream();
            
            // Check broker status initially
            fetch('/api/broker_status')
                .then(res => res.json())
                .then(status => {
                    const brokerStatusDot = document.getElementById('broker-dot');
                    const brokerStatusText = document.getElementById('broker-status');
                    if (status.connected) {
                        brokerStatusText.innerText = "Online";
                        brokerStatusDot.className = "status-dot online";
                    } else {
                        brokerStatusText.innerText = "Offline";
                        brokerStatusDot.className = "status-dot offline";
                    }
                });
        });
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/history')
def get_history():
    with data_lock:
        return jsonify(list(temperature_history))

@app.route('/api/broker_status')
def get_broker_status():
    return jsonify({"connected": broker_connected})

@app.route('/stream')
def stream():
    def event_stream():
        q = queue.Queue()
        with data_lock:
            sse_listeners.append(q)
        try:
            # Yield initial keep-alive
            yield "data: {\"keep_alive\": true}\n\n"
            while True:
                try:
                    data = q.get(timeout=5.0)
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    # Send periodic keep-alive
                    yield "data: {\"keep_alive\": true}\n\n"
        finally:
            with data_lock:
                sse_listeners.remove(q)
                
    return Response(event_stream(), mimetype="text/event-stream")

# =============================================================
# ENTRY POINT
# =============================================================
def main():
    print("=" * 60)
    print("    STARTING VPS DASHBOARD SERVER")
    print("    MQTT Sub + SSE Broadcast + Premium Web UI")
    print("=" * 60)
    
    # 1. Start MQTT background thread
    mqtt_thread = threading.Thread(target=start_mqtt_client, daemon=True)
    mqtt_thread.start()
    
    # 2. Run Flask Web Server
    # Bind to 0.0.0.0 so it is publicly queryable outside the VPS
    app.run(host=DASHBOARD_HOST, port=DASHBOARD_PORT, debug=False, threaded=True)

if __name__ == "__main__":
    main()
