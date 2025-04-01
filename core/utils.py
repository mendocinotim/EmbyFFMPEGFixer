"""
Utility functions for Emby FFMPEG Fixer.
Contains pure utility functions with no state management.
"""
import os
import sys
import platform
import shutil
import logging
import subprocess
from datetime import datetime
import glob

def setup_logging():
    """Configure logging for the application"""
    logs_dir = 'logs'
    try:
        # Create logs directory with proper permissions
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, mode=0o755, exist_ok=True)
        
        # Ensure the logs directory is writable
        if not os.access(logs_dir, os.W_OK):
            raise OSError("Logs directory {} is not writable".format(logs_dir))

        log_file = os.path.join(logs_dir, 'emby_ffmpeg_fixer.log')
        
        # Configure logging with proper file permissions
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Set proper file permissions for the log file
        if os.path.exists(log_file):
            os.chmod(log_file, 0o644)
            
        return True
    except OSError as e:
        print("Error setting up logging: {}".format(e))
        return False

def get_system_architecture(target_system=None):
    """Get the system architecture.
    
    Args:
        target_system (str, optional): The system to check architecture for. 
                                     If None, uses the current system.
    """
    if target_system == 'remote':
        # When checking from a remote system, we need to get the architecture
        # of the system where Emby Server is installed
        try:
            # Use system_profiler to get the architecture of the remote system
            result = subprocess.run(['system_profiler', 'SPHardwareDataType'], 
                                 capture_output=True, text=True)
            output = result.stdout.lower()
            
            if 'chip' in output and 'apple' in output:
                return 'arm64'
            elif 'intel' in output:
                return 'x86_64'
            else:
                # Fallback to platform.machine()
                arch = platform.machine()
                if arch == 'x86_64':
                    return 'x86_64'
                elif arch == 'arm64':
                    return 'arm64'
                return arch
        except Exception as e:
            logging.error("Error getting remote system architecture: {}".format(e))
            # Fallback to platform.machine()
            return platform.machine()
    else:
        # For local system check
        return platform.machine()

def get_default_emby_path():
    """Get the default Emby Server installation path."""
    if platform.system() == 'Darwin':  # macOS
        default_paths = [
            "/Applications/EmbyServer.app",
            "/Applications/Emby Server.app"
        ]
        for path in default_paths:
            if os.path.exists(path):
                return path
    return None

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def find_ffmpeg_binaries(emby_path):
    """Find FFMPEG binaries in the Emby Server application"""
    try:
        if not emby_path:
            logging.error("No Emby Server path provided")
            return None
            
        logging.info("Searching for FFMPEG in Emby Server at: {}".format(emby_path))
        
        # For macOS, check in the app bundle
        if emby_path.endswith('.app'):
            # Define possible locations for FFMPEG
            possible_paths = [
                os.path.join(emby_path, 'Contents', 'MacOS', 'ffmpeg'),
                os.path.join(emby_path, 'Contents', 'Resources', 'ffmpeg'),
                os.path.join(emby_path, 'Contents', 'Frameworks', 'ffmpeg'),
                os.path.join(emby_path, 'Contents', 'MacOS', 'Emby Server', 'ffmpeg'),
                os.path.join(emby_path, 'Contents', 'Resources', 'Emby Server', 'ffmpeg'),
                os.path.join(emby_path, 'Contents', 'Frameworks', 'Emby Server', 'ffmpeg')
            ]
            
            # Log the paths we're checking
            logging.info("Checking for FFMPEG in standard locations:")
            for path in possible_paths:
                logging.info("Checking: {}".format(path))
                if os.path.exists(path):
                    if os.access(path, os.X_OK):
                        logging.info(f"Found executable FFMPEG at: {path}")
                        return path
                    else:
                        logging.warning(f"Found FFMPEG at {path} but it's not executable")
                        
            # If not found in standard locations, search the entire app bundle
            logging.info("FFMPEG not found in standard locations, searching entire app bundle...")
            for root, dirs, files in os.walk(emby_path):
                if 'ffmpeg' in files:
                    ffmpeg_path = os.path.join(root, 'ffmpeg')
                    if os.access(ffmpeg_path, os.X_OK):
                        logging.info(f"Found executable FFMPEG at: {ffmpeg_path}")
                        return ffmpeg_path
                    else:
                        logging.warning(f"Found FFMPEG at {ffmpeg_path} but it's not executable")
                        
            logging.error(f"FFMPEG not found in Emby Server application bundle: {emby_path}")
            return None
            
        logging.error("Unsupported Emby Server path format")
        return None
    except Exception as e:
        logging.error(f"Error finding FFMPEG binaries: {str(e)}")
        return None

def get_ffmpeg_architecture(ffmpeg_path):
    """Get the architecture of FFMPEG binary."""
    try:
        if not os.path.exists(ffmpeg_path):
            logging.error(f"FFMPEG binary not found at: {ffmpeg_path}")
            return None

        if platform.system() == 'Darwin':  # macOS
            # Use file command to check architecture
            result = subprocess.run(['file', ffmpeg_path], capture_output=True, text=True)
            output = result.stdout.lower()
            
            logging.info(f"File command output: {output}")
            
            if 'arm64' in output:
                return 'arm64'
            elif 'x86_64' in output:
                return 'x86_64'
            
            # If architecture not found in file output, try lipo
            try:
                result = subprocess.run(['lipo', '-info', ffmpeg_path], capture_output=True, text=True)
                output = result.stdout.lower()
                logging.info(f"Lipo command output: {output}")
                
                if 'arm64' in output:
                    return 'arm64'
                elif 'x86_64' in output:
                    return 'x86_64'
            except Exception as e:
                logging.error(f"Error running lipo command: {e}")
        
        # Fallback to running ffmpeg -version
        try:
            result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, text=True)
            output = result.stdout.lower()
            logging.info(f"FFMPEG version output: {output}")
            
            if 'arm64' in output:
                return 'arm64'
            elif 'x86_64' in output:
                return 'x86_64'
        except Exception as e:
            logging.error(f"Error running ffmpeg -version: {e}")
        
        logging.error("Could not determine FFMPEG architecture using any method")
        return None
    except Exception as e:
        logging.error(f"Error getting FFMPEG architecture: {e}")
        return None

