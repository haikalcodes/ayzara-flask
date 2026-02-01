import os
# [ANTIGRAVITY] GEVENT MONKEY PATCH - MUST BE FIRST
from gevent import monkey
monkey.patch_all()

import logging
import ssl
import socket

# DEV MODE (GEVENT)
os.environ['AYZARA_MODE'] = 'development'

from app import create_app, init_database
import config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger("secure_dev")

app, socketio = create_app()

with app.app_context():
    init_database(app)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

if __name__ == '__main__':
    host = '0.0.0.0'
    port = 5000
    local_ip = get_local_ip()
    
    # Path to certificates in ssl/ folder
    cert_path = os.path.join("ssl", "cert.pem")
    key_path = os.path.join("ssl", "key.pem")
    
    print(f"\n{'='*60}")
    print(f"   AYZARA DASHBOARD - SECURE DEV MODE (HTTPS)")
    print(f"   v{config.APP_VERSION}")
    print(f"{'='*60}")
    print(f"   >> Access Secure : https://{local_ip}:{port}")
    print(f"   >> Engine         : Gevent (Async/Monkey Patched)")
    print(f"   >> Note           : Install ssl/rootCA.pem on phone for valid lock!")
    print(f"{'='*60}\n")
    

    if os.path.exists(cert_path) and os.path.exists(key_path):
        logger.info(f"Loading SSL from {cert_path}...")
        # Start Resource Monitor
        from app.services.resource_monitor import start_resource_monitoring
        start_resource_monitoring()
        
        # Run with SSL (Gevent uses keyfile/certfile)
        socketio.run(app, 
                     host=host, 
                     port=port, 
                     debug=True,
                     use_reloader=False, 
                     log_output=True,
                     keyfile=key_path,
                     certfile=cert_path)
    else:
        logger.error(f"SSL Certificates not found at {cert_path}")
        logger.error("Please run 'installer_ssl.bat' first.")
