/**
 * Application Utilities (app_utils.js)
 * Shared logic for Sound Effects and Toast Notifications.
 * Available globally via window object.
 */

// ==========================================
// TOAST NOTIFICATIONS (SweetAlert2 Mixin)
// ==========================================
window.Toast = Swal.mixin({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 3000,
    timerProgressBar: true,
    didOpen: (toast) => {
        toast.addEventListener('mouseenter', Swal.stopTimer)
        toast.addEventListener('mouseleave', Swal.resumeTimer)
    }
});

// ==========================================
// SAFE DIALOG WRAPPER (Anti-Spam)
// ==========================================
// Use this for alerts triggered by events (errors, sockets) 
// to prevent stacking/spamming multiple dialogs.
window.showSafeDialog = function (config) {
    if (typeof Swal === 'undefined') return;

    // If a dialog is already open, do not show another one.
    if (Swal.isVisible()) {
        console.log('[SafeDialog] Blocked implicit dialog (Anti-Spam)');
        return;
    }

    return Swal.fire(config);
};

// ==========================================
// SOUND ENGINE (AudioContext)
// ==========================================
// Initialize AudioContext lazily to handle browser policies
let audioCtx = null;

function initAudioContext() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    return audioCtx;
}

// Function to play a synthesized tone
window.playTone = function (freq, type, duration, vol = 0.1) {
    const ctx = initAudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime);

    gain.gain.setValueAtTime(0, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(vol, ctx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + duration);
};

// Main Sound Player
window.playSound = function (name) {
    try {
        switch (name) {
            // 1. Scan Berhasil (Idle/Start) -> "Tit"
            case 'start':
            case 'beep':
                playTone(1500, 'sine', 0.1, 0.2);
                break;

            // 2. Scan saat Recording -> "Tit" (Sama persis)
            case 'scan_warning':
                playTone(1500, 'sine', 0.1, 0.2);
                break;

            // 3. Recording START (Baru mulai rekam) -> "Blip-Blop"
            case 'record_start':
                playTone(600, 'sine', 0.1, 0.2);
                setTimeout(() => playTone(800, 'sine', 0.15, 0.2), 100);
                break;

            // 4. Simpan Video / Success -> "Chime"
            case 'save':
            case 'success':
                playTone(523.25, 'sine', 0.2, 0.2); // C5
                setTimeout(() => playTone(659.25, 'sine', 0.2, 0.2), 100); // E5
                setTimeout(() => playTone(783.99, 'sine', 0.4, 0.2), 200); // G5
                break;

            // 5. Error -> "Buzz"
            case 'error':
                playTone(150, 'sawtooth', 0.3, 0.2);
                break;

            // 6. Camera Connected -> "Ding-Dong" (Ascending chime)
            case 'camera_connected':
                playTone(440, 'sine', 0.15, 0.15); // A4
                setTimeout(() => playTone(554.37, 'sine', 0.25, 0.15), 120); // C#5
                break;

            default:
                playTone(440, 'sine', 0.1);
        }
    } catch (e) {
        console.error("Audio error:", e);
    }
};

// Auto-initialize on first user interaction to unlock AudioContext
['click', 'keydown', 'touchstart'].forEach(event => {
    window.addEventListener(event, () => {
        if (!audioCtx) initAudioContext();
    }, { once: true });
});
