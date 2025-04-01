Emby FFMPEG Fixer v1.0.2
========================

A utility to detect and fix FFMPEG architecture compatibility issues in Emby Server on macOS.

INSTALLATION:
1. Drag the EmbyFFMPEGFixer app to the Applications folder.
2. Launch the app from Applications.

USAGE:
1. Select your Emby Server application location (typically /Applications/EmbyServer.app)
2. The tool will automatically detect your system architecture and check FFMPEG compatibility
3. If incompatible, click "Fix FFMPEG Compatibility" to resolve the issue
4. Your Emby Server should now work properly with compatible FFMPEG binaries

SYSTEM REQUIREMENTS:
- macOS 10.13 or later
- Emby Server installed

UNINSTALLATION:
The included uninstaller safely removes the application and can restore original FFMPEG binaries:
1. Launch the DMG installer
2. Open the Uninstaller folder
3. Run the uninstall.sh script

The uninstaller will:
- Restore original FFMPEG binaries from backup (if available)
- Remove the EmbyFFMPEGFixer application
- Clean up temporary files and configurations

For additional help or to report issues, visit:
https://github.com/mendocinotim/EmbyFFMPEGFixer
