/**
 * Resource Monitor Module
 * =======================
 * Handles real-time system resource visualization
 */

import { getSocket } from './socket.js';

export function initResourceMonitor() {
    console.log('[Monitor] Initializing resource monitor...');

    const socket = getSocket();
    if (!socket) {
        console.warn('[Monitor] Socket not available yet, retrying in 1s...');
        setTimeout(initResourceMonitor, 1000);
        return;
    }

    // Listen for resource updates
    socket.on('resource_update', (data) => {
        updateResourceUI(data);
    });

    // Listen for warnings
    socket.on('resource_warning', (data) => {
        showResourceWarning(data);
    });

    console.log('[Monitor] Resource monitor initialized');
}

function updateResourceUI(data) {
    // RAM
    const ramPercent = data.ram_percent || data.ram || 0; // Handle different key names if any
    updateProgressBar('ram', ramPercent, `${data.ram_used_gb?.toFixed(1) || 0} / ${data.ram_total_gb?.toFixed(1) || 0} GB`);

    // CPU
    const cpuPercent = data.cpu_percent || data.cpu || 0;
    updateProgressBar('cpu', cpuPercent, `${data.cpu_cores || 0} cores`);

    // Disk
    const diskPercent = data.disk_percent || data.disk || 0;
    updateProgressBar('disk', diskPercent, `${data.disk_used_gb?.toFixed(1) || 0} / ${data.disk_total_gb?.toFixed(1) || 0} GB`);

    const statusEl = document.getElementById('monitor-status');

    // Status indicator
    if (statusEl) {
        statusEl.className = 'badge bg-success';
        statusEl.textContent = 'Live';
    }
}

function updateProgressBar(id, percent, detailText) {
    const percentEl = document.getElementById(`${id}-percent`);
    const detailEl = document.getElementById(`${id}-detail`);
    const barEl = document.getElementById(`${id}-bar`);

    if (percentEl) percentEl.textContent = percent.toFixed(1) + '%';
    if (detailEl) detailEl.textContent = detailText;

    if (barEl) {
        barEl.style.width = percent + '%';
        barEl.className = 'progress-bar ' + getColorClass(percent);
    }
}

function getColorClass(percent) {
    if (percent >= 90) return 'bg-danger';
    if (percent >= 75) return 'bg-warning';
    if (percent >= 50) return 'bg-info';
    return 'bg-success';
}

let warningShown = false; // [ANTIGRAVITY] Spam Prevention Flag

function showResourceWarning(data) {
    if (typeof Swal === 'undefined') return;
    if (warningShown) return; // Prevent spam if already shown

    const resourceName = data.resource === 'CPU' ? 'CPU Server' :
        data.resource === 'RAM' ? 'RAM Server' : data.resource;

    // Determine action advice
    let advice = 'Silakan periksa kondisi server.';
    if (data.resource === 'Disk') advice = 'Mohon hapus data lama atau arsipkan video.';
    else advice = 'Silakan restart server website (run_prod.bat) agar performa kembali lancar.';

    warningShown = true; // Set flag

    Swal.fire({
        icon: 'warning',
        title: `⚠️ ${resourceName} Critical!`,
        html: `
            <div class="text-start">
                <p>Penggunaan <strong>${resourceName}</strong> mencapai <strong>${data.percent}%</strong>.</p>
                <p class="mb-2 text-warning">${advice}</p>
                <hr>
                <p class="small text-muted mb-0">
                    <i class="bi bi-info-circle me-1"></i> 
                    Jika halaman macet/hang, silakan refresh browser Anda. 
                    Notifikasi ini tidak akan muncul lagi sampai halaman di-refresh.
                </p>
            </div>
        `,
        background: '#1a1a2e',
        color: '#fff',
        confirmButtonColor: '#ffc107',
        confirmButtonText: 'Oke, Mengerti',
        allowOutsideClick: false
    }).then(() => {
        // Optional: Could reset flag here if we want to allow re-showing after explicit dismissal,
        // but user requested "only once until restart/page load", so we keep it true.
    });
}

// showRestartNotification removed as requested
