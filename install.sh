#!/bin/bash
set -e

echo ""
echo "Open Wisper — Install"
echo "---------------------"
echo ""

# Check Apple Silicon
if [ "$(uname -m)" != "arm64" ]; then
  echo "Error: Open Wisper requires Apple Silicon (M1/M2/M3/M4)."
  echo "Intel Macs are not supported (MLX is Apple Silicon only)."
  exit 1
fi

# Check macOS 12+
OS_VER=$(sw_vers -productVersion | cut -d. -f1)
if [ "$OS_VER" -lt 12 ]; then
  echo "Error: macOS 12 or later required (you have $(sw_vers -productVersion))"
  exit 1
fi

# Check Python 3.9+
if ! python3 -c "import sys; assert sys.version_info >= (3, 9)" 2>/dev/null; then
  echo "Error: Python 3.9 or later is required."
  echo "Install: brew install python3  or  https://www.python.org/downloads/"
  exit 1
fi
echo "Python: $(python3 --version)"

# Check / install Homebrew
if ! command -v brew &>/dev/null; then
  echo "Error: Homebrew is required."
  echo "Install: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
  exit 1
fi

# Install portaudio
if ! brew list portaudio &>/dev/null 2>&1; then
  echo "Installing portaudio..."
  brew install portaudio
else
  echo "portaudio: already installed"
fi

# Install Python packages
echo "Installing Python packages..."
pip3 install --user -r requirements.txt

echo ""
echo "Done! Run the app:"
echo ""
echo "  python3 app.py"
echo ""
echo "On first launch, Open Wisper will guide you through setup:"
echo "  - Downloading the AI model (~750 MB, one time only)"
echo "  - Granting microphone and accessibility permissions"
echo ""
echo "After setup, press Fn+R anywhere to start recording."
echo ""
