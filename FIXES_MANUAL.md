# FIXES NEEDED - Apply these changes manually

## 1. Fix recording.html - Add viewLastRecording function wrapper
File: templates/pages/recording.html
Line: Around 952

REPLACE:
```javascript
    if (lastRecordingData) {
        openVideoModal(lastRecordingData);
    } else {
        alert('Tidak ada rekaman terakhir');
    }
```

WITH:
```javascript
    // View last recording in popup
    function viewLastRecording() {
        if (lastRecordingData) {
            openVideoModal(lastRecordingData);
        } else {
            alert('Tidak ada rekaman terakhir');
        }
    }
```

## 2. Fix app.py - Update serve_recording for video playback
File: app.py
Line: Around 1141

REPLACE:
```python
@app.route('/recordings/<path:filename>')
def serve_recording(filename):
    """Serve recording video files"""
    # Debug info
    print(f">>> [Serving] Request for: {filename}")
    print(f">>> [Serving] From folder: {config.RECORDINGS_FOLDER}")
    return send_from_directory(config.RECORDINGS_FOLDER, filename)
```

WITH:
```python
@app.route('/recordings/<path:filename>')
def serve_recording(filename):
    """Serve recording video files from hierarchical structure"""
    # filename is relative path: 2026-01-06/SHOPEE/test/RESI_PLATFORM_AYZARA_001.mp4
    print(f">>> [Serving] Request for: {filename}")
    print(f">>> [Serving] From folder: {config.RECORDINGS_FOLDER}")
    
    # Construct full path
    full_path = config.RECORDINGS_FOLDER / filename
    
    if not full_path.exists():
        print(f">>> [Serving] File not found: {full_path}")
        return "File not found", 404
    
    # Get file extension
    file_ext = full_path.suffix.lower()
    
    # Set proper MIME type for videos
    mimetype = 'video/mp4' if file_ext == '.mp4' else 'application/octet-stream'
    
    # Serve with proper headers for video streaming
    response = send_from_directory(full_path.parent, full_path.name, mimetype=mimetype)
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Content-Type'] = mimetype
    
    return response
```

## 3. Fix videos.html - Center modal without scroll
File: templates/pages/videos.html
Line: Around 179

REPLACE:
```html
<div class="modal-dialog modal-xl modal-dialog-centered">
```

WITH:
```html
<div class="modal-dialog modal-xl modal-dialog-centered" style="max-height: 90vh; margin: 5vh auto;">
```

AND add this CSS in the same file (in <style> tag or at the end):
```css
<style>
#videoModal .modal-dialog {
    display: flex;
    align-items: center;
    min-height: calc(100% - 1rem);
}

#videoModal .modal-content {
    max-height: 90vh;
    overflow: hidden;
}

#videoModal .modal-body {
    overflow-y: auto;
    max-height: calc(90vh - 120px);
}
</style>
```

## 4. Add same fix to recording.html modal
File: templates/pages/recording.html
Line: Around 179 (in the modal section you added)

Apply the same modal centering fix as #3 above.

## 5. Camera disconnect handling - Add to app.py
File: app.py
In VideoCamera class, update() method, around line 800

ADD after line that checks for errors:
```python
# In the update() method, after checking for reconnection failures
if self.consecutive_errors > 5:
    print(f"[Camera] Too many errors ({self.consecutive_errors}), stopping stream: {self.url}")
    self.running = False
    break
```

## 6. Camera disconnect feedback - Add to recording.html
File: templates/pages/recording.html
In startPreview() function, around line 370

ADD error handler:
```javascript
// Add interval to check if stream is still alive
const streamCheckInterval = setInterval(() => {
    if (!img.complete || img.naturalHeight === 0) {
        clearInterval(streamCheckInterval);
        document.getElementById('camera-status-indicator').innerHTML = '<span class="text-danger">🔴 Kamera Terputus</span>';
        
        // Show error in placeholder
        placeholder.classList.remove('d-none');
        placeholder.classList.add('d-flex');
        placeholder.style.display = 'flex';
        img.style.display = 'none';
        
        placeholder.innerHTML = `
            <i class="fs-1 mb-3 text-danger">⚠️</i>
            <h4 class="text-danger">Koneksi Kamera Terputus</h4>
            <p>Kamera tidak merespon atau koneksi terputus.</p>
            <button class="btn btn-primary mt-2" onclick="startPreview()">🔄 Reconnect</button>
        `;
    }
}, 3000); // Check every 3 seconds
```
