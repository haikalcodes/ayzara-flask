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

    // Listen for restart notifications
    socket.on('system_restart', (data) => {
        showRestartNotification(data);
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

function showResourceWarning(data) {
    if (typeof Swal === 'undefined') return;

    Swal.fire({
        icon: 'warning',
        title: 'System Warning',
        html: `<strong>${data.resource || 'System'}</strong> usage is at <strong>${data.percent || data.ram}%</strong><br>${data.message}`,
        background: '#1a1a2e',
        color: '#fff',
        confirmButtonColor: '#ff6b6b',
        timer: 10000
    });
}

function showRestartNotification(data) {
    if (typeof Swal === 'undefined') return;

    Swal.fire({
        icon: 'error',
        title: 'System Restarting',
        html: `<strong>Critical RAM Usage: ${data.ram}%</strong><br>System will restart in ${data.countdown} seconds to prevent crash.`,
        background: '#1a1a2e',
        color: '#fff',
        timer: data.countdown * 1000,
        timerProgressBar: true,
        showConfirmButton: false,
        allowOutsideClick: false
    });
}
