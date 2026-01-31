"""
Resource Monitor Service
=========================
Real-time system resource monitoring with SocketIO broadcasting
"""

import psutil
import threading
import time
from app import socketio


class ResourceMonitor:
    """Monitor system resources and emit updates via SocketIO"""
    
    def __init__(self):
        self.running = False
        self.monitor_thread = None
        self.update_interval = 5  # seconds
        
    def get_system_resources(self):
        """Get current system resource usage"""
        try:
            # Get RAM usage
            memory = psutil.virtual_memory()
            ram_percent = memory.percent
            
            # Get CPU usage (non-blocking, instant)
            cpu_percent = psutil.cpu_percent(interval=0)
            
            # Get disk usage for recordings folder
            import config
            disk = psutil.disk_usage(str(config.RECORDINGS_FOLDER))
            disk_percent = disk.percent
            
            # Count active cameras and recordings
            from app.services.camera_service import active_cameras
            from app.services.recording_service import active_recordings
            
            cameras_count = len(active_cameras)
            recordings_count = len(active_recordings)
            
            return {
                'ram': round(ram_percent, 1),
                'cpu': round(cpu_percent, 1),
                'disk': round(disk_percent, 1),
                'cameras': cameras_count,
                'recordings': recordings_count,
                'timestamp': time.time()
            }
        except Exception as e:
            print(f"[ResourceMonitor] Error getting resources: {e}")
            return {
                'ram': 0,
                'cpu': 0,
                'disk': 0,
                'cameras': 0,
                'recordings': 0,
                'timestamp': time.time()
            }
    
    def check_thresholds(self, ram_percent, disk_percent):
        """Check resource thresholds and emit critical warnings (No Auto-Restart)"""
        CRITICAL_THRESHOLD = 95
        WARNING_THRESHOLD = 90
        
        # 1. RAM Check
        if ram_percent >= CRITICAL_THRESHOLD:
            socketio.emit('resource_warning', {
                'type': 'critical_ram',
                'resource': 'RAM',
                'percent': ram_percent,
                'message': 'Memory is critically high! Server instability may occur.',
                'action': 'restart' # Instruction for frontend
            })
        elif ram_percent >= WARNING_THRESHOLD:
            socketio.emit('resource_warning', {
                'type': 'warning_ram',
                'resource': 'RAM',
                'percent': ram_percent,
                'message': 'High memory usage detected.'
            })

        # 2. Disk Check
        if disk_percent >= CRITICAL_THRESHOLD:
            socketio.emit('resource_warning', {
                'type': 'critical_disk',
                'resource': 'Disk',
                'percent': disk_percent,
                'message': 'Storage is almost full! Recordings may fail.',
                'action': 'delete' # Instruction for frontend
            })
    
    def monitoring_loop(self):
        """Background monitoring loop (Wrapped via safe_thread_loop in start())"""
        # Get resources
        resources = self.get_system_resources()
        
        # Emit to all connected clients
        socketio.emit('resource_update', resources)
        
        # Check critical thresholds
        self.check_thresholds(resources['ram'], resources['disk'])
    
    def start(self):
        """Start monitoring in background thread"""
        if self.running:
            print("[ResourceMonitor] Already running")
            return
        
        self.running = True
        
        # Use safe_thread_loop to create the thread wrapper dynamically
        from app.utils.safe_execution import safe_thread_loop
        
        @safe_thread_loop("ResourceMonitor", interval=self.update_interval)
        def _safe_wrapper():
            if self.running:
                self.monitoring_loop()
            else:
                # If stopped, raise exception to break loop? 
                # No, safe_thread_loop is infinite. 
                # We should just check running inside.
                pass

        # Actually, safe_thread_loop is designed for standalone functions.
        # For a class method, we can just define the processing logic and wrap it.
        
        self.monitor_thread = threading.Thread(target=_safe_wrapper, daemon=True)
        self.monitor_thread.start()
        print("[ResourceMonitor] Started (Safe Mode)")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print("[ResourceMonitor] Stopped")


# Global instance
resource_monitor = ResourceMonitor()


def start_resource_monitoring():
    """Start the global resource monitor"""
    resource_monitor.start()


def stop_resource_monitoring():
    """Stop the global resource monitor"""
    resource_monitor.stop()
