"""
State management module for Emby FFMPEG Fixer.
Handles all application state including main app running state and initial state backups.
"""
import os
import logging
import threading
import shutil
from datetime import datetime
from .process_manager import process_manager

class StateManager:
    def __init__(self):
        self._main_app_running = False
        self._initial_state_backup_dir = None
        self._lock = threading.Lock()

    def set_main_app_running(self, running):
        """Set whether the main app is running."""
        with self._lock:
            if running:
                self._main_app_running = True
                logging.info("Main app state set to running")
            else:
                logging.info("Stopping main app and cleaning up processes")
                # When stopping the main app, ensure process is stopped
                if process_manager.is_running:
                    process_manager.stop_process()
                self._main_app_running = False
                logging.info("Main app state set to stopped")

    def is_main_app_running(self):
        """Check if the main app is running."""
        with self._lock:
            return self._main_app_running

    def get_initial_state_backup_dir(self):
        """Get the current initial state backup directory."""
        with self._lock:
            return self._initial_state_backup_dir

    def set_initial_state_backup_dir(self, directory):
        """Set the initial state backup directory."""
        with self._lock:
            self._initial_state_backup_dir = directory

    def get_state(self):
        """Get the complete application state."""
        with self._lock:
            process_state = process_manager.get_state()
            state = {
                "main_app_running": self._main_app_running,
                "initial_state_backup_dir": self._initial_state_backup_dir,
                "process_state": process_state
            }
            logging.debug(f"Current application state: {state}")
            return state

    def create_initial_state_backup(self, emby_path):
        """Create a backup of the initial Emby Server state."""
        with self._lock:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dir = os.path.join(os.path.dirname(emby_path), f"emby_initial_backup_{timestamp}")
                shutil.copytree(emby_path, backup_dir)
                self._initial_state_backup_dir = backup_dir
                return {"success": True, "backup_dir": backup_dir}
            except Exception as e:
                return {"success": False, "message": str(e)}

    def restore_initial_state(self, emby_path):
        """Restore Emby Server to initial state."""
        with self._lock:
            try:
                if not self._initial_state_backup_dir or not os.path.exists(self._initial_state_backup_dir):
                    return {"success": False, "message": "No initial state backup found"}
                
                if os.path.exists(emby_path):
                    shutil.rmtree(emby_path)
                shutil.copytree(self._initial_state_backup_dir, emby_path)
                return {"success": True}
            except Exception as e:
                return {"success": False, "message": str(e)}

# Create a global instance
state_manager = StateManager() 