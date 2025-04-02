"""
Process management module for Emby FFMPEG Fixer.
Handles all subprocess creation, monitoring, and termination.
"""
import subprocess
import logging
import threading
from datetime import datetime

class ProcessManager:
    def __init__(self):
        self._current_process = None
        self._is_running = False
        self._lock = threading.Lock()

    @property
    def is_running(self):
        """Check if a process is running."""
        with self._lock:
            if self._current_process:
                # Check if process is actually still running
                if self._current_process.poll() is not None:
                    self._is_running = False
                    self._current_process = None
            return self._is_running

    def run_process(self, cmd, shell=False):
        """Run a subprocess and track it."""
        with self._lock:
            if self._is_running:
                return None  # Don't start a new process if one is running
            
            try:
                self._current_process = subprocess.Popen(cmd, shell=shell)
                self._is_running = True
                return_code = self._current_process.wait()
                self._current_process = None
                self._is_running = False
                return return_code
            except Exception as e:
                self._current_process = None
                self._is_running = False
                raise e

    def stop_process(self):
        """Stop the current process if any."""
        with self._lock:
            try:
                if self._current_process:
                    logging.info("Attempting to stop process...")
                    self._current_process.terminate()
                    try:
                        self._current_process.wait(timeout=5)  # Wait up to 5 seconds
                        logging.info("Process terminated successfully")
                    except subprocess.TimeoutExpired:
                        logging.warning("Process did not terminate, forcing kill")
                        self._current_process.kill()  # Force kill if it doesn't terminate
                    finally:
                        self._current_process = None
                        self._is_running = False
                        logging.info("Process state cleared")
                return True
            except Exception as e:
                logging.error(f"Error stopping process: {e}")
                self._is_running = False
                return False

    def get_state(self):
        """Get the current process state."""
        with self._lock:
            # Update running state
            if self._current_process:
                if self._current_process.poll() is not None:
                    logging.info("Process has completed, clearing state")
                    self._is_running = False
                    self._current_process = None
                else:
                    # Process is still running
                    self._is_running = True
            
            state = {
                "is_running": self._is_running,
                "process": self._current_process
            }
            logging.debug(f"Current process state: {state}")
            return state

# Create a global instance
process_manager = ProcessManager() 