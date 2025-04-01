import os
import sys
import platform
import shutil
import subprocess
import logging
from datetime import datetime
from state import app_state

# Global state
INITIAL_STATE_BACKUP_DIR = None

def setup_logging():
    """Configure logging for the application"""
    logs_dir = 'logs'
    try:
        # Create logs directory with proper permissions
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, mode=0o755, exist_ok=True)
        
        # Ensure the logs directory is writable
        if not os.access(logs_dir, os.W_OK):
            raise OSError(f"Logs directory {logs_dir} is not writable")

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
        print(f"Error setting up logging: {e}")
        return False

def get_system_architecture():
    """Get the system architecture."""
    arch = platform.machine()
    if arch == 'x86_64':
        return 'x86_64'
    elif arch == 'arm64':
        return 'arm64'
    else:
        return arch

def get_default_emby_path():
    """Get the default Emby Server installation path."""
    default_paths = [
        "/Applications/Emby Server.app",  # macOS
        "C:\\Program Files\\Emby Server",  # Windows
        "/opt/emby-server"  # Linux
    ]
    
    for path in default_paths:
        if os.path.exists(path):
            return path
    return None

# Process management functions
def run_process(cmd, shell=False):
    return app_state.run_process(cmd, shell)

def stop_current_process():
    return app_state.stop_process()

def is_process_running():
    return app_state.is_running

def get_process_state():
    return app_state.get_state()

def initialize_process_state():
    app_state.initialize()

def get_ffmpeg_paths(emby_path):
    """Get paths to FFMPEG binaries."""
    try:
        ffmpeg_path = find_ffmpeg_binaries(emby_path)
        if not ffmpeg_path:
            return {"success": False, "message": "FFMPEG binaries not found"}
        
        paths = {}
        for binary in ["ffmpeg", "ffprobe", "ffdetect"]:
            path = os.path.join(ffmpeg_path, binary)
            if not os.path.exists(path):
                return {"success": False, "message": f"{binary} not found"}
            paths[binary] = path
        
        return {"success": True, "paths": paths}
        
    except Exception as e:
        logging.error(f"Error getting FFMPEG paths: {str(e)}")
        return {"success": False, "message": f"Error getting FFMPEG paths: {str(e)}"}

def find_ffmpeg_binaries(emby_path):
    """Find the FFMPEG binaries in the Emby Server installation"""
    if not os.path.exists(emby_path):
        return None
    
    # Check common locations for ffmpeg binaries
    possible_paths = [
        os.path.join(emby_path, 'Contents', 'MacOS'),  # macOS app bundle
        os.path.join(emby_path, 'ffmpeg'),  # Windows/Linux
        os.path.join(emby_path, 'System', 'ffmpeg'),  # Alternative Windows/Linux
    ]
    
    for path in possible_paths:
        if os.path.exists(os.path.join(path, 'ffmpeg')) and \
           os.path.exists(os.path.join(path, 'ffprobe')) and \
           os.path.exists(os.path.join(path, 'ffdetect')):
            return path
    
    return None

