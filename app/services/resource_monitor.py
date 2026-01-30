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
    
    def check_restart_threshold(self, ram_percent):
        """Check if system needs restart due to high memory"""
        RESTART_THRESHOLD = 95  # 95% RAM - restart point
        WARNING_THRESHOLD = 93  # 93% RAM - warning only
        
        if ram_percent >= RESTART_THRESHOLD:
            print(f"[RESTART] RAM at {ram_percent}% - Initiating graceful restart")
            
            # Emit restart warning to all clients
            socketio.emit('system_restart', {
                'message': 'Server restarting in 5 seconds due to high memory',
                'ram': ram_percent,
                'countdown': 5
            })
            
            # Wait 5 seconds for message delivery
            time.sleep(5)
            
            # Exit cleanly (batch script will restart)
            import sys
            sys.exit(0)
        
        elif ram_percent >= WARNING_THRESHOLD:
            # Soft warning only (approaching restart threshold)
            socketio.emit('resource_warning', {
                'level': 'critical',
                'ram': ram_percent,
                'message': f'Memory critical: {ram_percent}% - Restart imminent'
            })
    
    def monitoring_loop(self):
        """Background monitoring loop"""
        print("[ResourceMonitor] Monitoring started")
        
        while self.running:
            try:
                # Get resources
                resources = self.get_system_resources()
                
                # Emit to all connected clients
                socketio.emit('resource_update', resources)
                
                # Check restart threshold
                self.check_restart_threshold(resources['ram'])
                
                # Sleep until next update
                time.sleep(self.update_interval)
                
            except Exception as e:
                print(f"[ResourceMonitor] Loop error: {e}")
                time.sleep(self.update_interval)
        
        print("[ResourceMonitor] Monitoring stopped")
    
    def start(self):
        """Start monitoring in background thread"""
        if self.running:
            print("[ResourceMonitor] Already running")
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitor_thread.start()
        print("[ResourceMonitor] Started")
    
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
