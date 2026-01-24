"""
Application Factory (UPDATED)
==============================
Complete application factory with all blueprints registered

📁 Copy to: dashboard_flask_refactored/app/__init__.py
"""

from flask import Flask
from flask_socketio import SocketIO
from flask_login import LoginManager
import threading

# Import configuration
import config

# Import models
from app.models import db, init_models

# Global instances
socketio = None
login_manager = None

# Global state
camera_status_cache = {}
camera_status_lock = threading.Lock()
camera_usage = {}
camera_usage_lock = threading.Lock()
_project_config_cache = None
_config_lock = threading.Lock()


def create_app(config_object=config):
    """
    Application factory function
    
    Args:
        config_object: Configuration object (default: config module)
    
    Returns:
        Tuple of (Flask app, SocketIO instance)
    """
    global socketio, login_manager
    
    # Create Flask app with correct paths
    # Since app is in app/ package, we need to point to parent directory for templates/static
    import os
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    app = Flask(__name__, 
                template_folder=os.path.join(parent_dir, 'templates'),
                static_folder=os.path.join(parent_dir, 'static'))
    app.config.from_object(config_object)
    app.config['SECRET_KEY'] = config_object.SECRET_KEY
    
    # Initialize extensions
    db.init_app(app)
    
    # Initialize models
    with app.app_context():
        init_models()
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Silakan login terlebih dahulu'
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))
    
    # Initialize SocketIO
    import os
    mode = 'gevent' if os.environ.get('AYZARA_MODE') == 'production' else 'threading'
    print(f"[SocketIO] Initializing with {mode} mode...")
    
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode=mode, 
                       logger=False, engineio_logger=False)
    
    # Request logging
    @app.before_request
    def log_request_info():
        from flask import request
        if request.path.startswith('/api/'):
            print(f">>> [API] {request.method} {request.path}")
    
    # Register blueprints
    register_blueprints(app)
    
    # Register SocketIO handlers
    register_socketio_handlers(socketio)
    
    return app, socketio


def register_blueprints(app):
    """Register all blueprints"""
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.camera import camera_bp
    from app.routes.recording import recording_bp
    from app.routes.api import api_bp
    from app.routes.pegawai import pegawai_bp
    from app.routes.control_center import control_center_bp
    
    # Register all blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(camera_bp)
    app.register_blueprint(recording_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(pegawai_bp)
    app.register_blueprint(control_center_bp)
    
    print("[Flask] All blueprints registered")



def register_socketio_handlers(socketio):
    """Register SocketIO event handlers"""
    from app.socketio_handlers.recording_events import register_socketio_handlers as register_handlers
    register_handlers(socketio)
    print("[SocketIO] Event handlers registered")


def init_database(app):
    """Initialize database and create tables"""
    with app.app_context():
        db.create_all()
        check_and_migrate_db(app)
        print(f"[Flask] Database initialized at {config.DATABASE_FILE}")
        
        # Create default admin if no users exist
        from app.models import User
        if User.query.count() == 0:
            admin = User(
                username='admin',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("[Flask] Default admin created (username: admin, password: admin123)")
            print("[Flask] IMPORTANT: Please change the default password after first login!")


def check_and_migrate_db(app):
    """Check database schema and migrate if necessary"""
    inspector = db.inspect(db.engine)
    
    try:
        columns = [c['name'] for c in inspector.get_columns('packing_records')]
        
        with db.engine.connect() as conn:
            # Check and add json_metadata_path
            if 'json_metadata_path' not in columns:
                print("[Migration] Adding json_metadata_path column...")
                conn.execute(db.text('ALTER TABLE packing_records ADD COLUMN json_metadata_path VARCHAR(500)'))
                
            # Check and add sha256_hash
            if 'sha256_hash' not in columns:
                print("[Migration] Adding sha256_hash column...")
                conn.execute(db.text('ALTER TABLE packing_records ADD COLUMN sha256_hash VARCHAR(64)'))
                
            # Check and add created_at
            if 'created_at' not in columns:
                print("[Migration] Adding created_at column...")
                conn.execute(db.text('ALTER TABLE packing_records ADD COLUMN created_at DATETIME'))
                conn.execute(db.text('UPDATE packing_records SET created_at = waktu_mulai WHERE created_at IS NULL'))
            
            conn.commit()
    except:
        # Table might not exist yet
        pass

