/**
 * Socket.IO Module
 * =================
 * Handles WebSocket connections and real-time updates
 */

let socket;

/**
 * Initialize Socket.IO connection
 */
export function initSocket() {
    console.log('[SocketIO] Initializing socket connection...');
    window.socket = io({
        transports: ['websocket', 'polling'],
        upgrade: true,
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 10
    });
    socket = window.socket;

    socket.on('connect', () => {
        console.log('[SocketIO] Connected successfully! Socket ID:', socket.id);
        socket.emit('request_status');
    });

    socket.on('reconnect', (attemptNumber) => {
        console.log('[SocketIO] Reconnected after', attemptNumber, 'attempts');
    });

    socket.on('reconnect_attempt', (attemptNumber) => {
        console.log('[SocketIO] Reconnection attempt', attemptNumber);
    });

    socket.on('reconnect_error', (error) => {
        console.error('[SocketIO] Reconnection error:', error);
    });

    // Debug: Log all emits
    const originalEmit = socket.emit;
    socket.emit = function () {
        if (arguments[0] !== 'request_status') {
            console.log('>>> [Socket] Emitting:', arguments[0], arguments[1]);
        }
        return originalEmit.apply(this, arguments);
    };

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
