# app.py - Web Interface for Raspberry Pi Rebar Analysis

from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import requests
import json
import base64
import time
import threading

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configuration
RASPI_IP = "localhost"  # Default IP for Raspberry Pi in WiFi direct mode
RASPI_PORT = 5000
RASPI_API_URL = f"http://{RASPI_IP}:{RASPI_PORT}/api"
POLLING_INTERVAL = 5  # Seconds between polling for new data

# Local storage for the latest data
latest_data = {
    "connected": False,
    "last_image": None,
    "last_results": [],
    "last_update": None,
    "total_volume": 0
}

def check_connection():
    """Check if we can connect to the Raspberry Pi"""
    try:
        response = requests.get(f"{RASPI_API_URL}/status", timeout=2)
        if response.status_code == 200:
            return True
        return False
    except:
        return False

def get_raspi_data():
    """Poll the Raspberry Pi for new data"""
    global latest_data
    
    while True:
        connected = check_connection()
        latest_data["connected"] = connected
        
        if connected:
            try:
                # Get the latest analysis results
                response = requests.get(f"{RASPI_API_URL}/latest", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("timestamp") != latest_data.get("last_update"):
                        latest_data["last_update"] = data.get("timestamp")
                        latest_data["last_results"] = data.get("segments", [])
                        latest_data["total_volume"] = data.get("total_volume", 0)
                        
                        # Get the latest image if available
                        if data.get("image_available", False):
                            img_response = requests.get(f"{RASPI_API_URL}/latest_image", timeout=5)
                            if img_response.status_code == 200:
                                latest_data["last_image"] = img_response.json().get("image")
                        
                        # Notify clients about new data
                        socketio.emit("new_data", {
                            "connected": True,
                            "timestamp": latest_data["last_update"],
                            "has_image": latest_data["last_image"] is not None,
                            "segments_count": len(latest_data["last_results"]),
                            "total_volume": latest_data["total_volume"]
                        })
            except Exception as e:
                print(f"Error polling Raspberry Pi: {e}")
                socketio.emit("connection_error", {"error": str(e)})
        else:
            socketio.emit("connection_status", {"connected": False})
        
        # Wait before polling again
        time.sleep(POLLING_INTERVAL)

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/api/connection_status')
def connection_status():
    return jsonify({
        "connected": latest_data["connected"],
        "last_update": latest_data["last_update"]
    })

@app.route('/api/latest_data')
def get_latest_data():
    return jsonify({
        "connected": latest_data["connected"],
        "timestamp": latest_data["last_update"],
        "segments": latest_data["last_results"],
        "total_volume": latest_data["total_volume"],
        "has_image": latest_data["last_image"] is not None
    })

@app.route('/api/latest_image')
def get_latest_image():
    if latest_data["last_image"]:
        return jsonify({"image": latest_data["last_image"]})
    return jsonify({"error": "No image available"}), 404

@app.route('/api/trigger_capture', methods=["POST"])
def trigger_capture():
    if not latest_data["connected"]:
        return jsonify({"error": "Not connected to Raspberry Pi"}), 503
    
    try:
        response = requests.post(f"{RASPI_API_URL}/capture", timeout=5)
        if response.status_code == 200:
            return jsonify({"message": "Capture triggered successfully"})
        return jsonify({"error": f"Error: {response.text}"}), response.status_code
    except Exception as e:
        return jsonify({"error": f"Connection error: {str(e)}"}), 500

@app.route('/api/set_config', methods=["POST"])
def set_config():
    if not latest_data["connected"]:
        return jsonify({"error": "Not connected to Raspberry Pi"}), 503
    
    try:
        # Forward the configuration to the Raspberry Pi
        config_data = request.json
        response = requests.post(
            f"{RASPI_API_URL}/config", 
            json=config_data,
            timeout=5
        )
        if response.status_code == 200:
            return jsonify({"message": "Configuration updated successfully"})
        return jsonify({"error": f"Error: {response.text}"}), response.status_code
    except Exception as e:
        return jsonify({"error": f"Connection error: {str(e)}"}), 500

@app.route('/api/get_config')
def get_config():
    if not latest_data["connected"]:
        return jsonify({"error": "Not connected to Raspberry Pi"}), 503
    
    try:
        response = requests.get(f"{RASPI_API_URL}/config", timeout=5)
        if response.status_code == 200:
            return jsonify(response.json())
        return jsonify({"error": f"Error: {response.text}"}), response.status_code
    except Exception as e:
        return jsonify({"error": f"Connection error: {str(e)}"}), 500

@socketio.on('connect')
def socket_connect():
    emit('connection_status', {
        "connected": latest_data["connected"],
        "last_update": latest_data["last_update"]
    })

if __name__ == "__main__":
    # Start the data polling thread
    polling_thread = threading.Thread(target=get_raspi_data, daemon=True)
    polling_thread.start()
    
    # Start the Flask-SocketIO server
    socketio.run(app, host='0.0.0.0', port=8000, debug=True, use_reloader=False)