"""
Logging Utilities
=================
Implementation of asynchronous, structured logging using JSON Lines (.jsonl).
Designed for high-throughput video applications without I/O blocking.

Features:
- Asynchronous logging via QueueHandler/QueueListener
- JSON Structured logging
- Domain separation (App, Video, Audit, Resource)
- Automatic log rotation
"""

import logging
import logging.handlers
import json
import os
import datetime
import queue
import threading
from flask import has_request_context, request

# Configuration
LOG_DIR = 'logs'
MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
BACKUP_COUNT = 10             # Retain 10 files

# Ensure logs directory exists
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

class JSONFormatter(logging.Formatter):
    """Formats log records as JSON objects."""
    
    def format(self, record):
        # Base log record
        log_record = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno
        }

        # Context from Flask request (if available)
        if has_request_context():
            try:
                log_record['path'] = request.path
                log_record['method'] = request.method
                log_record['ip'] = request.remote_addr
            except:
                pass
        
        # Custom Context passed via extra={'context': {...}}
        if hasattr(record, 'context'):
            log_record['context'] = record.context

        # Exception Info with Stacktrace
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_record)

def setup_logger(name, log_filename, level=logging.INFO):
    """
    Sets up a logger with asynchronous file writing.
    
    Args:
        name: Logger name
        log_filename: Filename inside logs/ directory
        level: Logging level
        
    Returns:
        Configured Logger instance
    """
    
    # 1. Destination Handler (Rotating File) - Runs in background thread
    file_path = os.path.join(LOG_DIR, log_filename)
    file_handler = logging.handlers.RotatingFileHandler(
        file_path, 
        maxBytes=MAX_BYTES, 
        backupCount=BACKUP_COUNT,
        encoding='utf-8',
        delay=False
    )
    file_handler.setFormatter(JSONFormatter())

    # 2. Queue (Buffer) - Infinite size to prevent blocking
    log_queue = queue.Queue(-1) 

    # 3. Source Handler (QueueHandler) - Runs in main app thread
    queue_handler = logging.handlers.QueueHandler(log_queue)

    # 4. Listener (Worker Thread) - Moves logs from Queue to File
    listener = logging.handlers.QueueListener(log_queue, file_handler)
    listener.start()

    # 5. Configure Logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Clear existing handlers to prevent duplication
    logger.handlers = [] 
    logger.addHandler(queue_handler) 
    
    # Store listener reference to avoid garbage collection
    logger._listener = listener
    
    return logger

# ==========================================
# RESOURCE MONITOR
# ==========================================
def start_resource_monitor(interval=60):
    """
    Starts a background thread to log system resources.
    """
    import psutil
    import time
    
    def _monitor():
        while True:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                disk = psutil.disk_usage('.') # Current drive
                
                # Log usage
                resource_logger.info("system_metrics", extra={'context': {
                    'cpu_pct': cpu,
                    'ram_pct': ram.percent,
                    'ram_used_gb': round(ram.used / (1024**3), 2),
                    'disk_free_gb': round(disk.free / (1024**3), 2),
                    'disk_pct': disk.percent
                }})
                
                # Simple Alert Logic
                alerts = []
                if disk.free < 2 * 1024 * 1024 * 1024: # < 2GB
                    alerts.append("CRITICAL: Disk Low space (<2GB)")
                if ram.percent > 90:
                    alerts.append("WARNING: RAM usage >90%")
                    
                if alerts:
                    resource_logger.warning("system_alert", extra={'context': {'alerts': alerts}})
                    
            except Exception as e:
                resource_logger.error(f"Monitor error: {e}")
            
            time.sleep(interval)

    t = threading.Thread(target=_monitor, daemon=True, name="ResourceMonitor")
    t.start()
    return t

# ==========================================
# LOGGERS EXPORT
# ==========================================

# 1. Application Logic (Routes, DB)
app_logger = setup_logger('app_logic', 'app.jsonl')

# 2. Video Pipeline (OpenCV, FFmpeg, Cameras)
video_logger = setup_logger('video_pipeline', 'video.jsonl')

# 3. Audit Trail (Business Events: Login, Scan, Record)
audit_logger = setup_logger('audit_trail', 'audit.jsonl')

# 4. Resource Monitoring (CPU, RAM, Disk)
resource_logger = setup_logger('resource_monitor', 'resource.jsonl')

# Helper for Trace ID
def get_trace_id():
    import uuid
    return str(uuid.uuid4())
