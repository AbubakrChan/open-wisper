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

# Find a suitable Python (prefer Homebrew)
PYTHON_CMD=""
for p in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3; do
  if [ -x "$p" ]; then
    PYTHON_CMD="$p"
    break
  fi
done

if [ -z "$PYTHON_CMD" ]; then
  echo "Installing Python 3 via Homebrew..."
  brew install python@3.13
  PYTHON_CMD="/opt/homebrew/bin/python3.13"
fi

PYTHON_VER=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✓  Python $PYTHON_VER ($PYTHON_CMD)"

# ── PortAudio ──────────────────────────────────────────────────────────────────

if ! brew list portaudio &>/dev/null 2>&1; then
  echo "Installing PortAudio..."
  brew install portaudio
fi
echo "✓  PortAudio"

# ── Download ───────────────────────────────────────────────────────────────────

mkdir -p "$HOME/Applications"
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating existing installation..."
  git -C "$INSTALL_DIR" pull --ff-only 2>/dev/null || echo "  (already up to date)"
else
  echo "Downloading Open Wisper..."
  rm -rf "$INSTALL_DIR"
  git clone --depth=1 "$REPO" "$INSTALL_DIR"
fi
echo "✓  Open Wisper → $INSTALL_DIR"

cd "$INSTALL_DIR"

# ── Python packages ────────────────────────────────────────────────────────────

echo "Installing Python packages (first time takes ~30 seconds)..."
$PYTHON_CMD -m pip install --user -r "$INSTALL_DIR/requirements.txt" -q 2>/dev/null || \
$PYTHON_CMD -m pip install --user -r "$INSTALL_DIR/requirements.txt" --break-system-packages -q
echo "✓  Python packages"

# ── Install App ────────────────────────────────────────────────────────────────

# Copy the pre-built Swift app
APP_SRC="$INSTALL_DIR/OpenWisper.app"
APP_DST="$HOME/Applications/OpenWisper.app"

if [ -d "$APP_SRC" ]; then
  # Remove old app if exists
  rm -rf "$APP_DST"
  cp -r "$APP_SRC" "$APP_DST"

  # Sign the app (ad-hoc) to ensure it works
  codesign --force --deep --sign - "$APP_DST" 2>/dev/null || true

  echo "✓  App installed → $APP_DST"
else
  echo "⚠️  Pre-built app not found, will run Python directly"
fi

# ── Launcher command ───────────────────────────────────────────────────────────

# Create a simple launcher script
LAUNCHER=""
for dir in "/opt/homebrew/bin" "$HOME/.local/bin"; do
  if mkdir -p "$dir" 2>/dev/null && [ -w "$dir" ]; then
    LAUNCHER="$dir/open-wisper"
    break
  fi
done

if [ -n "$LAUNCHER" ]; then
  cat > "$LAUNCHER" << 'EOF'
#!/bin/bash
APP="$HOME/Applications/OpenWisper.app"
if [ -d "$APP" ]; then
  open "$APP"
else
  # Fallback to Python directly
  nohup python3 "$HOME/Applications/OpenWisper/app.py" >/dev/null 2>&1 &
  disown
fi
EOF
  chmod +x "$LAUNCHER"
  echo "✓  Launcher → type 'open-wisper' in Terminal"
fi

# ── Launch ─────────────────────────────────────────────────────────────────────

echo ""
echo "✅  Installation complete!"
echo ""

# Launch the app
if [ -d "$APP_DST" ]; then
  echo "Launching Open Wisper..."
  echo ""
  open "$APP_DST"

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "  A permission dialog will appear."
  echo ""
  echo "  Click 'Open Settings', find 'Open Wisper' in the list,"
  echo "  and toggle it ON."
  echo ""
  echo "  The app will start automatically once enabled."
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo "After setup, press Fn+R anywhere to record your voice."
  echo ""
else
  # Fallback: run Python directly
  echo "Launching Open Wisper (Python mode)..."
  nohup $PYTHON_CMD "$INSTALL_DIR/app.py" >/dev/null 2>&1 &
  disown
fi

echo "To launch Open Wisper in the future:"
echo "  • Type 'open-wisper' in Terminal"
echo "  • Or open ~/Applications/OpenWisper.app"
echo ""
