# rpi_api.py - API Server for Raspberry Pi Rebar Analysis

from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import time
import json
import base64
import cv2
import os
import numpy as np
from datetime import datetime
import traceback
import io
from PIL import Image

# Mock imports for testing without actual hardware
try:
    import picamera2
    HAS_CAMERA = True
except ImportError:
    HAS_CAMERA = False
    print("Warning: picamera2 not available. Using mock camera.")

# Import your actual rebar analysis components or use mocks
try:
    from master import RebarAnalysisApp
    HAS_ANALYSIS = True
except ImportError:
    HAS_ANALYSIS = False
    print("Warning: RebarAnalysisApp not available. Using mock analysis.")

app = Flask(__name__)
CORS(app)

# Configuration
RESULTS_DIR = "analysis_results"
CONFIG_FILE = "api_config.json"

# Default configuration
default_config = {
    "camera_enabled": True,
    "detection_threshold": 0.7,
    "cement_ratios": {
        "small": {"cement": 1, "sand": 2, "aggregate": 3, "diameter_range": [6, 12]},
        "medium": {"cement": 1, "sand": 2, "aggregate": 4, "diameter_range": [12, 20]},
        "large": {"cement": 1, "sand": 3, "aggregate": 5, "diameter_range": [20, 50]}
    }
}

# Global state
latest_analysis = {
    "timestamp": None,
    "image": None,
    "image_path": None,
    "segments": [],
    "total_volume": 0
}

camera = None
config = default_config.copy()

# Ensure directories exist
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

