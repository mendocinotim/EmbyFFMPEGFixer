#!/bin/bash

# EmbyFFMPEGFixer Uninstaller Script
# This script completely removes the EmbyFFMPEGFixer application
# and optionally restores original FFMPEG binaries if a backup exists.

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

APP_NAME="EmbyFFMPEGFixer"
APP_PATH="/Applications/${APP_NAME}.app"
PREFERENCES_PATH="$HOME/Library/Preferences/com.emby.ffmpegfixer"
LOGS_PATH="$HOME/Library/Logs/${APP_NAME}"
LAUNCHER_NAME="com.emby.ffmpegfixer"

# Function to display status messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if application is installed
check_installation() {
    if [ ! -d "$APP_PATH" ]; then
        print_warning "${APP_NAME} not found in Applications folder."
        return 1
    fi
    return 0
}

# Function to stop running processes
stop_processes() {
    print_status "Stopping any running ${APP_NAME} processes..."
    
    # Kill by process name
    pkill -f "${APP_NAME}" 2>/dev/null
    
    # Kill any processes using port 5001 (which our app uses)
    PORT_PID=$(lsof -ti:5001 2>/dev/null)
    if [ ! -z "$PORT_PID" ]; then
        print_status "Killing process $PORT_PID using port 5001"
        kill -9 $PORT_PID 2>/dev/null
    fi
    
    print_success "All processes stopped."
}

# Function to remove the application
remove_application() {
    print_status "Removing ${APP_NAME} application..."
    
    if [ -d "$APP_PATH" ]; then
        rm -rf "$APP_PATH"
        print_success "Application removed from ${APP_PATH}"
    else
        print_warning "Application not found at ${APP_PATH}"
    fi
}

# Function to remove preferences
remove_preferences() {
    print_status "Removing application preferences..."
    
    if [ -d "$PREFERENCES_PATH" ]; then
        rm -rf "$PREFERENCES_PATH"
        print_success "Preferences removed."
    else
        print_warning "No preferences found."
    fi
    
    # Remove any plist files
    PLIST_FILES=$(find "$HOME/Library/Preferences" -name "*${LAUNCHER_NAME}*" 2>/dev/null)
    if [ ! -z "$PLIST_FILES" ]; then
        for file in $PLIST_FILES; do
            rm -f "$file"
            print_status "Removed preference file: $file"
        done
    fi
}

# Function to remove logs
remove_logs() {
    print_status "Removing application logs..."
    
    if [ -d "$LOGS_PATH" ]; then
        rm -rf "$LOGS_PATH"
        print_success "Logs removed."
    else
        print_warning "No log directory found."
    fi
    
    # Remove any log files in the current user's home directory
    LOG_FILES=$(find "$HOME" -name "emby_ffmpeg_fixer*.log" 2>/dev/null)
    if [ ! -z "$LOG_FILES" ]; then
        for file in $LOG_FILES; do
            rm -f "$file"
            print_status "Removed log file: $file"
        done
    fi
}

# Function to check for and offer to restore FFMPEG backups
check_and_restore_backups() {
    print_status "Checking for FFMPEG backups..."
    
    # Look for Emby Server in common locations
    EMBY_LOCATIONS=(
        "/Applications/EmbyServer.app"
        "/Applications/Emby Server.app"
        "/opt/emby-server"
    )
    
    for EMBY_PATH in "${EMBY_LOCATIONS[@]}"; do
        if [ -d "$EMBY_PATH" ]; then
            print_status "Found Emby Server at $EMBY_PATH"
            
            # Look for FFMPEG backup
            FFMPEG_PATHS=(
                "$EMBY_PATH/Contents/MacOS"
                "$EMBY_PATH/Contents/Resources"
            )
            
            for FFMPEG_PATH in "${FFMPEG_PATHS[@]}"; do
                BACKUP_PATH="$FFMPEG_PATH/ffmpeg_backup_original"
                
                if [ -d "$BACKUP_PATH" ]; then
                    print_status "Found FFMPEG backup at $BACKUP_PATH"
                    
                    read -p "Would you like to restore the original FFMPEG binaries? (y/n): " RESTORE_CHOICE
                    if [[ $RESTORE_CHOICE == "y" || $RESTORE_CHOICE == "Y" ]]; then
                        print_status "Restoring original FFMPEG binaries..."
                        
                        # Copy all files from backup to ffmpeg directory
                        for file in "$BACKUP_PATH"/*; do
                            filename=$(basename "$file")
                            cp -f "$file" "$FFMPEG_PATH/$filename"
                            chmod +x "$FFMPEG_PATH/$filename"
                            print_status "Restored $filename"
                        done
                        
                        print_success "Original FFMPEG binaries restored."
                        
                        read -p "Would you like to remove the backup files? (y/n): " REMOVE_BACKUP_CHOICE
                        if [[ $REMOVE_BACKUP_CHOICE == "y" || $REMOVE_BACKUP_CHOICE == "Y" ]]; then
                            rm -rf "$BACKUP_PATH"
                            print_success "Backup files removed."
                        else
                            print_status "Backup files kept for future reference."
                        fi
                    
                    else
                        print_status "Original FFMPEG binaries not restored."
                    fi
                
                else 
                    print_warning "No backup found at $BACKUP_PATH."
                fi
            
            done
        
        else 
            print_warning "${EMBY_LOCATIONS[@]} not found!"
        
        fi
    
done 
}


main(){
echo "[Starting Uninstallation]"}


