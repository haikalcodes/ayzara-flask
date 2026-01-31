/**
 * Resource Monitor Module
 * =======================
 * Handles real-time system resource visualization
 */

import { getSocket } from './socket.js';

let isWarningSuppressed = false;

export function initResourceMonitor() {
    console.log('[Monitor] Initializing resource monitor...');

    const socket = getSocket();
    if (!socket) {
        console.warn('[Monitor] Socket not available yet, retrying in 1s...');
        setTimeout(initResourceMonitor, 1000);
        return;
    }

    // [ANTIGRAVITY] Reset suppression on connection (Server Restart)
    socket.on('connect', () => {
        isWarningSuppressed = false;
        console.log('[Monitor] Connected - Warning suppression reset');
    });

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

function showResourceWarning(data) {
    if (typeof Swal === 'undefined') return;

    // [ANTIGRAVITY] Prevent Spam: Don't stack alerts if one is already open
    if (Swal.isVisible()) return;

    // [ANTIGRAVITY] Suppression: Don't show again if closed once (until restart)
    if (isWarningSuppressed) return;

    // Default configuration for standard warnings
    let config = {
        icon: 'warning',
        title: 'Peringatan Sistem',
        html: `<strong>${data.resource || 'System'}</strong> usage: <strong>${data.percent || 0}%</strong><br>${data.message}`,
        background: '#1a1a2e',
        color: '#fff',
        confirmButtonColor: '#ff6b6b',
        timer: 5000,
        // Close handler to suppress future warnings
        didClose: () => {
            // [ANTIGRAVITY] Strict Suppression
            // User requested: "Once OK is clicked, don't show again until restart"
            if (!isWarningSuppressed) {
                isWarningSuppressed = true;
                console.log('[Monitor] All warnings suppressed until next server restart/page reload');
            }
        }
    };

    // [ANTIGRAVITY] Critical Action Handlers
    const troubleshootingInfo = `
        <div class="mt-3 pt-2 border-top border-secondary small text-warning opacity-75">
            <i class="bi bi-info-circle me-1"></i>
            <strong>Info:</strong> Jika aplikasi macet/hang, cek Kondisi Server & Refresh halaman di HP/PC Pegawai.
        </div>
    `;

    if (data.action === 'restart') {
        // Critical RAM -> Manual Restart Required
        config.icon = 'error';
        config.title = 'MEMORI SERVER KRITIS (RAM)';
        config.html = `
            <div class="text-start">
                <p>RAM (Memory) Server hampir penuh (<strong>${data.percent}%</strong>). Sistem mungkin tidak stabil atau crash.</p>
                <div class="alert alert-dark border border-secondary p-2 mb-2">
                    <strong>TINDAKAN DIPERLUKAN:</strong>
                    <ol class="mb-0 ps-3">
                        <li>Tutup jendela server (Command Prompt).</li>
                        <li>Jalankan ulang <code>run_prod.py</code> secara manual.</li>
                    </ol>
                </div>
                ${troubleshootingInfo}
            </div>
        `;
        config.timer = null; // Sticky
        config.showConfirmButton = true;
        config.confirmButtonText = 'Saya Mengerti (Tutup)';
    }
    else if (data.action === 'delete') {
        // Critical Disk -> Manual Cleanup Required
        config.icon = 'error';
        config.title = 'PENYIMPANAN SERVER PENUH';
        config.html = `
            <div class="text-start">
                <p>Penyimpanan (Disk) Server hampir penuh (<strong>${data.percent}%</strong>). Gagal menyimpan rekaman baru!</p>
                <div class="alert alert-dark border border-secondary p-2 mb-2">
                    <strong>TINDAKAN DIPERLUKAN:</strong>
                    <ul class="mb-0 ps-3">
                        <li>Hapus video lama di menu "Galeri Video".</li>
                        <li>Atau pindahkan file rekaman ke harddisk eksternal.</li>
                    </ul>
                </div>
                ${troubleshootingInfo}
            </div>
        `;
        config.timer = null; // Sticky
        config.showConfirmButton = true;
        config.confirmButtonText = 'OK, Saya Cek Folder';
    }

    Swal.fire(config);
}