class MockCamera:
    """Mock camera for testing without hardware"""
    def __init__(self):
        self.running = False
        self.test_images = [
            np.zeros((400, 300, 3), dtype=np.uint8),  # Blank image
        ]
        # Try to load test images if available
        try:
            for i in range(1, 4):
                img = cv2.imread(f"test_image_{i}.jpg")
                if img is not None:
                    self.test_images.append(img)
        except:
            pass
        
        self.current_image_index = 0
    
    def start(self):
        self.running = True
    
    def stop(self):
        self.running = False
    
    def configure(self, config):
        pass
    
    def create_still_configuration(self, **kwargs):
        return {}
    
    def create_preview_configuration(self, **kwargs):
        return {}
    
    def capture_array(self):
        """Return a test image"""
        img = self.test_images[self.current_image_index].copy()
        # Add timestamp to image
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(img, f"MOCK: {timestamp}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        return img

def mock_rebar_detection(image):
    """Mock rebar detection for testing"""
    height, width = image.shape[:2]
    segments = []
    
    # Create 2-3 random boxes to simulate rebar segments
    num_segments = np.random.randint(2, 4)
    
    for i in range(num_segments):
        # Create random box
        x1 = np.random.randint(10, width//2)
        y1 = np.random.randint(10, height//2)
        x2 = np.random.randint(width//2, width-10)
        y2 = np.random.randint(height//2, height-10)
        
        # Calculate dimensions
        width_px = x2 - x1
        height_px = y2 - y1
        diameter_mm = min(width_px, height_px) * 0.1
        
        # Determine segment size
        size = "small"
        for category, info in config["cement_ratios"].items():
            if "diameter_range" in info:
                min_diam, max_diam = info["diameter_range"]
                if min_diam <= diameter_mm < max_diam:
                    size = category
                    break
        
        # Calculate volume
        length_cm = height_px * 0.1
        width_cm = width_px * 0.1
        height_cm = width_cm
        volume = length_cm * width_cm * height_cm
        
        # Add to segments
        segments.append({
            "section_id": i + 1,
            "size_category": size,
            "diameter_mm": round(diameter_mm, 2),
            "confidence": round(np.random.random() * 0.3 + 0.7, 3),
            "width_cm": round(width_cm, 2),
            "length_cm": round(length_cm, 2),
            "height_cm": round(height_cm, 2),
            "volume_cc": round(volume, 2),
            "bbox": [x1, y1, x2, y2]
        })
    
    # Draw the segments on the image
    result_image = image.copy()
    total_volume = 0
    
    for segment in segments:
        x1, y1, x2, y2 = segment["bbox"]
        color = (0, 255, 0)  # Green
        cv2.rectangle(result_image, (x1, y1), (x2, y2), color, 2)
        
        # Add label
        label = f"S{segment['section_id']} ({segment['size_category']})"
        cv2.putText(result_image, label, (x1, y1-10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        total_volume += segment["volume_cc"]
    
    return result_image, segments, total_volume

def initialize_camera():
    """Initialize the camera module"""
    global camera
    
    if HAS_CAMERA:
        try:
            camera = picamera2.Picamera2()
            # Use original 300x400 resolution
            config = camera.create_preview_configuration(main={"size": (300, 400)})
            camera.configure(config)
            camera.start()
            print("Camera initialized with dimensions (300x400)")
            return True
        except Exception as e:
            print(f"Failed to initialize camera: {e}")
            return False
    else:
        # Use mock camera
        camera = MockCamera()
        camera.start()
        print("Mock camera initialized")
        return True

def load_config():
    """Load configuration from file"""
    global config
    
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                loaded_config = json.load(f)
                # Update with loaded config but keep defaults for missing values
                for key, value in loaded_config.items():
                    config[key] = value
            print("Configuration loaded from file")
    except Exception as e:
        print(f"Error loading configuration: {e}")
        # Keep using default config

def save_config():
    """Save current configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print("Configuration saved to file")
    except Exception as e:
        print(f"Error saving configuration: {e}")

def capture_and_analyze():
    """Capture an image and run rebar analysis"""
    global latest_analysis
    
    try:
        # Make sure camera is initialized
        if camera is None:
            if not initialize_camera():
                return {
                    "success": False,
                    "error": "Failed to initialize camera"
                }
        
        # Generate timestamp for this analysis session
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        # Create a unique folder for this analysis session
        result_dir = os.path.join(RESULTS_DIR, f"analysis_{timestamp}")
        os.makedirs(result_dir, exist_ok=True)
        
        # Capture image
        print("Capturing image...")
        if HAS_CAMERA:
            # Stop camera
            camera.stop()
            # Configure for high resolution capture
            still_config = camera.create_still_configuration(main={"size": (300, 400)})
            camera.configure(still_config)
            camera.start()
            time.sleep(0.5)
            
            # Capture image
            frame = camera.capture_array()
            
            # Reset to preview mode
            camera.stop()
            preview_config = camera.create_preview_configuration(main={"size": (300, 400)})
            camera.configure(preview_config)
            camera.start()
        else:
            # Use mock camera
            frame = camera.capture_array()
        
        # Save original image
        original_path = os.path.join(result_dir, 'original_image.jpg')
        cv2.imwrite(original_path, frame)
        
        # Run analysis (either real or mock)
        print("Analyzing image...")
        if HAS_ANALYSIS:
            # Use actual rebar analysis logic here
            # This would be integrated with your existing code
            pass
        else:
            # Use mock analysis
            result_image, segments, total_volume = mock_rebar_detection(frame)
            
            # Save result image
            result_path = os.path.join(result_dir, 'result_image.jpg')
            cv2.imwrite(result_path, result_image)
            
            # Convert result image to base64 for transfer
            pil_img = Image.fromarray(cv2.cvtColor(result_image, cv2.COLOR_BGR2RGB))
            img_io = io.BytesIO()
            pil_img.save(img_io, 'JPEG')
            img_io.seek(0)
            img_b64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
            
            # Update latest analysis data
            latest_analysis = {
                "timestamp": timestamp,
                "image": img_b64,
                "image_path": result_path,
                "segments": segments,
                "total_volume": total_volume
            }
            
            # Save analysis results to JSON
            results_path = os.path.join(result_dir, 'analysis_results.json')
            with open(results_path, 'w') as f:
                json.dump({
                    "timestamp": timestamp,
                    "segments": segments,
                    "total_volume": total_volume
                }, f, indent=2)
            
            print(f"Analysis complete: {len(segments)} segments, {total_volume:.2f} cc")
        
        return {
            "success": True,
            "timestamp": timestamp,
            "segments_count": len(segments)
        }
        
    except Exception as e:
        print(f"Error in capture and analysis: {e}")
        print(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }

# Root endpoint for basic testing
@app.route('/')
def home():
    """Root endpoint for testing"""
    return "RebarVista API is running!"

@app.route('/api/status')
def status():
    """Return the API status"""
    return jsonify({
        "status": "online",
        "camera_available": camera is not None,
        "has_results": latest_analysis["timestamp"] is not None
    })

@app.route('/api/latest')
def get_latest():
    """Return the latest analysis results (without image)"""
    if latest_analysis["timestamp"] is None:
        return jsonify({
            "timestamp": None,
            "segments": [],
            "total_volume": 0,
            "image_available": False
        })
    
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
    result = capture_and_analyze()
    
    if result["success"]:
        return jsonify({
            "message": "Capture and analysis successful",
            "timestamp": result["timestamp"],
            "segments_count": result.get("segments_count", 0)
        })
    else:
        return jsonify({
            "error": result.get("error", "Unknown error during capture and analysis")
        }), 500

@app.route('/api/config', methods=["GET"])
def get_config():
    """Get the current configuration"""
    return jsonify(config)

@app.route('/api/config', methods=["POST"])
def update_config():
    """Update the configuration"""
    global config
    
    try:
        new_config = request.json
        
        # Update config with new values
        for key, value in new_config.items():
            if key in config:
                config[key] = value
        
        # Save updated config
        save_config()
        
        return jsonify({
            "message": "Configuration updated successfully",
            "config": config
        })
    except Exception as e:
        return jsonify({
            "error": f"Error updating configuration: {str(e)}"
        }), 500

def initial_setup():
    """Run initial setup tasks"""
    # Load saved configuration
    load_config()
    
    # Initialize camera
    if config.get("camera_enabled", True):
        initialize_camera()

if __name__ == "__main__":
    # Run initial setup
    initial_setup()
    
    # Start Flask app
    print("Starting RebarVista API Server...")
    app.run(host='0.0.0.0', port=5000, debug=True)