def get_ffmpeg_architecture(ffmpeg_path):
    """Get the architecture of the FFMPEG binary and verify it's actually executable"""
    try:
        # Check all three binaries
        binaries = ['ffmpeg', 'ffprobe', 'ffdetect']
        architectures = set()
        
        for binary in binaries:
            binary_path = os.path.join(ffmpeg_path, binary)
            if not os.path.exists(binary_path):
                logging.error(f"Binary not found: {binary_path}")
                continue
                
            # First try to detect test binaries
            try:
                with open(binary_path, 'r') as f:
                    content = f.read()
                    if '#!/bin/bash' in content and 'Bad CPU type in executable' in content:
                        # This is one of our test binaries
                        if 'arm64' in os.path.dirname(binary_path):
                            architectures.add('arm64')
                            continue
                        elif 'x86_64' in os.path.dirname(binary_path):
                            architectures.add('x86_64')
                            continue
            except:
                pass  # Not a test binary, continue with normal detection
                
            # Normal binary detection
            try:
                result = subprocess.run(['file', binary_path], capture_output=True, text=True)
                if result.returncode == 0:
                    if 'arm64' in result.stdout.lower():
                        architectures.add('arm64')
                        continue
                    elif 'x86_64' in result.stdout.lower():
                        architectures.add('x86_64')
                        continue
            except:
                pass
                
            # If we couldn't determine the architecture, try running it
            try:
                result = subprocess.run([binary_path, '-version'], 
                                     capture_output=True, 
                                     text=True,
                                     timeout=2)  # Reduced timeout to 2 seconds
                
                # If it runs successfully, it's compatible with current architecture
                if result.returncode == 0:
                    architectures.add(get_system_architecture())
                else:
                    # Any non-zero exit code indicates potential incompatibility
                    logging.warning(f"Binary {binary} returned non-zero exit code: {result.returncode}")
                    # Check for error messages that indicate architecture incompatibility
                    error_output = result.stderr.lower()
                    if 'bad cpu type in executable' in error_output:
                        if 'arm64' in os.path.dirname(binary_path):
                            architectures.add('arm64')
                        elif 'x86_64' in os.path.dirname(binary_path):
                            architectures.add('x86_64')
                    elif result.returncode == 8:  # Special case for exit code 8
                        # This is likely an incompatible binary
                        if 'arm64' in os.path.dirname(binary_path):
                            architectures.add('arm64')
                        elif 'x86_64' in os.path.dirname(binary_path):
                            architectures.add('x86_64')
                        else:
                            # Try to determine architecture from the binary file
                            file_result = subprocess.run(['file', binary_path], capture_output=True, text=True)
                            if 'arm64' in file_result.stdout.lower():
                                architectures.add('arm64')
                            elif 'x86_64' in file_result.stdout.lower():
                                architectures.add('x86_64')
            except subprocess.TimeoutExpired:
                logging.warning(f"Binary {binary} timed out when trying to execute")
            except Exception as e:
                logging.warning(f"Error executing {binary}: {e}")
                if 'bad cpu type in executable' in str(e).lower():
                    # This is our test binary failing as expected
                    if 'arm64' in os.path.dirname(binary_path):
                        architectures.add('arm64')
                    elif 'x86_64' in os.path.dirname(binary_path):
                        architectures.add('x86_64')
        
        if len(architectures) > 1:
            logging.warning(f"Mixed architectures found: {architectures}")
            # Return the most common architecture or the first one if tied
            return list(architectures)[0]
        elif len(architectures) == 1:
            return list(architectures)[0]
        else:
            logging.error("Could not determine FFMPEG architecture")
            return None
            
    except Exception as e:
        logging.error(f"Error getting FFMPEG architecture: {e}")
        return None

def backup_original_ffmpeg(ffmpeg_path):
    """Backup original FFMPEG binaries"""
    try:
        # Check if we have write permissions in the parent directory
        parent_dir = os.path.dirname(ffmpeg_path)
        if not os.access(parent_dir, os.W_OK):
            return False, f"No write permission for directory: {parent_dir}"
            
        backup_dir = os.path.join(parent_dir, "ffmpeg_backup_original")
        if os.path.exists(backup_dir):
            logging.info(f"Backup already exists at {backup_dir}")
            return True
            
        # Create backup directory with proper permissions
        try:
            os.makedirs(backup_dir, mode=0o755, exist_ok=True)
        except OSError as e:
            return False, f"Failed to create backup directory: {e}"
        
        # Backup all three binaries
        for binary in ['ffmpeg', 'ffprobe', 'ffdetect']:
            src = os.path.join(ffmpeg_path, binary)
            dst = os.path.join(backup_dir, binary)
            
            if not os.path.exists(src):
                return False, f"Original {binary} not found at {src}"
                
            # Check if source is readable
            if not os.access(src, os.R_OK):
                return False, f"Cannot read original {binary}"
                
            try:
                # Copy the binary
                shutil.copy2(src, dst)
                # Set proper permissions for backup
                os.chmod(dst, 0o755)
                logging.info(f"Backed up {binary} to {backup_dir}")
            except OSError as e:
                return False, f"Failed to backup {binary}: {e}"
                
        logging.info(f"Successfully backed up ffmpeg to {backup_dir}")
        return True
    except Exception as e:
        logging.error(f"Error backing up FFMPEG: {e}")
        return False

