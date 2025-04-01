#!/bin/bash

# Move to project root directory to ensure correct relative paths
cd "$(dirname "$0")/.." || exit 1
PROJECT_ROOT=$(pwd)

echo "Working from project root: $PROJECT_ROOT"

# Clean up any previous DMG
test -f "$PROJECT_ROOT/EmbyFFMPEGFixer-1.0.2.dmg" && rm "$PROJECT_ROOT/EmbyFFMPEGFixer-1.0.2.dmg"

# Create a folder to prepare our DMG
mkdir -p "$PROJECT_ROOT/dist/dmg"
rm -rf "$PROJECT_ROOT/dist/dmg/"*

# Create Applications symlink
ln -s /Applications "$PROJECT_ROOT/dist/dmg/Applications"

# Check if app bundle exists
if [ ! -d "$PROJECT_ROOT/EmbyFFMPEGFixer.app" ]; then
  echo "App bundle not found at $PROJECT_ROOT/EmbyFFMPEGFixer.app"
  
  # Check if it exists in the dist directory
  if [ -d "$PROJECT_ROOT/dist/EmbyFFMPEGFixer" ]; then
    echo "Found executable in dist directory. Creating app bundle..."
    
    # Create app bundle structure if not exists
    mkdir -p "$PROJECT_ROOT/EmbyFFMPEGFixer.app/Contents/MacOS"
    mkdir -p "$PROJECT_ROOT/EmbyFFMPEGFixer.app/Contents/Resources"
    
    # Copy executable
    cp "$PROJECT_ROOT/dist/EmbyFFMPEGFixer" "$PROJECT_ROOT/EmbyFFMPEGFixer.app/Contents/MacOS/"
    
    # Copy resources if they exist
    if [ -d "$PROJECT_ROOT/resources" ]; then
      cp -r "$PROJECT_ROOT/resources/icon.icns" "$PROJECT_ROOT/EmbyFFMPEGFixer.app/Contents/Resources/" 2>/dev/null || echo "Icon not copied"
    fi
    
    # Create Info.plist if not exists
    if [ ! -f "$PROJECT_ROOT/EmbyFFMPEGFixer.app/Contents/Info.plist" ]; then
      cat > "$PROJECT_ROOT/EmbyFFMPEGFixer.app/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>EmbyFFMPEGFixer</string>
    <key>CFBundleIconFile</key>
    <string>icon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.emby.ffmpegfixer</string>
    <key>CFBundleName</key>
    <string>Emby FFMPEG Fixer</string>
    <key>CFBundleDisplayName</key>
    <string>Emby FFMPEG Fixer</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.2</string>
    <key>CFBundleVersion</key>
    <string>1.0.2</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF
    fi
  else
    echo "ERROR: No executable found in dist directory. Run PyInstaller first."
    exit 1
  fi
fi

# Copy the app bundle to the dmg folder
echo "Copying app bundle to DMG folder..."
cp -r "$PROJECT_ROOT/EmbyFFMPEGFixer.app" "$PROJECT_ROOT/dist/dmg/"

# Copy the uninstaller to the DMG
echo "Setting up uninstaller..."
mkdir -p "$PROJECT_ROOT/dist/dmg/Uninstaller"

# Check if uninstall.sh exists in scripts directory
if [ -f "$PROJECT_ROOT/scripts/uninstall.sh" ]; then
  cp "$PROJECT_ROOT/scripts/uninstall.sh" "$PROJECT_ROOT/dist/dmg/Uninstaller/"
  chmod +x "$PROJECT_ROOT/dist/dmg/Uninstaller/uninstall.sh"
else
  echo "WARNING: Uninstaller script not found at $PROJECT_ROOT/scripts/uninstall.sh"
  # Create a basic uninstaller if missing
  cat > "$PROJECT_ROOT/dist/dmg/Uninstaller/uninstall.sh" << EOF
#!/bin/bash
echo "Uninstalling EmbyFFMPEGFixer..."
rm -rf "/Applications/EmbyFFMPEGFixer.app"
echo "Uninstallation complete!"
EOF
  chmod +x "$PROJECT_ROOT/dist/dmg/Uninstaller/uninstall.sh"
fi

# Create README file for DMG
echo "Creating README..."
if [ -f "$PROJECT_ROOT/scripts/README.txt" ]; then
  cp "$PROJECT_ROOT/scripts/README.txt" "$PROJECT_ROOT/dist/dmg/README.txt"
else
  # Fallback if the file doesn't exist
  cat > "$PROJECT_ROOT/dist/dmg/README.txt" << EOF
Emby FFMPEG Fixer v1.0.2

INSTALLATION:
1. Drag the EmbyFFMPEGFixer app to the Applications folder.
2. Launch from Applications.

For more information, visit: https://github.com/mendocinotim/EmbyFFMPEGFixer
EOF
fi

# Create the DMG
echo "Creating DMG..."
DMG_PATH="$PROJECT_ROOT/EmbyFFMPEGFixer-1.0.2.dmg"

# Check if icon exists
ICON_PARAM=""
if [ -f "$PROJECT_ROOT/resources/icon.icns" ]; then
  ICON_PARAM="--volicon $PROJECT_ROOT/resources/icon.icns"
fi

create-dmg \
  --volname "Emby FFMPEG Fixer" \
  $ICON_PARAM \
  --window-pos 200 120 \
  --window-size 800 500 \
  --icon-size 100 \
  --icon "EmbyFFMPEGFixer.app" 200 190 \
  --icon "Applications" 600 190 \
  --icon "Uninstaller" 400 320 \
  --icon "README.txt" 200 320 \
  --hide-extension "README.txt" \
  --app-drop-link 600 185 \
  "$DMG_PATH" \
  "$PROJECT_ROOT/dist/dmg"

if [ $? -eq 0 ]; then
  echo "DMG installer created successfully: $DMG_PATH"
else
  echo "ERROR: DMG creation failed."
fi
