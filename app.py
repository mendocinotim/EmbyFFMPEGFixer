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
    find_emby_servers
)
import socket

def find_available_port(start_port=9876, max_port=9886):
    """Find an available port in the given range."""
    for port in range(start_port, max_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                s.close()
                logging.info(f"Successfully found available port: {port}")
                return port
            except OSError as e:
                logging.error(f"Port {port} is not available: {e}")
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
        logging.error(f"Error killing existing processes: {e}")

def is_port_in_use(port):
    """Check if a port is in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

@app.route('/')
def index():
    """Show start page if main app is not running, otherwise redirect to main"""
    if state_manager.is_main_app_running():
        return redirect(url_for('main'))
    return render_template('start.html')

@app.route('/main')
def main():
    """Main application page"""
    # Get default Emby Server path
    default_path = get_default_emby_path()
    
    # Get current process state
    process_state = process_manager.get_state()
    
    return render_template('index.html', 
                         default_emby_path=default_path,
                         is_processing=process_state["is_running"])

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
        error_msg = f"Error starting application: {str(e)}"
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
                'message': f'Path does not exist: {emby_path}'
            }), 404
        
        # Save the selected path
        app.config['EMBY_PATH'] = emby_path
        
        return jsonify({
            'success': True,
            'message': 'Path selected successfully',
            'path': emby_path
        })
        
    except Exception as e:
        logging.error(f"Error in select_emby: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/api/check-compatibility', methods=['POST'])
def check_compatibility():
    try:
        logging.info("Received compatibility check request")
        emby_path = request.json.get('path')
        logging.info(f"Checking compatibility for path: {emby_path}")
        
        if not emby_path:
            logging.warning("No Emby Server path provided")
            return jsonify({
                'success': False,
                'message': 'No Emby Server path provided',
                'system_architecture': get_system_architecture(),
                'ffmpeg_architecture': None,
                'compatible': False
            })
        
        if not os.path.exists(emby_path):
            logging.warning(f"Emby Server path does not exist: {emby_path}")
            return jsonify({
                'success': False,
                'message': f'Emby Server path does not exist: {emby_path}',
                'system_architecture': get_system_architecture(),
                'ffmpeg_architecture': None,
                'compatible': False
            })
        
        # Save the selected path for later use
        app.config['EMBY_PATH'] = emby_path
        
        # Get system architecture
        system_arch = get_system_architecture()
        logging.info(f"System architecture: {system_arch}")
        
        if not system_arch:
            logging.error("Could not determine system architecture")
            return jsonify({
                'success': False,
                'message': 'Could not determine system architecture',
                'system_architecture': None,
                'ffmpeg_architecture': None,
                'compatible': False
            })
        
        # Find FFMPEG binaries in Emby Server
        ffmpeg_path = find_ffmpeg_binaries(emby_path)
        logging.info(f"FFMPEG path: {ffmpeg_path}")
        
        if not ffmpeg_path:
            logging.warning("FFMPEG binaries not found in Emby Server")
            return jsonify({
                'success': False,
                'message': 'FFMPEG binaries not found in Emby Server',
                'system_architecture': system_arch,
                'ffmpeg_architecture': None,
                'compatible': False
            })
        
        # Get FFMPEG architecture
        ffmpeg_arch = get_ffmpeg_architecture(ffmpeg_path)
        logging.info(f"FFMPEG architecture: {ffmpeg_arch}")
        
        if not ffmpeg_arch:
            logging.error("Could not determine FFMPEG architecture")
            return jsonify({
                'success': False,
                'message': 'Could not determine FFMPEG architecture',
                'system_architecture': system_arch,
                'ffmpeg_architecture': None,
                'compatible': False
            })
        
        # Check compatibility
        compatible = system_arch == ffmpeg_arch
        logging.info(f"Compatibility check result: {compatible}")
        
        return jsonify({
            'success': True,
            'message': 'Compatibility check completed',
            'system_architecture': system_arch,
            'ffmpeg_architecture': ffmpeg_arch,
            'compatible': compatible
        })
        
    except Exception as e:
        logging.error(f"Error in check_compatibility: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}',
            'system_architecture': None,
            'ffmpeg_architecture': None,
            'compatible': False
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
            logging.error(f"FFMPEG compatibility fix failed: {result['message']}")
            return jsonify(result)
            
    except Exception as e:
        logging.error(f"Error fixing FFMPEG compatibility: {str(e)}")
        return jsonify({"success": False, "message": f"Error fixing FFMPEG compatibility: {str(e)}"})
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
                    logging.warning(f"Could not remove test marker file: {e}")
            
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
        error_msg = f"Error restoring FFMPEG: {str(e)}"
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
        logging.info(f"Attempting to read log file: {log_file}")
        
        if not os.path.exists(log_file):
            logging.error(f"Log file not found: {log_file}")
            response = jsonify({
                'success': False,
                'message': 'Log file not found'
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 404

        logging.info("Reading log file contents")
        with open(log_file, 'r', encoding='utf-8') as f:
            logs = f.read()
            logging.info(f"Successfully read {len(logs)} bytes from log file")

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
        logging.error(f"Error reading logs: {str(e)}", exc_info=True)
        response = jsonify({
            'success': False,
            'message': f'Error reading logs: {str(e)}'
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
                'message': f'Cannot force {target_arch} architecture as it matches your system. Please select the opposite architecture to simulate incompatibility.'
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
        error_msg = f"Error setting up test mode: {str(e)}"
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
        error_msg = f"Error checking test mode: {str(e)}"
        logging.error(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg,
            'test_mode_active': False
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
        logging.info(f"Process stop result: {process_stopped}")
        
        # Then restore to initial state
        restore_result = state_manager.restore_initial_state(emby_path)
        logging.info(f"State restore result: {restore_result}")
        
        if not restore_result["success"]:
            logging.error(f"Failed to restore initial state: {restore_result['message']}")
            return jsonify({
                "success": False,
                "message": f"Process stopped but failed to restore initial state: {restore_result['message']}"
            })
        
        # Reset application state
        state_manager.set_main_app_running(False)
        logging.info("Process stopped and initial state restored")
        
        # Kill any remaining Python processes
        kill_existing_flask()
        
        # Return success response with redirect
        return jsonify({
            "success": True,
            "message": "Process stopped and initial state restored successfully",
            "redirect": url_for('index')
        })
    except Exception as e:
        error_msg = f"Error stopping process: {str(e)}"
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
        error_msg = f"Error getting default path: {str(e)}"
        logging.error(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg
        }), 500

@app.route('/api/process-state', methods=['GET'])
def get_process_state():
    """Get the current process state"""
    try:
        process_state = process_manager.get_state()
        return jsonify({
            'success': True,
            'is_processing': process_state["is_running"]
        })
    except Exception as e:
        error_msg = f"Error getting process state: {str(e)}"
        logging.error(error_msg)
        return jsonify({
            'success': False,
            'message': error_msg,
            'is_processing': False
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
        error_msg = f"Error browsing for Emby Server: {str(e)}"
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
            logging.error(f"Port {APP_PORT} is already in use")
            sys.exit(1)
            
        logging.info(f"Starting application on {APP_HOST}:{APP_PORT}")
        print(f"Starting application on {APP_HOST}:{APP_PORT}")
        
        # Use Flask's development server with minimal options
        app.run(
            host=APP_HOST,
            port=APP_PORT,
            debug=False,
            use_reloader=False,
            threaded=False,  # Disable threading to prevent race conditions
            processes=1  # Single process
        )
        
    except Exception as e:
        logging.error(f"Error starting application: {e}", exc_info=True)
        print(f"Error starting application: {e}")
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
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
