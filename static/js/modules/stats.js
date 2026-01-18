/**
 * Stats Module
 * ============
 * Handles statistics updates and display
 */

/**
 * Update statistics display
 */
export function updateStats(stats) {
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

/**
 * Update recording status indicator
 */
export function updateRecordingStatus(data) {
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