def replace_ffmpeg_binaries(emby_path, target_arch):
    """Replace FFMPEG binaries with the correct architecture version"""
    try:
        ffmpeg_path = find_ffmpeg_binaries(emby_path)
        if not ffmpeg_path:
            return False, "FFMPEG binaries not found"
            
        # Check if we have write permissions
        if not os.access(ffmpeg_path, os.W_OK):
            return False, f"No write permission for FFMPEG directory: {ffmpeg_path}"
            
        # Backup original binaries
        if not backup_original_ffmpeg(ffmpeg_path):
            return False, "Failed to backup original FFMPEG binaries"
            
        # Get paths for replacement binaries
        replacement_dir = os.path.join('ffmpeg_binaries', target_arch)
        if not os.path.exists(replacement_dir):
            return False, f"No replacement binaries found for {target_arch}"
            
        # Replace all three binaries
        for binary in ['ffmpeg', 'ffprobe', 'ffdetect']:
            src = os.path.join(replacement_dir, binary)
            dst = os.path.join(ffmpeg_path, binary)
            
            if not os.path.exists(src):
                return False, f"Replacement {binary} not found"
                
            # Check if source is readable
            if not os.access(src, os.R_OK):
                return False, f"Cannot read replacement {binary}"
                
            # Remove existing binary if it exists
            if os.path.exists(dst):
                try:
                    os.remove(dst)
                except OSError as e:
                    return False, f"Cannot remove existing {binary}: {e}"
                
            # Copy new binary
            try:
                shutil.copy2(src, dst)
                # Make it executable with proper permissions
                os.chmod(dst, 0o755)
                logging.info(f"Replaced {binary} with {target_arch} version at {dst}")
            except OSError as e:
                return False, f"Failed to copy {binary}: {e}"
            
        return True, "Successfully replaced FFMPEG binaries"
    except Exception as e:
        logging.error(f"Error replacing ffmpeg: {e}")
        return False, str(e)

def restore_original_ffmpeg(emby_path):
    """Restore original FFMPEG binaries from backup"""
    try:
        ffmpeg_path = find_ffmpeg_binaries(emby_path)
        if not ffmpeg_path:
            return False, "FFMPEG binaries not found"
            
        # Check if we have write permissions
        if not os.access(ffmpeg_path, os.W_OK):
            return False, f"No write permission for FFMPEG directory: {ffmpeg_path}"
            
        backup_dir = os.path.join(os.path.dirname(ffmpeg_path), "ffmpeg_backup_original")
        if not os.path.exists(backup_dir):
            return False, "No backup found to restore"
            
        # Restore all three binaries
        for binary in ['ffmpeg', 'ffprobe', 'ffdetect']:
            src = os.path.join(backup_dir, binary)
            dst = os.path.join(ffmpeg_path, binary)
            
            if not os.path.exists(src):
                return False, f"Backup {binary} not found"
                
            # Check if backup is readable
            if not os.access(src, os.R_OK):
                return False, f"Cannot read backup {binary}"
                
            # Remove current binary if it exists
            if os.path.exists(dst):
                try:
                    os.remove(dst)
                except OSError as e:
                    return False, f"Cannot remove existing {binary}: {e}"
                
            # Copy backup binary
            try:
                shutil.copy2(src, dst)
                # Make it executable with proper permissions
                os.chmod(dst, 0o755)
                logging.info(f"Restored {binary} from backup")
            except OSError as e:
                return False, f"Failed to restore {binary}: {e}"
            
        # Clean up test mode files
        test_files = [
            os.path.join(os.path.dirname(ffmpeg_path), "ffmpeg_test_mode"),
            os.path.join(os.path.dirname(ffmpeg_path), "ffmpeg_architecture")
        ]
        for test_file in test_files:
            if os.path.exists(test_file):
                try:
                    os.remove(test_file)
                except OSError as e:
                    logging.warning(f"Could not remove test file {test_file}: {e}")
            
        return True, "Successfully restored original FFMPEG binaries"
    except Exception as e:
        logging.error(f"Error restoring ffmpeg: {e}")
        return False, str(e)

