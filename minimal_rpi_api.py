# minimal_rpi_api.py - Minimal version to test connectivity
from flask import Flask, jsonify
from flask_cors import CORS
import cv2
import numpy as np
import base64
import io
from PIL import Image

app = Flask(__name__)
CORS(app)

# Simple data structure for our mock results
latest_analysis = {
    "timestamp": None,
    "image": None,
    "segments": [],
    "total_volume": 0
}

@app.route('/')
def home():
    """Root route to verify server is running"""
    return "RebarVista Mock API is running!"

@app.route('/api/status')
def status():
    """Return the API status"""
    return jsonify({
        "status": "online",
        "camera_available": True,
        "has_results": latest_analysis["timestamp"] is not None
    })

@app.route('/api/latest')
def get_latest():
    """Return the latest analysis results (without image)"""
    if latest_analysis["timestamp"] is None:
        # Generate some mock data for testing
        import time
        import random
        
        latest_analysis["timestamp"] = time.strftime("%Y%m%d-%H%M%S")
        latest_analysis["segments"] = [
            {
                "section_id": 1,
                "size_category": "medium",
                "diameter_mm": 15.75,
                "confidence": 0.89,
                "width_cm": 3.2,
                "length_cm": 10.5,
                "height_cm": 3.2,
                "volume_cc": 108.16
            },
            {
                "section_id": 2,
                "size_category": "small",
                "diameter_mm": 8.32,
                "confidence": 0.92,
                "width_cm": 2.1,
                "length_cm": 8.4,
                "height_cm": 2.1,
                "volume_cc": 37.04
            }
        ]
        latest_analysis["total_volume"] = sum(seg["volume_cc"] for seg in latest_analysis["segments"])
        
        # Create a simple test image
        img = np.zeros((400, 300, 3), dtype=np.uint8)
        # Draw some rectangles to simulate detections
        cv2.rectangle(img, (50, 100), (150, 250), (0, 255, 0), 2)
        cv2.rectangle(img, (180, 120), (250, 220), (0, 255, 0), 2)
        # Add text
        cv2.putText(img, "S1 (medium)", (50, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.putText(img, "S2 (small)", (180, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Convert to base64
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        img_io = io.BytesIO()
        pil_img.save(img_io, 'JPEG')
        img_io.seek(0)
        latest_analysis["image"] = base64.b64encode(img_io.getvalue()).decode('utf-8')
    
    return jsonify({
        "timestamp": latest_analysis["timestamp"],
        "segments": latest_analysis["segments"],
        "total_volume": latest_analysis["total_volume"],
        "image_available": latest_analysis["image"] is not None
    })

@app.route('/api/latest_image')
def get_latest_image():
    """Return the latest analysis image"""
    if latest_analysis["image"] is None:
        return jsonify({"error": "No image available"}), 404
    
    return jsonify({
        "image": latest_analysis["image"]
    })

@app.route('/api/capture', methods=["POST"])
def trigger_capture():
    """Trigger a new capture and analysis"""
    # Reset the mock analysis so new data will be generated on next request
    latest_analysis["timestamp"] = None
    latest_analysis["image"] = None
    latest_analysis["segments"] = []
    latest_analysis["total_volume"] = 0
    
    return jsonify({
        "message": "Capture and analysis successful",
        "timestamp": "Simulated capture triggered"
    })

if __name__ == "__main__":
    print("Starting RebarVista Mock API Server...")
    app.run(host='0.0.0.0', port=5000, debug=True)