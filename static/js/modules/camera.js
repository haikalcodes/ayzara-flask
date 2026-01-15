/**
 * Camera Module
 * =============
 * Handles camera operations and frame capture
 */

/**
 * Capture frame from camera
 */
export async function captureFrame() {
    const btn = document.getElementById('captureBtn');
    const preview = document.getElementById('capturePreview');
    const status = document.getElementById('captureStatus');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Menangkap Gambar...';
    }

    if (status) {
        status.innerHTML = '<div class="alert alert-info"><span class="spinner-border spinner-border-sm me-2"></span>📷 Menghubungkan ke kamera...</div>';
    }

    try {
        // Get selected camera URL if available
        const select = document.getElementById('cameraSelect');
        const url = select ? select.value : null;

        if (select && !url) {
            alert('Silakan pilih kamera terlebih dahulu');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-camera me-2"></i>Capture';
            }
            if (status) status.innerHTML = '';
            return;
        }

        const body = url ? JSON.stringify({ url: url }) : null;
        const headers = url ? { 'Content-Type': 'application/json' } : {};

        const response = await fetch('/api/camera/capture', {
            method: 'POST',
            headers: headers,
            body: body
        });

        const data = await response.json();

        if (data.success) {
            if (preview) {
                preview.innerHTML = `
                    <img src="${data.path}?t=${Date.now()}" class="img-fluid rounded" alt="Captured Frame">
                    <div class="mt-3">
                        <a href="${data.path}" download="${data.filename}" class="btn btn-primary me-2">
                            <i class="bi bi-download me-2"></i>Download
                        </a>
                        <button onclick="captureFrame()" class="btn btn-glass">
                            <i class="bi bi-arrow-repeat me-2"></i>Capture Lagi
                        </button>
                    </div>
                `;
            }
            if (status) {
                status.innerHTML = '<div class="alert alert-success">✅ Gambar berhasil ditangkap!</div>';
            }
        } else {
            if (status) {
                console.log(data);
                status.innerHTML = `<div class="alert alert-danger">❌ Error: Kamera tidak terhubung!</div>`;
            }
        }
    } catch (error) {
        if (status) {
            status.innerHTML = `<div class="alert alert-danger">❌ Error: ${error.message}</div>`;
        }
    }

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-camera me-2"></i>Capture';
    }
}

/**
 * Generate thumbnails batch
 */
export async function generateThumbnails() {
    const btn = document.getElementById('btnGenerateThumbs');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    }

    try {
        const response = await fetch('/api/generate-thumbnails-batch', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            alert(`✅ Thumbnail Generated!\n\nGenerated: ${data.generated}\nSkipped (sudah ada): ${data.skipped}\nErrors: ${data.errors}`);
            location.reload();
        } else {
            alert('❌ Error: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        alert('❌ Error: ' + error.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-image"></i>';
        }
    }
}

// Make functions globally available
window.captureFrame = captureFrame;
window.generateThumbnails = generateThumbnails;
