# Emby FFMPEG Fixer

A utility tool that automatically detects and fixes FFMPEG compatibility issues in Emby Server installations on macOS systems.

## Overview

Emby FFMPEG Fixer is a specialized tool that resolves FFMPEG-related issues occurring after Emby Server updates, especially on older Intel-based Macs. It automatically detects your system architecture, validates Emby Server's FFMPEG configuration, and applies fixes when necessary to ensure smooth media transcoding and playback.

## What This Tool Does

If your Emby Server shows "Bad CPU type in executable" errors when playing media, it means your FFMPEG binaries don't match your system architecture (often x86_64 vs arm64). This tool automatically detects the mismatch and replaces the FFMPEG binaries with the correct version for your system.

## Problem Background

Emby Server relies on FFMPEG for media transcoding. After updates, some installations (particularly on macOS) may experience issues where:

- FFMPEG paths become incorrect
- Permission problems prevent proper execution 
- Library dependencies break
- Configuration settings revert to defaults

These issues often result in failed playback, transcoding errors, or suboptimal performance.

## Features

- **Automatic Detection**: Locates your Emby Server installation and identifies its FFMPEG configuration
- **System Architecture Analysis**: Determines your computer's CPU architecture (Intel/AMD = x86_64, Apple Silicon = arm64)
- **FFMPEG Compatibility Check**: Validates that FFMPEG binaries match your system architecture
- **Intelligent Repair**: Applies targeted fixes based on detected issues
- **Backup Creation**: Creates backups of original files before making any changes
- **User-Friendly Interface**: Simple step-by-step web interface accessible at http://127.0.0.1:5001

## Installation

### Requirements
- macOS 10.13 or later
- Emby Server installed on your system

### Installation Steps
1. Download the DMG file from [GitHub Releases](https://github.com/mendocinotim/EmbyFFMPEGFixer/releases)
2. Mount the DMG by double-clicking it
3. Drag the EmbyFFMPEGFixer app to your Applications folder
4. Launch the app from Applications

## Usage

1. **Select Emby Server Application**
   - Browse for your Emby Server installation or manually enter the path (typically `/Applications/EmbyServer.app`)

2. **Check FFMPEG Compatibility**
   - The tool will automatically detect your system architecture and the architecture of Emby's FFMPEG binaries
   - If they match, you'll see a "Compatible ✓" message
   - If they don't match, you'll see an "Incompatible ✗" message

3. **Fix Compatibility Issues**
   - If incompatible, click the "Fix FFMPEG Compatibility" button
   - The tool will replace the incompatible binaries with the correct version for your system

4. **View Process Logs**
   - Monitor the process in real-time through the log display
   - Download logs for future reference if needed

## Uninstallation

The EmbyFFMPEGFixer includes a comprehensive uninstaller that safely removes the application and can restore original FFMPEG binaries.

### Uninstallation Steps
1. Launch the DMG installer
2. Open the `Uninstaller` folder
3. Run the `uninstall.sh` script
4. Follow the prompts to complete the uninstallation

### What the Uninstaller Does
- Restores original FFMPEG binaries from backup (if available)
- Removes the EmbyFFMPEGFixer application from your system
- Cleans up any temporary files or configurations created by the application
- Provides detailed logging of the uninstallation process

Rest assured that the uninstaller is designed to leave your system in the same state it was before installation, with original FFMPEG binaries properly restored.

## Technical Details

### Architecture
- Built with Python and Flask for the web interface
- Uses PyInstaller for macOS application bundling
- Implements architecture detection using system commands
- Includes pre-compiled FFMPEG binaries for different architectures

### FFMPEG Compatibility
The tool fixes compatibility issues by:
1. Identifying the system architecture (x86_64 or arm64)
2. Checking FFMPEG binary architecture
3. Backing up original binaries
4. Replacing incompatible binaries with architecture-matching versions

## Contributing

Contributions to the EmbyFFMPEGFixer project are welcome:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

For bug reports or feature requests, please use the [Issues page](https://github.com/mendocinotim/EmbyFFMPEGFixer/issues).

## License

This project is released under the MIT License.
