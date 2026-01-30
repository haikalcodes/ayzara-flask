/**
 * AYZARA DASHBOARD - Main JavaScript (Refactored)
 * ================================================
 * Main orchestrator that imports and coordinates all modules
 */

// Import modules
import { initSocket, onStatusUpdate } from './modules/socket.js';
import { initSidebar, updateDateTime } from './modules/ui.js';
import { updateRecordingStatus } from './modules/stats.js';

// Import and expose camera functions
import './modules/camera.js';
import './modules/pegawai.js';
import { initResourceMonitor } from './modules/monitor.js';

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
    console.log('[AYZARA] Initializing modular dashboard...');

    // Initialize UI components
    initSidebar();
    updateDateTime();

    // Update datetime every minute
    setInterval(updateDateTime, 60000);

    // Try WebSocket first, fallback to polling
    try {
        initSocket();
        initResourceMonitor(); // Initialize resource monitor

        // Register status update handler
        onStatusUpdate((data) => {
            updateRecordingStatus(data);
        });
    } catch (error) {
        console.warn('[SocketIO] Failed, using polling fallback');
        startPolling();
    }

    console.log('[AYZARA] Dashboard initialized (Modular Architecture)');
});
