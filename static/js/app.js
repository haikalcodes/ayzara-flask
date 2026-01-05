/**
 * AYZARA DASHBOARD - Main JavaScript
 * ===================================
 * Handles real-time updates, UI interactions, and API calls
 */

// ============================================
// SOCKET.IO CONNECTION
// ============================================

let socket;

function initSocket() {
    socket = io();

    socket.on('connect', () => {
        console.log('[SocketIO] Connected');
        socket.emit('request_status');
    });

    socket.on('status_update', (data) => {
        updateRecordingStatus(data);
    });

    socket.on('disconnect', () => {
        console.log('[SocketIO] Disconnected');
    });
}

// ============================================
// RECORDING STATUS
// ============================================

function updateRecordingStatus(data) {
    const indicator = document.getElementById('globalRecordingIndicator');
    const recordingDot = document.getElementById('recording-dot');

    if (data.is_recording) {
        if (indicator) {
            indicator.style.display = 'flex';
        }
        if (recordingDot) {
            recordingDot.classList.add('recording');
        }
    } else {
        if (indicator) {
            indicator.style.display = 'none';
        }
        if (recordingDot) {
            recordingDot.classList.remove('recording');
        }
    }

    // Update stats if elements exist
    if (data.stats) {
        updateStats(data.stats);
    }
}

function updateStats(stats) {
    const elements = {
        'stat-total': stats.total,
        'stat-completed': stats.completed,
        'stat-errors': stats.errors,
        'stat-avg-duration': stats.avg_duration + 's',
        'stat-size': stats.total_size_mb + ' MB'
    };

    for (const [id, value] of Object.entries(elements)) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
        }
    }
}

// ============================================
// DATETIME UPDATE
// ============================================

function updateDateTime() {
    const el = document.getElementById('datetime');
    if (el) {
        const now = new Date();
        el.textContent = now.toLocaleString('id-ID', {
            weekday: 'short',
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
}

// ============================================
// SIDEBAR TOGGLE
// ============================================

function initSidebar() {
    const toggleBtn = document.getElementById('toggleSidebar');
    const sidebar = document.getElementById('sidebar');

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('show');
        });

        // Close on click outside (mobile)
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 992) {
                if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
                    sidebar.classList.remove('show');
                }
            }
        });
    }
}

// ============================================
// CAMERA CAPTURE
// ============================================

async function captureFrame() {
    const btn = document.getElementById('captureBtn');
    const preview = document.getElementById('capturePreview');
    const status = document.getElementById('captureStatus');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Capturing...';
    }

    if (status) {
        status.innerHTML = '<div class="alert alert-info">📷 Capturing frame...</div>';
    }

    try {
        const response = await fetch('/api/camera/capture', {
            method: 'POST'
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
                            <i class="bi bi-arrow-repeat me-2"></i>Capture Again
                        </button>
                    </div>
                `;
            }
            if (status) {
                status.innerHTML = '<div class="alert alert-success">✅ Frame captured successfully!</div>';
            }
        } else {
            if (status) {
                status.innerHTML = `<div class="alert alert-danger">❌ Error: ${data.error}</div>`;
            }
        }
    } catch (error) {
        if (status) {
            status.innerHTML = `<div class="alert alert-danger">❌ Error: ${error.message}</div>`;
        }
    }

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-camera me-2"></i>Capture Frame';
    }
}

// ============================================
// VIDEO PLAYER MODAL
// ============================================

function playVideo(videoPath, resi, duration) {
    const modal = new bootstrap.Modal(document.getElementById('videoModal'));
    const video = document.getElementById('modalVideo');
    const title = document.getElementById('modalVideoTitle');

    if (video) {
        video.src = videoPath;
        video.load();
    }

    if (title) {
        title.textContent = `${resi} (${duration}s)`;
    }

    modal.show();

    // Pause on close
    document.getElementById('videoModal').addEventListener('hidden.bs.modal', () => {
        if (video) {
            video.pause();
            video.src = '';
        }
    }, { once: true });
}

// ============================================
// PEGAWAI FORM
// ============================================

function showAddPegawaiModal() {
    const modal = new bootstrap.Modal(document.getElementById('pegawaiModal'));
    document.getElementById('pegawaiForm').reset();
    document.getElementById('pegawaiModalTitle').textContent = 'Tambah Pegawai';
    document.getElementById('pegawaiId').value = '';
    modal.show();
}

function editPegawai(id) {
    fetch(`/api/pegawai/${id}`)
        .then(res => res.json())
        .then(data => {
            document.getElementById('pegawaiId').value = data.id;
            document.getElementById('pegawaiNama').value = data.nama || '';
            document.getElementById('pegawaiJabatan').value = data.jabatan || '';
            document.getElementById('pegawaiTelepon').value = data.telepon || '';
            document.getElementById('pegawaiEmail').value = data.email || '';
            document.getElementById('pegawaiAlamat').value = data.alamat || '';
            document.getElementById('pegawaiModalTitle').textContent = 'Edit Pegawai';

            const modal = new bootstrap.Modal(document.getElementById('pegawaiModal'));
            modal.show();
        });
}

async function savePegawai(event) {
    event.preventDefault();

    const form = document.getElementById('pegawaiForm');
    const formData = new FormData(form);
    const id = document.getElementById('pegawaiId').value;

    const url = id ? `/api/pegawai/${id}` : '/api/pegawai';
    const method = id ? 'PUT' : 'POST';

    try {
        const response = await fetch(url, {
            method: method,
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            location.reload();
        } else {
            alert('Error saving pegawai');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function deletePegawai(id, nama) {
    if (!confirm(`Hapus pegawai "${nama}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/pegawai/${id}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            location.reload();
        } else {
            alert('Error deleting pegawai');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

// ============================================
// EXPORT
// ============================================

function exportCSV() {
    window.location.href = '/api/export/csv';
}

function exportPDF() {
    window.location.href = '/api/export/pdf';
}

// ============================================
// THUMBNAIL GENERATION
// ============================================

async function generateThumbnails() {
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

// ============================================
// SOCIAL MEDIA SHARE
// ============================================

function shareToSocial(platform, videoUrl, resi) {
    const text = `📦 Video Packing - ${resi}`;
    const url = encodeURIComponent(window.location.origin + videoUrl);

    let shareUrl;

    switch (platform) {
        case 'facebook':
            shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${url}`;
            break;
        case 'twitter':
            shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${url}`;
            break;
        case 'whatsapp':
            shareUrl = `https://wa.me/?text=${encodeURIComponent(text + ' ' + window.location.origin + videoUrl)}`;
            break;
        case 'telegram':
            shareUrl = `https://t.me/share/url?url=${url}&text=${encodeURIComponent(text)}`;
            break;
        default:
            // Copy to clipboard
            navigator.clipboard.writeText(window.location.origin + videoUrl);
            alert('Link copied to clipboard!');
            return;
    }

    window.open(shareUrl, '_blank', 'width=600,height=400');
}

// ============================================
// POLLING FOR UPDATES (fallback if WebSocket fails)
// ============================================

let pollInterval;

function startPolling() {
    pollInterval = setInterval(async () => {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            updateRecordingStatus(data);
        } catch (error) {
            console.error('[Polling] Error:', error);
        }
    }, 5000);
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
    }
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize components
    initSidebar();
    updateDateTime();

    // Update datetime every minute
    setInterval(updateDateTime, 60000);

    // Try WebSocket first, fallback to polling
    try {
        initSocket();
    } catch (error) {
        console.warn('[SocketIO] Failed, using polling fallback');
        startPolling();
    }

    console.log('[AYZARA] Dashboard initialized');
});
