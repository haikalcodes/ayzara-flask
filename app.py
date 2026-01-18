"""
AYZARA DASHBOARD - FLASK APPLICATION (REFACTORED)
==================================================
Modular entry point using application factory pattern

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
    print(f"[Flask] Open http://localhost:5000")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)

# Test Comment: Fitur Multi Camera (Hanya ada di branch ini jika sudah di-COMMIT)

