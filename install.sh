#!/bin/bash
# Open Wisper — One-command installer
# Run with: curl -fsSL https://raw.githubusercontent.com/AbubakrChan/open-wisper/main/install.sh | bash

set -e

REPO="https://github.com/AbubakrChan/open-wisper.git"
INSTALL_DIR="$HOME/Applications/OpenWisper"

echo ""
echo "Open Wisper Installer"
echo "====================="
echo ""

# ── Requirements ───────────────────────────────────────────────────────────────

if [ "$(uname -m)" != "arm64" ]; then
  echo "❌  Requires Apple Silicon (M1/M2/M3/M4). Intel Macs are not supported."
  exit 1
fi

OS_VER=$(sw_vers -productVersion | cut -d. -f1)
if [ "$OS_VER" -lt 12 ]; then
  echo "❌  Requires macOS 12 or later (you have $(sw_vers -productVersion))."
  exit 1
fi
echo "✓  macOS $(sw_vers -productVersion), Apple Silicon"

# ── Homebrew ───────────────────────────────────────────────────────────────────

if ! command -v brew &>/dev/null; then
  echo ""
  echo "Homebrew not found — installing it now (this may take a few minutes)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
fi
echo "✓  Homebrew"

# ── Python 3.9+ ────────────────────────────────────────────────────────────────

if ! python3 -c "import sys; assert sys.version_info >= (3, 9)" 2>/dev/null; then
  echo "Installing Python 3..."
  brew install python3
fi
echo "✓  Python $(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"

# ── Download ───────────────────────────────────────────────────────────────────

mkdir -p "$HOME/Applications"
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating existing installation..."
  git -C "$INSTALL_DIR" pull --ff-only 2>/dev/null || echo "  (already up to date)"
else
  echo "Downloading Open Wisper..."
  git clone --depth=1 "$REPO" "$INSTALL_DIR"
fi
echo "✓  Open Wisper → $INSTALL_DIR"

cd "$INSTALL_DIR"

# ── PortAudio ──────────────────────────────────────────────────────────────────

if ! brew list portaudio &>/dev/null 2>&1; then
  echo "Installing PortAudio..."
  brew install portaudio
fi
echo "✓  PortAudio"

# ── Python packages ────────────────────────────────────────────────────────────

echo "Installing Python packages (first time takes ~30 seconds)..."
pip3 install --user -r "$INSTALL_DIR/requirements.txt" -q
echo "✓  Python packages"

# ── Launcher command ───────────────────────────────────────────────────────────

LAUNCHER="/usr/local/bin/open-wisper"
if [ -w "/usr/local/bin" ] || mkdir -p "/usr/local/bin" 2>/dev/null; then
  cat > "$LAUNCHER" << 'EOF'
#!/bin/bash
nohup python3 "$HOME/Applications/OpenWisper/app.py" >/dev/null 2>&1 &
disown
EOF
  chmod +x "$LAUNCHER"
  echo "✓  Launcher → type 'open-wisper' in Terminal to start"
fi

# ── Launch ─────────────────────────────────────────────────────────────────────

echo ""
echo "✅  Done! Launching Open Wisper..."
echo ""
nohup python3 "$INSTALL_DIR/app.py" >/dev/null 2>&1 &
disown

echo "A setup wizard will walk you through two quick steps:"
echo "  1. Download the AI model (~750 MB, one time)"
echo "  2. Grant microphone + accessibility access"
echo ""
echo "After that, press your hotkey anywhere to start recording."
echo ""
echo "To launch Open Wisper in the future:"
echo "  • Type 'open-wisper' in Terminal"
echo "  • Or enable 'At Login' in Settings to auto-start with your Mac"
echo ""
