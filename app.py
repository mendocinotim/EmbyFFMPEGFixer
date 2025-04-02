from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_cors import CORS
from waitress import serve
import os
import sys
import platform
import subprocess
import logging
import psutil
import signal
import time
from datetime import datetime
from core.process_manager import process_manager
from core.state_manager import state_manager
from core.utils import (
    get_system_architecture, 
    find_ffmpeg_binaries,
    get_ffmpeg_architecture,
    backup_original_ffmpeg,
    restore_original_ffmpeg,
    replace_ffmpeg_binaries,
    force_single_architecture,
    setup_logging,
    create_backup,
    restore_from_backup,
    force_architecture_incompatibility,
    get_default_emby_path,
    find_emby_servers,
    check_ffmpeg_compatibility
)
import socket

def find_available_port(start_port=9876, max_port=9886):
    """Find an available port in the given range."""
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                s.close()
                logging.info("Successfully found available port: {}".format(port))
                return port
            except OSError as e:
                logging.error("Port {} is not available: {}".format(port, e))
                continue
    logging.error("No available ports found in range")
    return None

# Global Configuration
APP_HOST = '0.0.0.0'  # Listen on all interfaces
APP_PORT = 5050  # Use port 5050

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['EMBY_PATH'] = None  # Initialize EMBY_PATH config
app.config['DEBUG'] = True  # Enable debug mode for development
app.config['PROPAGATE_EXCEPTIONS'] = True  # Enable exception propagation

# Ensure logs directory exists
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging with more detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/emby_ffmpeg_fixer.log')
    ]
)

def kill_existing_flask():
    """Kill any existing Flask processes"""
    try:
        # More aggressive process killing
        os.system('pkill -9 -f "python.*app.py"')
        time.sleep(1)
    except Exception as e:
        logging.error("Error killing existing processes: {}".format(e))

