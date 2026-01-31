"""
Safe Execution Utilities
========================
Decorators and helpers for crash-proof execution of functions.
"""
import functools
import traceback
from app.utils.logger import app_logger

def safe_socket_handler(f):
    """
    Decorator to wrap SocketIO event handlers in a try-except block.
    Prevents unhandled exceptions from crashing the Gevent greenlet or disconnecting the client.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            error_msg = f"SocketIO Handler Error [{f.__name__}]: {str(e)}"
            app_logger.error(error_msg, exc_info=True)
            print(f"[SafeSocket] ❌ {error_msg}")
            # Optionally emit an error back to client? 
            # Usually better to stay silent or generic to avoid leaking info, 
            # but for this app, maybe alert the user.
            try:
                from flask_socketio import emit
                emit('error_notification', {'message': 'Internal Server Error (Socket)', 'details': str(e)})
            except:
                pass
    return wrapper

def safe_thread_loop(name, interval=1.0):
    """
    Decorator/Factory for infinite thread loops.
    Ensures the loop NEVER dies even if an iteration crashes.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            print(f"[{name}] Starting safe loop...")
            while True:
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    print(f"[{name}] ❌ CRITICAL LOOP ERROR: {e}")
                    traceback.print_exc()
                    app_logger.error(f"Thread Loop Crash [{name}]: {e}", exc_info=True)
                    time.sleep(5.0) # Backoff before restart
                
                time.sleep(interval)
        return wrapper
    return decorator
