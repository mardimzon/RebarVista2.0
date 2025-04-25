// static/js/scripts.js

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const connectionStatus = document.getElementById('connection-status');
    const statusMessage = document.getElementById('status-message');
    const lastCaptureTime = document.getElementById('last-capture-time');
    const captureBtn = document.getElementById('capture-btn');
    const loadingSpinner = document.getElementById('loading-spinner');
    const volumeInfoDiv = document.getElementById('volume-info');
    const volumeTableBody = document.querySelector('#volume-table tbody');
    const totalVolumeCell = document.getElementById('total-volume-cell');
    const downloadImageBtn = document.getElementById('download-image');
    const downloadCsvBtn = document.getElementById('download-csv');
    const downloadPdfBtn = document.getElementById('download-pdf');
    const processedImageLink = document.getElementById('processed-image-link');
    const processedImage = document.getElementById('processed-image');
    const modalImage = document.getElementById('modal-image');
    const imagePlaceholderIcon = document.getElementById('image-placeholder-icon');
    const imagePlaceholderText = document.getElementById('image-placeholder-text');
    const alertPlaceholder = document.getElementById('alert-placeholder');
    const settingsForm = document.getElementById('settings-form');
    const detectionThreshold = document.getElementById('detection-threshold');
    const thresholdValue = document.getElementById('threshold-value');
    const cameraEnabled = document.getElementById('camera-enabled');

    // Socket.IO setup
    const socket = io();
    let connected = false;

    // Reset application state on page load - IMPORTANT FIX
    window.addEventListener('load', function() {
        console.log("Page loaded - resetting state");
        resetApplicationState();
        // Clear any cached data from sessionStorage
        sessionStorage.removeItem('lastImageData');
    });

    // Function to reset application state
    function resetApplicationState() {
        // Reset image display
        updateImageDisplay(null);
        
        // Reset volume table
        volumeTableBody.innerHTML = '';
        totalVolumeCell.textContent = 'Total Volume: 0.00 cc';
        
        // Hide volume info initially
        volumeInfoDiv.style.display = 'none';
        
        // Reset last capture time
        lastCaptureTime.textContent = 'None';
        
        // Show the image placeholder
        document.querySelector('.image-placeholder').style.display = 'flex';
        imagePlaceholderIcon.className = 'fas fa-camera fa-5x text-muted';
        imagePlaceholderText.textContent = 'No image available';
    }

    // Function to format timestamps
    function formatTimestamp(timestamp) {
        if (!timestamp) return 'None';
        
        // Check if timestamp is in YYYYMMDD-HHMMSS format
        if (/^\d{8}-\d{6}$/.test(timestamp)) {
            const year = timestamp.substring(0, 4);
            const month = timestamp.substring(4, 6);
            const day = timestamp.substring(6, 8);
            const hour = timestamp.substring(9, 11);
            const minute = timestamp.substring(11, 13);
            const second = timestamp.substring(13, 15);
            
            const date = new Date(`${year}-${month}-${day}T${hour}:${minute}:${second}`);
            return date.toLocaleString();
        }
        
        // If it's a different format, try to parse it directly
        return new Date(timestamp).toLocaleString();
    }

    // Function to update connection status
    function updateConnectionStatus(isConnected) {
        connected = isConnected;
        
        if (isConnected) {
            connectionStatus.className = 'alert connected';
            statusMessage.innerHTML = '<i class="fas fa-check-circle me-2"></i>Connected to Raspberry Pi';
            captureBtn.disabled = false;
        } else {
            connectionStatus.className = 'alert disconnected';
            statusMessage.innerHTML = '<i class="fas fa-exclamation-circle me-2"></i>Disconnected from Raspberry Pi';
            captureBtn.disabled = true;
        }
    }

    // Function to show alerts
    function showAlert(message, type='success', duration=5000) {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        
        alertPlaceholder.appendChild(wrapper);
        
        // Auto-dismiss after duration
        if (duration > 0) {
            setTimeout(() => {
                wrapper.querySelector('.alert').classList.remove('show');
                setTimeout(() => {
                    wrapper.remove();
                }, 150);
            }, duration);
        }
    }

    // Function to clear alerts
    function clearAlerts() {
        alertPlaceholder.innerHTML = '';
    }

    // Populate the volume table with segments data
    function populateVolumeTable(segments, totalVolume) {
        // Clear existing rows
        volumeTableBody.innerHTML = '';

        // Add rows for each segment
        segments.forEach(seg => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${seg.section_id}</td>
                <td>${seg.volume_cc.toFixed(2)}</td>
                <td>${seg.width_cm.toFixed(2)}</td>
                <td>${seg.length_cm.toFixed(2)}</td>
                <td>${seg.height_cm.toFixed(2)}</td>
            `;
            volumeTableBody.appendChild(tr);
        });

        // Set total volume
        totalVolumeCell.textContent = `Total Volume: ${totalVolume.toFixed(2)} cc`;
    }

    // Function to update the image display - IMPROVED
    function updateImageDisplay(imageData) {
        // Clear any previous image
        processedImage.src = '';
        modalImage.src = '';
        
        if (!imageData) {
            // Hide image and show placeholder
            processedImageLink.style.display = 'none';
            document.querySelector('.image-placeholder').style.display = 'flex';
            imagePlaceholderIcon.className = 'fas fa-camera fa-5x text-muted';
            imagePlaceholderText.textContent = 'No image available';
            downloadImageBtn.disabled = true;
            return;
        }
        
        // Set image source
        const imgSrc = `data:image/jpeg;base64,${imageData}`;
        processedImage.src = imgSrc;
        modalImage.src = imgSrc;
        
        // Hide placeholder and show image
        document.querySelector('.image-placeholder').style.display = 'none';
        processedImageLink.style.display = 'block';
        downloadImageBtn.disabled = false;
    }

    // Function to fetch and display the latest data - IMPROVED FOR REFRESH
    function fetchLatestData() {
        // Clear current display data first
        updateImageDisplay(null);
        volumeTableBody.innerHTML = '';
        totalVolumeCell.textContent = 'Total Volume: 0.00 cc';
        
        fetch('/api/latest_data')
            .then(response => response.json())
            .then(data => {
                if (data.connected) {
                    updateConnectionStatus(true);
                    
                    // Update last capture time
                    lastCaptureTime.textContent = formatTimestamp(data.timestamp);
                    
                    // Update segments data if available
                    if (data.segments && data.segments.length > 0) {
                        populateVolumeTable(data.segments, data.total_volume);
                        volumeInfoDiv.style.display = 'block';
                    } else {
                        volumeInfoDiv.style.display = 'none';
                    }
                    
                    // Check if there's an image to fetch
                    if (data.has_image) {
                        fetchLatestImage();
                    } else {
                        updateImageDisplay(null);
                    }
                } else {
                    updateConnectionStatus(false);
                }
            })
            .catch(error => {
                console.error('Error fetching latest data:', error);
                updateConnectionStatus(false);
            });
    }

    // Function to fetch the latest processed image
    function fetchLatestImage() {
        fetch('/api/latest_image')
            .then(response => response.json())
            .then(data => {
                if (data.image) {
                    updateImageDisplay(data.image);
                } else {
                    updateImageDisplay(null);
                }
            })
            .catch(error => {
                console.error('Error fetching image:', error);
                updateImageDisplay(null);
            });
    }

    // Function to trigger a capture - IMPROVED FOR REFRESH
    function triggerCapture() {
        if (!connected) {
            showAlert('Not connected to Raspberry Pi', 'warning');
            return;
        }
        
        // Show loading spinner
        loadingSpinner.style.display = 'block';
        captureBtn.disabled = true;
        
        // Clear previous image and show processing indicator
        updateImageDisplay(null);
        document.querySelector('.image-placeholder').style.display = 'flex';
        imagePlaceholderIcon.className = 'fas fa-sync fa-spin fa-5x text-primary';
        imagePlaceholderText.textContent = 'Processing image...';
        
        // Trigger image capture on the Raspberry Pi
        fetch('/api/trigger_capture', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            // Hide loading spinner
            loadingSpinner.style.display = 'none';
            captureBtn.disabled = false;
            
            if (data.error) {
                showAlert(`Error: ${data.error}`, 'danger');
                imagePlaceholderIcon.className = 'fas fa-exclamation-circle fa-5x text-warning';
                imagePlaceholderText.textContent = 'Capture failed';
            } else {
                showAlert('Image captured and analyzed successfully', 'success');
                
                // Set a timeout to fetch the latest data
                setTimeout(function() {
                    fetchLatestData();
                    
                    // If no image is received after 5 seconds, reset the placeholder
                    setTimeout(function() {
                        if (document.querySelector('.image-placeholder').style.display === 'flex') {
                            imagePlaceholderIcon.className = 'fas fa-exclamation-circle fa-5x text-warning';
                            imagePlaceholderText.textContent = 'Image processing timed out';
                        }
                    }, 5000);
                }, 2000);
            }
        })
        .catch(error => {
            console.error('Error triggering capture:', error);
            showAlert('Failed to communicate with the server', 'danger');
            loadingSpinner.style.display = 'none';
            captureBtn.disabled = false;
            imagePlaceholderIcon.className = 'fas fa-exclamation-circle fa-5x text-warning';
            imagePlaceholderText.textContent = 'Connection error';
        });
    }

    // Function to fetch settings
    function fetchSettings() {
        fetch('/api/get_config')
            .then(response => response.json())
            .then(data => {
                // Update form values
                if (data.detection_threshold) {
                    detectionThreshold.value = data.detection_threshold;
                    thresholdValue.textContent = data.detection_threshold;
                }
                
                if (data.camera_enabled !== undefined) {
                    cameraEnabled.checked = data.camera_enabled;
                }
            })
            .catch(error => {
                console.error('Error fetching settings:', error);
            });
    }

    // Download the processed image
    downloadImageBtn.addEventListener('click', function() {
        if (!processedImage.src || processedImage.src === '') {
            showAlert('No processed image available to download', 'warning');
            return;
        }

        const link = document.createElement('a');
        link.href = processedImage.src;
        link.download = `rebar_analysis_${new Date().toISOString().replace(/[:.]/g, '-')}.jpg`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });

    // Download volume data as CSV
    downloadCsvBtn.addEventListener('click', function() {
        const rows = document.querySelectorAll('#volume-table tbody tr');
        if (rows.length === 0) {
            showAlert('No volume data available to download', 'warning');
            return;
        }

        const headers = ['Segment No.', 'Volume (cc)', 'Width (cm)', 'Length (cm)', 'Height (cm)'];
        const csvRows = [headers.join(',')];

        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            const rowData = Array.from(cells).map(cell => cell.textContent);
            csvRows.push(rowData.join(','));
        });

        const totalText = totalVolumeCell.textContent.replace('Total Volume: ', '');
        csvRows.push(`Total,,,,${totalText}`);

        const csvContent = csvRows.join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.href = url;
        link.download = `rebar_volume_${new Date().toISOString().replace(/[:.]/g, '-')}.csv`;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    });

    // Download volume data as PDF
    downloadPdfBtn.addEventListener('click', function() {
        const rows = document.querySelectorAll('#volume-table tbody tr');
        if (rows.length === 0) {
            showAlert('No volume data available to download', 'warning');
            return;
        }

        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();

        // Add title
        doc.setFontSize(16);
        doc.text('RebarVista Analysis Results', 14, 22);
        doc.setFontSize(12);
        doc.text(`Generated: ${new Date().toLocaleString()}`, 14, 30);

        let y = 40;

        // Headers
        doc.setFontSize(10);
        doc.text('Segment No.', 14, y);
        doc.text('Volume (cc)', 50, y);
        doc.text('Width (cm)', 85, y);
        doc.text('Length (cm)', 120, y);
        doc.text('Height (cm)', 155, y);
        
        y += 8;

        // Rows
        doc.setFontSize(9);
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            const rowData = Array.from(cells).map(cell => cell.textContent);
            
            doc.text(rowData[0], 14, y);  // Segment No
            doc.text(rowData[1], 50, y);  // Volume
            doc.text(rowData[2], 85, y);  // Width
            doc.text(rowData[3], 120, y); // Length
            doc.text(rowData[4], 155, y); // Height
            
            y += 8;
        });

        // Total volume
        const totalText = totalVolumeCell.textContent;
        y += 5;
        doc.setFontSize(11);
        doc.setFont(undefined, 'bold');
        doc.text(totalText, 120, y);

        // Add image if available
        if (processedImage.src && processedImage.src !== '') {
            try {
                y += 15;
                doc.text('Processed Image:', 14, y);
                y += 10;
                doc.addImage(processedImage.src, 'JPEG', 14, y, 180, 100);
            } catch (e) {
                console.error('Error adding image to PDF:', e);
            }
        }

        doc.save(`rebar_analysis_${new Date().toISOString().replace(/[:.]/g, '-')}.pdf`);
    });

    // Event listeners
    captureBtn.addEventListener('click', triggerCapture);

    // Detection threshold range input
    detectionThreshold.addEventListener('input', function() {
        thresholdValue.textContent = this.value;
    });

    // Settings form submission
    settingsForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Get values
        const configData = {
            detection_threshold: parseFloat(detectionThreshold.value),
            camera_enabled: cameraEnabled.checked
        };
        
        // Submit settings to the server
        fetch('/api/set_config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(configData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showAlert(`Error updating settings: ${data.error}`, 'danger');
            } else {
                showAlert('Settings updated successfully', 'success');
            }
        })
        .catch(error => {
            console.error('Error saving settings:', error);
            showAlert('Failed to save settings', 'danger');
        });
    });

    // Socket.IO event listeners
    socket.on('connect', function() {
        console.log('Socket.IO connected');
    });

    socket.on('connection_status', function(data) {
        updateConnectionStatus(data.connected);
    });

    socket.on('new_data', function(data) {
        console.log('New data received:', data);
        // Refresh the data display
        fetchLatestData();
    });

    socket.on('connection_error', function(data) {
        console.error('Socket connection error:', data.error);
        showAlert(`Connection error: ${data.error}`, 'danger');
    });

    // Initial setup
    fetchLatestData();
    fetchSettings();
    
    // Poll for connection status every 30 seconds
    setInterval(function() {
        fetch('/api/connection_status')
            .then(response => response.json())
            .then(data => {
                updateConnectionStatus(data.connected);
            })
            .catch(error => {
                console.error('Error checking connection:', error);
                updateConnectionStatus(false);
            });
    }, 30000);
});