def is_port_in_use(port):
    """Check if a port is in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

@app.route('/')
def index():
    """Show introduction page"""
    return render_template('intro.html')

@app.route('/main')
def main():
    """Main application page"""
    if not state_manager.is_main_app_running():
        state_manager.set_main_app_running(True)
    return render_template('index.html', default_emby_path=get_default_emby_path())

@app.route('/intro')
def intro():
    """Show the introduction/welcome page"""
    return render_template('intro.html')

@app.route('/static/start.html')
def start_page():
    """Serve the static start page"""
    return send_file('static/start.html')

@app.route('/api/start-application', methods=['POST'])
def start_application():
    """Start the main application"""
    try:
        logging.info("Attempting to start main application")
        
        # Check if another instance is running
        if is_port_in_use(APP_PORT):
            logging.info("Found existing Flask process, attempting to kill it")
            kill_existing_flask()
            # Give the process a moment to terminate
            time.sleep(1)
        
        # Start the main application
        state_manager.set_main_app_running(True)
        logging.info("Main application started successfully")
        
        return jsonify({
            'success': True,
            'message': 'Application started successfully'
        })
    except Exception as e:
        error_msg = "Error starting application: {}".format(str(e))
        logging.error(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

@app.route('/api/select-emby', methods=['POST'])
def select_emby():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
            
        emby_path = data.get('path')
        if not emby_path:
            return jsonify({
                'success': False,
                'message': 'No path provided'
            }), 400
            
        if not os.path.exists(emby_path):
            return jsonify({
                'success': False,
                'message': 'Path does not exist: {}'.format(emby_path)
            }), 404
        
        # Save the selected path
        app.config['EMBY_PATH'] = emby_path
        
        return jsonify({
            'success': True,
            'message': 'Path selected successfully',
            'path': emby_path
        })
        
    except Exception as e:
        logging.error("Error in select_emby: {}".format(str(e)))
        return jsonify({
            'success': False,
            'message': 'Server error: {}'.format(str(e))
        }), 500

@app.route('/api/check-compatibility', methods=['POST'])
def check_compatibility():
    """Check FFMPEG compatibility."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
            
        emby_path = data.get('path')
        if not emby_path:
            return jsonify({
                'success': False,
                'message': 'No path provided'
            }), 400
            
        # Get the client's IP address to determine if it's a remote access
        client_ip = request.remote_addr
        is_remote_access = client_ip != '127.0.0.1' and client_ip != 'localhost'
        
        # Get system architecture
        system_arch = get_system_architecture('remote' if is_remote_access else None)
        
        # Get FFMPEG architecture
        ffmpeg_path = find_ffmpeg_binaries(emby_path)
        ffmpeg_arch = get_ffmpeg_architecture(ffmpeg_path) if ffmpeg_path else None
        
        # Check compatibility
        is_compatible = system_arch == ffmpeg_arch if system_arch and ffmpeg_arch else False
        message = "FFMPEG is compatible with your system" if is_compatible else \
                 "FFMPEG architecture ({}) does not match system architecture ({})".format(
                     ffmpeg_arch or "Unknown", system_arch or "Unknown")
        
        return jsonify({
            'success': True,
            'is_compatible': is_compatible,
            'message': message,
            'system_architecture': system_arch or "Unknown",
            'ffmpeg_architecture': ffmpeg_arch or "Unknown"
        })
    except Exception as e:
        error_msg = "Error checking compatibility: {}".format(str(e))
        logging.error(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

@app.route('/api/fix-ffmpeg', methods=['POST'])
def fix_ffmpeg():
    global CURRENT_PROCESS
    try:
        data = request.get_json()
        emby_path = data.get('path')
        
        if not emby_path:
            return jsonify({"success": False, "message": "No Emby Server path provided"})
        
        if not os.path.exists(emby_path):
            return jsonify({"success": False, "message": "Emby Server path does not exist"})
        
        # Create backup if it doesn't exist
        backup_result = create_backup(emby_path)
        if not backup_result["success"]:
            return jsonify(backup_result)
        
        # Fix FFMPEG compatibility
        logging.info("Starting FFMPEG compatibility fix...")
        result = fix_ffmpeg_compatibility(emby_path)
        
        if result["success"]:
            logging.info("FFMPEG compatibility fix completed successfully")
            return jsonify({"success": True, "message": "FFMPEG compatibility fixed successfully"})
        else:
            logging.error("FFMPEG compatibility fix failed: {}".format(result['message']))
            return jsonify(result)
            
    except Exception as e:
        logging.error("Error fixing FFMPEG compatibility: {}".format(str(e)))
        return jsonify({"success": False, "message": "Error fixing FFMPEG compatibility: {}".format(str(e))})
    finally:
        CURRENT_PROCESS = None

@app.route('/api/restore-ffmpeg', methods=['POST'])
def restore_ffmpeg():
    """Restore original FFMPEG binaries and clean up test mode"""
    try:
        emby_path = request.json.get('path')
        
        if not emby_path or not os.path.exists(emby_path):
            return jsonify({
                'success': False,
                'message': 'Invalid Emby Server path'
            })
        
        # Restore original FFMPEG binaries
        success, message = restore_original_ffmpeg(emby_path)
        
        if success:
            # Clean up test mode marker if it exists
            test_marker = os.path.join(os.path.dirname(find_ffmpeg_binaries(emby_path)), "ffmpeg_test_mode")
            if os.path.exists(test_marker):
                try:
                    os.remove(test_marker)
                except OSError as e:
                    logging.warning("Could not remove test marker file: {}".format(e))
            
            return jsonify({
                'success': True,
                'message': message,
                'details': {
                    'test_mode_cleaned': True,
                    'system_architecture': get_system_architecture(),
                    'ffmpeg_architecture': get_ffmpeg_architecture(find_ffmpeg_binaries(emby_path))
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            })
            
    except Exception as e:
        error_msg = "Error restoring FFMPEG: {}".format(str(e))
        logging.error(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

@app.route('/api/check-backup', methods=['POST'])
def check_backup():
    emby_path = request.json.get('path')
    
    if not emby_path or not os.path.exists(emby_path):
        return jsonify({
            'success': False,
            'message': 'Invalid Emby Server path',
            'has_backup': False
        })
    
    ffmpeg_path = find_ffmpeg_binaries(emby_path)
    if not ffmpeg_path:
        return jsonify({
            'success': False,
            'message': 'FFMPEG binaries not found in Emby Server',
            'has_backup': False
        })
    
    backup_dir = os.path.join(os.path.dirname(ffmpeg_path), "ffmpeg_backup_original")
    has_backup = os.path.exists(backup_dir)
    
    return jsonify({
        'success': True,
        'has_backup': has_backup
    })

@app.route('/api/get-logs', methods=['GET', 'OPTIONS'])
def get_logs():
    """Get the contents of the log file"""
    # Handle OPTIONS request for CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept')
        return response

    try:
        log_file = os.path.join('logs', 'emby_ffmpeg_fixer.log')
        logging.info("Attempting to read log file: {}".format(log_file))
        
        if not os.path.exists(log_file):
            logging.error("Log file not found: {}".format(log_file))
            response = jsonify({
                'success': False,
                'message': 'Log file not found'
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 404

        logging.info("Reading log file contents")
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = f.read()
            logging.info("Successfully read {} bytes from log file".format(len(logs)))

        # Return logs with proper headers
        response = jsonify({
            'success': True,
            'logs': logs
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Accept')
        response.headers.add('Content-Type', 'application/json')
        logging.info("Returning log file contents with CORS headers")
        return response

    except Exception as e:
        logging.error("Error reading logs: {}".format(str(e)), exc_info=True)
        response = jsonify({
            'success': False,
            'message': "Error reading logs: {}".format(str(e))
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500

@app.route('/api/download-log')
def download_log():
    log_file = os.path.join('logs', 'emby_ffmpeg_fixer.log')
    return send_file(log_file, as_attachment=True)

@app.route('/api/force-test-mode', methods=['POST'])
def force_test_mode():
    """Force FFMPEG binaries to be single-architecture for testing"""
    try:
        emby_path = request.json.get('path')
        target_arch = request.json.get('architecture')  # 'x86_64' or 'arm64'
        
        if not emby_path or not os.path.exists(emby_path):
            return jsonify({
                'success': False,
                'message': 'Invalid Emby Server path'
            })
        
        if target_arch not in ['x86_64', 'arm64']:
            return jsonify({
                'success': False,
                'message': 'Invalid architecture specified'
            })
        
        # Get current system architecture
        system_arch = get_system_architecture()
        
        # Only allow forcing incompatible architecture
        if target_arch == system_arch:
            return jsonify({
                'success': False,
                'message': 'Cannot force {} architecture as it matches your system. Please select the opposite architecture to simulate incompatibility.'.format(target_arch)
            })
        
        # Force single architecture
        message = force_single_architecture(find_ffmpeg_binaries(emby_path), target_arch)
        success = message.startswith('Success:')
        
        if success:
            # Get test mode info
            test_info = get_test_mode_info(emby_path)
            
            return jsonify({
                'success': True,
                'message': message,
                'test_info': test_info,
                'details': {
                    'system_architecture': system_arch,
                    'forced_architecture': target_arch,
                    'emby_path': emby_path,
                    'warning': 'Emby Server should now show compatibility issues. Use the Fix button to resolve them.'
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            })
            
    except Exception as e:
        error_msg = "Error setting up test mode: {}".format(str(e))
        logging.error(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

@app.route('/api/check-test-mode', methods=['POST'])
def check_test_mode():
    """Check if test mode is currently active and get its status"""
    try:
        emby_path = request.json.get('path')
        
        if not emby_path or not os.path.exists(emby_path):
            return jsonify({
                'success': False,
                'message': 'Invalid Emby Server path',
                'test_mode_active': False
            })
        
        # Check if test mode is active
        is_active = is_test_mode_active(emby_path)
        test_info = get_test_mode_info(emby_path) if is_active else None
        
        # Get current FFMPEG architecture
        ffmpeg_path = find_ffmpeg_binaries(emby_path)
        current_arch = get_ffmpeg_architecture(ffmpeg_path) if ffmpeg_path else None
        system_arch = get_system_architecture()
        
        return jsonify({
            'success': True,
            'test_mode_active': is_active,
            'test_info': test_info,
            'details': {
                'system_architecture': system_arch,
                'current_ffmpeg_architecture': current_arch,
                'is_compatible': current_arch == system_arch if current_arch else None
            }
        })
        
    except Exception as e:
        error_msg = "Error checking test mode: {}".format(str(e))
        logging.error(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg,
            'test_mode_active': False
        }), 500

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the Flask server."""
    try:
        # Get the current process
        pid = os.getpid()
        
        # Send success response before killing the server
        response = jsonify({
            'success': True,
            'message': 'Server shutdown initiated'
        })
        
        def shutdown_server():
            time.sleep(1)  # Give time for response to be sent
            os.kill(pid, signal.SIGTERM)
        
        # Start shutdown in a separate thread
        from threading import Thread
        shutdown_thread = Thread(target=shutdown_server)
        shutdown_thread.daemon = True
        shutdown_thread.start()
        
        return response
        
    except Exception as e:
        logging.error(f"Error during shutdown: {e}")
        return jsonify({
            'success': False,
            'message': f'Error during shutdown: {str(e)}'
        }), 500

@app.route('/api/stop-process', methods=['POST'])
def stop_process():
    """Stop any running process, restore initial state, and reset application state"""
    try:
        # Get current Emby path
        data = request.get_json()
        emby_path = data.get('path')
        
        if not emby_path:
            return jsonify({
                "success": False,
                "message": "No Emby Server path provided"
            })
        
        logging.info("Attempting to stop process and restore state...")
        
        # First stop any running process
        process_stopped = process_manager.stop_process()
        logging.info("Process stop result: {}".format(process_stopped))
        
        # Then restore to initial state
        restore_result = state_manager.restore_initial_state(emby_path)
        logging.info("State restore result: {}".format(restore_result))
        
        if not restore_result["success"]:
            logging.error("Failed to restore initial state: {}".format(restore_result['message']))
            return jsonify({
                "success": False,
                "message": "Process stopped but failed to restore initial state: {}".format(restore_result['message'])
            })
        
        # Reset application state
        state_manager.set_main_app_running(False)
        logging.info("Process stopped and initial state restored")
        
        # Return success response with redirect to static page
        return jsonify({
            "success": True,
            "message": "Process stopped and initial state restored successfully",
            "redirect": "/static/start.html"
        })
    except Exception as e:
        error_msg = "Error stopping process: {}".format(str(e))
        logging.error(error_msg, exc_info=True)
        return jsonify({
            "success": False,
            "message": error_msg
        }), 500

@app.route('/api/get-default-path', methods=['GET'])
def get_default_path():
    """Get the default Emby Server path"""
    try:
        default_path = get_default_emby_path()
        if default_path:
            return jsonify({
                'success': True,
                'path': default_path
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No default Emby Server path found'
            })
    except Exception as e:
        error_msg = "Error getting default path: {}".format(str(e))
        logging.error(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

@app.route('/api/process-state')
def get_process_state():
    """Get the current process state"""
    try:
        state = process_manager.get_state()
        return jsonify({
            'success': True,
            'is_processing': state['is_running'],
            'initialized': state['initialized']
        })
    except Exception as e:
        logging.error(f"Error getting process state: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/browse-emby', methods=['GET'])
def browse_emby():
    """Open a native file dialog to select Emby Server application"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        # Create and hide the root window
        root = tk.Tk()
        root.withdraw()
        
        # Open file dialog
        file_path = filedialog.askdirectory(
            initialdir="/Applications",
            title="Select Emby Server Application",
            mustexist=True
        )
        
        if file_path:
            # Validate that it's an Emby Server application
            if file_path.endswith('.app') and ('Emby' in file_path or 'emby' in file_path):
                return jsonify({
                    'success': True,
                    'path': file_path
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Selected path is not an Emby Server application'
                })
        
        return jsonify({
            'success': False,
            'message': 'No path selected'
        })
        
    except Exception as e:
        error_msg = "Error browsing for Emby Server: {}".format(str(e))
        logging.error(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

@app.route('/api/list-emby-servers')
def list_emby_servers():
    """Get a list of all detected Emby Server installations."""
    try:
        servers = find_emby_servers()
        return jsonify({
            "success": True,
            "servers": servers
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

def run_process(cmd, shell=False):
    global CURRENT_PROCESS
    try:
        CURRENT_PROCESS = subprocess.Popen(cmd, shell=shell)
        return_code = CURRENT_PROCESS.wait()
        CURRENT_PROCESS = None
        return return_code
    except Exception as e:
        CURRENT_PROCESS = None
        raise e

def main():
    """Main entry point for the application"""
    try:
        # Configure logging first
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('logs/emby_ffmpeg_fixer.log')
            ]
        )

        # Kill any existing Flask processes
        kill_existing_flask()
        time.sleep(2)  # Give processes more time to die
        
        # Check if port is in use
        if is_port_in_use(APP_PORT):
            logging.error("Port {} is already in use".format(APP_PORT))
            sys.exit(1)
            
        logging.info("Starting application on {}:{}".format(APP_HOST, APP_PORT))
        print("Starting application on {}:{}".format(APP_HOST, APP_PORT))
        
        # Use waitress instead of Flask's development server
        serve(app, host=APP_HOST, port=APP_PORT)
        
    except Exception as e:
        logging.error("Error starting application: {}".format(e), exc_info=True)
        print("Error starting application: {}".format(e))
        sys.exit(1)

if __name__ == '__main__':
    try:
        # Set up signal handlers
        signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
        signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
        signal.signal(signal.SIGABRT, lambda s, f: sys.exit(0))
        
        main()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        logging.error("Fatal error: {}".format(e), exc_info=True)
        sys.exit(1)

# Add a health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify server status."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })
