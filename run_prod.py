import os
import logging

# FORCE THREADING MODE
# Windows + OpenCV works best with real threads, not async/gevent.
os.environ['AYZARA_MODE'] = 'threading'

from app import create_app, init_database
import config

# Setup logging but suppress the "Development Server" warning
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger("prod")

# Filter out the Werkzeug warning
class NoDevWarningFilter(logging.Filter):
    def filter(self, record):
        return "development server" not in record.getMessage()

logging.getLogger("werkzeug").addFilter(NoDevWarningFilter())

logger.info("Initializing Ayzara Dashboard Application (Threading Mode)...")

# Create application
app, socketio = create_app()

# Initialize DB
with app.app_context():
    init_database(app)

if __name__ == '__main__':
    host = '0.0.0.0'
    port = 5000
    
    print(f"\n{'='*60}")
    print(f"   AYZARA DASHBOARD - PRODUCTION MODE (Stable)")
    print(f"   v{config.APP_VERSION}")
    print(f"{'='*60}")
    print(f"   ► Access Connect : http://<IP-SERVER>:{port}")
    print(f"   ► Engine         : Standard Threading (Best for OpenCV/Windows)")
    print(f"{'='*60}\n")
    
    # Run using SocketIO (Standard Threading)
    # This IS production ready for hardware apps because it isolates crashes
    # and handles blocking I/O (Cameras) much better than Gevent.
    socketio.run(app, 
                 host=host, 
                 port=port, 
                 debug=False,
                 use_reloader=False, 
                 log_output=True)