def backup_original_ffmpeg(ffmpeg_path):
    """Backup original FFMPEG binary."""
    try:
        backup_path = f"{ffmpeg_path}.backup"
        if not os.path.exists(backup_path):
            shutil.copy2(ffmpeg_path, backup_path)
            return True
        return False
    except Exception as e:
        logging.error(f"Error backing up FFMPEG: {e}")
        return False

def restore_original_ffmpeg(ffmpeg_path):
    """Restore original FFMPEG binary from backup."""
    try:
        backup_path = f"{ffmpeg_path}.backup"
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, ffmpeg_path)
            return True
        return False
    except Exception as e:
        logging.error(f"Error restoring FFMPEG: {e}")
        return False

def replace_ffmpeg_binaries(ffmpeg_path, new_ffmpeg_path):
    """Replace FFMPEG binaries with new ones."""
    try:
        shutil.copy2(new_ffmpeg_path, ffmpeg_path)
        return True
    except Exception as e:
        logging.error(f"Error replacing FFMPEG: {e}")
        return False

def force_single_architecture(ffmpeg_path, target_arch):
    """Force FFMPEG to use single architecture."""
    try:
        if platform.system() == 'Darwin':
            cmd = ['lipo', '-thin', target_arch, ffmpeg_path, '-output', f"{ffmpeg_path}.tmp"]
            subprocess.run(cmd, check=True)
            os.replace(f"{ffmpeg_path}.tmp", ffmpeg_path)
            return True
        return False
    except Exception as e:
        logging.error(f"Error forcing architecture: {e}")
        return False

def create_backup(emby_path):
    """Create a backup of the current Emby Server state."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.dirname(emby_path), f"emby_backup_{timestamp}")
        shutil.copytree(emby_path, backup_dir)
        return {"success": True, "backup_dir": backup_dir}
    except Exception as e:
        return {"success": False, "message": str(e)}

def restore_from_backup(backup_dir, emby_path):
    """Restore Emby Server from backup."""
    try:
        if os.path.exists(emby_path):
            shutil.rmtree(emby_path)
        shutil.copytree(backup_dir, emby_path)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}

def force_architecture_incompatibility(ffmpeg_path):
    """Force FFMPEG to use incompatible architecture."""
    try:
        if platform.system() == 'Darwin':
            current_arch = get_ffmpeg_architecture(ffmpeg_path)
            if current_arch == 'arm64':
                return force_single_architecture(ffmpeg_path, 'x86_64')
            else:
                return force_single_architecture(ffmpeg_path, 'arm64')
        return False
    except Exception as e:
        logging.error(f"Error forcing architecture incompatibility: {e}")
        return False

def create_initial_state_backup(emby_path):
    """Create a backup of the initial Emby Server state."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(os.path.dirname(emby_path), f"emby_initial_backup_{timestamp}")
        shutil.copytree(emby_path, backup_dir)
        return {"success": True, "backup_dir": backup_dir}
    except Exception as e:
        return {"success": False, "message": str(e)}

def restore_initial_state(emby_path):
    """Restore Emby Server to initial state."""
    try:
        backup_dir = state_manager.get_initial_state_backup_dir()
        if not backup_dir or not os.path.exists(backup_dir):
            return {"success": False, "message": "No initial state backup found"}
        
        if os.path.exists(emby_path):
            shutil.rmtree(emby_path)
        shutil.copytree(backup_dir, emby_path)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}

def find_emby_servers():
    """Scan the Applications directory for Emby Server installations."""
    if platform.system() != 'Darwin':
        return []
    
    # Search patterns for Emby Server
    patterns = [
        "/Applications/*[Ee]mby*[Ss]erver*.app",
        "/Applications/Emby*.app"
    ]
    
    found_servers = set()
    for pattern in patterns:
        matches = glob.glob(pattern)
        for match in matches:
            if os.path.isdir(match):
                found_servers.add(match)
    
    return sorted(list(found_servers))

def check_ffmpeg_compatibility(emby_path, is_remote_access=False):
    """Check if FFMPEG is compatible with the system.
    
    Args:
        emby_path (str): Path to the Emby Server installation
        is_remote_access (bool): Whether the check is being performed from a remote system
    
    Returns:
        tuple: (bool, str) - (is_compatible, message)
    """
    try:
        # Get FFMPEG binary path
        ffmpeg_path = find_ffmpeg_binaries(emby_path)
        if not ffmpeg_path:
            return False, "FFMPEG binary not found in Emby Server installation"

        # Get FFMPEG architecture
        ffmpeg_arch = get_ffmpeg_architecture(ffmpeg_path)
        if not ffmpeg_arch:
            return False, "Could not determine FFMPEG architecture"

        # Get system architecture
        system_arch = get_system_architecture('remote' if is_remote_access else None)
        if not system_arch:
            return False, "Could not determine system architecture"

        # Check compatibility
        is_compatible = ffmpeg_arch == system_arch
        message = "FFMPEG is compatible with your system" if is_compatible else \
                 f"FFMPEG architecture ({ffmpeg_arch}) does not match system architecture ({system_arch})"

        return is_compatible, message

    except Exception as e:
        logging.error(f"Error checking FFMPEG compatibility: {e}")
        return False, f"Error checking compatibility: {str(e)}" 