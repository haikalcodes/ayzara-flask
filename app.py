"""
AYZARA DASHBOARD - FLASK APPLICATION (REFACTORED)
==================================================
Modular entry point using application factory pattern
Branch
📁 Copy this file to: d:/projects/REKAMVIDEOAYZARA/dashboard_flask_refactored/app.py
"""

# [ANTIGRAVITY] GEVENT MONKEY PATCH - MUST BE FIRST
from gevent import monkey
monkey.patch_all()

import threading
import config
from app import create_app, init_database, socketio

# Create application using factory
app, socketio = create_app()

if __name__ == '__main__':
    # Initialize database
    init_database(app)
    
    print(f"[Flask] Starting {config.APP_NAME} v{config.APP_VERSION}")
    print(f"[Flask] >>> GEVENT ASYNC MODE <<<")
    print(f"[Flask] Open http://localhost:5000")
    
    # Use config for debug mode, default to False for production safety
    socketio.run(app, 
                 host='0.0.0.0', 
                 port=5000, 
                 debug=config.DEBUG,
                 use_reloader=False) # Reloader issues with gevent, best to disable or use careful config