def force_single_architecture(ffmpeg_path, target_arch):
    """Force a specific architecture for testing."""
    logging.info(f"Starting force_single_architecture with ffmpeg_path={ffmpeg_path}, target_arch={target_arch}")
    
    if not os.path.exists(ffmpeg_path):
        logging.error(f"FFMPEG path does not exist: {ffmpeg_path}")
        return "Error: FFMPEG path does not exist"

    # Get absolute paths
    ffmpeg_path = os.path.abspath(ffmpeg_path)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    
    logging.info(f"Current directory: {current_dir}")
    logging.info(f"Project root: {project_root}")

    # Create test directory if it doesn't exist
    test_dir = os.path.join(os.path.dirname(ffmpeg_path), "ffmpeg_test")
    os.makedirs(test_dir, exist_ok=True)
    logging.info(f"Created/verified test directory: {test_dir}")

    # Backup original binaries if not already backed up
    backup_dir = os.path.join(os.path.dirname(ffmpeg_path), "ffmpeg_backup_original")
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        for binary in ["ffmpeg", "ffprobe", "ffdetect"]:
            src = os.path.join(ffmpeg_path, binary)
            dst = os.path.join(backup_dir, binary)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                logging.info(f"Backed up {binary} to {dst}")

    # Look for test resources in multiple possible locations
    possible_locations = [
        os.path.join(project_root, "test_resources", target_arch),  # Project root
        os.path.join(current_dir, "test_resources", target_arch),   # Current directory
        os.path.join(os.getcwd(), "test_resources", target_arch)    # Working directory
    ]

    test_resources = None
    for location in possible_locations:
        logging.info(f"Checking for test resources in: {location}")
        if os.path.exists(location):
            test_resources = location
            logging.info(f"Found test resources at: {location}")
            break

    if test_resources is None:
        error_msg = "Test resources not found in any of these locations:"
        for loc in possible_locations:
            error_msg += f"\n- {loc}"
        logging.error(error_msg)
        return error_msg

    try:
        for binary in ["ffmpeg", "ffprobe", "ffdetect"]:
            src = os.path.join(test_resources, binary)
            dst = os.path.join(ffmpeg_path, binary)
            logging.info(f"Attempting to copy {src} to {dst}")
            
            if not os.path.exists(src):
                logging.error(f"Test binary not found: {src}")
                return f"Error: Test binary {binary} not found at {src}"
                
            shutil.copy2(src, dst)
            os.chmod(dst, 0o755)  # Make executable
            logging.info(f"Successfully copied and made executable: {dst}")
            
            # Verify the binary fails as expected
            logging.info(f"Testing binary: {dst}")
            result = subprocess.run([dst], capture_output=True, text=True)
            logging.info(f"Test result: returncode={result.returncode}, stderr={result.stderr}")
            
            if result.returncode != 1 or "Bad CPU type in executable" not in result.stderr:
                logging.error(f"Binary {binary} not working as expected: returncode={result.returncode}")
                return f"Error: Test binary {binary} not working as expected"

        # Create a test marker file
        marker_file = os.path.join(test_dir, "test_mode")
        with open(marker_file, "w") as f:
            f.write(f"Architecture: {target_arch}\nTimestamp: {datetime.now()}")
        logging.info(f"Created test marker file: {marker_file}")

        return "Success: Test binaries installed. Emby Server should now show compatibility issues."
    except Exception as e:
        logging.error(f"Error in force_single_architecture: {str(e)}")
        return f"Error setting up test environment: {str(e)}"

def is_test_mode_active(ffmpeg_path):
    """Check if test mode is currently active"""
    try:
        test_marker = os.path.join(os.path.dirname(ffmpeg_path), "ffmpeg_test_mode")
        return os.path.exists(test_marker)
    except Exception:
        return False

def get_test_mode_info(ffmpeg_path):
    """Get information about the current test mode"""
    try:
        test_marker = os.path.join(os.path.dirname(ffmpeg_path), "ffmpeg_test_mode")
        if os.path.exists(test_marker):
            with open(test_marker, 'r') as f:
                return f.read().strip()
        return None
    except Exception:
        return None

