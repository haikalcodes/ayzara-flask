"""
AYZARA DASHBOARD - FLASK APPLICATION (REFACTORED)
==================================================
Modular entry point using application factory pattern
Branch
📁 Copy this file to: d:/projects/REKAMVIDEOAYZARA/dashboard_flask_refactored/app.py
"""

import threading
import config
from app import create_app, init_database, socketio

# Create application using factory
app, socketio = create_app()

if __name__ == '__main__':
    # Initialize database
    init_database(app)
    
    print(f"[Flask] Starting {config.APP_NAME} v{config.APP_VERSION}")
    print(f"[Flask] >>> REFACTORED MODULAR ARCHITECTURE <<<")
    print(f"[Flask] Open https://192.168.43.94:5000 (SSL Enabled)")
    
    import os
    base_dir = os.path.abspath(os.path.dirname(__file__))
    cert = os.path.join(base_dir, '192.168.43.94+2.pem')
    key = os.path.join(base_dir, '192.168.43.94+2-key.pem')
    
    print(f"[Flask] SSL Cert: {cert}")
    print(f"[Flask] SSL Key: {key}")

    # Use ssl_context for Werkzeug
    socketio.run(app, 
                 host='0.0.0.0', 
                 port=5000, 
                 debug=True, 
                 allow_unsafe_werkzeug=True,
                 ssl_context=(cert, key))

# Test Comment: Fitur Multi Camera (Hanya ada di branch ini jika sudah di-COMMIT)

