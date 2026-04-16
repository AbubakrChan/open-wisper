#!/bin/bash
# Build OpenWisper.app from Swift source
set -e

cd "$(dirname "$0")"

echo "Building OpenWisper launcher..."

# Build the Swift executable
swift build -c release

# Create app bundle structure
APP_DIR="OpenWisper.app"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# Copy executable
cp .build/release/OpenWisperLauncher "$APP_DIR/Contents/MacOS/"

# Copy Info.plist
cp Info.plist "$APP_DIR/Contents/"

# Create PkgInfo
echo -n "APPL????" > "$APP_DIR/Contents/PkgInfo"

echo "Built: $APP_DIR"
echo ""
echo "To install:"
echo "  cp -r OpenWisper.app ~/Applications/"
echo "  open ~/Applications/OpenWisper.app"
