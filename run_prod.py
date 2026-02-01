import os
# [ANTIGRAVITY] GEVENT MONKEY PATCH - MUST BE FIRST
from gevent import monkey
monkey.patch_all()

import logging

# PRODUCTION MODE (GEVENT)
os.environ['AYZARA_MODE'] = 'production'

from app import create_app, init_database
import config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger("prod")

logger.info("Initializing Ayzara Dashboard Application (Production/Gevent Mode)...")

# Create application
app, socketio = create_app()

# [ANTIGRAVITY] FINAL VERIFICATION
print("SocketIO async mode:", socketio.async_mode)

# Initialize DB
with app.app_context():
    init_database(app)

if __name__ == '__main__':
    host = '0.0.0.0'
    port = 5000
    
    # Check for SSL
    cert_path = os.path.join("ssl", "cert.pem")
    key_path = os.path.join("ssl", "key.pem")
    ssl_args = {}
    
    protocol = "http"
    if os.path.exists(cert_path) and os.path.exists(key_path):
        print(f"[Gevent] SSL Enabled: {cert_path}")
        # Gevent/SocketIO uses keyfile/certfile
        ssl_args = {
            'keyfile': key_path,
            'certfile': cert_path
        }
        protocol = "https"
    
    # Detect IP
    import socket
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"

    print(f"\n{'='*60}")
    print(f"   AYZARA DASHBOARD - PRODUCTION MODE (Stable)")
    print(f"   v{config.APP_VERSION}")
    print(f"{'='*60}")
    print(f"   >> Local Access   : {protocol}://localhost:{port}")
    print(f"   >> Network Access : {protocol}://{local_ip}:{port}")
    print(f"   >> Engine         : Gevent (Async/Monkey Patched)")
    if ssl_args:
        print(f"   >> Security       : SSL/TLS Enabled")
    print(f"{'='*60}\n")
    
    # Run using SocketIO (Gevent)
    try:
        if ssl_args:
             socketio.run(app, 
                         host=host, 
                         port=port, 
                         debug=False,
                         use_reloader=False, 
                         log_output=True,
                         **ssl_args)
        else:
             socketio.run(app, 
                         host=host, 
                         port=port, 
                         debug=False,
                         use_reloader=False, 
                         log_output=True)
    except KeyboardInterrupt:
        print("Server stopped by user.")
