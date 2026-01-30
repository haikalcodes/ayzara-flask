/**
 * Socket.IO Module
 * =================
 * Handles WebSocket connection and event listeners
 */

let socket;
let statusUpdateCallbacks = [];

export function initSocket() {
    // Initialize SocketIO
    if (typeof io === 'undefined') {
        throw new Error('Socket.IO library not loaded');
    }

    if (!socket) {
        socket = io();
        window.socket = socket; // Expose to global scope for legacy scripts

        console.log('[SocketIO] Initialized');
    }

    // Debug: Log all emits
    const originalEmit = socket.emit;
    socket.emit = function () {
        if (arguments[0] !== 'request_status') {
            console.log('>>> [Socket] Emitting:', arguments[0], arguments[1]);
        }
        return originalEmit.apply(this, arguments);
    };

    socket.on('connect', () => {
        console.log('[SocketIO] Connected with ID:', socket.id);
    });

    socket.on('disconnect', (reason) => {
        console.log('[SocketIO] Disconnected. Reason:', reason);
    });

    return socket;
}

/**
 * Get socket instance
 */
export function getSocket() {
    return socket || window.socket;
}

/**
 * Register status update handler
 */
export function onStatusUpdate(callback) {
    const sock = getSocket();
    if (sock) {
        sock.on('status_update', callback);
    }
}