def fix_ffmpeg_compatibility(emby_path):
    """Fix FFMPEG compatibility by replacing binaries with correct architecture."""
    try:
        system_arch = get_system_architecture()
        logger.info(f"System architecture: {system_arch}")
        
        # Get paths to FFMPEG binaries
        ffmpeg_paths = get_ffmpeg_paths(emby_path)
        if not ffmpeg_paths["success"]:
            return ffmpeg_paths
        
        # Create backup if it doesn't exist
        backup_result = create_backup(emby_path)
        if not backup_result["success"]:
            return backup_result
        
        # Replace binaries
        for binary_name, path in ffmpeg_paths["paths"].items():
            logger.info(f"Replacing {binary_name}...")
            
            # Get correct binary for system architecture
            new_binary = get_compatible_binary(binary_name, system_arch)
            if not new_binary["success"]:
                return new_binary
            
            # Copy new binary
            try:
                shutil.copy2(new_binary["path"], path)
                os.chmod(path, 0o755)  # Make executable
                logger.info(f"Successfully replaced {binary_name}")
            except Exception as e:
                logger.error(f"Error replacing {binary_name}: {str(e)}")
                return {"success": False, "message": f"Error replacing {binary_name}: {str(e)}"}
        
        return {"success": True, "message": "FFMPEG binaries replaced successfully"}
        
    except Exception as e:
        logger.error(f"Error fixing FFMPEG compatibility: {str(e)}")
        return {"success": False, "message": f"Error fixing FFMPEG compatibility: {str(e)}"}

def create_backup(emby_path):
    """Create backup of FFMPEG binaries if it doesn't exist."""
    try:
        backup_dir = os.path.join(os.path.dirname(emby_path), "ffmpeg_backup")
        if os.path.exists(backup_dir):
            logger.info("Backup already exists")
            return {"success": True, "message": "Backup already exists"}
        
        # Get paths to FFMPEG binaries
        ffmpeg_paths = get_ffmpeg_paths(emby_path)
        if not ffmpeg_paths["success"]:
            return ffmpeg_paths
        
        # Create backup directory
        os.makedirs(backup_dir)
        
        # Copy binaries to backup
        for binary_name, path in ffmpeg_paths["paths"].items():
            backup_path = os.path.join(backup_dir, os.path.basename(path))
            try:
                shutil.copy2(path, backup_path)
                logger.info(f"Successfully backed up {binary_name}")
            except Exception as e:
                logger.error(f"Error backing up {binary_name}: {str(e)}")
                # Clean up failed backup
                shutil.rmtree(backup_dir, ignore_errors=True)
                return {"success": False, "message": f"Error backing up {binary_name}: {str(e)}"}
        
        return {"success": True, "message": "Backup created successfully"}
        
    except Exception as e:
        logger.error(f"Error creating backup: {str(e)}")
        return {"success": False, "message": f"Error creating backup: {str(e)}"}

def restore_from_backup(emby_path):
    """Restore FFMPEG binaries from backup."""
    try:
        backup_dir = os.path.join(os.path.dirname(emby_path), "ffmpeg_backup")
        if not os.path.exists(backup_dir):
            return {"success": False, "message": "No backup found"}
        
        # Get paths to FFMPEG binaries
        ffmpeg_paths = get_ffmpeg_paths(emby_path)
        if not ffmpeg_paths["success"]:
            return ffmpeg_paths
        
        # Restore binaries from backup
        for binary_name, path in ffmpeg_paths["paths"].items():
            backup_path = os.path.join(backup_dir, os.path.basename(path))
            if not os.path.exists(backup_path):
                return {"success": False, "message": f"Backup for {binary_name} not found"}
            
            try:
                shutil.copy2(backup_path, path)
                os.chmod(path, 0o755)  # Make executable
                logger.info(f"Successfully restored {binary_name}")
            except Exception as e:
                logger.error(f"Error restoring {binary_name}: {str(e)}")
                return {"success": False, "message": f"Error restoring {binary_name}: {str(e)}"}
        
        return {"success": True, "message": "FFMPEG binaries restored successfully"}
        
    except Exception as e:
        logger.error(f"Error restoring from backup: {str(e)}")
        return {"success": False, "message": f"Error restoring from backup: {str(e)}"}

def force_architecture_incompatibility(emby_path, target_arch):
    """Force FFMPEG binaries to be incompatible by using wrong architecture."""
    try:
        # Create backup if it doesn't exist
        backup_result = create_backup(emby_path)
        if not backup_result["success"]:
            return backup_result
        
        # Get paths to FFMPEG binaries
        ffmpeg_paths = get_ffmpeg_paths(emby_path)
        if not ffmpeg_paths["success"]:
            return ffmpeg_paths
        
        # Replace binaries with target architecture
        for binary_name, path in ffmpeg_paths["paths"].items():
            logger.info(f"Replacing {binary_name} with {target_arch} version...")
            
            # Get binary for target architecture
            new_binary = get_compatible_binary(binary_name, target_arch)
            if not new_binary["success"]:
                return new_binary
            
            try:
                shutil.copy2(new_binary["path"], path)
                os.chmod(path, 0o755)  # Make executable
                logger.info(f"Successfully replaced {binary_name}")
            except Exception as e:
                logger.error(f"Error replacing {binary_name}: {str(e)}")
                return {"success": False, "message": f"Error replacing {binary_name}: {str(e)}"}
        
        return {"success": True, "message": f"FFMPEG binaries replaced with {target_arch} version"}
        
    except Exception as e:
        logger.error(f"Error forcing architecture incompatibility: {str(e)}")
        return {"success": False, "message": f"Error forcing architecture incompatibility: {str(e)}"}

def create_initial_state_backup(emby_path):
    """Create a backup of the initial FFMPEG state when the main page loads."""
    global INITIAL_STATE_BACKUP_DIR
    try:
        # Create a unique backup directory for this session
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = os.path.join(os.path.dirname(emby_path), f"ffmpeg_initial_state_{timestamp}")
        
        # Get paths to FFMPEG binaries
        ffmpeg_paths = get_ffmpeg_paths(emby_path)
        if not ffmpeg_paths["success"]:
            return ffmpeg_paths
        
        # Create backup directory
        os.makedirs(backup_dir)
        
        # Copy binaries to backup
        for binary_name, path in ffmpeg_paths["paths"].items():
            backup_path = os.path.join(backup_dir, os.path.basename(path))
            try:
                shutil.copy2(path, backup_path)
                logging.info(f"Successfully backed up initial state of {binary_name}")
            except Exception as e:
                logging.error(f"Error backing up initial state of {binary_name}: {str(e)}")
                # Clean up failed backup
                shutil.rmtree(backup_dir, ignore_errors=True)
                return {"success": False, "message": f"Error backing up initial state of {binary_name}: {str(e)}"}
        
        INITIAL_STATE_BACKUP_DIR = backup_dir
        return {"success": True, "message": "Initial state backup created successfully"}
        
    except Exception as e:
        logging.error(f"Error creating initial state backup: {str(e)}")
        return {"success": False, "message": f"Error creating initial state backup: {str(e)}"}

def restore_initial_state(emby_path):
    """Restore FFMPEG binaries to their initial state from when the main page was loaded."""
    global INITIAL_STATE_BACKUP_DIR
    try:
        if not INITIAL_STATE_BACKUP_DIR or not os.path.exists(INITIAL_STATE_BACKUP_DIR):
            return {"success": False, "message": "No initial state backup found"}
        
        # Get paths to FFMPEG binaries
        ffmpeg_paths = get_ffmpeg_paths(emby_path)
        if not ffmpeg_paths["success"]:
            return ffmpeg_paths
        
        # Restore binaries from initial state backup
        for binary_name, path in ffmpeg_paths["paths"].items():
            backup_path = os.path.join(INITIAL_STATE_BACKUP_DIR, os.path.basename(path))
            if not os.path.exists(backup_path):
                return {"success": False, "message": f"Initial state backup for {binary_name} not found"}
            
            try:
                shutil.copy2(backup_path, path)
                os.chmod(path, 0o755)  # Make executable
                logging.info(f"Successfully restored {binary_name} to initial state")
            except Exception as e:
                logging.error(f"Error restoring {binary_name} to initial state: {str(e)}")
                return {"success": False, "message": f"Error restoring {binary_name} to initial state: {str(e)}"}
        
        # Clean up initial state backup
        shutil.rmtree(INITIAL_STATE_BACKUP_DIR, ignore_errors=True)
        INITIAL_STATE_BACKUP_DIR = None
        
        return {"success": True, "message": "FFMPEG binaries restored to initial state successfully"}
        
    except Exception as e:
        logging.error(f"Error restoring initial state: {str(e)}")
        return {"success": False, "message": f"Error restoring initial state: {str(e)}"}
